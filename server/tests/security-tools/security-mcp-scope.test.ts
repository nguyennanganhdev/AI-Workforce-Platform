/**
 * Gate R3 (spec §2, §3.1, §5.1): ID của property khác trông như ID không tồn tại, không lộ dữ liệu,
 * không có side effect; WRITE trên incident đã có phải đi bằng phiên của đúng ticket của incident đó.
 * Property khác ở đây là một scope không có dữ liệu của tenant_demo (mock trả scope rỗng).
 */
import { beforeEach, describe, expect, test } from "bun:test";
import {
  createHarness,
  expectFailure,
  type Row,
  session,
  TICKET,
} from "./helpers/write-harness";

const h = createHarness();
beforeEach(() => h.reset());

const OTHER = session("tkt_1001", {
  tenant_id: "tenant_other",
  property_id: "property_other",
});

const READS: [string, Row, Row][] = [
  ["get_incident", { incident_id: "inc_01" }, { incident_id: "inc_missing" }],
  [
    "get_guard_status",
    { guard_id: "guard_001" },
    { guard_id: "guard_missing" },
  ],
  ["get_dispatch", { dispatch_id: "dsp_0003" }, { dispatch_id: "dsp_missing" }],
  [
    "get_emergency_escalation",
    { escalation_id: "esc_0003" },
    { escalation_id: "esc_missing" },
  ],
  [
    "get_camera_metadata",
    { camera_id: "cam_01" },
    { camera_id: "cam_missing" },
  ],
  [
    "get_emergency_protocol",
    { incident_type: "INTRUSION", severity: "P0" },
    { incident_type: "THEFT", severity: "P0" },
  ],
  [
    "get_incident_cameras",
    { incident_id: "inc_01" },
    { incident_id: "inc_missing" },
  ],
  [
    "get_incident_escalations",
    { incident_id: "inc_01" },
    { incident_id: "inc_missing" },
  ],
  [
    "get_dispatch_history",
    { incident_id: "inc_01" },
    { incident_id: "inc_missing" },
  ],
  [
    "get_incident_evidence",
    { incident_id: "inc_01" },
    { incident_id: "inc_missing" },
  ],
  [
    "get_security_event_timeline",
    { incident_id: "inc_01" },
    { incident_id: "inc_missing" },
  ],
  [
    "get_available_guards",
    { location_id: "loc_01" },
    { location_id: "loc_missing" },
  ],
  [
    "get_cameras_by_location",
    { location_id: "loc_01" },
    { location_id: "loc_missing" },
  ],
];

describe("R3: READ từ property khác", () => {
  test.each(READS)(
    "%s: giống hệt ID không tồn tại, không lộ dữ liệu",
    async (tool, args, missing) => {
      const own = await h.read(tool, args);
      expect(own.success).toBe(true);
      const other = expectFailure(await h.read(tool, args, OTHER), "NOT_FOUND");
      const none = expectFailure(
        await h.read(tool, missing, OTHER),
        "NOT_FOUND",
      );
      expect(other).toEqual(none);
      expect(other.message).not.toContain("tenant_demo");
      expect(other.message).not.toContain("property_demo");
    },
  );

  test("danh sách ở property khác là rỗng, không trộn dữ liệu tenant_demo", async () => {
    expect((await h.read("search_incidents", {}, OTHER)).data).toEqual({
      incidents: [],
      next_cursor: null,
    });
    expect((await h.read("search_cameras", {}, OTHER)).data).toEqual({
      cameras: [],
      next_cursor: null,
    });
    expect(
      (await h.read("get_escalation_contacts", { severity: "P0" }, OTHER)).data,
    ).toEqual({ contacts: [], next_cursor: null });
  });

  test("cursor của property này không dùng được ở property khác", async () => {
    const first = await h.read("search_cameras", { limit: 2 });
    expect(first.data.next_cursor).toBeString();
    expectFailure(
      await h.read(
        "search_cameras",
        { limit: 2, cursor: first.data.next_cursor },
        OTHER,
      ),
      "VALIDATION_ERROR",
    );
  });
});

describe("R3: WRITE từ property khác (grant khớp phiên của property đó)", () => {
  const cases: [string, Row][] = [
    [
      "dispatch_guard",
      { incident_id: "inc_01", guard_id: "guard_001", incident_version: 6 },
    ],
    [
      "cancel_dispatch",
      {
        dispatch_id: "dsp_0003",
        expected_version: 3,
        reason: "Hủy từ property khác",
      },
    ],
    [
      "escalate_emergency",
      {
        incident_id: "inc_02",
        incident_version: 6,
        protocol_id: "prt_intrusion_p0",
        protocol_version: 2,
        contact_id: "ct_pm_01",
        reason: "Từ property khác",
      },
    ],
    [
      "acknowledge_emergency",
      {
        escalation_id: "esc_0003",
        expected_version: 2,
        ack_receipt_id: "ack_7101",
      },
    ],
    [
      "create_incident",
      {
        incident_type: "THEFT",
        description: "Từ property khác",
        severity: "P2",
        location_id: "loc_01",
      },
    ],
  ];
  test.each(cases)(
    "%s → NOT_FOUND, dữ liệu tenant_demo không đổi",
    async (tool, args) => {
      const before = await snapshot();
      const env = await h.write({
        action: tool as never,
        args,
        key: `k_other_${tool}`,
        session: OTHER,
      });
      expectFailure(env, "NOT_FOUND");
      expect(await snapshot()).toEqual(before);
    },
  );
});

describe("R3: ticket của phiên khác ticket của incident", () => {
  const cases: [string, Row][] = [
    [
      "dispatch_guard",
      { incident_id: "inc_02", guard_id: "guard_001", incident_version: 6 },
    ],
    [
      "cancel_dispatch",
      {
        dispatch_id: "dsp_0005",
        expected_version: 1,
        reason: "Phiên của ticket khác",
      },
    ],
    [
      "escalate_emergency",
      {
        incident_id: "inc_02",
        incident_version: 6,
        protocol_id: "prt_intrusion_p0",
        protocol_version: 2,
        contact_id: "ct_pm_01",
        reason: "Phiên của ticket khác",
      },
    ],
    [
      "acknowledge_emergency",
      {
        escalation_id: "esc_0003",
        expected_version: 2,
        ack_receipt_id: "ack_7101",
      },
    ],
  ];
  test.each(cases)(
    "%s trên incident của tkt_1002 bằng phiên tkt_1001 → SCOPE_MISMATCH",
    async (tool, args) => {
      h.clock.set(new Date("2026-09-29T04:21:45.000Z"));
      const before = await snapshot();
      const env = await h.write({
        action: tool as never,
        args,
        key: `k_ticket_${tool}`,
        session: session(TICKET.inc_01),
      });
      expect(expectFailure(env, "SCOPE_MISMATCH")).toMatchObject({
        retry: "NEVER",
        operation_state: "NOT_STARTED",
      });
      expect(await snapshot()).toEqual(before);
    },
  );

  test("đối chứng: cùng lệnh bằng phiên đúng ticket thì chạy được", async () => {
    const env = await h.write({
      action: "dispatch_guard",
      args: {
        incident_id: "inc_02",
        guard_id: "guard_001",
        incident_version: 6,
      },
      key: "k_ticket_ok",
      session: session(TICKET.inc_02),
    });
    expect(env.success).toBe(true);
  });
});

/** Trạng thái quan sát được của tenant_demo, để chứng minh lệnh bị từ chối không đổi gì. */
async function snapshot() {
  const incidents = await h.read("search_incidents", { limit: 100 });
  const guards = await Promise.all(
    ["guard_001", "guard_002", "guard_004"].map((g) =>
      h.read("get_guard_status", { guard_id: g }),
    ),
  );
  const dispatch = await h.read("get_dispatch", { dispatch_id: "dsp_0003" });
  const escalations = await h.read("get_incident_escalations", {
    incident_id: "inc_02",
  });
  return {
    incidents: incidents.data,
    guards: guards.map((g) => g.data),
    dispatch: dispatch.data,
    escalations: escalations.data,
  };
}
