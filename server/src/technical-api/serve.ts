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
 */
import { Hono } from "hono";
import { createDatabase } from "../db/client";
import { createTechnicalApiDependencies } from "./runtime";
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
const app = new Hono().route(
  "/internal/technical/v1",
  createSessionToolRoutes(deps, token),
);
const port = Number(process.env.TECHNICAL_TOOLS_PORT ?? 8788);
Bun.serve({ hostname: "127.0.0.1", port, fetch: app.fetch });
console.log(
  `Technical tools for sessions on http://127.0.0.1:${port}/internal/technical/v1`,
);
