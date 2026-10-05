import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { sql } from "drizzle-orm";
import {
  createDbUnitReadPort,
  createDbWorkOrderReadPort,
  type UnitReadPort,
  type WorkOrderReadPort,
} from "../../src/technical-tools";
import { RESIDENT_USER, UNIT } from "./fixtures/units";
import { WORK, type WorkFixture } from "./fixtures/work-orders";
import { BUILDING, TENANT, USER } from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";

/**
 * The apartment reader against the real schema, and the ticket facts the entry and dispatch tools
 * read: which apartment, whether triage marked it an emergency, its priority.
 */
let db: TestDatabase;
let units: UnitReadPort;
let workOrders: WorkOrderReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  units = createDbUnitReadPort(db.database);
  workOrders = createDbWorkOrderReadPort(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

const job = (key: string) => WORK[key] as WorkFixture;

describe("finding an apartment", () => {
  test("hands back its code and building", async () => {
    expect(
      await units.findUnit({ tenantId: TENANT.vinhomes, unitId: UNIT.a1_1305 }),
    ).toEqual({
      unitId: UNIT.a1_1305,
      code: "A1-1305",
      buildingId: BUILDING.a1,
    });
  });

  test("an apartment in another building is found, with that building, for the tool to refuse", async () => {
    expect(
      (
        await units.findUnit({
          tenantId: TENANT.vinhomes,
          unitId: UNIT.a2_0803,
        })
      )?.buildingId,
    ).toBe(BUILDING.a2);
  });

  test("another tenant's apartment, a missing one, or an id that is not one, is nothing", async () => {
    for (const unitId of [
      UNIT.x1_0101,
      "76000000-0000-4000-8000-000000000099",
      "A1-1305",
    ]) {
      expect(
        await units.findUnit({ tenantId: TENANT.vinhomes, unitId }),
      ).toBeNull();
    }
  });
});

describe("who lives there, as the table holds it", () => {
  test("A1-1305: its verified owner", async () => {
    expect(
      await units.residents({
        tenantId: TENANT.vinhomes,
        unitId: UNIT.a1_1305,
      }),
    ).toEqual([
      {
        userId: RESIDENT_USER.a1_1305,
        relation: "owner",
        verificationStatus: "verified",
        validFrom: new Date("2025-01-01T00:00:00Z"),
        validTo: null,
      },
    ]);
  });

  test("A1-1105: a former tenant and an unverified one, both handed back for the rules to judge", async () => {
    const found = await units.residents({
      tenantId: TENANT.vinhomes,
      unitId: UNIT.a1_1105,
    });
    expect(found.map((r) => r.verificationStatus).sort()).toEqual([
      "pending",
      "verified",
    ]);
  });

  test("none under another tenant", async () => {
    expect(
      await units.residents({ tenantId: TENANT.other, unitId: UNIT.a1_1305 }),
    ).toEqual([]);
  });
});

describe("what a ticket says about urgency", () => {
  test("the breaker ticket is an emergency, critical", async () => {
    expect(
      await workOrders.getTicket({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        ticketId: job("breaker").ticketId,
      }),
    ).toEqual({
      ticketId: job("breaker").ticketId,
      buildingId: BUILDING.a1,
      unitId: UNIT.a1_1205,
      isEmergency: true,
      priority: "critical",
    });
  });

  test("the leak ticket is not", async () => {
    expect(
      await workOrders.getTicket({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        ticketId: job("leak").ticketId,
      }),
    ).toMatchObject({ isEmergency: false, priority: "normal" });
  });

  test("a ticket's work orders, each with who is on it", async () => {
    const found = await workOrders.listWorkOrders({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      ticketId: job("breaker").ticketId,
    });
    expect(found.map((w) => w.workOrderId)).toEqual([
      job("breaker").workOrderId,
    ]);
    expect(found[0]?.assignments[0]?.staffUserId).toBe(USER.secondTechnician);
  });

  test("none from another building", async () => {
    expect(
      await workOrders.listWorkOrders({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a2,
        ticketId: job("breaker").ticketId,
      }),
    ).toEqual([]);
  });
});

describe("what the role the tools run as cannot do", () => {
  test.each([
    [
      "change who lives in an apartment",
      sql`update unit_residents set verification_status = 'verified'`,
    ],
    [
      "raise a ticket's priority",
      sql`update tickets set priority = 'critical'`,
    ],
    [
      "mark a ticket an emergency",
      sql`update tickets set is_emergency = true, priority = 'critical'`,
    ],
  ])("%s", async (_label, statement) => {
    const failure: { cause?: unknown } | null = await Promise.resolve(
      db.database.execute(statement),
    ).then(
      () => null,
      (error) => error,
    );
    expect(String(failure?.cause)).toMatch(/permission denied/);
  });
});
