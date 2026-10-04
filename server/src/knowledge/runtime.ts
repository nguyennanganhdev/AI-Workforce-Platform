import { sql } from "drizzle-orm";
import { z } from "zod";
import { createDatabase } from "../db/client";
import { createOpenAIEmbedder } from "./embedder";
import { createRetrievalStore } from "./pg-store";
import type { AuthorizeKnowledgeSearch, KnowledgeRouteDeps } from "./routes";
import { SUPPORTED_EMBEDDING_MODELS } from "./types";

const authority = z.object({
  ok: z.literal(true), knowledgeBaseId: z.uuid(),
  context: z.object({
    tenantId: z.uuid(), userId: z.string().min(1).nullable(), roleCodes: z.array(z.string()),
    targetScopeId: z.uuid(), ancestorScopeIds: z.array(z.uuid()),
    agentRunId: z.uuid(), principalId: z.uuid(), bindingId: z.uuid(),
  }),
});

export function createBackendKnowledgeAuthorization(options: {
  baseUrl: string; tenantId: string; knowledgeBaseId: string; fetch?: typeof fetch;
  internalHttpHost?: string;
}): AuthorizeKnowledgeSearch {
  const base = new URL(options.baseUrl);
  if (base.username || base.password || base.search || base.hash ||
      !(base.protocol === "https:" || (base.protocol === "http:" &&
        (["localhost", "127.0.0.1", "[::1]"].includes(base.hostname) ||
          (options.internalHttpHost === "api" && base.hostname === "api"))))) {
    throw new Error("Knowledge authority requires HTTPS or loopback HTTP");
  }
  return async (request, ask) => {
    const token = request.headers.get("authorization");
    if (!token?.startsWith("Bearer ")) return { ok: false, status: 401, code: "unauthenticated", message: "Reception delegation required." };
    const response = await (options.fetch ?? fetch)(new URL("/internal/reception/v1/knowledge-authorization", base), {
      method: "POST", redirect: "error", signal: AbortSignal.timeout(5000),
      headers: { "content-type": "application/json", authorization: token },
      body: JSON.stringify({ knowledgeBaseId: options.knowledgeBaseId, ...ask }),
    });
    if (response.status === 401) return { ok: false, status: 401, code: "unauthenticated", message: "Knowledge access denied." };
    if (response.status === 403) return { ok: false, status: 403, code: "forbidden", message: "Knowledge access denied." };
    const data = await response.json();
    if (response.status === 409) {
      const error = z.object({ error: z.object({ code: z.literal("scope_required"), message: z.string(), choices: z.array(z.object({ scopeId: z.uuid(), label: z.string() })) }) }).parse(data);
      return { ok: false, status: 409, ...error.error };
    }
    if (!response.ok) throw new Error("Knowledge authority unavailable");
    const verified = authority.parse(data);
    if (verified.context.tenantId !== options.tenantId || verified.knowledgeBaseId !== options.knowledgeBaseId ||
        (ask.scopeId && verified.context.targetScopeId !== ask.scopeId)) throw new Error("Knowledge authority context mismatch");
    return verified;
  };
}

/** Explicit opt-in; missing configuration fails startup instead of selecting demo adapters. */
export async function knowledgeRuntimeFromEnv(env: Record<string, string | undefined>): Promise<KnowledgeRouteDeps | undefined> {
  if (env.KNOWLEDGE_ENABLED !== "1") return undefined;
  const required = (name: string) => { const value = env[name]?.trim(); if (!value) throw new Error(`${name} is required`); return value; };
  const tenantId = z.uuid().parse(required("KNOWLEDGE_TENANT_ID"));
  const knowledgeBaseId = z.uuid().parse(required("KNOWLEDGE_BASE_ID"));
  const database = createDatabase(required("KNOWLEDGE_DATABASE_URL"), { tenantId });
  const roles = await database.execute(sql`SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user`) as unknown as { rolsuper: boolean; rolbypassrls: boolean }[];
  if (roles[0]?.rolsuper !== false || roles[0]?.rolbypassrls !== false) throw new Error("Knowledge runtime requires NOSUPERUSER NOBYPASSRLS");
  // Embeddings keep their own key and address. Reception's chat model may move to another vendor;
  // the vectors stored here were made by this model and must be queried with it.
  const embeddingKey = env.KNOWLEDGE_EMBEDDING_API_KEY?.trim();
  return {
    authorize: createBackendKnowledgeAuthorization({ baseUrl: required("RECEPTION_API_URL"), tenantId, knowledgeBaseId,
      internalHttpHost: env.KNOWLEDGE_INTERNAL_HTTP_HOST }),
    retrieval: {
      store: createRetrievalStore(database),
      embedder: createOpenAIEmbedder({ apiKey: embeddingKey || required("OPENAI_API_KEY"),
        baseUrl: env.KNOWLEDGE_EMBEDDING_BASE_URL?.trim() || (embeddingKey ? undefined : env.OPENAI_BASE_URL),
        model: z.enum(SUPPORTED_EMBEDDING_MODELS).parse(env.KNOWLEDGE_EMBEDDING_MODEL ?? "text-embedding-3-large") }),
    },
  };
}
