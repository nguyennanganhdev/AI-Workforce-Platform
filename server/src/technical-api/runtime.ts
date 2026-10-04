import { randomUUID } from "node:crypto";
import { sql } from "drizzle-orm";
import { authoriseAgentCall, readRunAssertion } from "../agents/callback-token";
import type { Database } from "../db/client";
import { createTechnicalToolHost } from "../technical-tools";
import { responseEnvelopeSchema } from "../technical-tools/contracts/envelope";
import type {
  ResolvedIdentity,
  ResponseEnvelope,
  TenantTransaction,
} from "../technical-tools";
import type { StoredOutcome } from "../technical-tools/ports/idempotency-store";
import { databasePorts, rows } from "./database";
import { sessionRun } from "./session";
import { technicalEnvelope } from "./routes";
import type {
  TechnicalApiDependencies,
  VerifiedTechnicalCaller,
} from "./routes";

export type TechnicalApiOptions = {
  database: Database;
  tenantId: string;
  encryptionKey: string;
  lookupToken(hash: string): Promise<{ id: string } | null>;
};

/** All ports, audit records and replay receipts share the same tenant transaction. */
export function createTechnicalApiDependencies(
  options: TechnicalApiOptions,
): TechnicalApiDependencies & {
  sessionCaller(runId: string): Promise<VerifiedTechnicalCaller | null>;
} {
  const { database, tenantId } = options;
  async function scoped<T>(
    work: (tx: TenantTransaction) => Promise<T>,
  ): Promise<T> {
    return database.transaction(async (tx) => {
      await tx.execute(
        sql`select set_config('app.tenant_id',${tenantId},true), set_config('statement_timeout','15000',true)`,
      );
      const [role] = await rows<{ unsafe: boolean }>(
        tx,
        sql`select rolsuper or rolbypassrls or exists(
        select 1 from pg_tables where schemaname='public' and (
          has_table_privilege(current_user,format('%I.%I',schemaname,tablename),'UPDATE') or
          has_table_privilege(current_user,format('%I.%I',schemaname,tablename),'DELETE'))) as unsafe
        from pg_roles where rolname=current_user`,
      );
      if (!role || role.unsafe)
        throw new Error("Technical API requires a restricted database role");
      return work(tx);
    });
  }
  async function identity(
    tx: TenantTransaction,
    caller: VerifiedTechnicalCaller,
    buildingId?: string,
  ): Promise<ResolvedIdentity | null> {
    if (caller.session)
      return (
        (await sessionRun(tx, tenantId, caller.assertion.runId))?.identity ??
        null
      );
    if (
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        caller.assertion.runId,
      )
    )
      return null;
    const [agent] = await rows<{ version_no: number }>(
      tx,
      sql`select v.version_no from agents a
      join agent_versions v on v.tenant_id=a.tenant_id and v.agent_id=a.id
      where a.tenant_id=${tenantId} and a.id=${caller.botId} and a.status='active'
      order by v.version_no desc limit 1`,
    );
    if (!agent) return null;
    const grants = await rows<{
      capability: string;
      scope_id: string;
      role_code: ResolvedIdentity["role_code"];
    }>(
      tx,
      sql`select g.capability,g.scope_id,r.role_code from vh_technical_agent_grants g
      join scoped_user_roles r on r.tenant_id=g.tenant_id and r.scope_id=g.scope_id
      join tenant_memberships m on m.tenant_id=r.tenant_id and m.id=r.membership_id
      where g.tenant_id=${tenantId} and g.agent_id=${caller.botId} and m.user_id=${caller.actorId}
      and m.status='active' and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
      and r.role_code in ('admin','management','staff','customer')`,
    );
    if (!grants.length) return null;
    let roleCode: ResolvedIdentity["role_code"];
    if (
      buildingId &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        buildingId,
      )
    ) {
      const { buildingAccess } = await databasePorts(tx, tenantId);
      // A management role for tower A must not become management authority in tower B.
      for (const grant of grants) {
        if (
          await buildingAccess.canAccessBuilding({
            tenantId,
            buildingId,
            scopeIds: [grant.scope_id],
          })
        ) {
          roleCode = grant.role_code;
          if (roleCode === "management") break;
        }
      }
    }
    return {
      tenant_id: tenantId,
      principal_id: caller.botId,
      user_id: caller.actorId,
      ...(roleCode ? { role_code: roleCode } : {}),
      source_run_id: caller.assertion.runId,
      trace_id: randomUUID(),
      agent_version: String(agent.version_no),
      grants: grants.map((g) => ({
        capability: g.capability,
        scope_ids: [g.scope_id],
      })),
    };
  }
  async function audit(tx: TenantTransaction, metadata: unknown) {
    await tx.execute(
      sql`insert into vh_technical_api_audit(tenant_id,metadata) values(${tenantId},${JSON.stringify(metadata)}::text::jsonb)`,
    );
  }
  return {
    async authorise(c) {
      const run = c.req.header("X-OpenBot-Run") ?? "";
      const verdict = await authoriseAgentCall({
        presented: c.req.header("X-OpenBot-Agent-Token") ?? "",
        run,
        encryptionKey: options.encryptionKey,
        lookup: options.lookupToken,
      });
      const assertion = run
        ? readRunAssertion(run, options.encryptionKey)
        : null;
      if (!verdict.ok || !assertion) return null;
      const caller = { ...verdict, assertion };
      return (await scoped((tx) => identity(tx, caller))) ? caller : null;
    },
    async sessionCaller(runId) {
      const run = await scoped((tx) => sessionRun(tx, tenantId, runId));
      return run
        ? {
            ok: true,
            botId: run.agentId,
            actorId: run.principalId,
            assertion: {
              botId: run.agentId,
              actorId: run.principalId,
              runId,
            },
            session: true,
          }
        : null;
    },
    async refusal(status, endpoint) {
      await scoped((tx) =>
        audit(tx, { status, endpoint, occurred_at: new Date().toISOString() }),
      );
    },
    async call(caller, tool, args) {
      let failedAudit: unknown[] = [];
      class Rollback extends Error {
        constructor(public response: ResponseEnvelope) {
          super("Technical call rolled back");
        }
      }
      try {
        return await scoped(async (tx) => {
          const resolved = await identity(
            tx,
            caller,
            typeof args.building_id === "string" ? args.building_id : undefined,
          );
          const ports = await databasePorts(tx, tenantId);
          let stored: StoredOutcome | undefined;
          let replay: ResponseEnvelope | undefined;
          let running: Promise<unknown> | undefined;
          const host = createTechnicalToolHost({
            ...ports,
            contextResolver: async () => resolved,
            audit: {
              record: async (entry) => {
                failedAudit.push(entry);
                await audit(tx, entry);
              },
            },
            idempotency: {
              async reserve(scope, hash) {
                const lockKey = JSON.stringify([
                  tenantId,
                  caller.actorId,
                  scope.tool,
                  scope.key,
                ]);
                const [lock] = await rows<{ acquired: boolean }>(
                  tx,
                  sql`select pg_try_advisory_xact_lock(hashtextextended(${lockKey},0)) as acquired`,
                );
                if (!lock?.acquired)
                  return { state: "in_progress", payloadHash: hash };
                const [receipt] = await rows<{
                  payload_hash: string;
                  outcome: StoredOutcome["outcome"];
                  response: ResponseEnvelope;
                }>(
                  tx,
                  sql`select payload_hash,outcome,response from vh_technical_api_receipts where tenant_id=${tenantId}
                  and actor_id=${caller.actorId} and tool=${scope.tool} and idempotency_key=${scope.key}`,
                );
                if (!receipt) return { state: "reserved" };
                const checked = responseEnvelopeSchema.safeParse(
                  receipt.response,
                );
                if (
                  !checked.success ||
                  !receipt.outcome ||
                  typeof receipt.outcome !== "object"
                ) {
                  throw new Error("Invalid stored technical response");
                }
                replay =
                  receipt.payload_hash === hash ? receipt.response : undefined;
                return {
                  state: "completed",
                  stored: {
                    payloadHash: receipt.payload_hash,
                    outcome: receipt.outcome,
                  },
                };
              },
              async complete(_scope, value) {
                stored = value;
              },
              async release() {
                /* transaction lock is released by commit/rollback */
              },
            },
          });
          const tracked = {
            ...tool,
            run: (...params: Parameters<typeof tool.run>) => {
              const work = tool.run(...params);
              running = work;
              return work;
            },
          };
          const response = await host.call(caller, tracked, args);
          // A host timeout cannot commit late writes from an unfinished tool.
          if (running) await running.catch(() => undefined);
          if (
            !["OK", "PENDING_APPROVAL", "NEEDS_INPUT", "STALE_DATA"].includes(
              response.status,
            )
          )
            throw new Rollback(response);
          if (stored)
            await tx.execute(sql`insert into vh_technical_api_receipts
            (tenant_id,actor_id,tool,idempotency_key,payload_hash,outcome,response)
            values(${tenantId},${caller.actorId},${tool.name},${String(args.idempotency_key)},${stored.payloadHash},
              ${JSON.stringify(stored.outcome)}::text::jsonb,${JSON.stringify(response)}::text::jsonb)`);
          failedAudit = [];
          return replay ?? response;
        });
      } catch (error) {
        await scoped(async (tx) => {
          for (const entry of failedAudit) await audit(tx, entry);
          if (!failedAudit.length)
            await audit(tx, { status: "INTERNAL_ERROR", tool: tool.name });
        });
        return error instanceof Rollback
          ? error.response
          : technicalEnvelope(
              "INTERNAL_ERROR",
              "The request could not be completed.",
            );
      }
    },
  };
}
