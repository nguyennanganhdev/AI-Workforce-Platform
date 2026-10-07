/**
 * Publish a folder of Markdown knowledge to the scopes a tenant really has.
 *
 *   cd server
 *   KNOWLEDGE_ADMIN_DATABASE_URL=postgresql://owner@host/db OPENAI_API_KEY=... \
 *     bun src/knowledge/publish.ts <data-dir> --site ocean-park-1 --user <publisher's user id or email>
 *
 * `cli.ts` is the developer fixture: it invents a scope per folder. This entry point maps each
 * folder to a scope of the business database instead, so the backend's own authorization
 * (`/internal/reception/v1/knowledge-authorization`) decides who can read a document:
 *
 *   00-do-thi                  -> the site
 *   <operator>                 -> the zone of the one area that operator runs here
 *   <operator>/<area>          -> the zone whose code is <area>
 *   .../<building>             -> the building whose code is <building>
 *
 * An operator with several areas has no single scope for its own documents: they are reported
 * like any folder without a scope, never published to the whole site.
 *
 * A folder with no such scope is reported and its documents are not published. Re-running is
 * safe: unchanged files are skipped and files that disappeared are retired. The tenant's
 * Reception agents are granted the knowledge base, and its id is printed for KNOWLEDGE_BASE_ID.
 * Chunk text is sent to the embedding provider.
 */
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { SQL } from "bun";
import { createDatabase } from "../db/client";
import { URBAN } from "./dev-fixture";
import { createOpenAIEmbedder } from "./embedder";
import { createIngestStore } from "./pg-store";
import { BQL_DOCUMENT_PREFIX } from "./publish-bql";
import { ingestDirectory } from "./source-directory";
import { BUILDING_FOLDER } from "./source-metadata";

function argument(name: string): string {
  const index = process.argv.indexOf(`--${name}`);
  const value = index > 0 ? process.argv[index + 1] : undefined;
  if (!value) throw new Error(`--${name} is required`);
  return value;
}

const root = process.argv[2];
if (!root || root.startsWith("--"))
  throw new Error("Usage: publish.ts <data-dir> --site <code> --user <id>");
const url = process.env.KNOWLEDGE_ADMIN_DATABASE_URL;
if (!url) throw new Error("KNOWLEDGE_ADMIN_DATABASE_URL is required");
const apiKey = process.env.OPENAI_API_KEY;
if (!apiKey) throw new Error("OPENAI_API_KEY is required");

const admin = new SQL(url);
const [site] = await admin`
  select id, tenant_id, domain_id, code, name from sites where code = ${argument("site")}`;
if (!site) throw new Error("No site with that code");
const tenant: string = site.tenant_id;
const [user] = await admin`
  select u.id from users u join tenant_memberships m on m.user_id = u.id
  where (u.id = ${argument("user")} or lower(u.email) = lower(${argument("user")}))
    and m.tenant_id = ${tenant} and m.status = 'active'`;
if (!user) throw new Error("--user must be an active member of the tenant");

/** One row by its natural key, created the first time. */
async function ensure(rows: Promise<{ id: string }[]>): Promise<string> {
  const [row] = await rows;
  if (!row) throw new Error("Could not create a knowledge record");
  return row.id;
}
const category = await ensure(admin`
  insert into knowledge_categories (tenant_id, code, name) values (${tenant}, 'resident-care', 'Chăm sóc cư dân')
  on conflict (tenant_id, code) do update set name = excluded.name returning id`);
const knowledgeBase = await ensure(admin`
  insert into knowledge_bases (tenant_id, domain_id, code, name, status)
  values (${tenant}, ${site.domain_id}, ${site.code}, ${`Tri thức cư dân ${site.name}`}, 'active')
  on conflict (tenant_id, code) do update set status = 'active' returning id`);
// Document versions need a source file record. The originals live in the data repository, so
// one staged record stands for the whole folder until the storage service takes them.
const sources = await ensure(admin`
  insert into knowledge_bases (tenant_id, domain_id, code, name, status)
  values (${tenant}, ${site.domain_id}, ${`${site.code}-sources`}, ${`Tệp nguồn ${site.name}`}, 'archived')
  on conflict (tenant_id, code) do update set status = 'archived' returning id`);
const sourceDocument = await ensure(admin`
  insert into knowledge_documents (tenant_id, knowledge_base_id, category_id, code, title, status)
  values (${tenant}, ${sources}, ${category}, 'source-files', 'Tệp nguồn', 'draft')
  on conflict (knowledge_base_id, code) do update set title = excluded.title returning id`);
await admin`
  insert into execution_principals (tenant_id, kind, user_id, status) values (${tenant}, 'user', ${user.id}, 'active')
  on conflict (tenant_id, user_id) where kind = 'user' do nothing`;
const [principal] = await admin`
  select id from execution_principals where tenant_id = ${tenant} and kind = 'user' and user_id = ${user.id}`;
const [existingFile] = await admin`
  select id from files where tenant_id = ${tenant} and document_id = ${sourceDocument} limit 1`;
const file: string = existingFile?.id ??
  (await ensure(admin`
    insert into files (tenant_id, scope_kind, document_id, original_name, owner_principal_id, status)
    values (${tenant}, 'document', ${sourceDocument}, ${site.code}, ${principal.id}, 'staged') returning id`));

/** The area folders of an operator folder; a name that is no zone code simply matches nothing. */
async function areasOf(operator: string): Promise<string[]> {
  const entries = await readdir(join(root as string, operator), { withFileTypes: true });
  // The empty name keeps the SQL list valid for an operator folder without sub-folders.
  return ["", ...entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name)];
}

const missing = new Set<string>();
async function resolveScopeId(key: string): Promise<string> {
  const parts = key.split("/");
  const leaf = parts.at(-1) ?? "";
  const rows: { id: string }[] =
    key === URBAN
      ? await admin`select id from access_scopes where tenant_id = ${tenant} and kind = 'site' and site_id = ${site.id}`
      : BUILDING_FOLDER.test(leaf)
        ? await admin`
            select a.id from access_scopes a join buildings b on b.id = a.building_id
            where a.tenant_id = ${tenant} and a.kind = 'building' and b.site_id = ${site.id} and b.code = ${leaf}`
        : parts.length === 2
          ? await admin`
              select a.id from access_scopes a join zones z on z.id = a.zone_id
              where a.tenant_id = ${tenant} and a.kind = 'zone' and z.site_id = ${site.id} and z.code = ${leaf}`
          : parts.length === 1
            ? await admin`
                select a.id from access_scopes a join zones z on z.id = a.zone_id
                where a.tenant_id = ${tenant} and a.kind = 'zone' and z.site_id = ${site.id}
                  and z.code in ${admin(await areasOf(key))}`
            : [];
  if (rows.length !== 1) {
    missing.add(key);
    throw new Error(`no scope in the database for folder ${key}`);
  }
  return (rows[0] as { id: string }).id;
}

const embedder = createOpenAIEmbedder({ apiKey, baseUrl: process.env.OPENAI_BASE_URL });
const report = await ingestDirectory(
  { store: createIngestStore(createDatabase(url, { max: 3, tenantId: tenant })), embedder },
  {
    root,
    tenantId: tenant,
    knowledgeBaseId: knowledgeBase,
    categoryId: category,
    submittedBy: user.id,
    resolveScopeId,
    registerFile: async () => file,
    prune: true,
    // Management's reference documents (publish-bql.ts) are not in this folder and stay published.
    keep: (code) => code.startsWith(BQL_DOCUMENT_PREFIX),
  },
);

const granted: { agent_id: string }[] = await admin`
  insert into agent_knowledge_grants (tenant_id, agent_id, knowledge_base_id, granted_by)
  select ${tenant}, a.id, ${knowledgeBase}, ${user.id} from agents a
  where a.tenant_id = ${tenant} and a.purpose = 'reception' and a.status = 'active'
  on conflict do nothing returning agent_id`;

console.log(
  `Published to ${site.code}: ${report.ingested} new, ${report.unchanged} unchanged, ${report.skipped} skipped, ${report.retired} retired, ${report.failed.length} failed.`,
);
for (const failure of report.failed) console.log(`  failed ${failure.code}: ${failure.error}`);
if (missing.size > 0) console.log(`Folders without a scope: ${[...missing].sort().join(", ")}`);
console.log(`Reception agents granted now: ${granted.map((g) => g.agent_id).join(", ") || "none new"}`);
console.log(`KNOWLEDGE_TENANT_ID=${tenant}`);
console.log(`KNOWLEDGE_BASE_ID=${knowledgeBase}`);
await admin.close();
process.exit(report.failed.some((failure) => !failure.error.includes("no scope in the database")) ? 1 : 0);
