/**
 * Callback của worker platform trên mock (spec §6.1, §6.2, §9): recordDispatchStatus,
 * recordNotificationResult, recordAckReceipt, expireEscalation. Mock không tự gửi thông báo hay chạy
 * SLA timer, nên test gọi tay các lệnh này để chạy luồng gửi tin → xác nhận, timeout và callback tới
 * sai thứ tự. Mỗi callback phải ghi event + evidence và tăng version của incident.
 */
import { beforeEach, describe, expect, test } from "bun:test";
import type { Actor } from "../../src/security-tools/common/context";
import {
  createWriteControl,
  createMockWrite,
  type MockWrite,
} from "../../src/security-tools/providers/mock-write";
import {
  loadFixtureScope,
  MockSecurityProvider,
  type MockScopeData,
} from "../../src/security-tools/providers/mock-provider";
import {
  callTool,
  type SecurityToolsOptions,
} from "../../src/security-tools/tools";
import {
  ACTOR,
  createHarness,
  expectFailure,
  type GrantSpec,
  type Row,
  session,
  TICKET,
  writeGuard,
} from "./helpers/write-harness";

const h = createHarness();
const TENANT = { tenant_id: "tenant_demo", property_id: "property_demo" };
const T0 = new Date("2026-10-01T03:00:00.000Z");

let scope: MockScopeData;
let kit: MockWrite;
let control: ReturnType<typeof createWriteControl>;
let provider: MockSecurityProvider;
let sequence = 0;
const eventId = () => `cb_${++sequence}`;

beforeEach(() => {
  h.reset();
  h.clock.set(T0);
  sequence = 0;
  scope = loadFixtureScope();
  control = createWriteControl();
  kit = createMockWrite({
    control,
    scopeOf: (tenant, property) => provider.liveScope(tenant, property),
    now: h.clock.now,
  });
  provider = new MockSecurityProvider({
    scopes: [scope],
    now: h.clock.now,
    cursorSecret: "test-secret",
    writeHandlers: kit.handlers,
  });
});

const options = (): SecurityToolsOptions => ({
  provider,
  writeGuard,
  now: h.clock.now,
  onOutputRejected: () => {},
});

type Inc = keyof typeof TICKET;
async function write(
  action: GrantSpec["action"],
  args: Row,
  key: string,
  incident: Inc,
  actor = ACTOR,
) {
  const spec: GrantSpec = {
    action,
    args,
    key,
    session: session(TICKET[incident]),
    actor,
  };
  const identity = h.identity(
    session(TICKET[incident]),
    await h.grant(spec),
    key,
  );
  return (await callTool(action, args, identity, options()))
    .structuredContent as Row;
}

async function read(name: string, args: Row) {
  const identity = h.identity(session(), null, null);
  const result = await callTool(
    name,
    args,
    { ...identity, caller: { ...identity.caller, modes: new Set(["READ"]) } },
    options(),
  );
  return result.structuredContent as Row;
}

const dispatch = (key: string, incident: Inc = "inc_01") =>
  write(
    "dispatch_guard",
    { incident_id: incident, guard_id: "guard_001", incident_version: 6 },
    key,
    incident,
  );
const escalate = (key: string) =>
  write(
    "escalate_emergency",
    {
      incident_id: "inc_02",
      incident_version: 6,
      protocol_id: "prt_intrusion_p0",
      protocol_version: 2,
      contact_id: "ct_pm_01",
      reason: "Cần người phụ trách xác nhận",
    },
    key,
    "inc_02",
  );
const ack = (
  escalationId: string,
  version: number,
  receipt: string,
  key: string,
  actor: Actor = ACTOR,
) =>
  write(
    "acknowledge_emergency",
    {
      escalation_id: escalationId,
      expected_version: version,
      ack_receipt_id: receipt,
    },
    key,
    "inc_02",
    actor,
  );

/** Dữ liệu sống của provider; `scope` ở trên chỉ là bản gốc đã được provider chép. */
const live = () =>
  provider.liveScope(TENANT.tenant_id, TENANT.property_id) as MockScopeData;
const incidentRow = (id: string) =>
  live().incidents.find((i) => i.incident_id === id) as Row;
const lastEvent = () => live().events.at(-1) as Row;
const evidenceOf = (event: Row) =>
  live().evidence.find((e) => e.evidence_id === event.evidence_id) as Row;
const guardStatus = async (guard: string) =>
  (await read("get_guard_status", { guard_id: guard })).data.status;

const dispatchStatus = (
  dispatchId: string,
  expected: number,
  to: "EN_ROUTE" | "ON_SITE" | "COMPLETED" | "FAILED",
  event = eventId(),
) =>
  kit.worker.recordDispatchStatus({
    ...TENANT,
    event_id: event,
    dispatch_id: dispatchId,
    expected_version: expected,
    to,
    ...(to === "FAILED" ? { failure_code: "PROVIDER_REJECTED" as const } : {}),
  });
const notification = (
  escalationId: string,
  expected: number,
  result: "NOTIFIED" | "FAILED" = "NOTIFIED",
  event = eventId(),
) =>
  kit.worker.recordNotificationResult({
    ...TENANT,
    event_id: event,
    escalation_id: escalationId,
    expected_version: expected,
    result,
    provider_reference_id: `ntf_${event}`,
    ...(result === "FAILED"
      ? { failure_code: "DELIVERY_FAILED" as const }
      : {}),
  });
const receiptFor = (
  escalationId: string,
  contact = "ct_pm_01",
  actor: Actor = ACTOR,
) => {
  const r = kit.worker.recordAckReceipt({
    ...TENANT,
    event_id: eventId(),
    escalation_id: escalationId,
    contact_id: contact,
    actor,
  });
  if (!r.ok) throw new Error("recordAckReceipt thất bại");
  return r.data.ack_receipt_id;
};

describe("delivery_failed ghi event + evidence như một callback thật", () => {
  test("dispatch_guard: FAILED, guard được nhả, có event + evidence, incident tăng version và evidence", async () => {
    control.setFault("dispatch_guard", "delivery_failed");
    const env = await dispatch("k_df_d");
    expect(env).toMatchObject({ success: true, data: { status: "PENDING" } });

    const event = lastEvent();
    expect(event).toMatchObject({
      incident_id: "inc_01",
      event_type: "DISPATCH_STATUS_CHANGED",
      data: {
        dispatch_id: env.data.dispatch_id,
        previous_status: "PENDING",
        status: "FAILED",
        reason: "DELIVERY_FAILED",
      },
    });
    expect(evidenceOf(event)).toMatchObject({
      evidence_type: "EXTERNAL_REFERENCE",
      action: null,
      idempotency_key: null,
      incident_id: "inc_01",
    });
    expect(await guardStatus("guard_001")).toBe("AVAILABLE");

    // Commit gốc và callback mỗi bên tăng version + evidence một lần: 6 → 7 → 8, 4 → 5 → 6.
    expect(incidentRow("inc_01")).toMatchObject({
      version: 8,
      related_counts: { evidence: 6 },
    });

    // Đọc lại qua tool: dữ liệu mock phải thỏa output schema của contract.
    const evidence = (
      await read("get_incident_evidence", { incident_id: "inc_01" })
    ).data.evidence as Row[];
    expect(evidence.map((e) => e.evidence_id)).toContain(event.evidence_id);
    const timeline = (
      await read("get_security_event_timeline", { incident_id: "inc_01" })
    ).data.events as Row[];
    expect(timeline.map((e) => e.event_id)).toContain(event.event_id);
  });

  test("escalate_emergency: FAILED/DELIVERY_FAILED, có event + evidence", async () => {
    control.setFault("escalate_emergency", "delivery_failed");
    const env = await escalate("k_df_e");
    expect(env.success).toBe(true);

    const event = lastEvent();
    expect(event).toMatchObject({
      incident_id: "inc_02",
      event_type: "ESCALATION_STATUS_CHANGED",
      data: {
        escalation_id: env.data.escalation_id,
        previous_status: "PENDING",
        status: "FAILED",
        reason: "DELIVERY_FAILED",
      },
    });
    expect(evidenceOf(event)).toMatchObject({
      evidence_type: "EXTERNAL_REFERENCE",
      incident_id: "inc_02",
    });
    expect(incidentRow("inc_02")).toMatchObject({
      version: 8,
      related_counts: { evidence: 7 },
    });
    const timeline = (
      await read("get_security_event_timeline", { incident_id: "inc_02" })
    ).data.events as Row[];
    expect(timeline.map((e) => e.event_id)).toContain(event.event_id);
  });
});

describe("worker: recordDispatchStatus", () => {
  test("PENDING → EN_ROUTE → ON_SITE → COMPLETED: mỗi bước một event + evidence, guard nhả khi COMPLETED", async () => {
    const created = (await dispatch("k_w_d1")).data;
    const base = structuredClone(incidentRow("inc_01"));
    const events = live().events.length;
    const evidence = live().evidence.length;

    const steps = [
      ["EN_ROUTE", 1],
      ["ON_SITE", 2],
      ["COMPLETED", 3],
    ] as const;
    for (const [to, version] of steps) {
      const result = dispatchStatus(created.dispatch_id, version, to);
      expect(result).toMatchObject({
        ok: true,
        data: { status: to, version: version + 1 },
      });
      if (to !== "COMPLETED")
        expect(await guardStatus("guard_001")).toBe("ASSIGNED");
    }

    expect(await guardStatus("guard_001")).toBe("AVAILABLE");
    expect(live().events.length).toBe(events + 3);
    expect(live().evidence.length).toBe(evidence + 3);
    expect(incidentRow("inc_01")).toMatchObject({
      version: base.version + 3,
      related_counts: { evidence: base.related_counts.evidence + 3 },
    });
    // Dispatch xong không làm incident tự RESOLVED (§6.1).
    expect(incidentRow("inc_01").status).toBe("IN_PROGRESS");
  });

  test("callback tới muộn sau CANCELLED không hồi sinh dispatch và không ghi gì", async () => {
    const created = (await dispatch("k_w_d2")).data;
    const cancelled = await write(
      "cancel_dispatch",
      {
        dispatch_id: created.dispatch_id,
        expected_version: 1,
        reason: "Báo động nhầm",
      },
      "k_w_c2",
      "inc_01",
    );
    expect(cancelled.data.status).toBe("CANCELLED");
    const events = live().events.length;
    const evidence = live().evidence.length;

    const late = dispatchStatus(created.dispatch_id, 2, "EN_ROUTE");
    expect(late).toMatchObject({
      ok: false,
      rejection: { code: "INVALID_STATE_TRANSITION" },
    });
    expect(live().events.length).toBe(events);
    expect(live().evidence.length).toBe(evidence);
    expect(
      (await read("get_dispatch", { dispatch_id: created.dispatch_id })).data,
    ).toMatchObject({ status: "CANCELLED", version: 2 });
  });

  test("expected_version cũ → CONFLICT; nhảy cóc PENDING → COMPLETED → INVALID_STATE_TRANSITION", async () => {
    const created = (await dispatch("k_w_d3")).data;
    expect(dispatchStatus(created.dispatch_id, 9, "EN_ROUTE")).toMatchObject({
      ok: false,
      rejection: { code: "CONFLICT" },
    });
    expect(dispatchStatus(created.dispatch_id, 1, "COMPLETED")).toMatchObject({
      ok: false,
      rejection: { code: "INVALID_STATE_TRANSITION" },
    });
  });

  test("cùng event_id: replayed, không tạo event/evidence hay tăng version lần nữa", async () => {
    const created = (await dispatch("k_w_d4")).data;
    const first = dispatchStatus(
      created.dispatch_id,
      1,
      "EN_ROUTE",
      "evt_same",
    );
    const events = live().events.length;
    const incidentVersion = incidentRow("inc_01").version;

    const again = dispatchStatus(
      created.dispatch_id,
      1,
      "EN_ROUTE",
      "evt_same",
    );
    expect(again).toMatchObject({ ok: true, replayed: true });
    expect(first.ok && again.ok && again.data).toEqual(first.ok && first.data);
    expect(live().events.length).toBe(events);
    expect(incidentRow("inc_01").version).toBe(incidentVersion);
  });

  test("dispatch không tồn tại → NOT_FOUND", () => {
    expect(dispatchStatus("dsp_missing", 1, "EN_ROUTE")).toMatchObject({
      ok: false,
      rejection: { code: "NOT_FOUND" },
    });
  });
});

describe("worker: luồng gửi tin → xác nhận (R6)", () => {
  test("PENDING → NOTIFIED → receipt → acknowledge_emergency → ACKNOWLEDGED, acknowledged_by lấy từ receipt", async () => {
    const created = (await escalate("k_w_e1")).data;
    expect(created).toMatchObject({ status: "PENDING", version: 1 });

    // Chưa NOTIFIED thì chưa ACK được (§6.2), dù đã có receipt hợp lệ.
    const receipt = receiptFor(created.escalation_id);
    expectFailure(
      await ack(created.escalation_id, 1, receipt, "k_w_a_early"),
      "INVALID_STATE_TRANSITION",
    );

    const notified = notification(created.escalation_id, 1);
    expect(notified).toMatchObject({
      ok: true,
      data: { status: "NOTIFIED", version: 2 },
    });
    expect(lastEvent()).toMatchObject({
      event_type: "ESCALATION_STATUS_CHANGED",
      data: { previous_status: "PENDING", status: "NOTIFIED" },
    });

    h.clock.advance(30_000);
    const acked = await ack(created.escalation_id, 2, receipt, "k_w_a_ok");
    expect(acked).toMatchObject({
      success: true,
      data: {
        status: "ACKNOWLEDGED",
        version: 3,
        ack_receipt_id: receipt,
        acknowledged_by: ACTOR,
      },
    });
  });

  test("gửi thất bại: FAILED có failure_code, event + evidence; callback sau đó bị từ chối", async () => {
    const created = (await escalate("k_w_e2")).data;
    const failed = notification(created.escalation_id, 1, "FAILED");
    expect(failed).toMatchObject({
      ok: true,
      data: { status: "FAILED", failure_code: "DELIVERY_FAILED" },
    });
    expect(evidenceOf(lastEvent())).toMatchObject({
      evidence_type: "EXTERNAL_REFERENCE",
    });
    expect(notification(created.escalation_id, 2)).toMatchObject({
      ok: false,
      rejection: { code: "INVALID_STATE_TRANSITION" },
    });
  });

  test("callback NOTIFIED tới từ deadline trở đi → ACK_TIMEOUT, không NOTIFIED", async () => {
    const created = (await escalate("k_w_e3")).data;
    h.clock.advance(125_000); // ack_timeout_seconds của prt_intrusion_p0 v2 là 120
    const late = notification(created.escalation_id, 1);
    expect(late).toMatchObject({ ok: true, data: { status: "ACK_TIMEOUT" } });
    expect(lastEvent()).toMatchObject({
      data: {
        previous_status: "PENDING",
        status: "ACK_TIMEOUT",
        reason: "ACK_TIMEOUT",
      },
    });
  });

  test("expireEscalation: trước deadline bị từ chối, đúng deadline → ACK_TIMEOUT; ACK sau đó bị từ chối", async () => {
    const created = (await escalate("k_w_e4")).data;
    notification(created.escalation_id, 1);
    const receipt = receiptFor(created.escalation_id);

    h.clock.advance(119_000);
    expect(
      kit.worker.expireEscalation({
        ...TENANT,
        event_id: eventId(),
        escalation_id: created.escalation_id,
        expected_version: 2,
      }),
    ).toMatchObject({
      ok: false,
      rejection: { code: "INVALID_STATE_TRANSITION" },
    });

    h.clock.advance(1_000);
    expect(
      kit.worker.expireEscalation({
        ...TENANT,
        event_id: eventId(),
        escalation_id: created.escalation_id,
        expected_version: 2,
      }),
    ).toMatchObject({ ok: true, data: { status: "ACK_TIMEOUT", version: 3 } });
    expect(lastEvent()).toMatchObject({
      data: { previous_status: "NOTIFIED", status: "ACK_TIMEOUT" },
    });

    // Receipt có trước deadline nhưng lệnh ACK commit từ deadline trở đi: timeout thắng (§6.2).
    expectFailure(
      await ack(created.escalation_id, 3, receipt, "k_w_a_late"),
      "INVALID_STATE_TRANSITION",
    );
  });

  test("ACK commit từ deadline trở đi khi worker chưa kịp expire → vẫn bị từ chối", async () => {
    const created = (await escalate("k_w_e5")).data;
    notification(created.escalation_id, 1);
    const receipt = receiptFor(created.escalation_id);
    h.clock.advance(120_000);
    expectFailure(
      await ack(created.escalation_id, 2, receipt, "k_w_a_edge"),
      "INVALID_STATE_TRANSITION",
    );
  });

  test("cùng event_id: replayed, không ghi thêm; escalation không tồn tại → NOT_FOUND", async () => {
    const created = (await escalate("k_w_e6")).data;
    notification(created.escalation_id, 1, "NOTIFIED", "evt_dup");
    const events = live().events.length;
    expect(
      notification(created.escalation_id, 1, "NOTIFIED", "evt_dup"),
    ).toMatchObject({
      ok: true,
      replayed: true,
    });
    expect(live().events.length).toBe(events);
    expect(notification("esc_missing", 1)).toMatchObject({
      ok: false,
      rejection: { code: "NOT_FOUND" },
    });
  });
});

// Roster fixture (delegations.json): ct_pm_01 ủy quyền cho usr_deputy_01, ct_sup_day cho usr_deputy_02.
const DEPUTY: Actor = { actor_id: "usr_deputy_01", actor_type: "HUMAN" };
const OTHER_DEPUTY: Actor = { actor_id: "usr_deputy_02", actor_type: "HUMAN" };

describe("R6: ACK bởi người được ủy quyền trong roster (§6.2)", () => {
  /** Escalation tới ct_pm_01 đã NOTIFIED (version 2). */
  async function notified(key: string) {
    const created = (await escalate(key)).data;
    notification(created.escalation_id, 1);
    return created.escalation_id as string;
  }
  const status = async (id: string) =>
    (await read("get_emergency_escalation", { escalation_id: id })).data.status;

  test("người được ủy quyền cho contact của escalation: ACK hợp lệ dù receipt.contact_id khác, acknowledged_by là người ủy quyền", async () => {
    const id = await notified("k_dl_e1");
    const receipt = receiptFor(id, "ct_pm_02", DEPUTY);
    const env = await ack(id, 2, receipt, "k_dl_a1", DEPUTY);
    expect(env).toMatchObject({
      success: true,
      data: {
        status: "ACKNOWLEDGED",
        version: 3,
        ack_receipt_id: receipt,
        acknowledged_by: DEPUTY,
      },
    });
  });

  test("người được ủy quyền cho contact KHÁC → ACK_NOT_AUTHORIZED, escalation vẫn NOTIFIED", async () => {
    const id = await notified("k_dl_e2");
    const receipt = receiptFor(id, "ct_sup_day", OTHER_DEPUTY);
    expectFailure(
      await ack(id, 2, receipt, "k_dl_a2", OTHER_DEPUTY),
      "ACK_NOT_AUTHORIZED",
    );
    expect(await status(id)).toBe("NOTIFIED");
  });

  test("receipt của người được ủy quyền nhưng grant ký cho actor khác → ACK_NOT_AUTHORIZED", async () => {
    const id = await notified("k_dl_e3");
    const receipt = receiptFor(id, "ct_pm_02", DEPUTY);
    expectFailure(
      await ack(id, 2, receipt, "k_dl_a3", ACTOR),
      "ACK_NOT_AUTHORIZED",
    );
    expect(await status(id)).toBe("NOTIFIED");
  });

  test("roster không còn ủy quyền → ACK_NOT_AUTHORIZED", async () => {
    const id = await notified("k_dl_e4");
    const receipt = receiptFor(id, "ct_pm_02", DEPUTY);
    live().delegations = [];
    expectFailure(
      await ack(id, 2, receipt, "k_dl_a4", DEPUTY),
      "ACK_NOT_AUTHORIZED",
    );
  });

  test("người được ủy quyền vẫn bị chặn từ ack_deadline_at trở đi", async () => {
    const id = await notified("k_dl_e5");
    const receipt = receiptFor(id, "ct_pm_02", DEPUTY);
    h.clock.advance(120_000);
    expectFailure(
      await ack(id, 2, receipt, "k_dl_a5", DEPUTY),
      "INVALID_STATE_TRANSITION",
    );
  });
});

describe("worker: cách ly scope", () => {
  test("property khác → NOT_FOUND, không đổi gì", async () => {
    const created = (await dispatch("k_w_scope")).data;
    const result = kit.worker.recordDispatchStatus({
      tenant_id: "tenant_demo",
      property_id: "property_other",
      event_id: eventId(),
      dispatch_id: created.dispatch_id,
      expected_version: 1,
      to: "EN_ROUTE",
    });
    expect(result).toMatchObject({
      ok: false,
      rejection: { code: "NOT_FOUND" },
    });
    expect(
      (await read("get_dispatch", { dispatch_id: created.dispatch_id })).data
        .status,
    ).toBe("PENDING");
  });
});
