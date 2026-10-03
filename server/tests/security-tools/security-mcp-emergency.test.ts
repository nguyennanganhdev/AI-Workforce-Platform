/**
 * Gate R6 (spec §6.2): escalate chỉ cho P0/P1 với protocol/contact đúng, không trùng target đang chờ;
 * ACK chỉ từ receipt hợp lệ của đúng contact/actor, trước deadline, từ NOTIFIED.
 * Escalation mới dừng ở PENDING (mock không gửi thông báo), nên ACK dùng esc_0003 (NOTIFIED) trong fixture.
 */
import { beforeEach, describe, expect, test } from "bun:test";
import type { Actor } from "../../src/security-tools/common/context";
import {
  ACTOR,
  createHarness,
  expectFailure,
  type Row,
  session,
  TICKET,
} from "./helpers/write-harness";

const h = createHarness();
beforeEach(() => h.reset());

type Inc = keyof typeof TICKET;
const escalate = (
  incident: Inc,
  version: number,
  protocol: string,
  protocolVersion: number,
  contact: string,
  key: string,
) =>
  h.write({
    action: "escalate_emergency",
    args: {
      incident_id: incident,
      incident_version: version,
      protocol_id: protocol,
      protocol_version: protocolVersion,
      contact_id: contact,
      reason: "Cần người phụ trách xác nhận",
    },
    key,
    session: session(TICKET[incident]),
  });

const BEFORE_DEADLINE = new Date("2026-09-29T04:21:45.000Z");
const ack = (
  escalation: string,
  version: number,
  receipt: string,
  key: string,
  actor: Actor = ACTOR,
  incident: Inc = "inc_02",
) =>
  h.write({
    action: "acknowledge_emergency",
    args: {
      escalation_id: escalation,
      expected_version: version,
      ack_receipt_id: receipt,
    },
    key,
    session: session(TICKET[incident]),
    actor,
  });
const escalationsOf = async (incident: string) =>
  (await h.read("get_incident_escalations", { incident_id: incident })).data
    .escalations as Row[];

describe("R6: escalate_emergency", () => {
  test("hợp lệ: PENDING, snapshot severity/protocol, deadline = created_at + ack_timeout_seconds", async () => {
    h.clock.set(new Date("2026-10-01T03:00:00.000Z"));
    const env = await escalate(
      "inc_02",
      6,
      "prt_intrusion_p0",
      2,
      "ct_pm_01",
      "k_esc",
    );
    expect(env.data).toMatchObject({
      status: "PENDING",
      severity: "P0",
      protocol_id: "prt_intrusion_p0",
      protocol_version: 2,
      contact_id: "ct_pm_01",
      notification_reference_id: null,
      notified_at: null,
    });
    expect(env.data.ack_deadline_at).toBe("2026-10-01T03:02:00.000Z");
    expect(
      (await escalationsOf("inc_02")).map((e) => e.escalation_id),
    ).toContain(env.data.escalation_id);
  });

  test("escalation trước đã terminal thì escalate lại cùng contact được", async () => {
    expect(
      (await escalate("inc_01", 6, "prt_fire_p1", 1, "ct_sup_day", "k_again"))
        .success,
    ).toBe(true);
  });

  test("incident P2 gọi thẳng tool → EMERGENCY_NOT_ELIGIBLE, chặn trước mọi kiểm tra khác", async () => {
    const error = expectFailure(
      await escalate("inc_04", 999, "prt_missing", 9, "ct_missing", "k_p2"),
      "EMERGENCY_NOT_ELIGIBLE",
    );
    expect(error).toMatchObject({ retry: "NEVER", operation_state: "FAILED" });
    expect(await escalationsOf("inc_04")).toEqual([]);
  });

  test.each([
    [
      "contact OFF_DUTY",
      "inc_02",
      6,
      "prt_intrusion_p0",
      2,
      "ct_sup_night",
      "CONTACT_NOT_AVAILABLE",
    ],
    [
      "contact không hỗ trợ P1",
      "inc_01",
      6,
      "prt_fire_p1",
      1,
      "ct_coord_01",
      "CONTACT_NOT_AVAILABLE",
    ],
    [
      "contact availability UNKNOWN",
      "inc_01",
      6,
      "prt_fire_p1",
      1,
      "ct_pm_02",
      "CONTACT_NOT_AVAILABLE",
    ],
    [
      "trùng target đang NOTIFIED",
      "inc_02",
      6,
      "prt_intrusion_p0",
      2,
      "ct_sup_day",
      "CONFLICT",
    ],
    [
      "trùng target đang PENDING",
      "inc_02",
      6,
      "prt_intrusion_p0",
      2,
      "ct_coord_01",
      "CONFLICT",
    ],
    [
      "protocol lệch version",
      "inc_02",
      6,
      "prt_intrusion_p0",
      1,
      "ct_pm_01",
      "CONFLICT",
    ],
    [
      "protocol của loại incident khác",
      "inc_02",
      6,
      "prt_fire_p0",
      1,
      "ct_pm_01",
      "CONFLICT",
    ],
    [
      "incident_version cũ",
      "inc_02",
      5,
      "prt_intrusion_p0",
      2,
      "ct_pm_01",
      "CONFLICT",
    ],
    [
      "protocol không có",
      "inc_02",
      6,
      "prt_missing",
      1,
      "ct_pm_01",
      "NOT_FOUND",
    ],
    [
      "contact không có",
      "inc_02",
      6,
      "prt_intrusion_p0",
      2,
      "ct_missing",
      "NOT_FOUND",
    ],
  ] as const)(
    "%s → %s, không tạo escalation",
    async (_label, incident, version, protocol, pv, contact, code) => {
      const before = await escalationsOf(incident);
      expectFailure(
        await escalate(
          incident,
          version,
          protocol,
          pv,
          contact,
          `k_${contact}_${pv}_${version}`,
        ),
        code,
      );
      expect(await escalationsOf(incident)).toEqual(before);
    },
  );

  test("fault contact_unavailable lúc commit → CONTACT_NOT_AVAILABLE", async () => {
    h.control.setFault("escalate_emergency", "contact_unavailable");
    expectFailure(
      await escalate("inc_02", 6, "prt_intrusion_p0", 2, "ct_pm_01", "k_cu"),
      "CONTACT_NOT_AVAILABLE",
    );
  });

  test("delivery_failed: escalation đã tạo chuyển FAILED/DELIVERY_FAILED, incident không tự đổi", async () => {
    h.control.setFault("escalate_emergency", "delivery_failed");
    const env = await escalate(
      "inc_02",
      6,
      "prt_intrusion_p0",
      2,
      "ct_pm_01",
      "k_edf",
    );
    expect(env.success).toBe(true);
    const after = (
      await h.read("get_emergency_escalation", {
        escalation_id: env.data.escalation_id,
      })
    ).data;
    expect(after).toMatchObject({
      status: "FAILED",
      failure_code: "DELIVERY_FAILED",
    });
    expect(
      (await h.read("get_incident", { incident_id: "inc_02" })).data.status,
    ).toBe("IN_PROGRESS");
  });
});

describe("R6: acknowledge_emergency", () => {
  beforeEach(() => h.clock.set(BEFORE_DEADLINE));

  test("receipt đúng contact/actor trước deadline → ACKNOWLEDGED, acknowledged_by lấy từ receipt", async () => {
    const env = await ack("esc_0003", 2, "ack_7101", "k_ack");
    expect(env.data).toMatchObject({
      status: "ACKNOWLEDGED",
      version: 3,
      ack_receipt_id: "ack_7101",
      acknowledged_by: { actor_id: "usr_sup_day", actor_type: "HUMAN" },
      acknowledged_at: "2026-09-29T04:21:30.000Z",
    });
  });

  test("cùng key replay; key mới sau khi đã ACK → INVALID_STATE_TRANSITION", async () => {
    const first = await ack("esc_0003", 2, "ack_7101", "k_ack_r");
    expect(await ack("esc_0003", 2, "ack_7101", "k_ack_r")).toMatchObject({
      success: true,
      meta: { replayed: true },
      data: first.data,
    });
    expectFailure(
      await ack("esc_0003", 3, "ack_7101", "k_ack_r2"),
      "INVALID_STATE_TRANSITION",
    );
  });

  test.each([
    [
      "actor của grant khác actor của receipt",
      "esc_0003",
      2,
      "ack_7101",
      { actor_id: "usr_other", actor_type: "HUMAN" },
      "ACK_NOT_AUTHORIZED",
    ],
    [
      "receipt của contact khác",
      "esc_0003",
      2,
      "ack_7102",
      { actor_id: "usr_pm_01", actor_type: "HUMAN" },
      "ACK_NOT_AUTHORIZED",
    ],
    [
      "receipt của escalation khác",
      "esc_0003",
      2,
      "ack_7005",
      ACTOR,
      "ACK_NOT_AUTHORIZED",
    ],
    [
      "receipt không tồn tại",
      "esc_0003",
      2,
      "ack_missing",
      ACTOR,
      "ACK_NOT_AUTHORIZED",
    ],
    ["expected_version cũ", "esc_0003", 1, "ack_7101", ACTOR, "CONFLICT"],
    [
      "escalation còn PENDING (chưa NOTIFIED)",
      "esc_0004",
      1,
      "ack_7101",
      ACTOR,
      "INVALID_STATE_TRANSITION",
    ],
  ] as const)(
    "%s → %s, escalation không đổi",
    async (_label, escalation, version, receipt, actor, code) => {
      const before = (
        await h.read("get_emergency_escalation", { escalation_id: escalation })
      ).data;
      expectFailure(
        await ack(
          escalation,
          version,
          receipt,
          `k_ack_${receipt}_${version}_${actor.actor_id}`,
          actor,
        ),
        code,
      );
      expect(
        (
          await h.read("get_emergency_escalation", {
            escalation_id: escalation,
          })
        ).data,
      ).toEqual(before);
    },
  );

  test("đúng lúc deadline trở đi → INVALID_STATE_TRANSITION (timeout thắng)", async () => {
    h.clock.set(new Date("2026-09-29T04:22:00.000Z"));
    expectFailure(
      await ack("esc_0003", 2, "ack_7101", "k_ack_late"),
      "INVALID_STATE_TRANSITION",
    );
    expect(
      (await h.read("get_emergency_escalation", { escalation_id: "esc_0003" }))
        .data.status,
    ).toBe("NOTIFIED");
  });

  test.each([
    ["ACKNOWLEDGED", "esc_0005", 3, "inc_03"],
    ["FAILED", "esc_0001", 2, "inc_01"],
    ["ACK_TIMEOUT", "esc_0002", 3, "inc_01"],
  ] as const)(
    "escalation %s đã terminal → INVALID_STATE_TRANSITION, kể cả version sai",
    async (_s, escalation, version, incident) => {
      expectFailure(
        await ack(
          escalation,
          version,
          "ack_7005",
          `k_term_${escalation}`,
          ACTOR,
          incident,
        ),
        "INVALID_STATE_TRANSITION",
      );
      expectFailure(
        await ack(
          escalation,
          version + 9,
          "ack_7005",
          `k_term2_${escalation}`,
          ACTOR,
          incident,
        ),
        "INVALID_STATE_TRANSITION",
      );
    },
  );
});
