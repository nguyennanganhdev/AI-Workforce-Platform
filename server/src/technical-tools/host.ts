import { randomUUID } from "node:crypto";
import type { z } from "zod";
import { findTechnicalTool } from "./catalog";
import {
  type ResolvedIdentity,
  resolvedIdentitySchema,
  type ToolContext,
} from "./contracts/context";
import type {
  ResponseEnvelope,
  ToolError,
  ToolStatus,
} from "./contracts/envelope";
import { payloadHash, WRITTEN_STATUSES } from "./idempotency";
import type { AuditSink } from "./ports/audit-sink";
import type { ContextResolver, ToolCaller } from "./ports/context-resolver";
import type { IdempotencyStore, Reservation } from "./ports/idempotency-store";
import type { TechnicalTool, ToolDependencies, ToolOutcome } from "./tool";
import { FORBIDDEN_MESSAGE } from "./tools/outcomes";

export type HostDependencies = ToolDependencies & {
  contextResolver: ContextResolver;
  audit: AuditSink;
  /** Consulted only for tools that write; a read needs no key to be safe to repeat. */
  idempotency: IdempotencyStore;
};

export type HostOptions = {
  /** Replaces every tool's own timeout. For tests that need a call to give up quickly. */
  timeoutMs?: number;
};

class ToolTimeout extends Error {}

function withTimeout<T>(work: Promise<T>, timeoutMs: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const expiry = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new ToolTimeout()), timeoutMs);
  });
  return Promise.race([work, expiry]).finally(() => clearTimeout(timer));
}

function inputErrors(error: z.ZodError): ToolError[] {
  return error.issues.map((issue) => {
    // An unrecognised key is reported on the object that held it, so the key names are the field.
    const field =
      issue.code === "unrecognized_keys"
        ? [...issue.path, issue.keys.join(",")].join(".")
        : issue.path.join(".");
    return {
      code: "INVALID_INPUT" as const,
      message: issue.message,
      ...(field ? { field } : {}),
      retryable: false,
    };
  });
}

/**
 * Runs technical tools behind one sequence of checks, so no tool has to remember them.
 *
 * Who is calling, whether they hold the tool's capability, whether the input is well formed, whether
 * the building it names is inside their grant, and only then the tool. Every call ends in an audit
 * entry, including the ones refused before the tool was reached.
 */
export function createTechnicalToolHost(
  dependencies: HostDependencies,
  options: HostOptions = {},
) {
  const { contextResolver, audit, clock, idempotency } = dependencies;

  async function call(
    caller: ToolCaller,
    tool: TechnicalTool,
    args: Record<string, unknown>,
  ): Promise<ResponseEnvelope> {
    const receivedAt = clock.now();
    const started = performance.now();
    let identity: ResolvedIdentity | null = null;
    let buildingId: string | null = null;

    const respond = async (
      outcome: ToolOutcome<unknown>,
      detail?: string,
      replayed = false,
    ): Promise<ResponseEnvelope> => {
      const traceId = identity?.trace_id ?? randomUUID();
      const envelope = (
        status: ToolStatus,
        result: Omit<ToolOutcome<unknown>, "status">,
      ): ResponseEnvelope => ({
        status,
        trace_id: traceId,
        server_time: clock.now().toISOString(),
        data: (result.data ?? null) as ResponseEnvelope["data"],
        errors: result.errors ?? [],
        missing_fields: result.missingFields ?? [],
        provenance: result.provenance ?? [],
      });

      try {
        await audit.record({
          tool: tool.name,
          tool_version: tool.version,
          status: outcome.status,
          ...(detail ? { detail } : {}),
          trace_id: traceId,
          agent_version: identity?.agent_version ?? null,
          tenant_id: identity?.tenant_id ?? null,
          principal_id: identity?.principal_id ?? null,
          source_run_id: identity?.source_run_id ?? null,
          bot_id: caller.botId,
          actor_id: caller.actorId,
          ...(caller.initiator ? { initiator: caller.initiator } : {}),
          building_id: buildingId,
          ...(replayed ? { idempotent_replay: true } : {}),
          result_count: outcome.resultCount ?? null,
          duration_ms: Math.round(performance.now() - started),
          occurred_at: receivedAt.toISOString(),
        });
      } catch {
        /*
         * No record, no answer. The gateway this sits beside never acts without the audit row
         * existing, and handing back data the trail knows nothing about would be the one path
         * here that does.
         */
        return envelope("INTERNAL_ERROR", {
          data: null,
          errors: [
            {
              code: "INTERNAL_ERROR",
              message:
                "The call could not be recorded, so no result is returned.",
              retryable: tool.effect === "read",
            },
          ],
        });
      }
      return envelope(outcome.status, outcome);
    };

    const refuse = (detail: string) =>
      respond(
        {
          status: "FORBIDDEN",
          data: null,
          errors: [
            { code: "FORBIDDEN", message: FORBIDDEN_MESSAGE, retryable: false },
          ],
        },
        detail,
      );

    const fail = (detail: string) =>
      respond(
        {
          status: "INTERNAL_ERROR",
          data: null,
          errors: [
            {
              code: "INTERNAL_ERROR",
              message: "The tool could not complete the request.",
              // A write may have landed before the failure, so its caller reconciles first.
              retryable: tool.effect === "read",
            },
          ],
        },
        detail,
      );

    try {
      const resolved = resolvedIdentitySchema.safeParse(
        await contextResolver(caller),
      );
      if (!resolved.success) {
        return await refuse("The caller resolved to no usable identity.");
      }
      identity = resolved.data;
    } catch {
      return await fail("The caller's identity could not be resolved.");
    }

    if (!identity.capabilities.includes(tool.capability)) {
      return await refuse(`The caller does not hold ${tool.capability}.`);
    }

    const parsed = tool.inputSchema.safeParse(args);
    if (!parsed.success) {
      return await respond(
        {
          status: "INVALID_INPUT",
          data: null,
          errors: inputErrors(parsed.error),
        },
        "The input did not match the tool's schema.",
      );
    }
    buildingId = parsed.data.building_id;

    if (!identity.allowed_building_ids.includes(buildingId)) {
      return await refuse("The building is outside the caller's grant.");
    }

    const { capabilities, allowed_building_ids, ...runtime } = identity;
    const context: ToolContext = {
      ...runtime,
      received_at: receivedAt.toISOString(),
      capabilities: new Set(capabilities),
      allowedBuildingIds: new Set(allowed_building_ids),
    };

    const timeoutMs = options.timeoutMs ?? tool.timeoutMs;
    const failed = (error: unknown) =>
      fail(
        error instanceof ToolTimeout
          ? "The tool did not answer within its timeout."
          : "The tool's data source failed.",
      );
    const conflict = (message: string, retryable: boolean, detail: string) =>
      respond(
        {
          status: "CONFLICT",
          data: null,
          errors: [
            { code: "CONFLICT", message, field: "idempotency_key", retryable },
          ],
        },
        detail,
      );

    let outcome: ToolOutcome<unknown>;
    let replayed = false;

    if (tool.effect === "read") {
      try {
        outcome = await withTimeout(
          tool.run(context, parsed.data, dependencies),
          timeoutMs,
        );
      } catch (error) {
        return await failed(error);
      }
    } else {
      /*
       * A write runs at most once per key (tools.md §1.4). The key is claimed only now, after every
       * refusal above: a call refused before it reached the tool wrote nothing, and holding its key
       * would stop the agent correcting the request and sending it again under the same one.
       */
      const input = parsed.data as Record<string, unknown>;
      const key = input.idempotency_key;
      if (typeof key !== "string") {
        return await fail(
          "A write tool was called without an idempotency_key.",
        );
      }
      const scope = { tenantId: identity.tenant_id, tool: tool.name, key };
      const hash = payloadHash(input);

      let reservation: Reservation;
      try {
        reservation = await idempotency.reserve(scope, hash);
      } catch {
        return await fail("The idempotency store could not be reached.");
      }

      if (reservation.state !== "reserved") {
        const earlierHash =
          reservation.state === "completed"
            ? reservation.stored.payloadHash
            : reservation.payloadHash;
        if (earlierHash !== hash) {
          return await conflict(
            "This idempotency_key was already used for a different request. Use a new key for a new request.",
            false,
            "An idempotency_key was reused with a different payload.",
          );
        }
        if (reservation.state === "in_progress") {
          return await conflict(
            "A request with this idempotency_key is still being processed. Retry shortly with the same key.",
            true,
            "A request with this idempotency_key was already running.",
          );
        }
        // The same request again: hand back what it got the first time, and write nothing.
        outcome = reservation.stored.outcome;
        replayed = true;
      } else {
        /*
         * The key follows the run, not the wait. If the caller stops waiting at the timeout the
         * write may still land a moment later; releasing the key then would let the retry write it
         * a second time. So the key is completed or released only when the run itself settles, and
         * a retry in between is told the request is still in progress.
         */
        const settled = tool.run(context, parsed.data, dependencies).then(
          async (result) => {
            if (WRITTEN_STATUSES.has(result.status)) {
              await idempotency.complete(scope, {
                payloadHash: hash,
                outcome: result,
              });
            } else {
              await idempotency.release(scope);
            }
            return result;
          },
          async (error: unknown) => {
            await idempotency.release(scope);
            throw error;
          },
        );
        // A caller that stopped waiting must not leave an unhandled rejection behind it.
        settled.catch(() => {});
        try {
          outcome = await withTimeout(settled, timeoutMs);
        } catch (error) {
          return await failed(error);
        }
      }
    }

    /*
     * Whatever data an answer carries is checked, not only a successful one's. NEEDS_INPUT hands
     * back candidates and STALE_DATA hands back the old readings, and an agent reads those as
     * carefully as an OK: a malformed candidate list is as misleading as a malformed result.
     */
    if (outcome.data !== null && outcome.data !== undefined) {
      const checked = tool.outputSchema.safeParse(outcome.data);
      if (!checked.success) {
        return await fail("The tool's result did not match its output schema.");
      }
    }
    return await respond(
      outcome,
      replayed
        ? "Returned the result of an earlier call with the same idempotency_key."
        : undefined,
      replayed,
    );
  }

  return { find: findTechnicalTool, call };
}

export type TechnicalToolHost = ReturnType<typeof createTechnicalToolHost>;
