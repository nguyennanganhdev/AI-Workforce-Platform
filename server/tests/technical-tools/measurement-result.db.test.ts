import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { sql } from "drizzle-orm";
import { evidenceItems, workOrders } from "../../src/db/schema";
import {
  createDbWorkOrderReadPort,
  type WorkOrderReadPort,
} from "../../src/technical-tools";
import {
  EVIDENCE,
  STAGED_UPLOAD,
  WORK,
  type WorkFixture,
} from "./fixtures/work-orders";
import { BUILDING, TENANT, USER, WORK_ORDER } from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";

/**
 * The work-order adapter against the real schema: the published baseline in a real PostgreSQL,
 * with five jobs seeded through the same triggers the application's own writes go through.
 *
 * What is asked here is only what a database can get wrong: which building a work order is in,
 * who an assignment names, what an id offered as evidence turns out to be, whether another tenant's
 * rows can leak, and whether the role the tools run as could change any of it.
 */
let db: TestDatabase;
let port: WorkOrderReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  port = createDbWorkOrderReadPort(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

const job = (key: string) => WORK[key] as WorkFixture;

const read = (
  work: WorkFixture,
  buildingId = work.buildingId,
  tenantId: string = TENANT.vinhomes,
) => port.getWorkOrder({ tenantId, buildingId, workOrderId: work.workOrderId });

describe("finding a work order in a building", () => {
  test("hands back its ticket, its state and who is on it", async () => {
    const ac = job("ac");
    expect(await read(ac)).toEqual({
      workOrderId: ac.workOrderId,
      ticketId: ac.ticketId,
      buildingId: BUILDING.a1,
      status: "in_progress",
      assignments: [
        {
          assignmentId: ac.assignmentId,
          status: "accepted",
          staffUserId: USER.technician,
          acceptedAt: ac.acceptedAt,
        },
      ],
    });
  });

  test("names the technician as a user, through their staff profile", async () => {
    const breaker = await read(job("breaker"));
    expect(breaker?.assignments.map((a) => a.staffUserId)).toEqual([
      USER.secondTechnician,
    ]);
  });

  test("an assignment the technician was released from is still listed, as released", async () => {
    const old = await read(job("old"));
    expect(old?.assignments).toEqual([
      expect.objectContaining({
        status: "released",
        staffUserId: USER.technician,
      }),
    ]);
  });

  /*
   * A work order in another building and one that does not exist must be the same answer, or the
   * refusal would confirm which work orders exist elsewhere.
   */
  test("one in another building is not found from this one", async () => {
    expect(await read(job("b1"), BUILDING.a1)).toBeNull();
  });

  test("which is there, from the building it is in", async () => {
    // The positive control: without it the test above would also pass on an empty table.
    expect((await read(job("b1"), BUILDING.b1))?.workOrderId).toBe(
      job("b1").workOrderId,
    );
  });

  test("one whose ticket names no building is in no building", async () => {
    expect(
      await port.getWorkOrder({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        workOrderId: WORK_ORDER.vinhomes,
      }),
    ).toBeNull();
  });

  test("one that does not exist is not found", async () => {
    expect(
      await port.getWorkOrder({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        workOrderId: "54000000-0000-4000-8000-000000000099",
      }),
    ).toBeNull();
  });

  test("another tenant asking for this tenant's work order finds nothing", async () => {
    expect(await read(job("ac"), BUILDING.a1, TENANT.other)).toBeNull();
  });
});

describe("what an id offered as evidence turns out to be", () => {
  const lookup = async (...ids: string[]) =>
    (await port.findEvidence({ tenantId: TENANT.vinhomes, ids })).sort((a, b) =>
      a.id.localeCompare(b.id),
    );

  test("a registered photo, with its ticket, job, purpose and state", async () => {
    const [after] = await lookup(EVIDENCE.acAfter.evidenceId);
    expect(after).toEqual({
      kind: "evidence",
      id: EVIDENCE.acAfter.evidenceId,
      ticketId: job("ac").ticketId,
      workOrderId: job("ac").workOrderId,
      assignmentId: job("ac").assignmentId,
      purpose: "after",
      status: "active",
      fileStatus: "ready",
    });
  });

  test("a withdrawn photo is found, and found withdrawn", async () => {
    const [withdrawn] = await lookup(EVIDENCE.acWithdrawn.evidenceId);
    expect(withdrawn).toMatchObject({ kind: "evidence", status: "withdrawn" });
  });

  test("a photo from another ticket is found, with that ticket", async () => {
    const [leak] = await lookup(EVIDENCE.leakBefore.evidenceId);
    expect(leak).toMatchObject({
      ticketId: job("leak").ticketId,
      purpose: "before",
    });
  });

  /*
   * The database will not register a file as evidence until it is ready, so a photo still
   * uploading exists only as a file. Reporting it as unknown would tell the agent it made the id
   * up; telling it apart says to wait.
   */
  test("an upload still staged is told apart from an id that names nothing", async () => {
    const [staged] = await lookup(STAGED_UPLOAD.fileId);
    expect(staged).toEqual({
      kind: "file",
      id: STAGED_UPLOAD.fileId,
      ticketId: job("breaker").ticketId,
      fileStatus: "staged",
    });
  });

  test("a photo's file id is not its evidence id, and is reported as the file it is", async () => {
    // The evidence row and its file have different ids; only the one asked for comes back.
    const found = await lookup(EVIDENCE.acAfter.fileId);
    expect(found).toEqual([
      expect.objectContaining({ kind: "file", fileStatus: "ready" }),
    ]);
  });

  test("ids that name nothing, or are not ids at all, are simply absent", async () => {
    expect(
      await lookup("56000000-0000-4000-8000-000000000099", "EV-22", ""),
    ).toEqual([]);
  });

  test("asking twice for one id answers once", async () => {
    expect(
      await lookup(EVIDENCE.acBefore.evidenceId, EVIDENCE.acBefore.evidenceId),
    ).toHaveLength(1);
  });

  test("everything asked for in one call comes back in one answer", async () => {
    const found = await lookup(
      EVIDENCE.acBefore.evidenceId,
      EVIDENCE.acAfter.evidenceId,
      STAGED_UPLOAD.fileId,
    );
    expect(found.map((item) => item.kind).sort()).toEqual([
      "evidence",
      "evidence",
      "file",
    ]);
  });

  test("another tenant asking for these ids finds none of them", async () => {
    expect(
      await port.findEvidence({
        tenantId: TENANT.other,
        ids: [EVIDENCE.acAfter.evidenceId, STAGED_UPLOAD.fileId],
      }),
    ).toEqual([]);
  });
});

/*
 * Tenant isolation that does not depend on the adapter remembering its `tenant_id` filter: these
 * queries have none, and what comes back is decided by the policies on the tables alone.
 */
describe("row-level security, with the tenant filter left out", () => {
  const visible = (tenantId: string | null) =>
    db.database.transaction(async (tx) => {
      if (tenantId) {
        await tx.execute(
          sql`select set_config('app.tenant_id', ${tenantId}, true)`,
        );
      }
      const orders = await tx.select({ id: workOrders.id }).from(workOrders);
      const evidence = await tx
        .select({ id: evidenceItems.id })
        .from(evidenceItems);
      return {
        orders: orders.map((row) => row.id).sort(),
        evidence: evidence.length,
      };
    });

  test("this tenant sees its six work orders and six photos", async () => {
    const seen = await visible(TENANT.vinhomes);
    expect(seen.orders).toHaveLength(6);
    expect(seen.orders).toContain(job("ac").workOrderId);
    expect(seen.evidence).toBe(6);
  });

  test("the other tenant sees only its own work order and none of the photos", async () => {
    expect(await visible(TENANT.other)).toEqual({
      orders: [WORK_ORDER.other],
      evidence: 0,
    });
  });

  test("a query that never says which tenant it is for sees nothing", async () => {
    expect(await visible(null)).toEqual({ orders: [], evidence: 0 });
  });
});

describe("what the role the tools run as cannot do", () => {
  test.each([
    ["close a work order", sql`update work_orders set status = 'completed'`],
    ["withdraw a photo", sql`update evidence_items set status = 'withdrawn'`],
    ["delete an assignment", sql`delete from work_assignments`],
    ["read the storage objects behind a file", sql`select 1 from file_objects`],
  ])("%s", async (_label, statement) => {
    const failure: { cause?: unknown } | null = await Promise.resolve(
      db.database.execute(statement),
    ).then(
      () => null,
      (error) => error,
    );
    expect(String(failure?.cause)).toMatch(/permission denied/);
  });

  test("and every job is still as it was seeded afterwards", async () => {
    for (const work of Object.values(WORK)) {
      const found = await read(work);
      expect(found?.status).toBe("in_progress");
      expect(found?.assignments[0]?.status).toBe(work.assignmentStatus);
    }
  });
});
