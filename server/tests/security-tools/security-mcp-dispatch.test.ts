/**
 * Gate R5 (spec §6.1): một dispatch mở cho mỗi guard, kiểm version, terminal state giữ nguyên,
 * delivery_failed nhả guard. Chạy qua wrapper + grant thật trên mock.
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

type Inc = keyof typeof TICKET;
const dispatch = (
  incident: Inc,
  guard: string,
  version: number,
  key: string,
  extra: Row = {},
) =>
  h.write({
    action: "dispatch_guard",
    args: {
      incident_id: incident,
      guard_id: guard,
      incident_version: version,
      ...extra,
    },
    key,
    session: session(TICKET[incident]),
  });
const cancel = (
  incident: Inc,
  dispatchId: string,
  version: number,
  key: string,
  reason = "Đã xác minh báo động nhầm",
) =>
  h.write({
    action: "cancel_dispatch",
    args: { dispatch_id: dispatchId, expected_version: version, reason },
    key,
    session: session(TICKET[incident]),
  });
const guardStatus = async (guard: string) =>
  (await h.read("get_guard_status", { guard_id: guard })).data.status;
const available = async (location: string) =>
  (
    await h.read("get_available_guards", { location_id: location })
  ).data.guards.map((g: Row) => g.guard_id);

describe("R5: dispatch_guard", () => {
  test("tạo PENDING v1, location chụp từ incident, guard sang ASSIGNED và rời danh sách rảnh", async () => {
    const incident = (await h.read("get_incident", { incident_id: "inc_01" }))
      .data;
    const env = await dispatch("inc_01", "guard_001", 6, "k_new", {
      instruction: "Kiểm tra khu vực cháy",
    });
    expect(env.data).toMatchObject({
      status: "PENDING",
      version: 1,
      guard_id: "guard_001",
      location: incident.location,
      instruction: "Kiểm tra khu vực cháy",
    });
    expect(await guardStatus("guard_001")).toBe("ASSIGNED");
    expect(await available("loc_01")).not.toContain("guard_001");
    expect(
      (await h.read("get_incident", { incident_id: "inc_01" })).data.version,
    ).toBe(7);
  });

  test.each([
    ["guard đang giữ dispatch mở", "guard_004"],
    ["guard OFF_DUTY", "guard_007"],
    ["guard UNAVAILABLE", "guard_008"],
    ["guard UNKNOWN", "guard_009"],
  ])("%s → GUARD_NOT_AVAILABLE (NEVER/FAILED)", async (_label, guard) => {
    const error = expectFailure(
      await dispatch("inc_01", guard, 6, `k_busy_${guard}`),
      "GUARD_NOT_AVAILABLE",
    );
    expect(error).toMatchObject({ retry: "NEVER", operation_state: "FAILED" });
  });

  test("guard ngoài property → NOT_FOUND", async () => {
    expectFailure(
      await dispatch("inc_01", "guard_999", 6, "k_noguard"),
      "NOT_FOUND",
    );
  });

  test("incident_version cũ → CONFLICT, guard vẫn rảnh", async () => {
    expectFailure(
      await dispatch("inc_01", "guard_001", 5, "k_stale"),
      "CONFLICT",
    );
    expect(await guardStatus("guard_001")).toBe("AVAILABLE");
  });

  test("incident đã RESOLVED → INVALID_STATE_TRANSITION, kể cả version đúng", async () => {
    expectFailure(
      await dispatch("inc_04", "guard_001", 5, "k_resolved"),
      "INVALID_STATE_TRANSITION",
    );
    expect(await guardStatus("guard_001")).toBe("AVAILABLE");
  });

  test("một incident có thể có nhiều guard cùng lúc", async () => {
    expect(
      (await dispatch("inc_01", "guard_001", 6, "k_multi_1")).success,
    ).toBe(true);
    expect(
      (await dispatch("inc_01", "guard_002", 7, "k_multi_2")).success,
    ).toBe(true);
  });

  test("hai key tranh một guard đồng thời → đúng một thành công, còn lại GUARD_NOT_AVAILABLE", async () => {
    h.env.hold("dispatch_guard");
    const racing = Promise.all([
      dispatch("inc_01", "guard_001", 6, "k_race_a"),
      dispatch("inc_03", "guard_001", 4, "k_race_b"),
    ]);
    await Bun.sleep(30);
    h.env.release("dispatch_guard");
    const results = await racing;
    expect(results.filter((r) => r.success)).toHaveLength(1);
    expectFailure(results.find((r) => !r.success)!, "GUARD_NOT_AVAILABLE");
    expect(await guardStatus("guard_001")).toBe("ASSIGNED");
  });

  test("fault guard_unavailable lúc commit → GUARD_NOT_AVAILABLE, không side effect", async () => {
    h.control.setFault("dispatch_guard", "guard_unavailable");
    expectFailure(
      await dispatch("inc_01", "guard_001", 6, "k_gu"),
      "GUARD_NOT_AVAILABLE",
    );
    expect(await guardStatus("guard_001")).toBe("AVAILABLE");
  });

  test("delivery_failed: lệnh đã commit, sau đó dispatch FAILED/DELIVERY_FAILED và guard được nhả", async () => {
    h.control.setFault("dispatch_guard", "delivery_failed");
    const env = await dispatch("inc_01", "guard_001", 6, "k_df");
    expect(env.success).toBe(true);
    const after = (
      await h.read("get_dispatch", { dispatch_id: env.data.dispatch_id })
    ).data;
    expect(after).toMatchObject({
      status: "FAILED",
      failure_code: "DELIVERY_FAILED",
      version: 2,
    });
    expect(await guardStatus("guard_001")).toBe("AVAILABLE");
  });
});

describe("R5: cancel_dispatch", () => {
  test("hủy rồi hủy lại: cùng key replay, key mới → INVALID_STATE_TRANSITION, lý do hủy giữ nguyên, guard được nhả", async () => {
    const created = (await dispatch("inc_01", "guard_001", 6, "k_c_new")).data;
    const first = await cancel("inc_01", created.dispatch_id, 1, "k_cancel");
    expect(first.data).toMatchObject({
      status: "CANCELLED",
      version: 2,
      cancel_reason: "Đã xác minh báo động nhầm",
    });
    expect(first.data.cancelled_at).toBeString();
    expect(await guardStatus("guard_001")).toBe("AVAILABLE");

    const replay = await cancel("inc_01", created.dispatch_id, 1, "k_cancel");
    expect(replay).toMatchObject({ success: true, meta: { replayed: true } });
    expect(replay.data).toEqual(first.data);

    expectFailure(
      await cancel("inc_01", created.dispatch_id, 2, "k_cancel_2", "Lý do mới"),
      "INVALID_STATE_TRANSITION",
    );
    expect(
      (await h.read("get_dispatch", { dispatch_id: created.dispatch_id })).data
        .cancel_reason,
    ).toBe("Đã xác minh báo động nhầm");
  });

  test.each([
    ["COMPLETED", "inc_04", "dsp_0002", 4],
    ["CANCELLED", "inc_04", "dsp_0001", 2],
    ["FAILED", "inc_02", "dsp_0004", 2],
  ] as const)(
    "dispatch %s không hủy được, kể cả version sai",
    async (_status, incident, id, version) => {
      expectFailure(
        await cancel(incident, id, version, `k_term_${id}`),
        "INVALID_STATE_TRANSITION",
      );
      expectFailure(
        await cancel(incident, id, version + 9, `k_term2_${id}`),
        "INVALID_STATE_TRANSITION",
      );
    },
  );

  test("dispatch đang mở với expected_version cũ → CONFLICT", async () => {
    expectFailure(
      await cancel("inc_01", "dsp_0003", 2, "k_c_stale"),
      "CONFLICT",
    );
    expect(
      (await h.read("get_dispatch", { dispatch_id: "dsp_0003" })).data.status,
    ).toBe("ON_SITE");
  });

  test("hủy dispatch đang mở trong fixture nhả guard của nó", async () => {
    expect(await guardStatus("guard_004")).toBe("ASSIGNED");
    expect((await cancel("inc_01", "dsp_0003", 3, "k_c_fixture")).success).toBe(
      true,
    );
    expect(await guardStatus("guard_004")).not.toBe("ASSIGNED");
  });

  test("dispatch không tồn tại → NOT_FOUND", async () => {
    expectFailure(
      await cancel("inc_01", "dsp_missing", 1, "k_c_missing"),
      "NOT_FOUND",
    );
  });
});
