/**
 * Schedules of management's agents, on their own port.
 *
 *   cd server && bun src/room-routines/serve.ts
 *
 * Serves /internal/routines/v1 for the business API (create, switch, remove) and, once a minute,
 * hands what is due to the business API, which posts the instruction in the room (routes.ts).
 *
 * Settings: ROUTINES_DATABASE_URL (the role of scripts/grant_routines_role.sql), ROUTINES_TENANT_ID,
 * ROUTINES_SERVICE_TOKEN (32+ characters, shared with the business API in both directions),
 * ROUTINES_API_URL (the business API's origin), ROUTINES_PORT.
 */
import { Hono } from "hono";
import { createDatabase } from "../db/client";
import { createRoutineRoutes, startRoutineSweeps } from "./routes";

const url = process.env.ROUTINES_DATABASE_URL?.trim();
const tenantId = process.env.ROUTINES_TENANT_ID?.trim();
const token = process.env.ROUTINES_SERVICE_TOKEN?.trim() ?? "";
const api = process.env.ROUTINES_API_URL?.trim().replace(/\/+$/, "");
if (!url || !tenantId || !api)
  throw new Error(
    "ROUTINES_DATABASE_URL, ROUTINES_TENANT_ID and ROUTINES_API_URL are required",
  );
if (token.length < 32)
  throw new Error("ROUTINES_SERVICE_TOKEN needs 32+ characters");
// The routine store writes no tenant of its own: this pool names it on every connection.
const database = createDatabase(url, { tenantId });
const app = new Hono().route(
  "/internal/routines/v1",
  createRoutineRoutes(token, database),
);
app.get("/health", (c) => c.json({ status: "ok" }));
startRoutineSweeps(database, api, token);
const port = Number(process.env.ROUTINES_PORT ?? 8789);
Bun.serve({ hostname: process.env.ROUTINES_HOST ?? "127.0.0.1", port, fetch: app.fetch });
console.log(`Agent schedules on http://127.0.0.1:${port}/internal/routines/v1`);
