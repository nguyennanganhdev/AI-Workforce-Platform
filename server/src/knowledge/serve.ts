/**
 * The knowledge search service on its own port, with production authorization.
 *
 *   cd server && bun src/knowledge/serve.ts
 *
 * Serves POST /internal/knowledge/search exactly as the platform server does when
 * KNOWLEDGE_ENABLED=1 (see runtime.ts for the settings), for deployments and local runs that
 * do not start the whole platform. The caller's Reception delegation is checked by the
 * business API on every search; nothing here trusts a scope from the request.
 */
import { Hono } from "hono";
import { createKnowledgeRoutes } from "./routes";
import { knowledgeRuntimeFromEnv } from "./runtime";

const deps = await knowledgeRuntimeFromEnv({ ...process.env, KNOWLEDGE_ENABLED: "1" });
if (!deps) throw new Error("Knowledge runtime is not configured");
const app = new Hono().route(
  "/internal/knowledge",
  createKnowledgeRoutes({
    ...deps,
    // The response never carries the detail; the operator still needs to see it.
    onError: (error) => console.error("knowledge search failed:", error instanceof Error ? error.message : error),
  }),
);
app.get("/health", (c) => c.json({ status: "ok" }));
const port = Number(process.env.KNOWLEDGE_PORT ?? 8787);
Bun.serve({ hostname: process.env.KNOWLEDGE_HOST ?? "127.0.0.1", port, fetch: app.fetch });
console.log(`Knowledge search on http://127.0.0.1:${port}/internal/knowledge/search`);
