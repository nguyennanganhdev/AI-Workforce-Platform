import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  searchKnowledgeError,
  searchKnowledgeJsonSchemas,
  searchKnowledgeResponse,
} from "../../src/knowledge/contract";
import { EmbeddingError } from "../../src/knowledge/embedder";
import {
  type AuthorizeKnowledgeSearch,
  createKnowledgeRoutes,
} from "../../src/knowledge/routes";
import {
  type AuthorizedContext,
  EMBEDDING_MODEL,
  type Embedder,
  type RetrievalStore,
} from "../../src/knowledge/types";

const context: AuthorizedContext = {
  tenantId: "00000000-0000-4000-8000-000000000001",
  userId: "resident-1",
  roleCodes: ["resident"],
  targetScopeId: "00000000-0000-4000-8000-000000000101",
  ancestorScopeIds: [],
  agentRunId: "00000000-0000-4000-8000-000000000201",
  principalId: "00000000-0000-4000-8000-000000000301",
  bindingId: "00000000-0000-4000-8000-000000000401",
};
const KB = "00000000-0000-4000-8000-000000000501";

function embedder(fail = false): Embedder {
  return {
    model: { ...EMBEDDING_MODEL },
    async embed(texts) {
      if (fail) throw new EmbeddingError("down", "http_503");
      return texts.map(() => [1]);
    },
  };
}

function store(): RetrievalStore & { searched: unknown[] } {
  const searched: unknown[] = [];
  return {
    searched,
    async ensureEmbeddingModel() {
      return { id: "m" };
    },
    async searchAuthorized(input) {
      searched.push(input);
      return {
        authorizedDocumentIds: ["00000000-0000-4000-8000-000000000601"],
        hits: [
          {
            chunkId: "00000000-0000-4000-8000-000000000701",
            documentId: "00000000-0000-4000-8000-000000000601",
            versionId: "00000000-0000-4000-8000-000000000801",
            documentTitle: "Số điện thoại trực tòa — S1.01",
            headingPath: "Số điện thoại trực tòa — S1.01 > Cách gọi an ninh",
            text: "An ninh cao tầng: 0858 001 080. Ghi nhận team.",
            similarity: 0.62,
            vectorRank: 1,
            keywordRank: 1,
            fusedScore: 0.0328,
            metadata: {
              don_vi: "vinhomes",
              phan_khu: "sapphire",
              cum: "sapphire-1",
              toa: ["S1.01"],
              cap: "toa",
              loai: "lien_he",
              trang_thai: "da-thu-thap-mot-phan",
              cap_nhat: "2026-09-29",
              chua_xac_minh: false,
            },
            sources: ["Ghi nhận team 29/09/2026"],
          },
        ],
      };
    },
    async recordRun() {
      return { id: "00000000-0000-4000-8000-000000000901" };
    },
  };
}

const allow: AuthorizeKnowledgeSearch = async () => ({
  ok: true,
  context,
  knowledgeBaseId: KB,
});

function app(
  authorize: AuthorizeKnowledgeSearch = allow,
  options: { embedFails?: boolean; retrievalStore?: RetrievalStore } = {},
) {
  return createKnowledgeRoutes({
    authorize,
    retrieval: {
      store: options.retrievalStore ?? store(),
      embedder: embedder(options.embedFails),
    },
    onError: () => {},
  });
}

const post = (routes: ReturnType<typeof app>, body: unknown) =>
  routes.request("/search", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });

describe("POST /internal/knowledge/search", () => {
  test("answers with passages that match the published response schema", async () => {
    const response = await post(app(), { query: "số an ninh tòa mình?" });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(searchKnowledgeResponse.safeParse(body).success).toBe(true);
    expect(body.hits[0]).toMatchObject({
      rank: 1,
      reliability: "ghi_nhan_team",
      scope: { operator: "vinhomes", level: "toa", buildings: ["S1.01"] },
      kind: "lien_he",
      unverified: false,
    });
  });

  test("authority comes from authorize, never from the body", async () => {
    const retrievalStore = store();
    let asked: { scopeId?: string } | undefined;
    const routes = app(
      async (_request, ask) => {
        asked = ask;
        return { ok: true, context, knowledgeBaseId: KB };
      },
      { retrievalStore },
    );
    const scopeId = "00000000-0000-4000-8000-000000000999";
    await post(routes, { query: "x", scopeId });
    expect(asked).toEqual({ scopeId });
    expect(
      (retrievalStore.searched[0] as { context: AuthorizedContext }).context,
    ).toBe(context);
  });

  test("unknown fields such as a self-declared tenant are rejected", async () => {
    const response = await post(app(), { query: "x", tenantId: "other" });
    expect(response.status).toBe(400);
    expect(searchKnowledgeError.safeParse(await response.json()).success).toBe(
      true,
    );
  });

  test("an empty query or broken JSON is a 400 invalid_request", async () => {
    for (const body of [
      { query: "  " },
      "{not json",
      { query: "x", topK: 99 },
    ]) {
      const response = await post(app(), body);
      expect(response.status).toBe(400);
      expect((await response.json()).error.code).toBe("invalid_request");
    }
  });

  test("authorization refusals pass through with their status", async () => {
    const forbidden = await post(
      app(async () => ({
        ok: false,
        status: 403,
        code: "forbidden",
        message: "No grant.",
      })),
      { query: "x" },
    );
    expect(forbidden.status).toBe(403);

    const choices = [
      { scopeId: "00000000-0000-4000-8000-000000000111", label: "S1.01-1203" },
      { scopeId: "00000000-0000-4000-8000-000000000112", label: "R1.02-0801" },
    ];
    const ambiguous = await post(
      app(async () => ({
        ok: false,
        status: 409,
        code: "scope_required",
        message: "Which apartment?",
        choices,
      })),
      { query: "x" },
    );
    expect(ambiguous.status).toBe(409);
    expect((await ambiguous.json()).error).toEqual({
      code: "scope_required",
      message: "Which apartment?",
      choices,
    });
  });

  test("nothing is searched when authorization refuses", async () => {
    const retrievalStore = store();
    await post(
      app(
        async () => ({
          ok: false,
          status: 401,
          code: "unauthenticated",
          message: "No token.",
        }),
        {
          retrievalStore,
        },
      ),
      { query: "x" },
    );
    expect(retrievalStore.searched).toHaveLength(0);
  });

  test("an embedding outage is a 502 the caller may retry; other failures do not leak detail", async () => {
    const outage = await post(app(allow, { embedFails: true }), { query: "x" });
    expect(outage.status).toBe(502);
    expect((await outage.json()).error.code).toBe("embedding_unavailable");

    const broken = await post(
      app(async () => {
        throw new Error("password=secret");
      }),
      { query: "x" },
    );
    expect(broken.status).toBe(500);
    expect(JSON.stringify(await broken.json())).not.toContain("secret");
  });
});

describe("published contract", () => {
  test("the JSON Schema handed to other teams matches the code", () => {
    const published = JSON.parse(
      readFileSync(
        join(
          import.meta.dir,
          "../../../docs/teams/quang/handoffs/contracts/search_knowledge.v1.schema.json",
        ),
        "utf8",
      ),
    );
    expect(published).toEqual(
      JSON.parse(JSON.stringify(searchKnowledgeJsonSchemas())),
    );
  });
});
