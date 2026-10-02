/**
 * Gate R4 (spec §5): một key + một binding = tối đa một commit, qua retry, grant cấp lại, kết quả đã
 * archive và mọi trường hợp không rõ outcome. Phần replay cơ bản đã có trong security-mcp-write.test.ts.
 */
import { beforeEach, describe, expect, test } from "bun:test";
import {
  createHarness,
  expectFailure,
  type Row,
  session,
} from "./helpers/write-harness";

const h = createHarness({ useOwnLedger: true });
beforeEach(() => h.reset());

const DISPATCH = {
  incident_id: "inc_01",
  guard_id: "guard_001",
  incident_version: 6,
};
const spec = (key: string, args: Row = DISPATCH, extra: Row = {}) => ({
  action: "dispatch_guard" as const,
  args,
  key,
  ...extra,
});
const SCOPE = { tenant_id: "tenant_demo", property_id: "property_demo" };

async function dispatchesOfGuard(guard: string) {
  const history = await h.read("get_dispatch_history", {
    incident_id: "inc_01",
  });
  return history.data.dispatches.filter((d: Row) => d.guard_id === guard);
}

describe("R4: proposal và key", () => {
  test("cùng proposal nhưng key mới → IDEMPOTENCY_CONFLICT, không tạo lệnh thứ hai", async () => {
    expect(
      (await h.write(spec("k_p1", DISPATCH, { proposal: "prop_shared" })))
        .success,
    ).toBe(true);
    const again = await h.write(
      spec("k_p2", DISPATCH, { proposal: "prop_shared" }),
    );
    expect(expectFailure(again, "IDEMPOTENCY_CONFLICT")).toMatchObject({
      retry: "NEVER",
      operation_state: "NOT_STARTED",
    });
    expect(await dispatchesOfGuard("guard_001")).toHaveLength(1);
  });

  test("key đã dùng cho action khác → IDEMPOTENCY_CONFLICT", async () => {
    expect((await h.write(spec("k_shared"))).success).toBe(true);
    const cancel = {
      action: "cancel_dispatch" as const,
      args: {
        dispatch_id: "dsp_0003",
        expected_version: 3,
        reason: "Dùng lại key",
      },
      key: "k_shared",
    };
    expectFailure(await h.write(cancel), "IDEMPOTENCY_CONFLICT");
    expect(
      (await h.read("get_dispatch", { dispatch_id: "dsp_0003" })).data.status,
    ).toBe("ON_SITE");
  });

  test("key giống nhau ở hai scope khác nhau không đụng nhau", async () => {
    expect((await h.write(spec("k_scoped"))).success).toBe(true);
    const other = session("tkt_1001", {
      tenant_id: "tenant_other",
      property_id: "property_other",
    });
    const env = await h.write({
      action: "create_incident",
      args: {
        incident_type: "THEFT",
        description: "Scope khác",
        severity: "P2",
        location_id: "loc_01",
      },
      key: "k_scoped",
      session: other,
    });
    expectFailure(env, "NOT_FOUND");
  });
});

describe("R4: grant hết hạn được cấp lại", () => {
  test("cùng binding/key, grant mới (jti mới) sau khi grant cũ hết hạn → replay, không chạy lại", async () => {
    h.clock.set(new Date("2026-10-01T03:00:00.000Z"));
    const first = await h.write(spec("k_renew"));
    expect(first.success).toBe(true);
    h.clock.advance(10 * 60_000);
    const renewed = await h.grant(spec("k_renew"));
    const again = await h.write(spec("k_renew"), { token: renewed });
    expect(again).toMatchObject({ success: true, meta: { replayed: true } });
    expect(again.data).toEqual(first.data);
    expect(again.evidence).toEqual(first.evidence);
    expect(await dispatchesOfGuard("guard_001")).toHaveLength(1);
  });

  test("grant cũ đã hết hạn thì không replay được (vẫn phải xác thực)", async () => {
    h.clock.set(new Date("2026-10-01T03:00:00.000Z"));
    const token = await h.grant(spec("k_old"));
    expect((await h.write(spec("k_old"), { token })).success).toBe(true);
    h.clock.advance(10 * 60_000);
    expectFailure(await h.write(spec("k_old"), { token }), "GRANT_EXPIRED");
  });
});

describe("R4: kết quả đã archive", () => {
  test("COMMITTED nhưng result đã archive → IDEMPOTENCY_RESULT_EXPIRED (RECONCILE), không chạy lại", async () => {
    expect((await h.write(spec("k_archive"))).success).toBe(true);
    h.ledger!.archiveResult(SCOPE, "k_archive");
    const again = await h.write(spec("k_archive"));
    expect(expectFailure(again, "IDEMPOTENCY_RESULT_EXPIRED")).toMatchObject({
      retry: "RECONCILE",
      operation_state: "UNKNOWN",
      retry_after_ms: null,
    });
    expect(await dispatchesOfGuard("guard_001")).toHaveLength(1);
  });

  test("REJECTED đã archive cũng không chạy lại", async () => {
    const stale = { ...DISPATCH, incident_version: 1 };
    expectFailure(await h.write(spec("k_archive_rej", stale)), "CONFLICT");
    h.ledger!.archiveResult(SCOPE, "k_archive_rej");
    expectFailure(
      await h.write(spec("k_archive_rej", stale)),
      "IDEMPOTENCY_RESULT_EXPIRED",
    );
  });

  test("ledger ghi đúng trạng thái operation (đối soát kiểu getOperation)", async () => {
    await h.write(spec("k_ledger"));
    expect(h.ledger!.get(SCOPE, "k_ledger")).toMatchObject({
      status: "COMMITTED",
      idempotency_key: "k_ledger",
      proposal_id: "prop_k_ledger",
    });
    expectFailure(
      await h.write(spec("k_ledger_rej", { ...DISPATCH, incident_version: 1 })),
      "CONFLICT",
    );
    expect(h.ledger!.get(SCOPE, "k_ledger_rej")).toMatchObject({
      status: "REJECTED",
      rejection: { code: "CONFLICT" },
    });
  });
});

describe("R4: outcome không rõ", () => {
  test("timeout_before_commit → PROVIDER_TIMEOUT RECONCILE/UNKNOWN, không side effect; gửi lại cùng key vẫn chờ đối soát", async () => {
    h.control.setFault("dispatch_guard", "timeout_before_commit");
    const first = await h.write(spec("k_tbc"));
    expect(expectFailure(first, "PROVIDER_TIMEOUT")).toMatchObject({
      retry: "RECONCILE",
      operation_state: "UNKNOWN",
    });
    expect(
      (await h.read("get_guard_status", { guard_id: "guard_001" })).data.status,
    ).toBe("AVAILABLE");
    expect(h.ledger!.get(SCOPE, "k_tbc")?.status).toBe("UNKNOWN");
    const again = await h.write(spec("k_tbc"));
    expect(expectFailure(again, "PROVIDER_TIMEOUT")).toMatchObject({
      retry: "RECONCILE",
    });
    expect(await dispatchesOfGuard("guard_001")).toHaveLength(0);
  });

  test("timeout_before_commit: key mới cho cùng proposal không lách được để chạy lại", async () => {
    h.control.setFault("dispatch_guard", "timeout_before_commit");
    expectFailure(
      await h.write(spec("k_tbc_a", DISPATCH, { proposal: "prop_tbc" })),
      "PROVIDER_TIMEOUT",
    );
    expectFailure(
      await h.write(spec("k_tbc_b", DISPATCH, { proposal: "prop_tbc" })),
      "IDEMPOTENCY_CONFLICT",
    );
    expect(await dispatchesOfGuard("guard_001")).toHaveLength(0);
  });

  test("invalid_response sau commit → không trả success giả; replay cùng key trả data đúng contract", async () => {
    h.control.setFault("dispatch_guard", "invalid_response");
    const first = await h.write(spec("k_bad_resp"));
    expect(expectFailure(first, "PROVIDER_INVALID_RESPONSE")).toMatchObject({
      retry: "RECONCILE",
      operation_state: "UNKNOWN",
    });
    const again = await h.write(spec("k_bad_resp"));
    expect(again).toMatchObject({
      success: true,
      meta: { replayed: true },
      data: { guard_id: "guard_001", status: "PENDING" },
    });
    expect(again.data.mock_invalid_field).toBeUndefined();
    expect(await dispatchesOfGuard("guard_001")).toHaveLength(1);
  });

  test("timeout_after_commit rồi replay: evidence giữ committed_at của lần đầu", async () => {
    h.clock.set(new Date("2026-10-01T03:00:00.000Z"));
    h.control.setFault("dispatch_guard", "timeout_after_commit");
    expectFailure(await h.write(spec("k_tac")), "PROVIDER_TIMEOUT");
    h.clock.advance(60_000);
    const again = await h.write(spec("k_tac"));
    expect(again.meta).toMatchObject({
      replayed: true,
      executed_at: "2026-10-01T03:01:00.000Z",
    });
    expect(again.evidence.committed_at).toBe("2026-10-01T03:00:00.000Z");
  });
});
