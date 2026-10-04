import { randomUUID } from "node:crypto";
import { sql } from "drizzle-orm";
import type { ResolvedIdentity, TenantTransaction } from "../technical-tools";
import { technicalTools } from "../technical-tools";
import { rows } from "./database";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** One specialist turn of a Supervisor session, as the business database holds it now. */
export type SessionRun = {
  agentId: string;
  principalId: string;
  identity: ResolvedIdentity;
};

/**
 * Who a Supervisor session's specialist is while one of its turns runs, and what it may touch.
 *
 * The other callers of this API are a person's Bot, identified by the Bot's token and a signed
 * run. A specialist in a Supervisor's room has no person behind it: the business API opened an
 * agent run for the turn, under the workspace's service identity. That row is the authority
 * here, read fresh on every call, so nothing the runtime sends decides what the agent may do:
 *
 *   - the run is still running and belongs to an active specialist of a session that has not
 *     finished, for the ticket generation the session was opened for;
 *   - the member's pinned agent version is still published (a revoked release stops the tools);
 *   - capabilities are those of the tools the version was configured and approved with;
 *   - they hold over the scopes the management unit of the workspace covers, and nowhere else.
 *
 * There is no user and no role: documents reach the agent only where they are granted to its
 * workspace, and tools reserved for a management role stay closed.
 */
export async function sessionRun(
  tx: TenantTransaction,
  tenantId: string,
  runId: string,
): Promise<SessionRun | null> {
  if (!UUID.test(runId)) return null;
  const [run] = await rows<{
    agent_id: string;
    principal_id: string;
    version_no: number;
    tools: unknown;
    workspace_id: string;
    management_unit_id: string | null;
  }>(
    tx,
    sql`select r.agent_id,r.authority_principal_id as principal_id,v.version_no,
          v.config->'mcp_tools' as tools,tm.workspace_id,w.management_unit_id
        from agent_runs r
        join team_members m on m.tenant_id=r.tenant_id and m.id=r.team_member_id
          and m.member_kind='specialist' and m.status='active' and m.version_id=r.version_id
        join agent_teams tm on tm.tenant_id=m.tenant_id and tm.id=m.team_id
          and tm.status not in ('completed','failed','cancelled')
        join tickets t on t.tenant_id=tm.tenant_id and t.id=tm.ticket_id
          and t.reopen_count=tm.ticket_generation
        join agent_versions v on v.tenant_id=r.tenant_id and v.id=r.version_id
        join agent_releases rel on rel.tenant_id=v.tenant_id and rel.version_id=v.id
          and rel.status='published' and rel.revoked_at is null
        join workspaces w on w.tenant_id=tm.tenant_id and w.id=tm.workspace_id and w.status='active'
        join agents a on a.tenant_id=r.tenant_id and a.id=r.agent_id and a.status='active'
        join execution_principals p on p.tenant_id=r.tenant_id and p.id=r.authority_principal_id
          and p.status='active' and p.authz_version=r.authority_version
        join runtime_session_bindings b on b.tenant_id=r.tenant_id and b.id=r.binding_id and b.status='active'
        where r.tenant_id=${tenantId} and r.id=${runId} and r.status='running'
        union all
        select r.agent_id,r.authority_principal_id as principal_id,v.version_no,
          v.config->'mcp_tools' as tools,a.workspace_id,w.management_unit_id
        from agent_runs r
        join agent_versions v on v.tenant_id=r.tenant_id and v.id=r.version_id
        join agents a on a.tenant_id=r.tenant_id and a.id=r.agent_id and a.status='active'
        join agent_releases rel on rel.tenant_id=v.tenant_id and rel.version_id=v.id
          and rel.status='published' and rel.revoked_at is null
        join execution_principals p on p.tenant_id=r.tenant_id and p.id=r.authority_principal_id
          and p.kind='user' and p.user_id=r.actor_user_id and p.status='active' and p.authz_version=r.authority_version
        join runtime_session_bindings binding on binding.tenant_id=r.tenant_id and binding.id=r.binding_id
          and binding.audience_kind='personal' and binding.customer_user_id=r.actor_user_id and binding.status='active'
        join channels c on c.tenant_id=r.tenant_id and c.id=r.channel_id and c.workspace_id=a.workspace_id
          and c.kind='management' and c.deleted_at is null
        join workspaces w on w.tenant_id=a.tenant_id and w.id=a.workspace_id and w.status='active'
        join users u on u.id=r.actor_user_id and u.status='active'
        join tenant_memberships membership on membership.tenant_id=r.tenant_id and membership.user_id=u.id and membership.status='active'
        where r.tenant_id=${tenantId} and r.id=${runId} and r.status='running' and r.team_member_id is null
          and (exists(select 1 from platform_admins where user_id=u.id)
            or (exists(select 1 from channel_memberships cm where cm.tenant_id=r.tenant_id and cm.channel_id=c.id and cm.user_id=u.id)
              and exists(select 1 from scoped_user_roles role join access_scopes scope on scope.id=role.scope_id and scope.tenant_id=role.tenant_id
                where role.membership_id=membership.id and role.role_code='management' and role.valid_from<=now()
                  and (role.valid_to is null or role.valid_to>now())
                  and (scope.kind='tenant' or (scope.kind='management' and scope.management_unit_id=w.management_unit_id)))))`,
  );
  if (!run?.management_unit_id) return null;
  const configured: unknown =
    typeof run.tools === "string" ? JSON.parse(run.tools) : run.tools;
  const granted = new Set(
    (Array.isArray(configured) ? configured : []).filter((tool) => tool?.server_id === "technical-tools").map(
      (tool: { name?: unknown }) => String(tool?.name ?? ""),
    ),
  );
  const capabilities = [
    ...new Set(
      technicalTools
        .filter((tool) => granted.has(tool.name))
        .map((tool) => tool.capability),
    ),
  ];
  if (!capabilities.length) return null;
  const scopes = await rows<{ scope_id: string }>(
    tx,
    sql`select distinct scope_id from management_coverage
        where tenant_id=${tenantId} and management_unit_id=${run.management_unit_id}
          and valid_from<=now() and (valid_to is null or valid_to>now())`,
  );
  return {
    agentId: run.agent_id,
    principalId: run.principal_id,
    identity: {
      tenant_id: tenantId,
      workspace_id: run.workspace_id,
      principal_id: run.agent_id,
      source_run_id: runId,
      trace_id: randomUUID(),
      agent_version: String(run.version_no),
      grants: capabilities.map((capability) => ({
        capability,
        scope_ids: scopes.map((scope) => scope.scope_id),
      })),
    },
  };
}
