import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { sql } from "drizzle-orm";
import {
  createDbIsolationWriter,
  createDbScopeReadPort,
  type IsolationWriter,
  type ScopeReadPort,
  type WaterIsolation,
} from "../../src/technical-tools";
import { idOf } from "./fixtures/interruptions";
import { WORK, type WorkFixture } from "./fixtures/work-orders";
import {
  BUILDING,
  SCOPE,
  SITE,
  TENANT,
  WORK_ORDER,
  ZONE,
} from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";

/**
 * The scope reader and the water isolation writer against the real schema, in a database of this
 * file's own so what it writes cannot move the counts other files assert on.
 *
 * What is asked here is what only a database can answer: that a request lands in all three tables
 * or in none, that it lands as `pending` and `proposed`, and that the role the tools run as can
 * write a request but cannot turn it into an approval or an outage.
 */
let db: TestDatabase;
let scopes: ScopeReadPort;
let writer: IsolationWriter;

beforeAll(async () => {
  db = await technicalToolsTestDatabase({ isolated: true });
  scopes = createDbScopeReadPort(db.database);
  writer = createDbIsolationWriter(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

const leak = WORK.leak as WorkFixture;

const isolation = (change: Partial<WaterIsolation> = {}): WaterIsolation => ({
  tenantId: TENANT.vinhomes,
  workOrderId: leak.workOrderId,
  approvalId: randomUUID(),
  interruptionId: randomUUID(),
  requiredScopeId: SCOPE.buildingA1,
  scopeIds: [SCOPE.buildingA1],
  reason: "Cần khóa nước để thay đoạn ống rò âm tường",
  plannedStart: new Date("2026-09-30T10:00:00Z"),
  plannedEnd: new Date("2026-09-30T11:00:00Z"),
  requestDetail: { reason: "Cần khóa nước để thay đoạn ống rò âm tường" },
  requestHash: "hash-1",
  ...change,
});

/** Rows as the runtime role sees them, under the tenant. */
function asTenant<T>(
  statement: ReturnType<typeof sql>,
  tenantId: string = TENANT.vinhomes,
) {
  return db.database.transaction(async (tx) => {
    await tx.execute(
      sql`select set_config('app.tenant_id', ${tenantId}, true)`,
    );
    const result = await tx.execute(statement);
    return (
      Array.isArray(result) ? result : (result as { rows: T[] }).rows
    ) as T[];
  });
}

const approvalRow = (id: string) =>
  asTenant<{
    kind: string;
    status: string;
    required_scope_id: string;
    work_order_id: string;
  }>(
    sql`select kind, status, required_scope_id, work_order_id from work_approvals where id = ${id}`,
  );
const interruptionRow = (id: string) =>
  asTenant<{ status: string; utility: string; approval_id: string }>(
    sql`select status, utility, approval_id from service_interruptions where id = ${id}`,
  );
const scopeRows = (id: string) =>
  asTenant<{ scope_id: string }>(
    sql`select scope_id from interruption_scopes where interruption_id = ${id} order by scope_id`,
  );

describe("where a building is", () => {
  test("A1 is in zone S1 of Ocean Park", async () => {
    expect(
      await scopes.placement({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
      }),
    ).toEqual({
      buildingId: BUILDING.a1,
      zoneId: ZONE.s1,
      siteId: SITE.oceanPark,
    });
  });

  test("another tenant's building is nowhere, under this tenant", async () => {
    expect(
      await scopes.placement({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.x1,
      }),
    ).toBeNull();
  });
});

describe("what a scope id names", () => {
  test("its kind and the area it names", async () => {
    const found = await scopes.findScopes({
      tenantId: TENANT.vinhomes,
      ids: [SCOPE.zoneS1, SCOPE.buildingA2],
    });
    expect(found.sort((a, b) => a.id.localeCompare(b.id))).toEqual(
      [
        {
          id: SCOPE.zoneS1,
          kind: "zone",
          buildingId: null,
          zoneId: ZONE.s1,
          siteId: null,
        },
        {
          id: SCOPE.buildingA2,
          kind: "building",
          buildingId: BUILDING.a2,
          zoneId: null,
          siteId: null,
        },
      ].sort((a, b) => a.id.localeCompare(b.id)),
    );
  });

  test("another tenant's scope, or an id that is not one, is simply absent", async () => {
    expect(
      await scopes.findScopes({
        tenantId: TENANT.vinhomes,
        ids: [SCOPE.buildingX1, "not-a-uuid"],
      }),
    ).toEqual([]);
  });
});

describe("writing a water isolation request", () => {
  test("lands in all three tables, as pending and proposed", async () => {
    const request = isolation({
      scopeIds: [SCOPE.buildingA1, SCOPE.zoneS1],
      requiredScopeId: SCOPE.zoneS1,
    });
    await writer.createWaterIsolation(request);

    expect(await approvalRow(request.approvalId)).toEqual([
      {
        kind: "management_water_shutdown",
        status: "pending",
        required_scope_id: SCOPE.zoneS1,
        work_order_id: leak.workOrderId,
      },
    ]);
    expect(await interruptionRow(request.interruptionId)).toEqual([
      { status: "proposed", utility: "water", approval_id: request.approvalId },
    ]);
    expect(
      (await scopeRows(request.interruptionId)).map((r) => r.scope_id),
    ).toEqual([SCOPE.buildingA1, SCOPE.zoneS1].sort());
  });

  test("is found again as open on its work order", async () => {
    const request = isolation({
      workOrderId: (WORK.ac as WorkFixture).workOrderId,
    });
    await writer.createWaterIsolation(request);
    const open = await writer.findOpen({
      tenantId: TENANT.vinhomes,
      workOrderId: (WORK.ac as WorkFixture).workOrderId,
      utility: "water",
    });
    expect(open).toEqual([
      {
        requestId: request.approvalId,
        interruptionId: request.interruptionId,
        status: "proposed",
        plannedStart: request.plannedStart,
        plannedEnd: request.plannedEnd,
      },
    ]);
  });

  /*
   * One of the scopes does not exist, so the third insert fails. Had the approval been written in a
   * transaction of its own, a pending shutdown request would be left behind that nothing shows the
   * reach of, waiting for a manager to approve it.
   */
  test("fails whole: a scope that does not exist leaves no approval behind", async () => {
    const request = isolation({
      scopeIds: [SCOPE.buildingA1, "30000000-0000-4000-8000-000000000099"],
    });
    const failure = await writer.createWaterIsolation(request).then(
      () => null,
      (error) => error,
    );
    expect(failure).not.toBeNull();
    expect(await approvalRow(request.approvalId)).toEqual([]);
    expect(await interruptionRow(request.interruptionId)).toEqual([]);
  });

  test("fails whole: an interruption that cannot be written leaves no approval behind", async () => {
    // I1's id is taken, so the second insert fails after the approval was written.
    const request = isolation({ interruptionId: idOf("I1") });
    const failure = await writer.createWaterIsolation(request).then(
      () => null,
      (error) => error,
    );
    expect(failure).not.toBeNull();
    expect(await approvalRow(request.approvalId)).toEqual([]);
  });

  test("a work order of another tenant cannot be written against", async () => {
    const request = isolation({
      tenantId: TENANT.other,
      workOrderId: leak.workOrderId,
      requiredScopeId: SCOPE.buildingX1,
      scopeIds: [SCOPE.buildingX1],
    });
    const failure = await writer.createWaterIsolation(request).then(
      () => null,
      (error) => error,
    );
    expect(failure).not.toBeNull();
    expect(await approvalRow(request.approvalId)).toEqual([]);
  });
});

describe("finding what is already open", () => {
  test("everything on the work order but what is cancelled or restored", async () => {
    const open = await writer.findOpen({
      tenantId: TENANT.vinhomes,
      workOrderId: WORK_ORDER.vinhomes,
      utility: "water",
    });
    // I1 and I8 are active, I3 proposed, I7 approved; I5 was restored.
    expect(open.map((isolation) => isolation.interruptionId).sort()).toEqual(
      ["I1", "I3", "I7", "I8"].map(idOf).sort(),
    );
  });

  test("not another tenant's", async () => {
    expect(
      await writer.findOpen({
        tenantId: TENANT.other,
        workOrderId: WORK_ORDER.vinhomes,
        utility: "water",
      }),
    ).toEqual([]);
  });
});

/*
 * The role can insert a request. If it could also update, an agent with a prompt injected into it
 * could approve its own request or start the outage; the grant is what makes that impossible
 * rather than merely not attempted.
 */
describe("what the role the tools run as cannot do", () => {
  test.each([
    [
      "approve a request",
      sql`update work_approvals set status = 'approved' where status = 'pending'`,
    ],
    [
      "start an outage",
      sql`update service_interruptions set status = 'active' where status = 'proposed'`,
    ],
    [
      "mark a proposal approved",
      sql`update service_interruptions set status = 'approved'`,
    ],
    ["withdraw a request", sql`delete from work_approvals`],
    ["remove an interruption's scopes", sql`delete from interruption_scopes`],
  ])("%s", async (_label, statement) => {
    const failure: { cause?: unknown } | null = await asTenant(statement).then(
      () => null,
      (error) => error,
    );
    expect(String(failure?.cause)).toMatch(/permission denied/);
  });

  test("and every request written here is still pending", async () => {
    const rows = await asTenant<{ status: string }>(
      sql`select distinct status from work_approvals where request_hash = 'hash-1'`,
    );
    expect(rows).toEqual([{ status: "pending" }]);
  });
});
