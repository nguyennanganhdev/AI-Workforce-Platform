import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { SQL } from "bun";
import { createDatabase, type Database } from "../../src/db/client";
import { ingestDocument } from "../../src/knowledge/ingest";
import {
  createIngestStore,
  createRetrievalStore,
} from "../../src/knowledge/pg-store";
import { retrieve } from "../../src/knowledge/retrieve";
import {
  type AuthorizedContext,
  EMBEDDING_MODEL,
  type Embedder,
  RETRIEVAL_POLICY_VERSION,
} from "../../src/knowledge/types";
import { testDatabaseUrl } from "../support/database";

/**
 * Needs a dedicated, fully migrated database (TEST_DATABASE_URL) whose role may set
 * `session_replication_role`: the fixture rows (tenant, file, agent run...) belong to services this
 * module does not own, so they are inserted without their own foreign-key chains. Everything the
 * knowledge module itself writes goes through the real constraints and triggers, the 1536-dimension
 * trigger and the append-only chunk trigger included.
 */
const url = process.env.TEST_DATABASE_URL ? testDatabaseUrl() : undefined;

/** A fake embedding space: one axis per topic, so "nearest" is predictable. */
const embedder: Embedder = {
  model: { ...EMBEDDING_MODEL },
  async embed(texts) {
    return texts.map((text) => {
      const vector = new Array<number>(1536).fill(0);
      vector[/ồn|yên lặng/i.test(text) ? 0 : /gas/i.test(text) ? 1 : 2] = 1;
      return vector;
    });
  },
};

const ids = {
  tenant: randomUUID(),
  kb: randomUUID(),
  category: randomUUID(),
  file: randomUUID(),
  urban: randomUUID(),
  sapphire: randomUUID(),
  masterise: randomUUID(),
  principal: randomUUID(),
  binding: randomUUID(),
  run: randomUUID(),
};

const doc = (title: string, body: string) =>
  `---\ntrang_thai: da-thu-thap-mot-phan\n---\n# ${title}\n\n${body}`;

function context(
  overrides: Partial<AuthorizedContext> = {},
): AuthorizedContext {
  return {
    tenantId: ids.tenant,
    userId: "u1",
    roleCodes: ["resident"],
    targetScopeId: ids.sapphire,
    ancestorScopeIds: [ids.urban],
    agentRunId: ids.run,
    principalId: ids.principal,
    bindingId: ids.binding,
    ...overrides,
  };
}

describe.skipIf(!url)("knowledge pg store", () => {
  let admin: SQL;
  let database: Database;
  const deps = () => ({
    store: createIngestStore(database),
    embedder,
  });
  const retrieval = () => ({ store: createRetrievalStore(database), embedder });
  const ingest = (code: string, raw: string, scopeId: string) =>
    ingestDocument(deps(), {
      tenantId: ids.tenant,
      knowledgeBaseId: ids.kb,
      categoryId: ids.category,
      code,
      title: code,
      raw,
      fileId: ids.file,
      submittedBy: "u1",
      scopeIds: [scopeId],
    });
  const ask = (query: string, ctx = context()) =>
    retrieve(retrieval(), {
      context: ctx,
      knowledgeBaseId: ids.kb,
      query,
      minSimilarity: 0.5,
    });

  beforeAll(async () => {
    admin = new SQL(url as string);
    await admin.begin(async (tx) => {
      await tx`set local session_replication_role = replica`;
      await tx`insert into tenants (id, status, name, code) values (${ids.tenant}, 'active', 'T', ${`t-${ids.tenant}`})`;
      const domain = randomUUID();
      await tx`insert into domains (id, tenant_id, code, name, status) values (${domain}, ${ids.tenant}, 'oc', 'Ocean Park', 'active')`;
      await tx`insert into knowledge_categories (id, tenant_id, code, name) values (${ids.category}, ${ids.tenant}, 'quy-dinh', 'Quy định')`;
      await tx`insert into knowledge_bases (id, tenant_id, domain_id, code, name, status) values (${ids.kb}, ${ids.tenant}, ${domain}, 'kb', 'KB', 'active')`;
      for (const id of [ids.urban, ids.sapphire, ids.masterise]) {
        await tx`insert into access_scopes (id, tenant_id, kind) values (${id}, ${ids.tenant}, 'management')`;
      }
      await tx`insert into files (id, tenant_id, scope_kind, channel_id, original_name, owner_principal_id, status) values (${ids.file}, ${ids.tenant}, 'channel', 'c', 'f.md', ${ids.principal}, 'staged')`;
      await tx`insert into users (id, email) values ('u1', 'u1@example.test') on conflict do nothing`;
      await tx`insert into execution_principals (id, kind, tenant_id, status, user_id) values (${ids.principal}, 'user', ${ids.tenant}, 'active', 'u1')`;
      await tx`insert into runtime_session_bindings (id, backend_id, audience_kind, customer_user_id, runtime_session_key, status, policy_version, tenant_id, identity_id, channel_id, agent_id, agent_version_id) values (${ids.binding}, ${randomUUID()}, 'personal', 'u1', 'k', 'active', 'p', ${ids.tenant}, ${randomUUID()}, 'c', 'a', ${randomUUID()})`;
      await tx`insert into agent_runs (id, policy_version, version_id, idempotency_key, status, trace_id, binding_id, authority_principal_id, authority_version, tenant_id, channel_id, agent_id) values (${ids.run}, 'p', ${randomUUID()}, 'k', 'running', 't', ${ids.binding}, ${ids.principal}, 1, ${ids.tenant}, 'c', 'a')`;
    });
    database = createDatabase(url as string, { max: 2, tenantId: ids.tenant });
  });

  afterAll(async () => {
    await admin?.close();
  });

  test("ingest then re-ingest is a no-op; changed content is a new version", async () => {
    const raw = doc("Quy định", "## Giờ ồn\nSau 22h giữ yên lặng.");
    expect(
      (await ingest("sapphire/quy-dinh.md", raw, ids.sapphire)).status,
    ).toBe("ingested");
    expect(
      (await ingest("sapphire/quy-dinh.md", raw, ids.sapphire)).status,
    ).toBe("unchanged");
    const [{ count }] =
      await admin`select count(*)::int as count from knowledge_chunks where tenant_id = ${ids.tenant}`;
    expect(count).toBe(1);

    const changed = await ingest(
      "sapphire/quy-dinh.md",
      `${raw}\nCuối tuần nới đến 23h.`,
      ids.sapphire,
    );
    expect(changed.status).toBe("ingested");
    const [{ versions }] =
      await admin`select count(*)::int as versions from document_versions where tenant_id = ${ids.tenant}`;
    expect(versions).toBe(2);
  });

  test("retrieval is limited to the question's scope and never crosses to another operator", async () => {
    await ingest(
      "sapphire/gas.md",
      doc("Gas", "## Mùi gas\nKhông bật công tắc."),
      ids.sapphire,
    );
    await ingest(
      "masterise/quy-dinh.md",
      doc("Masterise", "## Giờ ồn\nGiờ yên lặng của Masterise."),
      ids.masterise,
    );

    const result = await ask("giờ yên lặng");
    const titles = result.hits.map((hit) => hit.documentTitle);
    expect(titles).toContain("sapphire/quy-dinh.md");
    expect(titles).not.toContain("masterise/quy-dinh.md");
  });

  test("only the active version is served", async () => {
    const result = await ask("giờ yên lặng");
    expect(
      result.hits.every(
        (hit) => hit.text.includes("23h") || !hit.text.includes("Cuối tuần"),
      ),
    ).toBe(true);
    const sapphire = result.hits.filter(
      (hit) => hit.documentTitle === "sapphire/quy-dinh.md",
    );
    expect(sapphire).toHaveLength(1);
    expect(sapphire[0]?.text).toContain("Cuối tuần nới đến 23h");
  });

  test("a document published to descendants reaches a child scope only through its ancestors", async () => {
    await ingest(
      "urban/giao-thong.md",
      doc("Giao thông", "## Giờ ồn\nQuy định chung về yên lặng toàn đô thị."),
      ids.urban,
    );
    const withAncestor = await ask("yên lặng");
    expect(withAncestor.hits.map((h) => h.documentTitle)).toContain(
      "urban/giao-thong.md",
    );
    const without = await ask("yên lặng", context({ ancestorScopeIds: [] }));
    expect(without.hits.map((h) => h.documentTitle)).not.toContain(
      "urban/giao-thong.md",
    );
  });

  test("a deny rule hides a document and an allow list admits only its principals", async () => {
    const [{ id: documentId }] =
      await admin`select id from knowledge_documents where tenant_id = ${ids.tenant} and code = 'sapphire/gas.md'`;
    await admin`insert into document_acl (tenant_id, document_id, principal_kind, role_code, effect) values (${ids.tenant}, ${documentId}, 'role', 'staff', 'allow')`;
    expect(
      (await ask("mùi gas")).hits.map((h) => h.documentTitle),
    ).not.toContain("sapphire/gas.md");
    expect(
      (await ask("mùi gas", context({ roleCodes: ["staff"] }))).hits.map(
        (h) => h.documentTitle,
      ),
    ).toContain("sapphire/gas.md");

    await admin`insert into document_acl (tenant_id, document_id, principal_kind, user_id, effect) values (${ids.tenant}, ${documentId}, 'user', 'u1', 'deny')`;
    expect(
      (await ask("mùi gas", context({ roleCodes: ["staff"] }))).hits.map(
        (h) => h.documentTitle,
      ),
    ).not.toContain("sapphire/gas.md");
  });

  test("a tombstoned document is no longer retrieved", async () => {
    const [{ id: documentId }] =
      await admin`select id from knowledge_documents where tenant_id = ${ids.tenant} and code = 'urban/giao-thong.md'`;
    await createIngestStore(database).tombstone(ids.tenant, documentId);
    expect(
      (await ask("yên lặng")).hits.map((h) => h.documentTitle),
    ).not.toContain("urban/giao-thong.md");
  });

  test("every retrieval is audited with the documents it was allowed to read", async () => {
    const result = await ask("giờ yên lặng");
    const [run] =
      await admin`select authorized_document_ids, policy_version, top_k from retrieval_runs where id = ${result.retrievalRunId}`;
    expect(run.policy_version).toBe(RETRIEVAL_POLICY_VERSION);
    expect(run.authorized_document_ids.length).toBeGreaterThan(0);
    const [{ hits }] =
      await admin`select count(*)::int as hits from retrieval_hits where retrieval_run_id = ${result.retrievalRunId}`;
    expect(hits).toBeGreaterThan(0);
  });

  test("an exact code the vectors cannot tell apart is found by the keyword list, with its metadata", async () => {
    await ingestDocument(deps(), {
      tenantId: ids.tenant,
      knowledgeBaseId: ids.kb,
      categoryId: ids.category,
      code: "sapphire/so-truc.md",
      title: "Số trực",
      raw: doc("Số trực", "## Đầu mối\nAn ninh cao tầng: 0858 001 080."),
      fileId: ids.file,
      submittedBy: "u1",
      scopeIds: [ids.sapphire],
      scopePath: "Vinhomes > sapphire",
      metadata: { cap: "phan_khu", don_vi: "vinhomes" },
    });
    await ingest(
      "sapphire/khac.md",
      doc("Khác", "## Lễ tân\nQuầy lễ tân mở 8h."),
      ids.sapphire,
    );

    const result = await retrieve(retrieval(), {
      context: context(),
      knowledgeBaseId: ids.kb,
      query: "0858 001 080",
      minSimilarity: 0,
    });
    expect(result.hits[0]?.documentTitle).toBe("Số trực");
    expect(result.hits[0]?.keywordRank).toBe(1);
    expect(result.hits[0]?.metadata).toMatchObject({ don_vi: "vinhomes" });
  });

  test("a query typed without diacritics still matches by keyword", async () => {
    const result = await retrieve(retrieval(), {
      context: context(),
      knowledgeBaseId: ids.kb,
      query: "an ninh cao tang",
      minSimilarity: 0,
    });
    const hit = result.hits.find((h) => h.documentTitle === "Số trực");
    expect(hit?.keywordRank).not.toBeNull();
  });

  test("a notice number ranks the passage that carries all of it first in the keyword list", async () => {
    await ingest(
      "urban/do-sanh.md",
      doc(
        "Để đồ sảnh",
        "## Hàng hóa\nThông báo số 134/2026/TBCT-VHOCP: không để hàng ở sảnh.",
      ),
      ids.urban,
    );
    await ingest(
      "urban/giao-thong-2.md",
      doc(
        "Giao thông",
        "## Dừng đỗ\nThông báo 05/2026 quy định quy định dừng đỗ.",
      ),
      ids.urban,
    );
    const result = await retrieve(retrieval(), {
      context: context(),
      knowledgeBaseId: ids.kb,
      query: "TB 134/2026 quy định gì?",
      minSimilarity: 0,
    });
    const hit = result.hits.find((h) => h.documentTitle === "urban/do-sanh.md");
    expect(hit?.keywordRank).toBe(1);
  });
});
