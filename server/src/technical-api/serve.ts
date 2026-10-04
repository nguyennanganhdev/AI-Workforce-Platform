/**
 * The technical tools for Supervisor sessions, on their own port.
 *
 *   cd server && bun src/technical-api/serve.ts
 *
 * Serves /internal/technical/v1/tools and /internal/technical/v1/call for the Coordination
 * runtime (agent-coordination), for deployments and local runs that do not start the whole
 * platform server. Same database role, audit and tool host as /api/technical/v1; the caller is
 * a specialist's agent run instead of a person's Bot (session.ts).
 *
 * Settings: TECHNICAL_API_DATABASE_URL (the restricted role), TECHNICAL_API_TENANT_ID,
 * TECHNICAL_TOOLS_SERVICE_TOKEN (32+ characters, shared with the runtime), TECHNICAL_TOOLS_PORT.
 *
 * Also serves /internal/technical/v1/connections for the business API: the external MCP servers an
 * administrator connected for a management unit's agents. TECHNICAL_CONNECTIONS_KEY (base64 of 32
 * bytes) seals their tokens; without it those routes answer 503 and everything else works.
 * TECHNICAL_CONNECTIONS_HTTP_ORIGINS lists origins reachable over plain http, for a local test server.
 */
import { Hono } from "hono";
import { createDatabase } from "../db/client";
import { createTechnicalApiDependencies } from "./runtime";
import { createConnectionRoutes } from "./connection-routes";
import { createSessionToolRoutes } from "./session-routes";

const url = process.env.TECHNICAL_API_DATABASE_URL?.trim();
const tenantId = process.env.TECHNICAL_API_TENANT_ID?.trim();
const token = process.env.TECHNICAL_TOOLS_SERVICE_TOKEN?.trim() ?? "";
if (!url || !tenantId)
  throw new Error(
    "TECHNICAL_API_DATABASE_URL and TECHNICAL_API_TENANT_ID are required",
  );
const deps = createTechnicalApiDependencies({
  database: createDatabase(url),
  tenantId,
  // No Bot token is accepted on this port: a session call names an agent run instead.
  encryptionKey: "",
  lookupToken: async () => null,
});
// Mounted first: the session routes guard every path under their prefix with the same token.
const app = new Hono()
  .route(
    "/internal/technical/v1/connections",
    createConnectionRoutes(
      token,
      process.env.TECHNICAL_CONNECTIONS_KEY?.trim() ?? "",
      (process.env.TECHNICAL_CONNECTIONS_HTTP_ORIGINS ?? "")
        .split(",")
        .map((origin) => origin.trim())
        .filter(Boolean),
    ),
  )
  .route("/internal/technical/v1", createSessionToolRoutes(deps, token));
app.get("/health", (c) => c.json({ status: "ok" }));
const port = Number(process.env.TECHNICAL_TOOLS_PORT ?? 8788);
Bun.serve({ hostname: process.env.TECHNICAL_TOOLS_HOST ?? "127.0.0.1", port, fetch: app.fetch });
console.log(
  `Technical tools for sessions on http://127.0.0.1:${port}/internal/technical/v1`,
);
