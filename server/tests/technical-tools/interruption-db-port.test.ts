import { afterAll, describe, expect, test } from "bun:test";
import { PGlite } from "@electric-sql/pglite";
import { drizzle } from "drizzle-orm/pglite";
import type { Database } from "../../src/db/client";
import {
  createInterruptionDbPort,
  type ExecutionContext,
  runTechnicalTool,
} from "../../src/technical-tools";

const pg = new PGlite();
afterAll(async () => pg.close());
const tenant = "11111111-1111-4111-8111-111111111111";
const otherTenant = "22222222-2222-4222-8222-222222222222";
const building = "33333333-3333-4333-8333-333333333333";
const scope = "44444444-4444-4444-8444-444444444444";
const otherScope = "55555555-5555-4555-8555-555555555555";
const context: ExecutionContext = {
  tenant_id: tenant,
  principal_id: "staff-1",
  source_run_id: "66666666-6666-4666-8666-666666666666",
  trace_id: "trace-db",
  agent_version: "a2-1",
  received_at: "2026-09-30T09:00:00Z",
  grants: [
    {
      tool: "technical.get_active_outage",
      capability: "interruption:read",
      scopeIds: [scope],
    },
    {
      tool: "utility_schedule.read",
      capability: "interruption:read",
      scopeIds: [scope],
    },
  ],
};
const access = { canAccessBuilding: async () => true };
const ids = {
  active: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  planned: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  cancelled: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  foreignScope: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  foreignTenant: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
};

async function setup() {
  await pg.exec(`
    CREATE TABLE service_interruptions (
      id uuid PRIMARY KEY, tenant_id uuid NOT NULL, utility text NOT NULL,
      status text NOT NULL, planned_start timestamptz NOT NULL,
      planned_end timestamptz NOT NULL, actual_start timestamptz,
      actual_end timestamptz, updated_at timestamptz NOT NULL
    );
    CREATE TABLE interruption_scopes (
      interruption_id uuid NOT NULL, tenant_id uuid NOT NULL, scope_id uuid NOT NULL
    );
  `);
  for (const [id, rowTenant, status, actualStart, rowScope] of [
    [ids.active, tenant, "active", "2026-09-30T08:00:00Z", scope],
    [ids.planned, tenant, "notified", null, scope],
    [ids.cancelled, tenant, "cancelled", null, scope],
    [ids.foreignScope, tenant, "active", "2026-09-30T08:00:00Z", otherScope],
    [ids.foreignTenant, otherTenant, "active", "2026-09-30T08:00:00Z", scope],
  ] as const) {
    await pg.query(
      `INSERT INTO service_interruptions
       (id, tenant_id, utility, status, planned_start, planned_end, actual_start, updated_at)
       VALUES ($1,$2,'water',$3,'2026-09-30T08:00:00Z','2026-09-30T10:00:00Z',$4,'2026-09-30T08:05:00Z')`,
      [id, rowTenant, status, actualStart],
    );
    await pg.query(
      "INSERT INTO interruption_scopes (interruption_id, tenant_id, scope_id) VALUES ($1,$2,$3)",
      [id, rowTenant, rowScope],
    );
  }
}

describe("interruption DB adapter", () => {
  test("filters by tenant, covering scope, status and time", async () => {
    await setup();
    const db = drizzle(pg) as unknown as Database;
    const port = createInterruptionDbPort(
      { withTenantRead: async (_context, query) => query(db) },
      { forBuilding: async () => [scope] },
    );
    const outage = await runTechnicalTool(
      "technical.get_active_outage",
      {
        building_id: building,
        service_type: "water",
        occurred_at: "2026-09-30T08:30:00Z",
      },
      context,
      access,
      (input, trusted) => port.getActiveOutages(trusted, input),
    );
    expect(outage.status).toBe("OK");
    expect(outage.data).toMatchObject({
      outages: [{ outage_id: ids.active, scope_ids: [scope] }],
    });
    expect((outage.data as { outages: unknown[] }).outages).toHaveLength(1);
    const schedule = await runTechnicalTool(
      "utility_schedule.read",
      {
        building_id: building,
        utility_type: "water",
        time_range: {
          from: "2026-09-30T09:00:00Z",
          to: "2026-09-30T11:00:00Z",
        },
      },
      context,
      access,
      (input, trusted) => port.readSchedule(trusted, input),
    );
    expect(schedule.status).toBe("OK");
    expect(
      (schedule.data as { schedules: { schedule_id: string }[] }).schedules
        .map((item) => item.schedule_id)
        .sort(),
    ).toEqual([ids.active, ids.planned].sort());
  });
});
