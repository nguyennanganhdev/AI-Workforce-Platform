/**
 * Publish management-approved SOPs, the documents `sop_kb.retrieve` and its cleaning counterpart serve.
 *
 *   cd server
 *   KNOWLEDGE_ADMIN_DATABASE_URL=postgresql://owner@host/db OPENAI_API_KEY=... \
 *     bun src/knowledge/publish-sop.ts <sop-dir> --site ocean-park-1 --user <publisher's id or email> \
 *       --approved-by <approver's id or email>
 *
 * Each `<sop-dir>/*.md` has front matter `code`, `title`, `issue_codes`, `excerpt` and `acceptance_criteria`
 * (see `technical-tools/domain/sop.ts`). A SOP tool only uses a published document with a version in force,
 * granted to the asking workspace, with a profile naming its issue codes, so this writes exactly that:
 *
 *   - the document, in the site's own SOP knowledge base (`<site>-sop`), published to the site. It is not
 *     the knowledge base the search service serves, so neither Reception nor `knowledge.search` sees it;
 *   - an `allow` for the workspace of every active management unit;
 *   - its profile in `vh_technical_sop_profiles`, keyed by the version just published.
 *
 * `--approved-by` is required: a draft nobody approved is not guidance. A unit created later is granted
 * the published SOPs with `--rescope --site <code>`, without files or embedding.
 */
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { SQL } from "bun";
import { createDatabase } from "../db/client";
import { createOpenAIEmbedder } from "./embedder";
import { ingestDocument } from "./ingest";
import { parseFrontMatter } from "./markdown";
import { createIngestStore } from "./pg-store";

function argument(name: string): string {
  const index = process.argv.indexOf(`--${name}`);
  const value = index > 0 ? process.argv[index + 1] : undefined;
  if (!value) throw new Error(`--${name} is required`);
  return value;
}

const url = process.env.KNOWLEDGE_ADMIN_DATABASE_URL;
if (!url) throw new Error("KNOWLEDGE_ADMIN_DATABASE_URL is required");
const admin = new SQL(url);
const [site] = await admin`select id, tenant_id, domain_id, code, name from sites where code = ${argument("site")}`;
if (!site) throw new Error("No site with that code");
const tenant: string = site.tenant_id;
const sopBase = `${site.code}-sop`;

/** Every active management unit's workspace may read every published SOP of the site's SOP base. */
async function grantWorkspaces(): Promise<number> {
  const added = await admin`
    insert into document_acl (tenant_id, document_id, principal_kind, workspace_id, effect)
    select d.tenant_id, d.id, 'workspace', w.id, 'allow' from knowledge_documents d
    join knowledge_bases k on k.id = d.knowledge_base_id and k.tenant_id = d.tenant_id and k.code = ${sopBase}
    join workspaces w on w.tenant_id = d.tenant_id and w.status = 'active' and w.management_unit_id is not null
    where d.tenant_id = ${tenant} and d.status = 'published'
      and not exists (select 1 from document_acl a where a.tenant_id = d.tenant_id and a.document_id = d.id
        and a.principal_kind = 'workspace' and a.workspace_id = w.id)
    returning id`;
  return added.length;
}

if (process.argv.includes("--rescope")) {
  console.log(`Workspace grants added: ${await grantWorkspaces()}`);
  await admin.close();
  process.exit(0);
}

const root = process.argv[2];
if (!root || root.startsWith("--"))
  throw new Error("Usage: publish-sop.ts <sop-dir> --site <code> --user <id> --approved-by <id>");
const apiKey = process.env.OPENAI_API_KEY;
if (!apiKey) throw new Error("OPENAI_API_KEY is required");
async function member(who: string): Promise<string> {
  const [user] = await admin`
    select u.id from users u join tenant_memberships m on m.user_id = u.id
    where (u.id = ${who} or lower(u.email) = lower(${who})) and m.tenant_id = ${tenant} and m.status = 'active'`;
  if (!user) throw new Error(`${who} must be an active member of the tenant`);
  return user.id;
}
const publisher = await member(argument("user"));
const approver = await member(argument("approved-by"));
const [knowledgeBase] = await admin`
  insert into knowledge_bases (tenant_id, domain_id, code, name, status)
  values (${tenant}, ${site.domain_id}, ${sopBase}, ${`Quy trình vận hành BQL ${site.name}`}, 'active')
  on conflict (tenant_id, code) do update set status = 'active' returning id`;
const [category] = await admin`
  insert into knowledge_categories (tenant_id, code, name) values (${tenant}, 'bql-reference', 'Tài liệu tham khảo BQL')
  on conflict (tenant_id, code) do update set name = excluded.name returning id`;
// Document versions need a source file record; publish.ts made the site's staged one.
const [file] = await admin`
  select f.id from files f join knowledge_documents d on d.id = f.document_id and d.tenant_id = f.tenant_id
  join knowledge_bases k on k.id = d.knowledge_base_id
  where f.tenant_id = ${tenant} and k.code = ${`${site.code}-sources`} and d.code = 'source-files' limit 1`;
const [siteScope] = await admin`
  select id from access_scopes where tenant_id = ${tenant} and kind = 'site' and site_id = ${site.id}`;
if (!file || !siteScope) throw new Error("Publish the site's knowledge with publish.ts first");

const deps = {
  store: createIngestStore(createDatabase(url, { max: 3, tenantId: tenant })),
  embedder: createOpenAIEmbedder({ apiKey, baseUrl: process.env.OPENAI_BASE_URL }),
};
const published: string[] = [];
for (const name of (await readdir(root)).filter((n) => n.endsWith(".md")).sort()) {
  const raw = await readFile(join(root, name), "utf8");
  const meta = parseFrontMatter(raw).meta;
  const { code, title, issue_codes: issues, excerpt, acceptance_criteria: criteria } = meta;
  if (typeof code !== "string" || typeof title !== "string" || typeof excerpt !== "string" ||
      !Array.isArray(issues) || !issues.length || !Array.isArray(criteria) || !criteria.length)
    throw new Error(`${name}: code, title, issue_codes, excerpt and acceptance_criteria are required`);
  await ingestDocument(deps, {
    tenantId: tenant,
    knowledgeBaseId: knowledgeBase.id,
    categoryId: category.id,
    code,
    title,
    raw,
    fileId: file.id,
    submittedBy: publisher,
    scopeIds: [siteScope.id],
    scopePath: `Quy trình vận hành BQL > ${site.name}`,
    metadata: { loai: "sop", issue_codes: issues, duyet_boi: approver },
    source: { path: name, approvedBy: approver },
  });
  const [version] = await admin`
    select v.version_no from knowledge_documents d join document_versions v on v.id = d.active_version_id
    where d.tenant_id = ${tenant} and d.knowledge_base_id = ${knowledgeBase.id} and d.code = ${code}`;
  if (!version) throw new Error(`${code}: no active version after ingestion`);
  await admin`
    insert into vh_technical_sop_profiles (tenant_id, document_code, version_no, issue_codes, excerpt, acceptance_criteria)
    values (${tenant}, ${code}, ${version.version_no}, ${JSON.stringify(issues)}::text::jsonb, ${excerpt},
      ${JSON.stringify(criteria)}::text::jsonb)
    on conflict (tenant_id, document_code, version_no) do update
      set issue_codes = excluded.issue_codes, excerpt = excluded.excerpt, acceptance_criteria = excluded.acceptance_criteria`;
  published.push(`${code} v${version.version_no}`);
}
const granted = await grantWorkspaces();
console.log(`Published SOPs: ${published.join(", ")}. Workspace grants added: ${granted}.`);
await admin.close();
