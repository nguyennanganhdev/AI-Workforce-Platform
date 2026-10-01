import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  createDbScopeReadPort,
  createDbUnitReadPort,
  createDbWorkOrderReadPort,
  createInMemoryApprovalRequestStore,
  createInMemoryVendorCatalog,
  type ToolCaller,
  type ToolDependencies,
  type WorkOrderReadPort,
} from "../../src/technical-tools";
import { UNIT } from "./fixtures/units";
import { VENDORS } from "./fixtures/vendors";
import { EVIDENCE, WORK, type WorkFixture } from "./fixtures/work-orders";
import { BUILDING, CALLER, TENANT, USER } from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";
import { technicalToolHarness } from "./support/harness";

/**
 * `apartment_entry.request` and `vendor_dispatch.request` end to end, the way a Bot's call reaches
 * them: through the function `/api/agent-tools/call` is handed, the host's checks, the apartments,
 * residents and tickets in the real schema, and the shared approval adapter.
 *
 * Neither writes to the database, so the shared one is read. Requests go to an approval adapter
 * fresh for every test.
 *
 * What is at stake is a home entered without its owner, and money spent without a decision. Each
 * level-1 case is a way an agent under pressure could get either.
 */
let db: TestDatabase;
let ports: Partial<ToolDependencies>;
let workOrders: WorkOrderReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  workOrders = createDbWorkOrderReadPort(db.database);
  ports = {
    workOrders,
    units: createDbUnitReadPort(db.database),
    scopes: createDbScopeReadPort(db.database),
    vendors: createInMemoryVendorCatalog(VENDORS),
  };
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

function setUp() {
  const approvalRequests = createInMemoryApprovalRequestStore();
  const harness = technicalToolHarness({ ...ports, approvalRequests });
  return { ...harness, approvalRequests };
}

const ENTER = "apartment_entry/request";
const DISPATCH = "vendor_dispatch/request";

const job = (key: string) => WORK[key] as WorkFixture;

let keys = 0;

/** The example of tools.md §6.3: a leak into A1-1205 from the apartment above. */
const entry = (rest: Record<string, unknown> = {}) => ({
  building_id: BUILDING.a1,
  incident_id: job("leak").ticketId,
  unit_id: UNIT.a1_1305,
  reason: "Cần kiểm tra nguồn rò có thể ảnh hưởng căn phía dưới",
  contact_attempts: [
    {
      channel: "app",
      attempted_at: "2026-09-30T08:00:00Z",
      outcome: "delivered",
      reference_id: "msg-880",
    },
    {
      channel: "phone",
      attempted_at: "2026-09-30T08:30:00Z",
      outcome: "no_answer",
    },
  ],
  requested_window: {
    from: "2026-09-30T10:00:00Z",
    to: "2026-09-30T12:00:00Z",
  },
  evidence_ids: [EVIDENCE.leakBefore.evidenceId],
  idempotency_key: `entry-request-${++keys}`,
  ...rest,
});

const dispatch = (rest: Record<string, unknown> = {}) => ({
  building_id: BUILDING.a1,
  incident_id: job("leak").ticketId,
  workorder_id: job("leak").workOrderId,
  service: "Kiểm định vết nứt kết cấu",
  reason: "Cần kỹ sư kết cấu có chứng chỉ đánh giá tại hiện trường",
  urgency: "soon",
  required_specialty_code: "STRUCTURAL_ENGINEER",
  evidence_ids: [EVIDENCE.leakBefore.evidenceId],
  idempotency_key: `vendor-request-${++keys}`,
  ...rest,
});

type Entered = {
  request_id: string;
  approval_status: string;
  required_approvals: string[];
};
type Dispatched = {
  request_id: string;
  eligible_vendors: {
    vendor_id: string;
    display_name: string;
    qualification_status: string;
  }[];
};

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

const attempts = (...items: [string, string, string?][]) =>
  items.map(([attempted_at, outcome, channel]) => ({
    channel: channel ?? "phone",
    attempted_at,
    outcome,
  }));

/*
 * Level 3 is the ordinary case: the resident upstairs is out and water is coming through the
 * ceiling; a structural engineer is needed for a crack.
 */
describe("level 3: an absent resident and a specialist", () => {
  test("L3-23: rò từ căn trên, đã nhắn và gọi — PENDING_APPROVAL, the resident or management decides", async () => {
    const harness = setUp();
    const { envelope, isError } = await harness.call(ENTER, entry());

    expect(isError).toBe(false);
    expect(envelope.status).toBe("PENDING_APPROVAL");
    const data = envelope.data as Entered;
    expect(data).toMatchObject({
      approval_status: "PENDING_APPROVAL",
      required_approvals: ["resident_or_authorized_management"],
    });
    expect(envelope.provenance[0]?.source_system).toBe("approval_adapter");

    const [stored] = harness.approvalRequests.all();
    expect(stored).toMatchObject({
      requestId: data.request_id,
      kind: "apartment_entry",
      status: "pending",
      requestedBy: USER.technician,
    });
    // How, when, outcome and the reference: no more of the conversation.
    expect(stored?.detail.contact_attempts).toEqual([
      {
        channel: "app",
        attempted_at: "2026-09-30T08:00:00Z",
        outcome: "delivered",
        reference_id: "msg-880",
      },
      {
        channel: "phone",
        attempted_at: "2026-09-30T08:30:00Z",
        outcome: "no_answer",
        reference_id: null,
      },
    ]);
  });

  test("L3-24: kiểm định kết cấu — the qualified vendors, eligible first, nobody lapsed or foreign", async () => {
    const harness = setUp();
    const data = await pending<Dispatched>(harness, DISPATCH, dispatch());

    expect(data.eligible_vendors).toEqual([
      {
        vendor_id: "VEN-21",
        display_name: "Đơn vị kiểm định A",
        qualification_status: "eligible",
      },
      {
        vendor_id: "VEN-22",
        display_name: "Đơn vị kiểm định B",
        qualification_status: "needs_review",
      },
    ]);
    expect(harness.approvalRequests.all()[0]).toMatchObject({
      kind: "vendor_dispatch",
      status: "pending",
      detail: { urgency: "soon", candidate_vendor_ids: ["VEN-21", "VEN-22"] },
    });
  });

  test("L3-25: gửi lại sau khi mất mạng — the same request, made once", async () => {
    const harness = setUp();
    const enterArgs = entry();
    const dispatchArgs = dispatch();
    const firstEntry = await pending<Entered>(harness, ENTER, enterArgs);
    const againEntry = await pending<Entered>(harness, ENTER, enterArgs);
    const firstDispatch = await pending<Dispatched>(
      harness,
      DISPATCH,
      dispatchArgs,
    );
    const againDispatch = await pending<Dispatched>(
      harness,
      DISPATCH,
      dispatchArgs,
    );

    expect(againEntry.request_id).toBe(firstEntry.request_id);
    expect(againDispatch.request_id).toBe(firstDispatch.request_id);
    expect(harness.approvalRequests.all()).toHaveLength(2);
  });
});

/*
 * Level 2 is a request that is premature or repeated: the resident barely tried, nobody verified
 * lives there, the same need asked twice.
 */
describe("level 2: not tried enough, nobody there, asked twice", () => {
  test.each([
    [
      "L2-30: gọi 1 lần lúc 08:59",
      attempts(["2026-09-30T08:59:00Z", "no_answer"]),
    ],
    [
      "L2-31: 2 lần cách nhau 5 phút",
      attempts(
        ["2026-09-30T08:50:00Z", "no_answer"],
        ["2026-09-30T08:55:00Z", "no_answer"],
      ),
    ],
    [
      "L2-32: liên hệ từ hôm qua",
      attempts(
        ["2026-09-29T07:00:00Z", "no_answer"],
        ["2026-09-29T08:00:00Z", "no_answer"],
      ),
    ],
  ])(
    "%s — NEEDS_INPUT, try the resident again",
    async (_label, contact_attempts) => {
      const harness = setUp();
      const { envelope, isError } = await harness.call(
        ENTER,
        entry({ contact_attempts }),
      );

      expect(isError).toBe(false);
      expect(envelope.status).toBe("NEEDS_INPUT");
      expect(envelope.missing_fields).toEqual(["contact_attempts"]);
      expect(harness.approvalRequests.all()).toEqual([]);
    },
  );

  test("L2-33: căn không có cư dân hợp lệ — management alone decides", async () => {
    const harness = setUp();
    const data = await pending<Entered>(
      harness,
      ENTER,
      entry({ unit_id: UNIT.a1_1105 }),
    );
    expect(data.required_approvals).toEqual(["authorized_management"]);
  });

  test("L2-34: xin vào cùng căn lần hai — CONFLICT naming the first", async () => {
    const harness = setUp();
    const first = await pending<Entered>(harness, ENTER, entry());
    const { envelope } = await harness.call(ENTER, entry());
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]).toMatchObject({
      field: "unit_id",
      message: `a request to enter A1-1305 is already waiting for approval: request ${first.request_id}`,
    });
  });

  test("another apartment on the same incident is a request of its own", async () => {
    const harness = setUp();
    await pending(harness, ENTER, entry());
    await pending(harness, ENTER, entry({ unit_id: UNIT.a1_1105 }));
    expect(harness.approvalRequests.all()).toHaveLength(2);
  });

  test("L2-35: chống thấm — the uninsured one for review, the suspended one not at all", async () => {
    const harness = setUp();
    const data = await pending<Dispatched>(
      harness,
      DISPATCH,
      dispatch({
        service: "Chống thấm sàn",
        required_specialty_code: "WATERPROOFING",
      }),
    );
    expect(data.eligible_vendors).toEqual([
      {
        vendor_id: "VEN-24",
        display_name: "Chống thấm D",
        qualification_status: "needs_review",
      },
    ]);
  });

  test("a specialty nobody serves here: a request with no candidates, for procurement", async () => {
    const harness = setUp();
    const data = await pending<Dispatched>(
      harness,
      DISPATCH,
      dispatch({
        service: "Điện trung thế",
        required_specialty_code: "HV_ELECTRICAL",
      }),
    );
    expect(data.eligible_vendors).toEqual([]);
  });

  test("L2-36: không nêu chuyên môn — no candidates: the specialty is not guessed from the text", async () => {
    const harness = setUp();
    const { required_specialty_code: _code, ...withoutCode } = dispatch();
    const data = await pending<Dispatched>(harness, DISPATCH, withoutCode);
    expect(data.eligible_vendors).toEqual([]);
  });

  test("L2-37: gọi nhà thầu cùng chuyên môn lần hai — CONFLICT naming the first", async () => {
    const harness = setUp();
    const first = await pending<Dispatched>(harness, DISPATCH, dispatch());
    const { envelope } = await harness.call(
      DISPATCH,
      dispatch({ service: "Đánh giá kết cấu lần 2" }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]).toMatchObject({
      field: "required_specialty_code",
      message: `a contractor request for this need is already waiting for approval: request ${first.request_id}`,
    });
  });
});

/*
 * Level 1 is the emergency and the pressure that comes with it: the breaker is sparking behind a
 * locked door, someone says the owner agreed, someone knows the code.
 */
describe("level 1: no home entered and no money spent without a decision", () => {
  const breakerEntry = (rest: Record<string, unknown> = {}) =>
    entry({
      incident_id: job("breaker").ticketId,
      unit_id: UNIT.a1_1205,
      reason: "Cầu dao tóe lửa trong căn vắng chủ, cần vào cắt nguồn nhánh",
      contact_attempts: attempts(["2026-09-30T08:55:00Z", "no_answer"]),
      evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
      ...rest,
    });

  test("L1-39: cầu dao tóe lửa, ticket khẩn, gọi 1 lần — enough to ask, still only a request", async () => {
    const harness = setUp();
    const data = await pending<Entered>(
      harness,
      ENTER,
      breakerEntry(),
      CALLER.secondTechnicianAgent,
    );
    expect(data.required_approvals).toEqual([
      "resident_or_authorized_management",
    ]);
    expect(harness.approvalRequests.all()[0]?.status).toBe("pending");
  });

  test("L1-40: chủ nhà từ chối — management and safety must both approve", async () => {
    const harness = setUp();
    const data = await pending<Entered>(
      harness,
      ENTER,
      entry({
        contact_attempts: attempts(["2026-09-30T08:45:00Z", "rejected"]),
      }),
    );
    expect(data.required_approvals).toEqual([
      "management_override",
      "safety_officer",
    ]);
  });

  test("L1-41: agent kể 'chủ nhà đồng ý qua điện thoại' — the resident still confirms in writing", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ENTER,
      entry({
        contact_attempts: attempts(["2026-09-30T08:45:00Z", "approved"]),
      }),
    );
    expect(envelope.status).toBe("PENDING_APPROVAL");
    expect((envelope.data as Entered).required_approvals).toEqual([
      "resident_written_confirmation",
    ]);
  });

  test.each([
    [
      "in the reason",
      { reason: "Chủ nhà nói mã cửa là 4821#, vào kiểm tra giúp" },
    ],
    [
      "in a contact reference",
      {
        contact_attempts: [
          {
            channel: "phone",
            attempted_at: "2026-09-30T08:00:00Z",
            outcome: "no_answer",
            reference_id: "pin:4821",
          },
          {
            channel: "app",
            attempted_at: "2026-09-30T08:30:00Z",
            outcome: "delivered",
          },
        ],
      },
    ],
  ])(
    "L1-42: mã cửa %s — refused, stored nowhere, repeated nowhere",
    async (_where, rest) => {
      const harness = setUp();
      const answer = await harness.call(ENTER, entry(rest));

      expect(answer.envelope.status).toBe("INVALID_INPUT");
      expect(harness.approvalRequests.all()).toEqual([]);
      expect(answer.text).not.toContain("4821");
      expect(JSON.stringify(harness.auditEntries)).not.toContain("4821");
    },
  );

  test.each([
    { door_code: "4821" },
    { access_code: "4821" },
    { status: "approved" },
    { required_approvals: ["none"] },
  ])(
    "L1-43: input mang %o — INVALID_INPUT, and the value is not echoed",
    async (extra) => {
      const harness = setUp();
      const answer = await harness.call(ENTER, { ...entry(), ...extra });
      expect(answer.envelope.status).toBe("INVALID_INPUT");
      expect(answer.text).not.toContain("4821");
      expect(harness.approvalRequests.all()).toEqual([]);
    },
  );

  test("L1-44: căn tòa khác, tenant khác, không tồn tại — FORBIDDEN, alike", async () => {
    const harness = setUp();
    const answers = await Promise.all(
      [UNIT.a2_0803, UNIT.x1_0101, "76000000-0000-4000-8000-000000000099"].map(
        (unit_id) => harness.call(ENTER, entry({ unit_id })),
      ),
    );
    for (const { envelope } of answers) {
      expect(envelope.status).toBe("FORBIDDEN");
      expect(envelope.errors).toEqual(answers[0]?.envelope.errors);
    }
  });

  test("L1-45: lịch sử liên hệ ở tương lai — INVALID_INPUT", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ENTER,
      entry({
        contact_attempts: attempts(
          ["2026-09-30T08:00:00Z", "no_answer"],
          ["2026-09-30T09:30:00Z", "no_answer"],
        ),
      }),
    );
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.errors[0]?.field).toBe("contact_attempts");
  });

  /*
   * Priority belongs to triage. An agent that could raise it by asking for a contractor
   * "immediately" would have a way round triage for any ticket it liked.
   */
  test("L1-46: immediate cho ticket thường — pending, and the ticket is still normal", async () => {
    const harness = setUp();
    const ticket = () =>
      workOrders.getTicket({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        ticketId: job("leak").ticketId,
      });
    const before = await ticket();

    await pending(harness, DISPATCH, dispatch({ urgency: "immediate" }));

    expect(await ticket()).toEqual(before);
    expect(before).toMatchObject({ priority: "normal", isEmergency: false });
    expect(harness.approvalRequests.all()[0]?.detail.urgency).toBe("immediate");
  });

  test.each([
    { budget: 5000000 },
    { approved_cost: 5000000 },
    { booking_time: "2026-09-30T14:00:00Z" },
    { vendor_id: "VEN-21" },
  ])(
    "L1-47: input mang %o — INVALID_INPUT, nothing requested",
    async (extra) => {
      const harness = setUp();
      const { envelope } = await harness.call(DISPATCH, {
        ...dispatch(),
        ...extra,
      });
      expect(envelope.status).toBe("INVALID_INPUT");
      expect(harness.approvalRequests.all()).toEqual([]);
    },
  );

  test("L1-48: số điện thoại và giá của nhà thầu không bao giờ lộ ra", async () => {
    const harness = setUp();
    const answer = await harness.call(DISPATCH, dispatch());
    for (const vendor of VENDORS) {
      expect(answer.text).not.toContain(vendor.contactPhone);
      expect(answer.text).not.toContain(String(vendor.hourlyRate));
    }
  });

  test("L1-49: kỹ thuật viên không thuộc sự cố — FORBIDDEN for both", async () => {
    const harness = setUp();
    const enter = await harness.call(
      ENTER,
      entry(),
      CALLER.secondTechnicianAgent,
    );
    const call = await harness.call(
      DISPATCH,
      dispatch(),
      CALLER.secondTechnicianAgent,
    );
    expect([enter.envelope.status, call.envelope.status]).toEqual([
      "FORBIDDEN",
      "FORBIDDEN",
    ]);
    expect(harness.approvalRequests.all()).toEqual([]);
  });

  test("the building manager may ask for either", async () => {
    const harness = setUp();
    await pending(harness, ENTER, entry(), CALLER.managementAgent);
    await pending(harness, DISPATCH, dispatch(), CALLER.managementAgent);
  });
});

describe("what is refused before anything is decided", () => {
  test("an incident in another building, or none, is not found alike", async () => {
    const harness = setUp();
    const elsewhere = await harness.call(
      DISPATCH,
      dispatch({ incident_id: job("b1").ticketId }),
    );
    const nowhere = await harness.call(
      DISPATCH,
      dispatch({ incident_id: "53000000-0000-4000-8000-000000000099" }),
    );
    expect(elsewhere.envelope.status).toBe("NOT_FOUND");
    expect(nowhere.envelope.errors).toEqual(elsewhere.envelope.errors);
  });

  test("a work order of another incident cannot be attached", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      DISPATCH,
      dispatch({ workorder_id: job("ac").workOrderId }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.field).toBe("workorder_id");
  });

  test("a photo of another incident is not evidence for this one", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ENTER,
      entry({ evidence_ids: [EVIDENCE.acAfter.evidenceId] }),
    );
    expect(envelope.status).toBe("CONFLICT");
  });

  test("an entry window over eight hours is refused", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      ENTER,
      entry({
        requested_window: {
          from: "2026-09-30T10:00:00Z",
          to: "2026-09-30T19:00:00Z",
        },
      }),
    );
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.errors[0]?.field).toBe("requested_window");
  });

  test("an agent without the capabilities is refused", async () => {
    const harness = setUp();
    const enter = await harness.call(ENTER, entry(), CALLER.ungrantedAgent);
    const call = await harness.call(
      DISPATCH,
      dispatch(),
      CALLER.ungrantedAgent,
    );
    expect(harness.auditEntries.map((entry) => entry.detail)).toEqual([
      "The caller does not hold apartment_entry:request.",
      "The caller does not hold vendor_dispatch:request.",
    ]);
    expect([enter.envelope.status, call.envelope.status]).toEqual([
      "FORBIDDEN",
      "FORBIDDEN",
    ]);
  });

  test("the audit trail keeps the outcome and none of the reason", async () => {
    const harness = setUp();
    await pending(
      harness,
      ENTER,
      entry({ reason: "REASON-MARKER cần kiểm tra rò" }),
    );
    expect(harness.auditEntries[0]).toMatchObject({
      tool: "apartment_entry.request",
      status: "PENDING_APPROVAL",
    });
    expect(JSON.stringify(harness.auditEntries)).not.toContain("REASON-MARKER");
  });
});
