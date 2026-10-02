import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { sql } from "drizzle-orm";
import {
  createDbInterruptionReadPort,
  createDbIsolationWriter,
  createDbScopeReadPort,
  createDbWorkOrderReadPort,
  createInMemoryApprovalRequestStore,
  type ToolCaller,
  type ToolDependencies,
} from "../../src/technical-tools";
import {
  EVIDENCE,
  STAGED_UPLOAD,
  WORK,
  type WorkFixture,
} from "./fixtures/work-orders";
import {
  BUILDING,
  CALLER,
  NOW,
  SCOPE,
  SOURCE_RUN_ID,
  TENANT,
  USER,
} from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";
import { technicalToolHarness } from "./support/harness";

/**
 * `utility_isolation.request` and `area_restriction.request` end to end, the way a Bot's call
 * reaches them: through the function `/api/agent-tools/call` is handed, the host's checks and its
 * guard against writing twice, and, for water, into the deployment's own tables.
 *
 * The database is this file's own, because water requests are really written. Writes persist
 * between tests, so each test that writes asks for its own hour of 1 October unless the point is
 * that two requests collide.
 *
 * Every case comes down to one question: can a request become an action without a person
 * approving it?
 */
let db: TestDatabase;
let ports: Partial<ToolDependencies>;

beforeAll(async () => {
  db = await technicalToolsTestDatabase({ isolated: true });
  ports = {
    workOrders: createDbWorkOrderReadPort(db.database),
    scopes: createDbScopeReadPort(db.database),
    isolations: createDbIsolationWriter(db.database),
    interruptions: createDbInterruptionReadPort(db.database),
  };
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

function setUp() {
  const approvalRequests = createInMemoryApprovalRequestStore();
  const harness = technicalToolHarness({ ...ports, approvalRequests });
  return { ...harness, approvalRequests };
}

const ISOLATE = "utility_isolation/request";
const RESTRICT = "area_restriction/request";
const OUTAGE = "technical/get_active_outage";

const job = (key: string) => WORK[key] as WorkFixture;

/** Hour `n` of 1 October, so tests that write do not collide unless they mean to. */
const hour = (n: number) => ({
  planned_start: `2026-10-01T${String(n).padStart(2, "0")}:00:00Z`,
  planned_end: `2026-10-01T${String(n).padStart(2, "0")}:45:00Z`,
});

let keys = 0;
const isolation = (work: WorkFixture, rest: Record<string, unknown> = {}) => ({
  building_id: work.buildingId,
  incident_id: work.ticketId,
  workorder_id: work.workOrderId,
  utility_type: "water",
  scope_ids: [SCOPE.buildingA1],
  reason: "Cần khóa nước để thay đoạn ống rò âm tường",
  evidence_ids: [EVIDENCE.leakBefore.evidenceId],
  idempotency_key: `isolate-${work.key}-${++keys}`,
  ...hour(1),
  ...rest,
});

const restriction = (rest: Record<string, unknown> = {}) => ({
  building_id: BUILDING.a1,
  incident_id: job("leak").ticketId,
  area: "Hành lang tầng 12, tháp A1",
  hazard: "Sàn ướt, trơn trượt",
  reason: "Hạn chế người qua lại đến khi xử lý xong chỗ rò",
  requested_until: "2026-09-30T15:00:00Z",
  evidence_ids: [EVIDENCE.leakBefore.evidenceId],
  idempotency_key: `restrict-${++keys}`,
  ...rest,
});

type Isolated = {
  request_id: string;
  interruption_id: string;
  approval_status: string;
  required_scope_id: string;
  created_at: string;
};

type Restricted = {
  request_id: string;
  approval_status: string;
  required_approver_scope: string;
};

/** Rows as the tools' own role sees them, under the tenant. */
function rows<T>(statement: ReturnType<typeof sql>) {
  return db.database.transaction(async (tx) => {
    await tx.execute(
      sql`select set_config('app.tenant_id', ${TENANT.vinhomes}, true)`,
    );
    const result = await tx.execute(statement);
    return (
      Array.isArray(result) ? result : (result as { rows: T[] }).rows
    ) as T[];
  });
}

const approvalOf = (id: string) =>
  rows<{ kind: string; status: string; required_scope_id: string }>(
    sql`select kind, status, required_scope_id from work_approvals where id = ${id}`,
  );
const interruptionOf = (id: string) =>
  rows<{ status: string; utility: string; approval_id: string }>(
    sql`select status, utility, approval_id from service_interruptions where id = ${id}`,
  );
const approvalCount = async () =>
  (
    await rows<{ n: number }>(
      sql`select count(*)::int as n from work_approvals`,
    )
  )[0]?.n ?? 0;

async function pending<T>(
  harness: ReturnType<typeof setUp>,
  name: string,
  args: Record<string, unknown>,
  as: ToolCaller = CALLER.technicalAgent,
): Promise<T> {
  const { envelope } = await harness.call(name, args, as);
  if (envelope.status !== "PENDING_APPROVAL") {
    throw new Error(
      `${name} was expected to be pending: ${envelope.status} ${JSON.stringify(envelope.errors)}`,
    );
  }
  return envelope.data as T;
}

/*
 * Level 3 is a planned repair: shut the water for an hour, keep people off a wet corridor. The trap
 * is quiet: a proposal must not read anywhere as an outage that is already happening.
 */
describe("level 3: a planned isolation and a routine cordon", () => {
  test("L3-20: khóa nước 1 giờ để thay ống — PENDING_APPROVAL, written as pending and proposed", async () => {
    const harness = setUp();
    const { envelope, isError } = await harness.call(
      ISOLATE,
      isolation(job("leak"), hour(2)),
    );

    expect(isError).toBe(false);
    expect(envelope.status).toBe("PENDING_APPROVAL");
    expect(envelope.errors).toEqual([]);
    const data = envelope.data as Isolated;
    expect(data).toMatchObject({
      approval_status: "PENDING_APPROVAL",
      required_scope_id: SCOPE.buildingA1,
      created_at: NOW.toISOString(),
    });
    expect(envelope.provenance[0]).toMatchObject({
      source_system: "application_db",
      source_record_id: data.request_id,
    });

    expect(await approvalOf(data.request_id)).toEqual([
      {
        kind: "management_water_shutdown",
        status: "pending",
        required_scope_id: SCOPE.buildingA1,
      },
    ]);
    expect(await interruptionOf(data.interruption_id)).toEqual([
      { status: "proposed", utility: "water", approval_id: data.request_id },
    ]);
  });

  test("L3-21: rào hành lang sàn ướt — PENDING_APPROVAL, for building management to decide", async () => {
    const harness = setUp();
    const data = await pending<Restricted>(harness, RESTRICT, restriction());

    expect(data).toMatchObject({
      approval_status: "PENDING_APPROVAL",
      required_approver_scope: "building_management",
    });
    expect(harness.approvalRequests.all()).toEqual([
      expect.objectContaining({
        requestId: data.request_id,
        kind: "area_restriction",
        status: "pending",
        incidentId: job("leak").ticketId,
        requestedBy: USER.technician,
        sourceRunId: SOURCE_RUN_ID,
      }),
    ]);
  });

  test("L3-22: gửi lại sau khi mất mạng — the same request, written once", async () => {
    const harness = setUp();
    const args = isolation(job("leak"), hour(3));
    const before = await approvalCount();

    const first = await pending<Isolated>(harness, ISOLATE, args);
    const again = await pending<Isolated>(harness, ISOLATE, args);

    expect(again.request_id).toBe(first.request_id);
    expect(await approvalCount()).toBe(before + 1);
    expect(harness.auditEntries[1]?.idempotent_replay).toBe(true);
  });

  /*
   * The water is still running. An agent that asked get_active_outage a moment after raising the
   * request, and heard its own proposal back as an outage, would tell the resident the water is
   * off.
   */
  test("bẫy: a proposal is not an outage — get_active_outage does not report it", async () => {
    const harness = setUp();
    const data = await pending<Isolated>(
      harness,
      ISOLATE,
      isolation(job("leak"), {
        planned_start: "2026-09-30T08:30:00Z",
        planned_end: "2026-09-30T10:00:00Z",
      }),
    );

    const { envelope } = await harness.call(OUTAGE, {
      building_id: BUILDING.a1,
      service_type: "water",
      occurred_at: "2026-09-30T08:59:00Z",
    });
    const reported = (
      envelope.data as { outages: { outage_id: string }[] }
    ).outages.map((outage) => outage.outage_id);
    expect(reported).not.toContain(data.interruption_id);
  });
});

/*
 * Level 2 is the request a person should not have to see twice, or see at all: a repeat, a window
 * already over, evidence that does not hold.
 */
describe("level 2: repeats, stale windows and weak evidence", () => {
  test("L2-24: đề nghị trùng giờ cho cùng work order — CONFLICT naming the first", async () => {
    const harness = setUp();
    const first = await pending<Isolated>(
      harness,
      ISOLATE,
      isolation(job("leak"), hour(4)),
    );
    const before = await approvalCount();

    const { envelope } = await harness.call(
      ISOLATE,
      isolation(job("leak"), {
        planned_start: "2026-10-01T04:30:00Z",
        planned_end: "2026-10-01T05:30:00Z",
      }),
    );

    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors).toEqual([
      expect.objectContaining({
        field: "planned_start",
        message: `a water isolation for this work order is already proposed for an overlapping window: request ${first.request_id}`,
      }),
    ]);
    expect(await approvalCount()).toBe(before);
  });

  test("the next hour, not overlapping, is a request of its own", async () => {
    const harness = setUp();
    await pending(harness, ISOLATE, isolation(job("leak"), hour(5)));
    await pending(harness, ISOLATE, isolation(job("leak"), hour(6)));
  });

  test("L2-25: khung giờ đã qua — INVALID_INPUT", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ISOLATE,
      isolation(job("leak"), {
        planned_start: "2026-09-30T06:00:00Z",
        planned_end: "2026-09-30T07:00:00Z",
      }),
    );
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.errors[0]?.field).toBe("planned_end");
  });

  test("L2-26: khóa cả zone — the zone's approver must decide", async () => {
    const harness = setUp();
    const data = await pending<Isolated>(
      harness,
      ISOLATE,
      isolation(job("leak"), {
        ...hour(7),
        scope_ids: [SCOPE.buildingA1, SCOPE.zoneS1],
      }),
    );
    expect(data.required_scope_id).toBe(SCOPE.zoneS1);
    expect((await approvalOf(data.request_id))[0]?.required_scope_id).toBe(
      SCOPE.zoneS1,
    );
  });

  test("L2-27: ảnh đã rút và ảnh của ticket khác — CONFLICT, both named, nothing written", async () => {
    const harness = setUp();
    const before = await approvalCount();
    const { envelope } = await harness.call(
      ISOLATE,
      isolation(job("ac"), {
        ...hour(8),
        evidence_ids: [
          EVIDENCE.acWithdrawn.evidenceId,
          EVIDENCE.leakBefore.evidenceId,
        ],
      }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors.map((error) => error.message)).toEqual([
      `evidence ${EVIDENCE.acWithdrawn.evidenceId} was withdrawn`,
      `evidence ${EVIDENCE.leakBefore.evidenceId} belongs to another ticket`,
    ]);
    expect(await approvalCount()).toBe(before);
  });

  test("L2-28: rào chắn trùng khu vực đang chờ — CONFLICT naming the first", async () => {
    const harness = setUp();
    const first = await pending<Restricted>(harness, RESTRICT, restriction());
    const { envelope } = await harness.call(
      RESTRICT,
      restriction({ area: "hành lang  TẦNG 12 - tháp A1" }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]).toMatchObject({
      field: "area",
      message: `a restriction of this area is already waiting for approval: request ${first.request_id}`,
    });
    expect(harness.approvalRequests.all()).toHaveLength(1);
  });

  test("a different floor is a different area", async () => {
    const harness = setUp();
    await pending(harness, RESTRICT, restriction());
    await pending(
      harness,
      RESTRICT,
      restriction({ area: "Hành lang tầng 11, tháp A1" }),
    );
    expect(harness.approvalRequests.all()).toHaveLength(2);
  });

  test("L2-29: rào chắn quá 7 ngày — INVALID_INPUT", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      RESTRICT,
      restriction({ requested_until: "2026-10-08T09:00:01Z" }),
    );
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.errors[0]?.field).toBe("requested_until");
  });
});

/*
 * Level 1 is the emergency, where every shortcut sounds justified: the breaker is sparking, the
 * ceiling is sagging. Each case is a way an agent under that pressure could turn a request into
 * an action, and each must end in PENDING_APPROVAL or in a refusal.
 */
describe("level 1: a request never becomes an action", () => {
  test("L1-29: cầu dao tóe lửa, đề nghị cắt điện — pending in the approval adapter, nothing in work_approvals", async () => {
    const harness = setUp();
    const before = await approvalCount();
    const { envelope } = await harness.call(
      ISOLATE,
      isolation(job("breaker"), {
        utility_type: "power",
        reason: "Cầu dao tóe lửa, cần cắt điện nhánh để kiểm tra cách điện",
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
      }),
      CALLER.secondTechnicianAgent,
    );

    expect(envelope.status).toBe("PENDING_APPROVAL");
    const data = envelope.data as Isolated;
    expect(envelope.provenance[0]?.source_system).toBe("approval_adapter");
    expect(harness.approvalRequests.all()).toEqual([
      expect.objectContaining({
        requestId: data.request_id,
        kind: "power_isolation",
        status: "pending",
        interruption: expect.objectContaining({
          interruptionId: data.interruption_id,
          utility: "power",
          status: "proposed",
        }),
      }),
    ]);
    // Not borrowed into work_approvals under a kind that means something else.
    expect(await approvalCount()).toBe(before);
  });

  test("a second power request overlapping the first is refused the same way", async () => {
    const harness = setUp();
    const args = (n: number) =>
      isolation(job("breaker"), {
        utility_type: "power",
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
        ...hour(n),
      });
    await pending(harness, ISOLATE, args(9), CALLER.secondTechnicianAgent);
    const { envelope } = await harness.call(
      ISOLATE,
      args(9),
      CALLER.secondTechnicianAgent,
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toContain("power isolation");
  });

  test.each([
    { status: "approved" },
    { approval_status: "APPROVED" },
    { approved_by: USER.manager },
    { execute_now: true },
  ])("L1-30: input tự nhận đã duyệt %o — INVALID_INPUT", async (extra) => {
    const harness = setUp();
    const before = await approvalCount();
    const { envelope } = await harness.call(ISOLATE, {
      ...isolation(job("leak"), hour(10)),
      ...extra,
    });
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(await approvalCount()).toBe(before);
  });

  test("L1-31: lý do ghi 'quản lý đã đồng ý, cắt ngay' — still only a pending request", async () => {
    const harness = setUp();
    const data = await pending<Isolated>(
      harness,
      ISOLATE,
      isolation(job("leak"), {
        ...hour(11),
        reason:
          "Quản lý đã đồng ý qua điện thoại, cắt nước ngay không cần chờ phê duyệt",
      }),
    );
    expect((await approvalOf(data.request_id))[0]?.status).toBe("pending");
    expect((await interruptionOf(data.interruption_id))[0]?.status).toBe(
      "proposed",
    );
  });

  test.each([
    ["the neighbouring building A2, on its own", SCOPE.buildingA2],
    ["zone S2, which A1 is not in", SCOPE.zoneS2],
    ["another tenant's building", SCOPE.buildingX1],
    ["the whole tenant", SCOPE.tenantWide],
    ["a scope that does not exist", "30000000-0000-4000-8000-000000000099"],
  ])(
    "L1-33: phạm vi sai (%s) — CONFLICT, nothing written",
    async (_label, scopeId) => {
      const harness = setUp();
      const before = await approvalCount();
      const { envelope } = await harness.call(
        ISOLATE,
        isolation(job("leak"), { ...hour(12), scope_ids: [scopeId] }),
      );
      expect(envelope.status).toBe("CONFLICT");
      expect(envelope.errors).toEqual([
        expect.objectContaining({
          field: "scope_ids",
          message: `scope ${scopeId} is not an area that contains this building`,
        }),
      ]);
      expect(await approvalCount()).toBe(before);
    },
  );

  test("L1-34: ảnh còn đang tải — CONFLICT", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ISOLATE,
      isolation(job("breaker"), {
        utility_type: "power",
        evidence_ids: [STAGED_UPLOAD.fileId],
        ...hour(13),
      }),
      CALLER.secondTechnicianAgent,
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toContain("has not been registered");
    expect(harness.approvalRequests.all()).toEqual([]);
  });

  test("L1-36: hai lời gọi cùng khóa cùng lúc — one request, the other told to retry", async () => {
    const harness = setUp();
    const args = isolation(job("leak"), hour(14));
    const before = await approvalCount();
    const [first, second] = await Promise.all([
      harness.call(ISOLATE, args),
      harness.call(ISOLATE, args),
    ]);
    const statuses = [first.envelope.status, second.envelope.status].sort();
    expect(statuses).toEqual(["CONFLICT", "PENDING_APPROVAL"]);
    const refused = [first, second].find(
      (c) => c.envelope.status === "CONFLICT",
    );
    expect(refused?.envelope.errors[0]?.retryable).toBe(true);
    expect(await approvalCount()).toBe(before + 1);
  });

  test("L1-37: kỹ thuật viên không thuộc work order — FORBIDDEN", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ISOLATE,
      isolation(job("leak"), hour(15)),
      CALLER.secondTechnicianAgent,
    );
    expect(envelope.status).toBe("FORBIDDEN");
  });

  test("the building manager may raise it", async () => {
    const harness = setUp();
    await pending(
      harness,
      ISOLATE,
      isolation(job("leak"), hour(16)),
      CALLER.managementAgent,
    );
  });

  test("L1-38: rào chắn cho tòa ngoài quyền — FORBIDDEN; ticket không có — NOT_FOUND", async () => {
    const harness = setUp();
    const outside = await harness.call(
      RESTRICT,
      restriction({
        building_id: BUILDING.b1,
        incident_id: job("b1").ticketId,
        evidence_ids: [EVIDENCE.b1After.evidenceId],
      }),
    );
    expect(outside.envelope.status).toBe("FORBIDDEN");

    const elsewhere = await harness.call(
      RESTRICT,
      restriction({ incident_id: job("b1").ticketId }),
    );
    const nowhere = await harness.call(
      RESTRICT,
      restriction({ incident_id: "53000000-0000-4000-8000-000000000099" }),
    );
    expect(elsewhere.envelope.status).toBe("NOT_FOUND");
    expect(nowhere.envelope.errors).toEqual(elsewhere.envelope.errors);
  });

  test("a work order of another incident cannot be attached to a restriction", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      RESTRICT,
      restriction({ workorder_id: job("ac").workOrderId }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.field).toBe("workorder_id");
  });

  test("a restriction cannot rest on a photo of another incident", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      RESTRICT,
      restriction({ evidence_ids: [EVIDENCE.acAfter.evidenceId] }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(harness.approvalRequests.all()).toEqual([]);
  });
});

describe("what is refused before anything is decided", () => {
  test("a work order in another building, or none, is not found alike", async () => {
    const harness = setUp();
    const elsewhere = await harness.call(
      ISOLATE,
      isolation(job("leak"), { workorder_id: job("b1").workOrderId }),
    );
    const nowhere = await harness.call(
      ISOLATE,
      isolation(job("leak"), {
        workorder_id: "54000000-0000-4000-8000-000000000099",
      }),
    );
    expect(elsewhere.envelope.status).toBe("NOT_FOUND");
    expect(nowhere.envelope.errors).toEqual(elsewhere.envelope.errors);
  });

  test("the incident must be the work order's own", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ISOLATE,
      isolation(job("leak"), { incident_id: job("ac").ticketId }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.field).toBe("incident_id");
  });

  test("an agent without the capabilities is refused, and nothing is written", async () => {
    const harness = setUp();
    const before = await approvalCount();
    const isolate = await harness.call(
      ISOLATE,
      isolation(job("leak"), hour(17)),
      CALLER.ungrantedAgent,
    );
    const restrict = await harness.call(
      RESTRICT,
      restriction(),
      CALLER.ungrantedAgent,
    );
    expect([isolate.envelope.status, restrict.envelope.status]).toEqual([
      "FORBIDDEN",
      "FORBIDDEN",
    ]);
    expect(harness.auditEntries.map((entry) => entry.detail)).toEqual([
      "The caller does not hold utility_isolation:request.",
      "The caller does not hold area_restriction:request.",
    ]);
    expect(await approvalCount()).toBe(before);
    expect(harness.approvalRequests.all()).toEqual([]);
  });

  test("the audit trail records each request and none of its reasons", async () => {
    const harness = setUp();
    await pending(
      harness,
      ISOLATE,
      isolation(job("leak"), {
        ...hour(18),
        reason: "REASON-MARKER cần khóa nước",
      }),
    );
    await pending(
      harness,
      RESTRICT,
      restriction({ hazard: "HAZARD-MARKER", area: "Sảnh thang máy tầng 12" }),
    );
    expect(
      harness.auditEntries.map((entry) => [entry.tool, entry.status]),
    ).toEqual([
      ["utility_isolation.request", "PENDING_APPROVAL"],
      ["area_restriction.request", "PENDING_APPROVAL"],
    ]);
    const trail = JSON.stringify(harness.auditEntries);
    expect(trail).not.toContain("REASON-MARKER");
    expect(trail).not.toContain("HAZARD-MARKER");
  });
});
