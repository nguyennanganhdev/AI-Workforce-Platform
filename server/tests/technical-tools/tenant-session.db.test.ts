import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  createDbInterruptionReadPort,
  createDbScopeReadPort,
  createDbSopReadPort,
  createDbUnitReadPort,
  createDbWorkOrderReadPort,
  type TenantSession,
  tenantSessionFrom,
} from "../../src/technical-tools";
import { UNIT } from "./fixtures/units";
import { WORK, type WorkFixture } from "./fixtures/work-orders";
import { BUILDING, TENANT } from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";

/**
 * The database adapters run inside a tenant session the backend supplies (the
 * `TenantReadSessionPort` idea from dev_TeamQuang, 17e5826), rather than opening transactions of
 * their own. These tests hand them a session that records every call, and show that every query
 * goes through it, under the tenant asked for, and that a session which refuses stops the query.
 */
let db: TestDatabase;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

function recordingSession() {
  const inner = tenantSessionFrom(db.database);
  const calls: { mode: "read" | "write"; tenantId: string }[] = [];
  const session: TenantSession = {
    kind: "tenant-session",
    read: (tenantId, work) => {
      calls.push({ mode: "read", tenantId });
      return inner.read(tenantId, work);
    },
    write: (tenantId, work) => {
      calls.push({ mode: "write", tenantId });
      return inner.write(tenantId, work);
    },
  };
  return { session, calls };
}

const leak = WORK.leak as WorkFixture;

describe("a session the backend supplies", () => {
  test("carries every read of every adapter, under the tenant asked for", async () => {
    const { session, calls } = recordingSession();
    const tenantId = TENANT.vinhomes;

    await createDbWorkOrderReadPort(session).getWorkOrder({
      tenantId,
      buildingId: BUILDING.a1,
      workOrderId: leak.workOrderId,
    });
    await createDbUnitReadPort(session).findUnit({
      tenantId,
      unitId: UNIT.a1_1305,
    });
    await createDbScopeReadPort(session).placement({
      tenantId,
      buildingId: BUILDING.a1,
    });
    await createDbSopReadPort(session).listForBuilding({
      tenantId,
      buildingId: BUILDING.a1,
    });
    await createDbInterruptionReadPort(session).listCovering({
      tenantId,
      buildingId: BUILDING.a1,
      utility: "water",
      window: {
        from: new Date("2026-09-30T00:00:00Z"),
        to: new Date("2026-10-01T00:00:00Z"),
      },
    });

    expect(calls).toHaveLength(5);
    expect(calls.every((call) => call.mode === "read")).toBe(true);
    expect(calls.every((call) => call.tenantId === tenantId)).toBe(true);
  });

  test("gives the same answers as a database handed in directly", async () => {
    const { session } = recordingSession();
    const query = {
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      workOrderId: leak.workOrderId,
    };
    expect(
      await createDbWorkOrderReadPort(session).getWorkOrder(query),
    ).toEqual(await createDbWorkOrderReadPort(db.database).getWorkOrder(query));
  });

  test("a session that refuses stops the query: an adapter has no way round it", async () => {
    const refusing: TenantSession = {
      kind: "tenant-session",
      read: () => Promise.reject(new Error("no session for this caller")),
      write: () => Promise.reject(new Error("no session for this caller")),
    };
    const failure = await createDbWorkOrderReadPort(refusing)
      .getWorkOrder({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        workOrderId: leak.workOrderId,
      })
      .then(
        () => null,
        (error: Error) => error.message,
      );
    expect(failure).toBe("no session for this caller");
  });
});
