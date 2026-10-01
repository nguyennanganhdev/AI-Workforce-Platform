import { beforeEach, describe, expect, test } from "bun:test";
import { createLocalJWKSet, exportJWK, generateKeyPair, SignJWT } from "jose";
import type { RequestIdentity } from "../../src/security-tools/common/context";
import { type ActionBinding, createWriteGuard, GRANT_AUDIENCE, GRANT_TYP, payloadHash, type WriteAction } from "../../src/security-tools/common/execution-grant";
import { configFromEnv } from "../../src/security-tools/index";
import { createFaultsHandler, createMockEnvironment } from "../../src/security-tools/providers/mock-control";
import type { SecurityProvider } from "../../src/security-tools/providers/provider";
import { callTool, type SecurityToolsOptions } from "../../src/security-tools/tools";

const ISSUER = "https://platform.test";
const SCOPE = { tenant_id: "tenant_demo", property_id: "property_demo", ticket_id: "tkt_1001", task_id: "task_1" };
const ACTOR = { actor_id: "usr_sup_day", actor_type: "HUMAN" } as const;

const { privateKey, publicKey } = await generateKeyPair("ES256");
const writeGuard = createWriteGuard({
  issuers: { [ISSUER]: createLocalJWKSet({ keys: [{ ...(await exportJWK(publicKey)), kid: "g1", alg: "ES256" }] }) },
});

const env = createMockEnvironment({ cursorSecret: "test-secret" });
const faults = createFaultsHandler(env);
const options = (provider: SecurityProvider = env.provider): SecurityToolsOptions => ({
  provider,
  writeGuard,
  now: env.clock.now,
  onOutputRejected: () => {},
});

beforeEach(() => env.reset());

/** Grant đúng như platform ký sau khi duyệt: binding từ chính arguments, ký tại giờ của đồng hồ mock. */
async function grant(action: WriteAction, args: Record<string, unknown>, key: string): Promise<string> {
  const binding: ActionBinding = { contract_version: "0.3", proposal_id: `prop_${key}`, ...SCOPE, actor: ACTOR, action, idempotency_key: key, arguments: args };
  const { arguments: _arguments, ...claims } = binding;
  const iat = Math.floor(env.clock.now().getTime() / 1000);
  return new SignJWT({ ...claims, jti: `jti_${key}`, payload_hash: payloadHash(binding) })
    .setProtectedHeader({ alg: "ES256", typ: GRANT_TYP, kid: "g1" })
    .setIssuer(ISSUER)
    .setAudience(GRANT_AUDIENCE)
    .setSubject("executor")
    .setIssuedAt(iat)
    .setNotBefore(iat)
    .setExpirationTime(iat + 120)
    .sign(privateKey);
}

function executor(grantToken: string, key: string): RequestIdentity {
  return {
    caller: { principal_id: "executor", ...SCOPE, modes: new Set(["READ", "WRITE"]) },
    correlation_id: "corr_write",
    write_headers: { execution_grant: grantToken, idempotency_key: key },
  };
}

async function write(action: WriteAction, args: Record<string, unknown>, key: string, opts = options(), token?: string) {
  const result = await callTool(action, args, executor(token ?? (await grant(action, args, key)), key), opts);
  return result.structuredContent as Record<string, any>;
}

const read = async (name: string, args: Record<string, unknown>) =>
  (await callTool(name, args, { ...executor("", ""), write_headers: { execution_grant: null, idempotency_key: null } }, options())).structuredContent as Record<string, any>;

const control = (command: Record<string, unknown>) =>
  faults(new Request("http://localhost/faults", { method: "POST", body: JSON.stringify(command) }));

const DISPATCH = { incident_id: "inc_01", guard_id: "guard_001", incident_version: 6 };

describe("WRITE qua mock: idempotency và meta.replayed", () => {
  test("COMMITTED: gửi lại cùng key trả kết quả lần đầu, replayed=true, không tạo dispatch mới", async () => {
    const first = await write("dispatch_guard", DISPATCH, "key_ok");
    expect(first).toMatchObject({ success: true, meta: { replayed: false }, data: { status: "PENDING", guard_id: "guard_001" } });
    const again = await write("dispatch_guard", DISPATCH, "key_ok");
    expect(again).toMatchObject({ success: true, meta: { replayed: true } });
    expect(again.data).toEqual(first.data);
    expect(again.evidence).toEqual(first.evidence);
    const history = await read("get_dispatch_history", { incident_id: "inc_01" });
    expect(history.data.dispatches.filter((d: { guard_id: string }) => d.guard_id === "guard_001")).toHaveLength(1);
  });

  test("REJECTED: gửi lại cùng key trả đúng failure đã lưu với replayed=true", async () => {
    const stale = { ...DISPATCH, incident_version: 1 };
    const first = await write("dispatch_guard", stale, "key_stale");
    expect(first).toMatchObject({ success: false, meta: { replayed: false } });
    const again = await write("dispatch_guard", stale, "key_stale");
    expect(again).toMatchObject({ success: false, meta: { replayed: true } });
    expect(again.error).toEqual(first.error);
  });

  test("lỗi của chính lần gọi (cùng key, khác payload) không phải replay", async () => {
    await write("dispatch_guard", DISPATCH, "key_conflict");
    const other = await write("dispatch_guard", { ...DISPATCH, guard_id: "guard_002" }, "key_conflict");
    expect(other).toMatchObject({ success: false, error: { code: "IDEMPOTENCY_CONFLICT" }, meta: { replayed: false } });
  });
});

describe("POST /faults", () => {
  test("timeout_after_commit: lần đầu PROVIDER_TIMEOUT/RECONCILE, replay cùng key trả kết quả đã commit", async () => {
    expect((await control({ action: "set_fault", tool: "dispatch_guard", fault: "timeout_after_commit" })).status).toBe(200);
    const first = await write("dispatch_guard", DISPATCH, "key_lost");
    expect(first.error).toMatchObject({ code: "PROVIDER_TIMEOUT", retry: "RECONCILE", operation_state: "UNKNOWN" });
    const again = await write("dispatch_guard", DISPATCH, "key_lost");
    expect(again).toMatchObject({ success: true, meta: { replayed: true }, data: { guard_id: "guard_001" } });
  });

  test("provider_error_before_commit: NEVER/FAILED, không side effect, replay trả lại lỗi", async () => {
    await control({ action: "set_fault", tool: "dispatch_guard", fault: "provider_error_before_commit" });
    const first = await write("dispatch_guard", DISPATCH, "key_err");
    expect(first.error).toMatchObject({ code: "PROVIDER_ERROR", retry: "NEVER", operation_state: "FAILED" });
    expect((await read("get_guard_status", { guard_id: "guard_001" })).data.status).toBe("AVAILABLE");
    expect(await write("dispatch_guard", DISPATCH, "key_err")).toMatchObject({ success: false, meta: { replayed: true } });
  });

  test("fault chỉ áp cho số lần đã đặt", async () => {
    await control({ action: "set_fault", tool: "dispatch_guard", fault: "guard_unavailable", times: 1 });
    expect((await write("dispatch_guard", DISPATCH, "key_a")).error.code).toBe("GUARD_NOT_AVAILABLE");
    expect((await write("dispatch_guard", DISPATCH, "key_b")).success).toBe(true);
  });

  test("barrier: request thứ hai cùng key trong lúc lần đầu đang chạy → IDEMPOTENCY_IN_PROGRESS", async () => {
    let entered!: () => void;
    const reached = new Promise<void>((resolve) => {
      entered = resolve;
    });
    // Ledger claim key đồng bộ ngay khi provider.write được gọi; báo hiệu lúc đó để không phụ thuộc thời gian.
    const spy: SecurityProvider = {
      ...env.provider,
      write: (...args) => {
        const pending = env.provider.write(...args);
        entered();
        return pending;
      },
    };
    await control({ action: "hold", tool: "dispatch_guard" });
    const token = await grant("dispatch_guard", DISPATCH, "key_race");
    const first = write("dispatch_guard", DISPATCH, "key_race", options(spy), token);
    await reached;
    const second = await write("dispatch_guard", DISPATCH, "key_race", options(), token);
    expect(second.error).toMatchObject({ code: "IDEMPOTENCY_IN_PROGRESS", retry: "SAME_KEY" });
    await control({ action: "release", tool: "dispatch_guard" });
    expect(await first).toMatchObject({ success: true, meta: { replayed: false } });
  });

  test("đồng hồ giả: meta/evidence theo giờ mock; tiến quá hạn thì grant hết hạn", async () => {
    const at = "2026-10-01T03:00:00.000Z";
    expect(await (await control({ action: "set_clock", at })).json()).toEqual({ ok: true, now: at });
    const token = await grant("dispatch_guard", DISPATCH, "key_clock");
    await control({ action: "advance_clock", ms: 10 * 60_000 });
    expect((await write("dispatch_guard", DISPATCH, "key_clock", options(), token)).error.code).toBe("GRANT_EXPIRED");

    await control({ action: "set_clock", at });
    const res = await write("dispatch_guard", DISPATCH, "key_clock2");
    expect(res.meta.executed_at).toBe(at);
    expect(res.evidence.committed_at).toBe(at);
  });

  test("reset: dữ liệu về fixture, ledger trống, đồng hồ về giờ thật", async () => {
    await write("dispatch_guard", DISPATCH, "key_reset");
    expect((await read("get_guard_status", { guard_id: "guard_001" })).data.status).toBe("ASSIGNED");
    await control({ action: "set_clock", at: "2000-01-01T00:00:00.000Z" });
    await control({ action: "reset" });
    expect((await read("get_guard_status", { guard_id: "guard_001" })).data.status).toBe("AVAILABLE");
    expect(env.clock.now().getFullYear()).toBeGreaterThan(2000);
    expect(await write("dispatch_guard", DISPATCH, "key_reset")).toMatchObject({ success: true, meta: { replayed: false } });
  });

  test("lệnh sai → 400; không phải POST → 405", async () => {
    expect((await control({ action: "set_fault", tool: "dispatch_guard", fault: "boom" })).status).toBe(400);
    expect((await control({ action: "set_fault", tool: "get_dispatch", fault: "invalid_response" })).status).toBe(400);
    expect((await control({ action: "set_clock", at: "hôm qua" })).status).toBe(400);
    expect((await control({ action: "nuke" })).status).toBe(400);
    expect((await faults(new Request("http://localhost/faults"))).status).toBe(405);
  });

  test("configFromEnv: /faults chỉ bật khi SECURITY_MCP_TEST_CONTROL=1 với provider mock", () => {
    const base = {
      SECURITY_MCP_PROVIDER: "mock",
      SECURITY_MCP_ACCESS_ISSUERS: JSON.stringify({ "https://gateway.test": "https://gateway.test/jwks.json" }),
      SECURITY_MCP_ACCESS_AUDIENCE: "security-mcp",
    };
    expect(configFromEnv(base).faults).toBeUndefined();
    expect(configFromEnv({ ...base, SECURITY_MCP_TEST_CONTROL: "1" }).faults).toBeFunction();
    expect(() =>
      configFromEnv({ ...base, SECURITY_MCP_PROVIDER: "core", SECURITY_CORE_API_URL: "https://core.test", SECURITY_CORE_API_TOKEN: "x", SECURITY_MCP_TEST_CONTROL: "1" }),
    ).toThrow(/mock/);
  });
});
