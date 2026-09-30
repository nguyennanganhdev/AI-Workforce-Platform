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
import type { AuditSink } from "./ports/audit-sink";
import type { ContextResolver, ToolCaller } from "./ports/context-resolver";
import type { TechnicalTool, ToolDependencies, ToolOutcome } from "./tool";
import { FORBIDDEN_MESSAGE } from "./tools/outcomes";

export type HostDependencies = ToolDependencies & {
  contextResolver: ContextResolver;
  audit: AuditSink;
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
  const { contextResolver, audit, clock } = dependencies;

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

    let outcome: ToolOutcome<unknown>;
    try {
      outcome = await withTimeout(
        tool.run(context, parsed.data, dependencies),
        options.timeoutMs ?? tool.timeoutMs,
      );
    } catch (error) {
      return await fail(
        error instanceof ToolTimeout
          ? "The tool did not answer within its timeout."
          : "The tool's data source failed.",
      );
    }

    if (outcome.status === "OK") {
      const checked = tool.outputSchema.safeParse(outcome.data);
      if (!checked.success) {
        return await fail("The tool's result did not match its output schema.");
      }
    }
    return await respond(outcome);
  }

  return { find: findTechnicalTool, call };
}

export type TechnicalToolHost = ReturnType<typeof createTechnicalToolHost>;
