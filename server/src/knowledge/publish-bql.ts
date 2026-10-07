/**
 * Publish reference documents that only management's agents read.
 *
 *   cd server
 *   KNOWLEDGE_ADMIN_DATABASE_URL=postgresql://owner@host/db OPENAI_API_KEY=... \
 *     bun src/knowledge/publish-bql.ts <data-dir> --site ocean-park-1 --user <publisher's user id or email>
 *
 * `<data-dir>` holds one folder per topic (`ve-sinh/`, `ke-toan/`) of Markdown files whose front
 * matter has a `title`. The title is what a search hit shows the agent, so it also carries what the
 * source is not (an original law text without its amendments, a price list for reference only).
 *
 * Each file goes into the site's knowledge base as `bql/<topic>/<file>` and is published to the
 * scope of every active management unit. A specialist's search counts its own unit's scope among the
 * ancestors (services/vinhomes-api `v3_agent_knowledge.py`); a resident's search never does, so
 * Reception does not find these. Nothing is retired here, and `publish.ts` leaves `bql/` alone.
 * Chunk text is sent to the embedding provider.
 *
 * A management unit created later does not see them until they are published to its scope too,
 * which needs no source files and no embedding:
 *
 *   KNOWLEDGE_ADMIN_DATABASE_URL=... bun src/knowledge/publish-bql.ts --rescope --site ocean-park-1
 */
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { SQL } from "bun";
import { createDatabase } from "../db/client";
import { createOpenAIEmbedder } from "./embedder";
import { ingestDocument } from "./ingest";
import { parseFrontMatter } from "./markdown";
import { createIngestStore } from "./pg-store";

/** Codes of the documents this publisher owns in the site's knowledge base. */
export const BQL_DOCUMENT_PREFIX = "bql/";

const TOPICS: Record<string, string> = {
  "ve-sinh": "Tài liệu BQL > Vệ sinh & cảnh quan",
  "ke-toan": "Tài liệu BQL > Kế toán vận hành",
};

function argument(name: string): string {
  const index = process.argv.indexOf(`--${name}`);
  const value = index > 0 ? process.argv[index + 1] : undefined;
  if (!value) throw new Error(`--${name} is required`);
  return value;
}

if (import.meta.main) {
  const url = process.env.KNOWLEDGE_ADMIN_DATABASE_URL;
  if (!url) throw new Error("KNOWLEDGE_ADMIN_DATABASE_URL is required");
  const admin = new SQL(url);
  const [site] = await admin`select id, tenant_id, code from sites where code = ${argument("site")}`;
  if (!site) throw new Error("No site with that code");
  const tenant: string = site.tenant_id;
  if (process.argv.includes("--rescope")) {
    const added = await admin`
      insert into document_scopes (tenant_id, document_id, scope_id, applies_to_descendants)
      select d.tenant_id, d.id, s.id, true from knowledge_documents d
      join knowledge_bases k on k.id = d.knowledge_base_id and k.tenant_id = d.tenant_id and k.code = ${site.code}
      join access_scopes s on s.tenant_id = d.tenant_id and s.kind = 'management'
      join management_units u on u.id = s.management_unit_id and u.tenant_id = s.tenant_id and u.status = 'active'
      where d.tenant_id = ${tenant} and d.code like ${`${BQL_DOCUMENT_PREFIX}%`}
      on conflict do nothing returning document_id`;
    console.log(`Scopes added: ${added.length}`);
    await admin.close();
    process.exit(0);
  }
  const root = process.argv[2];
  if (!root || root.startsWith("--"))
    throw new Error("Usage: publish-bql.ts <data-dir> --site <code> --user <id>");
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY is required");
  const [user] = await admin`
    select u.id from users u join tenant_memberships m on m.user_id = u.id
    where (u.id = ${argument("user")} or lower(u.email) = lower(${argument("user")}))
      and m.tenant_id = ${tenant} and m.status = 'active'`;
  if (!user) throw new Error("--user must be an active member of the tenant");
  // The site's knowledge base and its staged source record are made by publish.ts.
  const [knowledgeBase] = await admin`
    select id from knowledge_bases where tenant_id = ${tenant} and code = ${site.code} and status = 'active'`;
  const [file] = await admin`
    select f.id from files f join knowledge_documents d on d.id = f.document_id and d.tenant_id = f.tenant_id
    join knowledge_bases k on k.id = d.knowledge_base_id
    where f.tenant_id = ${tenant} and k.code = ${`${site.code}-sources`} and d.code = 'source-files' limit 1`;
  if (!knowledgeBase || !file)
    throw new Error("Publish the site's knowledge with publish.ts first");
  const [category] = await admin`
    insert into knowledge_categories (tenant_id, code, name) values (${tenant}, 'bql-reference', 'Tài liệu tham khảo BQL')
    on conflict (tenant_id, code) do update set name = excluded.name returning id`;
  const units: { id: string }[] = await admin`
    select s.id from access_scopes s join management_units u on u.id = s.management_unit_id and u.tenant_id = s.tenant_id
    where s.tenant_id = ${tenant} and s.kind = 'management' and u.status = 'active'`;
  if (!units.length) throw new Error("No active management unit to publish to");

  const deps = {
    store: createIngestStore(createDatabase(url, { max: 3, tenantId: tenant })),
    embedder: createOpenAIEmbedder({ apiKey, baseUrl: process.env.OPENAI_BASE_URL }),
  };
  const counts: Record<string, number> = {};
  const failed: string[] = [];
  for (const topic of await readdir(root)) {
    const scopePath = TOPICS[topic];
    if (!scopePath) throw new Error(`Unknown topic folder ${topic}`);
    for (const name of (await readdir(join(root, topic))).filter((n) => n.endsWith(".md")).sort()) {
      const raw = await readFile(join(root, topic, name), "utf8");
      const title = parseFrontMatter(raw).meta.title;
      if (typeof title !== "string" || !title.trim())
        throw new Error(`${topic}/${name} has no title in its front matter`);
      const code = `${BQL_DOCUMENT_PREFIX}${topic}/${name}`;
      try {
        const result = await ingestDocument(deps, {
          tenantId: tenant,
          knowledgeBaseId: knowledgeBase.id,
          categoryId: category.id,
          code,
          title: title.trim(),
          raw,
          fileId: file.id,
          submittedBy: user.id,
          scopeIds: units.map((u) => u.id),
          scopePath,
          metadata: { loai: "tai-lieu-bql", chu_de: topic },
          source: { path: code },
        });
        counts[result.status] = (counts[result.status] ?? 0) + 1;
      } catch (error) {
        failed.push(`${code}: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
  }
  console.log(`Published for management units (${units.length}): ${JSON.stringify(counts)}, ${failed.length} failed.`);
  for (const failure of failed) console.log(`  failed ${failure}`);
  await admin.close();
  process.exit(failed.length ? 1 : 0);
}
