/**
 * The local development fixture behind the knowledge CLI and the evaluation runner.
 *
 * WHAT IT WRITES, until Chiến's real domain, knowledge base, scope tree and authorization exist.
 * Everything uses the existing tenant and is coded `rag-dev-…` so it can be found and replaced:
 * a domain, a category, two knowledge bases (the corpus, and one holding the placeholder document
 * the source file record hangs off), one access scope per data folder (the urban folder reuses the
 * tenant's own scope), an execution principal for an existing user, one file record, and one
 * runtime binding plus one agent run for the retrieval audit. Every row has valid foreign keys
 * except the last two: their agent, runtime and channel parents do not exist yet, so they are
 * inserted with foreign-key checks off for that one transaction. Nothing in the app reads those
 * two tables today. Not a production entry point.
 */
import { createHash } from "node:crypto";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import type { SQL } from "bun";
import { scopeKeyOf } from "./source-metadata";
import type { AuthorizedContext } from "./types";

export const PREFIX = "rag-dev";
export const URBAN = "00-do-thi";

/** A stable UUID from a name within the tenant, so every run finds the same rows. */
function idFor(tenantId: string, name: string): string {
  const hex = createHash("sha256")
    .update(`${PREFIX}:${tenantId}:${name}`)
    .digest("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-8${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

export type Ids = {
  tenant: string;
  user: string;
  domain: string;
  category: string;
  kb: string;
  filesKb: string;
  fileDocument: string;
  file: string;
  principal: string;
  binding: string;
  run: string;
  /** The tenant's own access scope, used for the urban folder, or null to create one. */
  tenantScope: string | null;
};

export function databaseUrl(name: string): string {
  const base = process.env.DATABASE_URL;
  if (!base)
    throw new Error("DATABASE_URL is not set. Run with --env-file=../.env.");
  if (name === "") return base;
  const url = new URL(base);
  url.pathname = `/${name}`;
  return url.toString();
}

export async function resolveIds(
  admin: SQL,
  tenantCode: string,
  userId: string,
): Promise<Ids> {
  const tenants: { id: string; code: string }[] = tenantCode
    ? await admin`select id, code from tenants where code = ${tenantCode}`
    : await admin`select id, code from tenants order by created_at`;
  if (tenants.length !== 1) {
    throw new Error(
      tenants.length === 0
        ? "Không thấy tenant nào. Hãy chạy app một lần để tạo tenant, hoặc kiểm tra --tenant."
        : `Có ${tenants.length} tenant (${tenants.map((t) => t.code).join(", ")}). Chọn bằng --tenant <code>.`,
    );
  }
  const tenant = (tenants[0] as { id: string }).id;
  const users: { id: string }[] = userId
    ? await admin`select id from users where id = ${userId}`
    : await admin`select id from users order by created_at limit 1`;
  if (users.length === 0) {
    throw new Error(
      "Không thấy user nào. Hãy đăng nhập app một lần, hoặc kiểm tra --user.",
    );
  }
  const scopes: { id: string }[] = await admin`
    select id from access_scopes where tenant_id = ${tenant} and kind = 'tenant' limit 1`;
  const id = (name: string) => idFor(tenant, name);
  return {
    tenant,
    user: (users[0] as { id: string }).id,
    domain: id("domain"),
    category: id("category"),
    kb: id("kb"),
    filesKb: id("files-kb"),
    fileDocument: id("file-document"),
    file: id("file"),
    principal: id("principal"),
    binding: id("binding"),
    run: id("run"),
    tenantScope: scopes[0]?.id ?? null,
  };
}

export async function seed(admin: SQL, ids: Ids) {
  await admin.begin(async (tx) => {
    await tx`insert into domains (id, tenant_id, code, name, status) values (${ids.domain}, ${ids.tenant}, ${`${PREFIX}-ocean-park`}, 'Ocean Park 1 (dev)', 'active') on conflict do nothing`;
    await tx`insert into knowledge_categories (id, tenant_id, code, name) values (${ids.category}, ${ids.tenant}, ${PREFIX}, 'Kho tri thức (dev)') on conflict do nothing`;
    await tx`insert into knowledge_bases (id, tenant_id, domain_id, code, name, status) values (${ids.kb}, ${ids.tenant}, ${ids.domain}, ${`${PREFIX}-ocean-park`}, 'Ocean Park 1 (dev)', 'active') on conflict do nothing`;
    await tx`insert into knowledge_bases (id, tenant_id, domain_id, code, name, status) values (${ids.filesKb}, ${ids.tenant}, ${ids.domain}, ${`${PREFIX}-files`}, 'Tệp nguồn (dev)', 'archived') on conflict do nothing`;
    await tx`insert into knowledge_documents (id, tenant_id, knowledge_base_id, category_id, code, title, status) values (${ids.fileDocument}, ${ids.tenant}, ${ids.filesKb}, ${ids.category}, ${`${PREFIX}-source-files`}, 'Tệp nguồn Data-Vinhome (dev)', 'draft') on conflict do nothing`;
    await tx`insert into execution_principals (id, kind, tenant_id, status, user_id) values (${ids.principal}, 'user', ${ids.tenant}, 'active', ${ids.user}) on conflict do nothing`;
    await tx`insert into files (id, tenant_id, scope_kind, document_id, original_name, owner_principal_id, status) values (${ids.file}, ${ids.tenant}, 'document', ${ids.fileDocument}, 'Data-Vinhome', ${ids.principal}, 'staged') on conflict do nothing`;
  });
  // The audit parents (agent, agent version, runtime identity and backend, channel) do not exist
  // yet, so these two rows are the only ones written with foreign-key checks off.
  await admin.begin(async (tx) => {
    await tx`set local session_replication_role = replica`;
    await tx`insert into runtime_session_bindings (id, backend_id, audience_kind, customer_user_id, runtime_session_key, status, policy_version, tenant_id, identity_id, channel_id, agent_id, agent_version_id) values (${ids.binding}, ${idFor(ids.tenant, "backend")}, 'personal', ${ids.user}, ${PREFIX}, 'active', ${PREFIX}, ${ids.tenant}, ${idFor(ids.tenant, "identity")}, ${PREFIX}, ${PREFIX}, ${idFor(ids.tenant, "agent-version")}) on conflict do nothing`;
    await tx`insert into agent_runs (id, policy_version, version_id, idempotency_key, status, trace_id, binding_id, authority_principal_id, authority_version, tenant_id, channel_id, agent_id) values (${ids.run}, ${PREFIX}, ${idFor(ids.tenant, "run-version")}, ${PREFIX}, 'running', ${PREFIX}, ${ids.binding}, ${ids.principal}, 1, ${ids.tenant}, ${PREFIX}, ${PREFIX}) on conflict do nothing`;
  });
}

/**
 * Scope keys from what is already loaded: every folder a live document sits in, and its parents.
 * A folded building document (`miami/{M1,M2}/x.md`) counts for each of its buildings.
 */
export async function loadedScopes(admin: SQL, ids: Ids): Promise<string[]> {
  const rows: { code: string }[] = await admin`
    select code from knowledge_documents
    where tenant_id = ${ids.tenant} and knowledge_base_id = ${ids.kb} and status = 'published'`;
  const keys = new Set<string>();
  for (const { code } of rows) {
    const parts = scopeKeyOf(code).split("/");
    const last = parts.at(-1) ?? "";
    const leaves = /^\{.*\}$/.test(last)
      ? last
          .slice(1, -1)
          .split(",")
          .map((b) => [...parts.slice(0, -1), b])
      : [parts];
    for (const leaf of leaves) {
      for (let i = 1; i <= leaf.length; i++)
        keys.add(leaf.slice(0, i).join("/"));
    }
  }
  return [...keys].sort();
}

/** Every folder under the data root that holds Markdown, as a scope key. */
async function folders(root: string, prefix = ""): Promise<string[]> {
  const out: string[] = [];
  for (const entry of await readdir(join(root, prefix), {
    withFileTypes: true,
  })) {
    if (
      !entry.isDirectory() ||
      entry.name.startsWith(".") ||
      entry.name === "luu-tru"
    )
      continue;
    const key = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
    out.push(key, ...(await folders(root, key)));
  }
  return out;
}

/** Ancestors of a folder scope: every parent folder, plus the urban area, which covers everything. */
export function ancestorsOf(scopeKey: string): string[] {
  const parts = scopeKey.split("/");
  const ancestors = parts
    .slice(0, -1)
    .map((_, i) => parts.slice(0, i + 1).join("/"));
  return scopeKey === URBAN ? ancestors : [...ancestors, URBAN];
}

/** Scope keys for every folder under a data root, material folders folded into their parent. */
export async function folderScopes(root: string): Promise<string[]> {
  const keys = new Set<string>();
  for (const folder of await folders(root))
    keys.add(scopeKeyOf(`${folder}/x.md`));
  return [...keys].sort();
}

/** Resolves a scope key to its access scope id, creating the scope row the first time. */
export function createScopeResolver(admin: SQL, ids: Ids) {
  const known = new Map<string, string>();
  return async (key: string): Promise<string> => {
    const cached = known.get(key);
    if (cached) return cached;
    let id = idFor(ids.tenant, `scope:${key}`);
    if (key === URBAN && ids.tenantScope) id = ids.tenantScope;
    else {
      await admin`insert into access_scopes (id, tenant_id, kind) values (${id}, ${ids.tenant}, 'management') on conflict do nothing`;
    }
    known.set(key, id);
    return id;
  };
}

/** The authority a resident of `scopeKey` would have, in the dev fixture. */
export async function devContext(
  ids: Ids,
  scopeId: (key: string) => Promise<string>,
  scopeKey: string,
): Promise<AuthorizedContext> {
  return {
    tenantId: ids.tenant,
    userId: ids.user,
    roleCodes: ["resident"],
    targetScopeId: await scopeId(scopeKey),
    ancestorScopeIds: await Promise.all(ancestorsOf(scopeKey).map(scopeId)),
    agentRunId: ids.run,
    principalId: ids.principal,
    bindingId: ids.binding,
  };
}
