import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { sql } from "drizzle-orm";
import { serviceInterruptions } from "../../src/db/schema";
import {
  createDbInterruptionReadPort,
  type InterruptionReadPort,
} from "../../src/technical-tools";
import type { InterruptionRecord } from "../../src/technical-tools/domain/interruption";
import { INTERRUPTIONS, idOf } from "./fixtures/interruptions";
import { BUILDING, SCOPE, TENANT } from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";

/**
 * The database adapter against the real schema: the published baseline migration in a real
 * PostgreSQL, with the sample estate in its real tables.
 *
 * What is asked of the adapter here is only what a database can get wrong: which rows a building's
 * scope reaches, whether another tenant's rows can leak, and whether the role it runs as could
 * change anything. Which statuses count is the rules' question and is tested without a database.
 */
let db: TestDatabase;
let port: InterruptionReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  port = createDbInterruptionReadPort(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

/** Wide enough to hold every fixture, so a test about scope is not also a test about time. */
const ALL_OF_IT = {
  from: new Date("2026-09-01T00:00:00Z"),
  to: new Date("2026-10-31T00:00:00Z"),
};

const keyOf = (record: InterruptionRecord) =>
  INTERRUPTIONS.find((fixture) => fixture.id === record.id)?.key ?? record.id;

async function keysFor(
  buildingId: string,
  utility: "water" | "power",
  window = ALL_OF_IT,
  tenantId: string = TENANT.vinhomes,
) {
  const records = await port.listCovering({
    tenantId,
    buildingId,
    utility,
    window,
  });
  return records?.map(keyOf).sort() ?? null;
}

describe("the schema under test", () => {
  test("is the whole published baseline, not a subset written for the test", async () => {
    const rows = await db.rows<{ tables: number }>(
      "select count(*)::int as tables from pg_tables where schemaname = 'public'",
    );
    expect(rows[0]?.tables).toBe(148);
  });

  test("is read as a role that row-level security applies to", async () => {
    const rows = await db.rows<{ superuser: boolean }>(
      "select rolsuper as superuser from pg_roles where rolname = current_user",
    );
    expect(rows[0]?.superuser).toBe(false);
  });
});

describe("which interruptions reach a building", () => {
  test("its own, its zone's and its site's", async () => {
    // I1 and I5 name building A1; I7 names the whole site.
    expect(await keysFor(BUILDING.a1, "water")).toEqual(["I1", "I5", "I7"]);
    // I2, I4 and I10 name building A1; I6 names zone S1.
    expect(await keysFor(BUILDING.a1, "power")).toEqual([
      "I10",
      "I2",
      "I4",
      "I6",
    ]);
  });

  test("a neighbour in the same zone shares the zone's and the site's, not the building's", async () => {
    expect(await keysFor(BUILDING.a2, "water")).toEqual(["I3", "I7"]);
    expect(await keysFor(BUILDING.a2, "power")).toEqual(["I2", "I6"]);
  });

  test("a building in another zone gets the site's but not zone S1's", async () => {
    expect(await keysFor(BUILDING.b1, "water")).toEqual(["I7", "I8"]);
    expect(await keysFor(BUILDING.b1, "power")).toEqual([]);
  });

  /*
   * The join is on scopes, so an interruption with two scopes is two joined rows. Reported as two
   * outages it would double every count an agent reads off the answer.
   */
  test("an interruption with two scopes comes back once, carrying both", async () => {
    const records = await port.listCovering({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      utility: "power",
      window: ALL_OF_IT,
    });
    const announced = records?.filter((record) => record.id === idOf("I2"));
    expect(announced).toHaveLength(1);
    expect(announced?.[0]?.scopeIds).toEqual(
      [SCOPE.buildingA1, SCOPE.buildingA2].sort(),
    );
  });

  test("hands back the row as the table holds it, times as instants", async () => {
    const records = await port.listCovering({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      utility: "water",
      window: ALL_OF_IT,
    });
    const restored = records?.find((record) => record.id === idOf("I5"));
    expect(restored).toMatchObject({
      utility: "water",
      status: "restored",
      plannedStart: new Date("2026-09-29T14:00:00Z"),
      plannedEnd: new Date("2026-09-29T16:00:00Z"),
      actualStart: new Date("2026-09-29T14:10:00Z"),
      actualEnd: new Date("2026-09-29T15:40:00Z"),
      scopeIds: [SCOPE.buildingA1],
    });
    expect(restored?.updatedAt).toBeInstanceOf(Date);
  });
});

/*
 * The window only bounds how much is read. It must never drop a row the rules would have selected,
 * and the row most at risk is an outage still running long after its planned end: every one of its
 * planned times is in the past.
 */
describe("how the window bounds the read", () => {
  const moment = (iso: string) => ({ from: new Date(iso), to: new Date(iso) });

  test("keeps an outage still running past its planned end", async () => {
    expect(
      await keysFor(BUILDING.a1, "water", moment("2026-09-30T09:00:00Z")),
    ).toEqual(["I1"]);
  });

  test("keeps a finished outage for a moment inside the hours it ran", async () => {
    expect(
      await keysFor(BUILDING.a1, "water", moment("2026-09-29T15:00:00Z")),
    ).toEqual(["I5"]);
  });

  test("drops what had not begun and what was already over", async () => {
    expect(
      await keysFor(BUILDING.a1, "water", moment("2026-09-28T12:00:00Z")),
    ).toEqual([]);
  });
});

describe("a building the tenant does not have", () => {
  test("no such building at all", async () => {
    expect(await keysFor(BUILDING.missing, "water")).toBeNull();
  });

  test("another tenant's building, asked for under this tenant", async () => {
    expect(await keysFor(BUILDING.x1, "power")).toBeNull();
  });

  test("which does exist, and has an outage, for the tenant that owns it", async () => {
    // The positive control: without it the two tests above would also pass on an empty table.
    expect(
      await keysFor(BUILDING.x1, "power", ALL_OF_IT, TENANT.other),
    ).toEqual(["I9"]);
  });
});

/*
 * Tenant isolation that does not depend on the adapter remembering its `tenant_id` filter. These
 * queries deliberately have no such filter; the rows that come back are decided by the policy on
 * the table alone.
 */
describe("row-level security, with the tenant filter left out", () => {
  const visibleTo = (tenantId: string | null) =>
    db.database.transaction(async (tx) => {
      if (tenantId) {
        await tx.execute(
          sql`select set_config('app.tenant_id', ${tenantId}, true)`,
        );
      }
      const rows = await tx
        .select({ id: serviceInterruptions.id })
        .from(serviceInterruptions);
      return rows.map((row) => row.id).sort();
    });

  test("one tenant sees its own nine interruptions and not the other's", async () => {
    const visible = await visibleTo(TENANT.vinhomes);
    expect(visible).toHaveLength(9);
    expect(visible).not.toContain(idOf("I9"));
  });

  test("the other tenant sees only its one", async () => {
    expect(await visibleTo(TENANT.other)).toEqual([idOf("I9")]);
  });

  test("a query that never says which tenant it is for sees nothing", async () => {
    expect(await visibleTo(null)).toEqual([]);
  });
});

describe("what the role the tools run as cannot do", () => {
  test.each([
    ["delete an interruption", sql`delete from service_interruptions`],
    [
      "mark a proposal as active",
      sql`update service_interruptions set status = 'active' where status = 'proposed'`,
    ],
    [
      "read tickets, which these tools have no use for",
      sql`select 1 from tickets`,
    ],
  ])("%s", async (_label, statement) => {
    const failure: { cause?: unknown } | null = await Promise.resolve(
      db.database.execute(statement),
    ).then(
      () => null,
      (error) => error,
    );
    // Drizzle wraps the driver's error; the database's own reason is the cause. Asserting on it
    // is what tells a refusal by the role's grants apart from a statement that failed to parse.
    expect(String(failure?.cause)).toMatch(/permission denied/);
  });

  test("and every fixture is still there afterwards", async () => {
    const total =
      ((await keysFor(BUILDING.a1, "water"))?.length ?? 0) +
      ((await keysFor(BUILDING.a1, "power"))?.length ?? 0);
    expect(total).toBe(7);
  });
});
