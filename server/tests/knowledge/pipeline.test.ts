import { describe, expect, test } from "bun:test";
import { ingestDocument } from "../../src/knowledge/ingest";
import { retrieve } from "../../src/knowledge/retrieve";
import {
  type AuthorizedContext,
  type ChunkWithEmbedding,
  EMBEDDING_MODEL,
  type Embedder,
  type IngestStore,
  type RetrievalStore,
} from "../../src/knowledge/types";

const embedder: Embedder & { calls: string[][] } = {
  model: { ...EMBEDDING_MODEL },
  calls: [],
  async embed(texts) {
    this.calls.push(texts);
    return texts.map(() => [1, 0]);
  },
};

function memoryStore() {
  const state = {
    versions: [] as { id: string; hash: string; embedded: boolean }[],
    chunks: [] as ChunkWithEmbedding[],
    jobs: new Map<string, { id: string; status: string; attempts: number }>(),
    active: null as string | null,
    activations: 0,
    failNextSave: false,
  };
  const store: IngestStore = {
    async ensureEmbeddingModel() {
      return { id: "model-1" };
    },
    async upsertDocument() {
      const active = state.versions.find((v) => v.id === state.active);
      return {
        id: "doc-1",
        activeVersion: active
          ? { id: active.id, contentHash: active.hash }
          : null,
      };
    },
    async findVersion({ contentHash }) {
      const found = state.versions.find((v) => v.hash === contentHash);
      return found ? { id: found.id, embedded: found.embedded } : null;
    },
    async createVersion(input) {
      const id = `v${state.versions.length + 1}`;
      state.versions.push({ id, hash: input.contentHash, embedded: false });
      return { id };
    },
    async startJob(input) {
      const existing = state.jobs.get(input.idempotencyKey);
      if (existing) {
        existing.attempts++;
        return { id: existing.id };
      }
      const job = {
        id: `job-${state.jobs.size + 1}`,
        status: "embedding",
        attempts: 1,
      };
      state.jobs.set(input.idempotencyKey, job);
      return { id: job.id };
    },
    async saveChunks(input) {
      if (state.failNextSave) {
        state.failNextSave = false;
        throw Object.assign(new Error("boom"), { code: "db_down" });
      }
      state.chunks.push(...input.chunks);
    },
    async completeJob() {
      for (const version of state.versions) version.embedded = true;
    },
    async failJob(_t, jobId, code) {
      for (const job of state.jobs.values()) {
        if (job.id === jobId) job.status = `failed:${code}`;
      }
    },
    async activateVersion({ versionId }) {
      state.active = versionId;
      state.activations++;
    },
    async tombstone() {
      state.active = null;
    },
    async listDocuments() {
      return [];
    },
  };
  return { state, store };
}

const input = (raw: string) => ({
  tenantId: "t1",
  knowledgeBaseId: "kb1",
  categoryId: "c1",
  code: "01-vinhomes/sapphire/quy-dinh.md",
  title: "Quy định",
  raw,
  fileId: "f1",
  submittedBy: "u1",
  scopeIds: ["s1"],
});

const FILE =
  "---\ntrang_thai: da-thu-thap-mot-phan\n---\n# Quy định\n\n## Giờ ồn\nSau 22h giữ yên lặng.";

describe("ingestDocument", () => {
  test("ingests, then a second run with the same content changes nothing", async () => {
    const { state, store } = memoryStore();
    const first = await ingestDocument({ store, embedder }, input(FILE));
    expect(first.status).toBe("ingested");
    expect(state.chunks).toHaveLength(1);

    embedder.calls.length = 0;
    const second = await ingestDocument({ store, embedder }, input(FILE));
    expect(second.status).toBe("unchanged");
    expect(state.chunks).toHaveLength(1);
    expect(embedder.calls).toHaveLength(0);
  });

  test("changed content becomes a new version", async () => {
    const { state, store } = memoryStore();
    await ingestDocument({ store, embedder }, input(FILE));
    const changed = await ingestDocument(
      { store, embedder },
      input(`${FILE}\nThêm một dòng.`),
    );
    expect(changed.status).toBe("ingested");
    expect(state.versions).toHaveLength(2);
    expect(state.active).toBe("v2");
  });

  test("a file still marked chua-thu-thap keeps its facts so missing data can be stated", async () => {
    const { state, store } = memoryStore();
    const result = await ingestDocument(
      { store, embedder },
      input(
        "---\ntrang_thai: chua-thu-thap\n---\n# PCCC R1.02\n## Fact\nChưa có sơ đồ thoát nạn R1.02.\n## Cần thu thập\n- ảnh sơ đồ",
      ),
    );
    expect(result.status).toBe("ingested");
    expect(state.chunks.map((chunk) => chunk.text)).toEqual([
      "Chưa có sơ đồ thoát nạn R1.02.",
    ]);
  });

  test("the scope line is embedded with every chunk and indexed for keywords", async () => {
    const { state, store } = memoryStore();
    embedder.calls.length = 0;
    await ingestDocument(
      { store, embedder },
      { ...input(FILE), scopePath: "Vinhomes > sapphire > sapphire-1 > S1.01" },
    );
    expect(embedder.calls[0]?.[0]).toStartWith(
      "[Vinhomes > sapphire > sapphire-1 > S1.01 | Quy định | Giờ ồn]",
    );
    expect(state.chunks[0]?.searchText).toContain("S1.01");
    expect(state.chunks[0]?.searchText).toContain("Gio on");
  });

  test("an empty template is skipped", async () => {
    const { store } = memoryStore();
    const result = await ingestDocument(
      { store, embedder },
      input("# Hướng dẫn\n\n## Fact\n\n-\n"),
    );
    expect(result).toEqual({ status: "skipped", reason: "empty" });
  });

  test("a failure leaves the previous version serving and a retry resumes the same version", async () => {
    const { state, store } = memoryStore();
    await ingestDocument({ store, embedder }, input(FILE));
    const changed = `${FILE}\nDòng mới.`;

    state.failNextSave = true;
    await expect(
      ingestDocument({ store, embedder }, input(changed)),
    ).rejects.toThrow("boom");
    expect(state.active).toBe("v1");
    expect(
      [...state.jobs.values()].some((j) => j.status === "failed:db_down"),
    ).toBe(true);

    const retried = await ingestDocument({ store, embedder }, input(changed));
    expect(retried.status).toBe("ingested");
    expect(state.versions).toHaveLength(2);
    expect(state.active).toBe("v2");
  });
});

const context: AuthorizedContext = {
  tenantId: "t1",
  userId: "u1",
  roleCodes: ["resident"],
  targetScopeId: "s1",
  ancestorScopeIds: [],
  agentRunId: "r1",
  principalId: "p1",
  bindingId: "b1",
};

function retrievalStore(similarities: number[]) {
  const recorded: Parameters<RetrievalStore["recordRun"]>[0][] = [];
  const store: RetrievalStore = {
    async ensureEmbeddingModel() {
      return { id: "model-1" };
    },
    async searchAuthorized() {
      return {
        authorizedDocumentIds: ["doc-1"],
        hits: similarities.map((similarity, index) => ({
          chunkId: `c${index}`,
          documentId: "doc-1",
          versionId: "v1",
          documentTitle: "Quy định",
          headingPath: "Giờ ồn",
          text: "Sau 22h giữ yên lặng.",
          similarity,
          vectorRank: index + 1,
          keywordRank: null,
          fusedScore: 1 / (61 + index),
          metadata: { cap: "phan_khu" },
          sources: [],
        })),
      };
    },
    async recordRun(run) {
      recorded.push(run);
      return { id: "run-1" };
    },
  };
  return { store, recorded };
}

describe("retrieve", () => {
  test("returns ranked hits with a retrieval run id and audits every candidate", async () => {
    const { store, recorded } = retrievalStore([0.9, 0.1]);
    const result = await retrieve(
      { store, embedder },
      { context, knowledgeBaseId: "kb1", query: "giờ yên lặng?" },
    );
    expect(result.retrievalRunId).toBe("run-1");
    expect(result.hits.map((hit) => hit.chunkId)).toEqual(["c0"]);
    expect(result.hits[0]?.rank).toBe(1);
    expect(result.insufficientSources).toBe(false);
    expect(recorded[0]?.hits).toHaveLength(2);
    expect(recorded[0]?.hits[1]?.included).toBe(false);
    expect(recorded[0]?.authorizedDocumentIds).toEqual(["doc-1"]);
  });

  test("a passage clearly closest in meaning leads, whatever its fused rank", async () => {
    // Fused order is c0, c1, c2. c2 restates the question; the others only share common words.
    const clear = await retrieve(
      { store: retrievalStore([0.52, 0.5, 0.78]).store, embedder },
      { context, knowledgeBaseId: "kb1", query: "mượn xe đẩy hàng?" },
    );
    expect(clear.hits.map((hit) => hit.chunkId)).toEqual(["c2", "c0", "c1"]);
    // Without a clear lead the fused order stands.
    const close = await retrieve(
      { store: retrievalStore([0.52, 0.5, 0.6]).store, embedder },
      { context, knowledgeBaseId: "kb1", query: "mượn xe đẩy hàng?" },
    );
    expect(close.hits.map((hit) => hit.chunkId)).toEqual(["c0", "c1", "c2"]);
  });

  test("nothing close enough means insufficient sources", async () => {
    const { store } = retrievalStore([0.05]);
    const result = await retrieve(
      { store, embedder },
      { context, knowledgeBaseId: "kb1", query: "câu hỏi lạc đề" },
    );
    expect(result.hits).toEqual([]);
    expect(result.insufficientSources).toBe(true);
  });

  test("the default threshold, 0.35, refuses the off-topic scores the evaluation measured", async () => {
    // ocean-park-v1 with text-embedding-3-large: "tôi tên gì" 0.33, "giá vàng SJC hôm nay" 0.33.
    const offTopic = await retrieve(
      { store: retrievalStore([0.33, 0.3]).store, embedder },
      { context, knowledgeBaseId: "kb1", query: "tôi tên gì" },
    );
    expect(offTopic.insufficientSources).toBe(true);
    // And keeps an answerable one just above it: "thang may bi ket" 0.35.
    const answerable = await retrieve(
      { store: retrievalStore([0.35]).store, embedder },
      { context, knowledgeBaseId: "kb1", query: "thang may bi ket" },
    );
    expect(answerable.insufficientSources).toBe(false);
  });

  test("an empty query does not call the embedder or search", async () => {
    const { store, recorded } = retrievalStore([0.9]);
    embedder.calls.length = 0;
    const result = await retrieve(
      { store, embedder },
      { context, knowledgeBaseId: "kb1", query: "   " },
    );
    expect(embedder.calls).toHaveLength(0);
    expect(result.insufficientSources).toBe(true);
    expect(recorded).toHaveLength(1);
  });

  test("topK is clamped", async () => {
    const { store, recorded } = retrievalStore([0.9]);
    await retrieve(
      { store, embedder },
      { context, knowledgeBaseId: "kb1", query: "x", topK: 999 },
    );
    expect(recorded[0]?.topK).toBe(20);
  });

  test("a building-level management notice outranks a city-wide team note with the same fused score", async () => {
    const recorded: unknown[] = [];
    const base = {
      documentId: "d",
      versionId: "v",
      documentTitle: "t",
      headingPath: null,
      similarity: 0.9,
      vectorRank: 1,
      keywordRank: 1,
      fusedScore: 0.03,
      sources: [],
    };
    const store: RetrievalStore = {
      async ensureEmbeddingModel() {
        return { id: "m" };
      },
      async searchAuthorized() {
        return {
          authorizedDocumentIds: ["d"],
          hits: [
            {
              ...base,
              chunkId: "city",
              text: "Ghi nhận team: phí 13.000.",
              metadata: { cap: "do_thi" },
            },
            {
              ...base,
              chunkId: "building",
              text: "Theo TB 134/2026: phí 13.000.",
              metadata: { cap: "toa" },
            },
            {
              ...base,
              chunkId: "draft",
              text: "Chưa có dữ liệu.",
              metadata: { cap: "toa", trang_thai: "chua-thu-thap" },
            },
          ],
        };
      },
      async recordRun(run) {
        recorded.push(run);
        return { id: "r" };
      },
    };
    const result = await retrieve(
      { store, embedder },
      { context, knowledgeBaseId: "kb1", query: "phí" },
    );
    expect(result.hits.map((hit) => hit.chunkId)).toEqual([
      "building",
      "city",
      "draft",
    ]);
    expect(result.hits[0]?.reliability).toBe("van_ban_bql");
    expect(result.hits[1]?.reliability).toBe("ghi_nhan_team");
  });
});
