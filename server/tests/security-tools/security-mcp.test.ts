import { describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createLocalJWKSet, exportJWK, generateKeyPair, SignJWT } from "jose";
import { toCameraSummary } from "../../src/security-tools/cameras/boundary";
import { CoreClient } from "../../src/security-tools/client";
import { readBodyText } from "../../src/security-tools/common/body";
import { DISPATCH_TOOLS } from "../../src/security-tools/dispatch/tools";
import { EMERGENCY_TOOLS } from "../../src/security-tools/emergency/tools";
import {
  type AuthenticatedCaller,
  callerFromClaims,
  createAccessTokenVerifier,
  type RequestIdentity,
  writeContext,
} from "../../src/security-tools/common/context";
import { retryPolicy, toolError } from "../../src/security-tools/common/errors";
import {
  failure,
  finalizeResponse,
  readSuccess,
  responseMeta,
} from "../../src/security-tools/common/responses";
import {
  parseStrictJson,
  StrictJsonError,
} from "../../src/security-tools/common/strict-json";
import { deriveGuardStatus } from "../../src/security-tools/guards/service";
import type { RosterEntry } from "../../src/security-tools/guards/types";
import {
  configFromEnv,
  createSecurityMcpHandler,
  MCP_PROTOCOL_VERSION,
} from "../../src/security-tools/index";
import {
  loadFixtureScope,
  MockSecurityProvider,
} from "../../src/security-tools/providers/mock-provider";
import { RealSecurityProvider } from "../../src/security-tools/providers/real-provider";
import {
  callTool,
  listTools,
  SECURITY_TOOLS,
  type SecurityToolsOptions,
} from "../../src/security-tools/tools";
import type { Row } from "./helpers/write-harness";

const CORRELATION = "corr_test";

function identity(caller: Partial<AuthenticatedCaller> = {}): RequestIdentity {
  return {
    caller: {
      principal_id: "bot_security",
      tenant_id: "tenant_demo",
      property_id: "property_demo",
      ticket_id: null,
      task_id: null,
      modes: new Set(["READ"]),
      ...caller,
    },
    correlation_id: CORRELATION,
    write_headers: { execution_grant: null, idempotency_key: null },
  };
}

const mockOptions = (
  extra: Partial<ConstructorParameters<typeof MockSecurityProvider>[0]> = {},
): SecurityToolsOptions => ({
  provider: new MockSecurityProvider({
    scopes: [loadFixtureScope()],
    cursorSecret: "test-secret",
    ...extra,
  }),
  onOutputRejected: () => {},
});

async function call(
  name: string,
  args: Record<string, unknown>,
  options = mockOptions(),
  who = identity(),
) {
  const result = await callTool(name, args, who, options);
  return result.structuredContent as Row;
}

describe("ToolError §5.1", () => {
  test("PROVIDER_* phụ thuộc mode và việc đã biết kết quả", () => {
    expect(retryPolicy("PROVIDER_TIMEOUT", { mode: "READ" })).toMatchObject({
      retry: "BACKOFF",
      operation_state: "NOT_STARTED",
    });
    expect(retryPolicy("PROVIDER_TIMEOUT", { mode: "WRITE" })).toEqual({
      retry: "RECONCILE",
      retry_after_ms: null,
      operation_state: "UNKNOWN",
    });
    expect(retryPolicy("PROVIDER_ERROR", { mode: "WRITE" })).toMatchObject({
      retry: "RECONCILE",
      operation_state: "UNKNOWN",
    });
    expect(
      retryPolicy("PROVIDER_ERROR", {
        mode: "WRITE",
        outcome: "NOT_COMMITTED",
      }),
    ).toMatchObject({ retry: "NEVER", operation_state: "FAILED" });
    expect(retryPolicy("IDEMPOTENCY_IN_PROGRESS")).toEqual({
      retry: "SAME_KEY",
      retry_after_ms: 1000,
      operation_state: "IN_PROGRESS",
    });
    expect(
      toolError("RATE_LIMITED", "x", { retryAfterMs: 999_999 }).retry_after_ms,
    ).toBe(60_000);
  });
});

describe("context", () => {
  test("claims hợp lệ thành caller; task không có ticket bị từ chối", () => {
    const caller = callerFromClaims({
      sub: "p1",
      tenant_id: "t1",
      property_id: "pr1",
      scope: "openid security:read",
    });
    expect([...caller.modes]).toEqual(["READ"]);
    expect(() =>
      callerFromClaims({
        sub: "p1",
        tenant_id: "t1",
        property_id: "pr1",
        scope: "security:read",
        task_id: "k1",
      }),
    ).toThrow();
    expect(() =>
      callerFromClaims({
        sub: "p1",
        tenant_id: "t1",
        property_id: "pr1",
        scope: "openid",
      }),
    ).toThrow();
  });

  test("WRITE cần ticket/task trong token", () => {
    expect(() =>
      writeContext(identity({ modes: new Set(["READ", "WRITE"]) })),
    ).toThrow();
    const ok = writeContext(identity({ ticket_id: "tk_1", task_id: "ts_1" }));
    expect(ok).toMatchObject({
      ticket_id: "tk_1",
      task_id: "ts_1",
      correlation_id: CORRELATION,
    });
  });
});

describe("strict JSON", () => {
  test("từ chối key trùng và surrogate lẻ, giữ __proto__ là dữ liệu", () => {
    expect(() => parseStrictJson('{"a":1,"a":2}')).toThrow(StrictJsonError);
    expect(() => parseStrictJson('"\\uD800"')).toThrow(StrictJsonError);
    const parsed = parseStrictJson('{"__proto__":{"x":1}}') as Record<
      string,
      unknown
    >;
    expect(Object.getPrototypeOf(parsed)).toBe(Object.prototype);
    expect(Object.keys(parsed)).toEqual(["__proto__"]);
  });
});

describe("envelope", () => {
  const contract = SECURITY_TOOLS.find((t) => t.name === "get_guard_status")!;
  const meta = responseMeta(CORRELATION, {
    now: new Date("2026-10-01T00:00:00Z"),
  });

  test("success sai contract được thay bằng PROVIDER_INVALID_RESPONSE", () => {
    const { response, issues } = finalizeResponse(
      contract,
      readSuccess({ guard_id: "guard_001" }, meta),
    );
    expect(issues.length).toBeGreaterThan(0);
    expect(response).toMatchObject({
      success: false,
      data: null,
      evidence: null,
      error: { code: "PROVIDER_INVALID_RESPONSE" },
    });
  });

  test("failure hợp lệ đi qua nguyên vẹn", () => {
    const original = failure(toolError("NOT_FOUND", "không có"), meta);
    expect(finalizeResponse(contract, original)).toEqual({
      response: original,
      issues: [],
    });
  });
});

describe("tools/list", () => {
  test("22 tool trong catalog; caller READ chỉ thấy 16 READ", () => {
    expect(SECURITY_TOOLS).toHaveLength(22);
    const tools = listTools(identity(), {});
    expect(tools).toHaveLength(16);
    expect(tools.every((t) => t.annotations?.readOnlyHint === true)).toBe(true);
  });

  test("WRITE ẩn khi chưa có writeGuard, hiện khi đã cắm", () => {
    const writer = identity({ modes: new Set(["READ", "WRITE"]) });
    expect(listTools(writer, {})).toHaveLength(16);
    expect(
      listTools(writer, {
        writeGuard: async () => ({
          ok: false,
          error: toolError("GRANT_MISSING", "x"),
        }),
      }),
    ).toHaveLength(22);
  });

  test("schema bundle độc lập, không còn $ref trỏ file", () => {
    for (const tool of listTools(
      identity({ modes: new Set(["READ", "WRITE"]) }),
      {
        writeGuard: async () => ({
          ok: false,
          error: toolError("GRANT_MISSING", "x"),
        }),
      },
    )) {
      const refs =
        JSON.stringify([tool.inputSchema, tool.outputSchema]).match(
          /"\$ref":"[^"]*"/g,
        ) ?? [];
      expect(refs.every((ref) => ref.startsWith('"$ref":"#/$defs/'))).toBe(
        true,
      );
    }
  });
});

describe("tools/call wrapper", () => {
  test("caller READ gọi WRITE → AUTH_ERROR", async () => {
    const res = await call("dispatch_guard", {});
    expect(res).toMatchObject({
      success: false,
      error: { code: "AUTH_ERROR", retry: "NEVER" },
    });
  });

  test("input lạ → VALIDATION_ERROR, không chạm provider", async () => {
    const res = await call("get_guard_status", {
      guard_id: "guard_001",
      tenant_id: "other",
    });
    expect(res.error.code).toBe("VALIDATION_ERROR");
  });

  test("provider treo quá budget → PROVIDER_TIMEOUT có thể thử lại (READ)", async () => {
    const options: SecurityToolsOptions = {
      budgetMs: 20,
      provider: {
        name: "slow",
        read: () => new Promise(() => {}),
        write: () => new Promise(() => {}),
      },
    };
    const res = await call(
      "get_guard_status",
      { guard_id: "guard_001" },
      options,
    );
    expect(res.error).toMatchObject({
      code: "PROVIDER_TIMEOUT",
      retry: "BACKOFF",
      operation_state: "NOT_STARTED",
    });
  });
});

describe("guards (P2)", () => {
  test("get_available_guards: chỉ AVAILABLE, sắp guard_id", async () => {
    const res = await call("get_available_guards", { location_id: "loc_01" });
    expect(res.success).toBe(true);
    expect(
      res.data.guards.map((g: { guard_id: string }) => g.guard_id),
    ).toEqual(["guard_001", "guard_002", "guard_003", "guard_010"]);
    expect(res.data.next_cursor).toBeNull();
    expect(res.evidence).toBeNull();
  });

  test("phân trang: cursor gắn với filter, đổi filter thì từ chối", async () => {
    const options = mockOptions();
    const first = await call(
      "get_available_guards",
      { location_id: "loc_01", limit: 3 },
      options,
    );
    expect(first.data.guards).toHaveLength(3);
    const cursor = first.data.next_cursor as string;
    const second = await call(
      "get_available_guards",
      { location_id: "loc_01", limit: 3, cursor },
      options,
    );
    expect(
      second.data.guards.map((g: { guard_id: string }) => g.guard_id),
    ).toEqual(["guard_010"]);
    expect(second.data.next_cursor).toBeNull();
    const reused = await call(
      "get_available_guards",
      { location_id: "loc_02", limit: 3, cursor },
      options,
    );
    expect(reused.error.code).toBe("VALIDATION_ERROR");
  });

  test("location không tồn tại → NOT_FOUND", async () => {
    expect(
      (await call("get_available_guards", { location_id: "loc_99" })).error
        .code,
    ).toBe("NOT_FOUND");
  });

  test("get_guard_status trong scope và khác scope", async () => {
    const own = await call("get_guard_status", { guard_id: "guard_007" });
    expect(own.data).toMatchObject({
      guard_id: "guard_007",
      status: "OFF_DUTY",
      current_location: null,
    });
    const other = await call(
      "get_guard_status",
      { guard_id: "guard_007" },
      mockOptions(),
      identity({ property_id: "property_other" }),
    );
    expect(other.error.code).toBe("NOT_FOUND");
  });

  test("bảng ánh xạ roster → GuardStatus", () => {
    const now = "2026-10-01T03:00:00.000Z";
    const roster = (patch: Partial<RosterEntry>): RosterEntry => ({
      guard_id: "guard_001",
      employment: "ACTIVE",
      shifts: [
        { start: "2026-10-01T00:00:00.000Z", end: "2026-10-01T08:00:00.000Z" },
      ],
      duty_state: "ON_DUTY",
      current_location: null,
      updated_at: now,
      ...patch,
    });
    expect(deriveGuardStatus(null, false, now)).toBe("UNKNOWN");
    expect(deriveGuardStatus(null, true, now)).toBe("ASSIGNED");
    expect(
      deriveGuardStatus(roster({ employment: "SUSPENDED" }), true, now),
    ).toBe("UNAVAILABLE");
    expect(deriveGuardStatus(roster({}), true, now)).toBe("ASSIGNED");
    expect(deriveGuardStatus(roster({ shifts: [] }), false, now)).toBe(
      "OFF_DUTY",
    );
    expect(deriveGuardStatus(roster({}), false, now)).toBe("AVAILABLE");
    expect(
      deriveGuardStatus(roster({ duty_state: "ON_BREAK" }), false, now),
    ).toBe("UNAVAILABLE");
    expect(deriveGuardStatus(roster({ duty_state: null }), false, now)).toBe(
      "UNKNOWN",
    );
    // Ca là [start, end): đúng mốc end là hết ca.
    expect(
      deriveGuardStatus(roster({}), false, "2026-10-01T08:00:00.000Z"),
    ).toBe("OFF_DUTY");
  });
});

describe("cameras (P2)", () => {
  test("search_cameras lọc AND, chính xác, sắp camera_id", async () => {
    const res = await call("search_cameras", {
      building: "Tòa A",
      floor: "T1",
    });
    expect(
      res.data.cameras.map((c: { camera_id: string }) => c.camera_id),
    ).toEqual(["cam_01", "cam_02", "cam_03"]);
    const none = await call("search_cameras", { building: "Tòa a" });
    expect(none.data).toEqual({ cameras: [], next_cursor: null });
  });

  test("get_cameras_by_location và get_camera_metadata (OFFLINE vẫn trả metadata)", async () => {
    const byLocation = await call("get_cameras_by_location", {
      location_id: "loc_03",
    });
    expect(
      byLocation.data.cameras.map((c: { camera_id: string }) => c.camera_id),
    ).toEqual(["cam_04", "cam_05"]);
    const offline = await call("get_camera_metadata", { camera_id: "cam_03" });
    expect(offline.data.status).toBe("OFFLINE");
  });

  test("provider lọt stream_url → PROVIDER_INVALID_RESPONSE, không trả field media", async () => {
    const res = await call(
      "get_camera_metadata",
      { camera_id: "cam_01" },
      mockOptions({ faults: { get_camera_metadata: "invalid_response" } }),
    );
    expect(res).toMatchObject({
      success: false,
      data: null,
      error: { code: "PROVIDER_INVALID_RESPONSE" },
    });
    expect(JSON.stringify(res)).not.toContain("rtsp://");
  });

  test("boundary chặn field ngoài whitelist và chuỗi dạng địa chỉ", () => {
    const camera = {
      camera_id: "cam_01",
      location: {
        location_id: "loc_01",
        building: "Tòa A",
        floor: "T1",
        zone: "Cổng chính",
      },
      status: "ONLINE",
      camera_type: "FIXED",
      reference_id: "ref_01",
      last_seen_at: null,
    };
    expect(toCameraSummary(camera)).toEqual(camera as never);
    expect(() => toCameraSummary({ ...camera, snapshot_url: "x" })).toThrow();
    expect(() =>
      toCameraSummary({ ...camera, reference_id: "https://cdn/x.jpg" }),
    ).toThrow();
  });
});

describe("Core client + real provider (READ)", () => {
  test("dùng credential của MCP, gửi ReadContext, không chuyển token caller", async () => {
    const seen: { auth: string | null; body: Row }[] = [];
    const fetchStub = (async (url: URL, init: RequestInit) => {
      const headers = new Headers(init.headers);
      seen.push({
        auth: headers.get("authorization"),
        body: JSON.parse(String(init.body)),
      });
      expect(String(url)).toBe("https://core.test/api/security/v0.3/query");
      return Response.json({ data: { guards: [], next_cursor: null } });
    }) as unknown as typeof fetch;
    const provider = new RealSecurityProvider(
      new CoreClient({
        baseUrl: new URL("https://core.test/api"),
        credential: () => "svc-token",
        fetch: fetchStub,
      }),
    );
    const res = await call(
      "get_available_guards",
      { location_id: "loc_01" },
      { provider },
    );
    expect(res.success).toBe(true);
    expect(seen[0]!.auth).toBe("Bearer svc-token");
    expect(seen[0]!.body).toEqual({
      context: {
        tenant_id: "tenant_demo",
        property_id: "property_demo",
        ticket_id: null,
        task_id: null,
        correlation_id: CORRELATION,
        principal_id: "bot_security",
      },
      tool_call: {
        name: "get_available_guards",
        arguments: { location_id: "loc_01" },
      },
    });
  });

  test("Core trả camera có stream_url → PROVIDER_INVALID_RESPONSE; 429 → RATE_LIMITED", async () => {
    const camera = {
      camera_id: "cam_01",
      location: {
        location_id: "loc_01",
        building: null,
        floor: null,
        zone: null,
      },
      status: "ONLINE",
      camera_type: "PTZ",
      reference_id: null,
      last_seen_at: null,
      stream_url: "rtsp://x",
    };
    const leaky = (async () =>
      Response.json({ data: camera })) as unknown as typeof fetch;
    const provider = new RealSecurityProvider(
      new CoreClient({
        baseUrl: new URL("https://core.test/"),
        credential: () => "svc",
        fetch: leaky,
      }),
    );
    expect(
      (
        await call(
          "get_camera_metadata",
          { camera_id: "cam_01" },
          { provider, onOutputRejected: () => {} },
        )
      ).error.code,
    ).toBe("PROVIDER_INVALID_RESPONSE");

    const limited = (async () =>
      new Response("{}", {
        status: 429,
        headers: { "retry-after": "2" },
      })) as unknown as typeof fetch;
    const provider2 = new RealSecurityProvider(
      new CoreClient({
        baseUrl: new URL("https://core.test/"),
        credential: () => "svc",
        fetch: limited,
      }),
    );
    const res = await call(
      "get_guard_status",
      { guard_id: "guard_001" },
      { provider: provider2 },
    );
    expect(res.error).toMatchObject({
      code: "RATE_LIMITED",
      retry: "BACKOFF",
      retry_after_ms: 2000,
    });
  });
});

describe("đăng ký P4, cấu hình, body", () => {
  test("9 tool P4 dùng khai báo của domain, không rơi về mô tả mặc định", () => {
    const p4 = [...DISPATCH_TOOLS, ...EMERGENCY_TOOLS];
    expect(p4).toHaveLength(9);
    for (const declared of p4) {
      const registered = SECURITY_TOOLS.find((t) => t.name === declared.name)!;
      expect(registered.description).toBe(declared.description);
      expect(registered.annotations).toEqual(declared.annotations);
    }
  });

  test("configFromEnv: grant issuer với jwks.json cục bộ bật writeGuard; production từ chối file cục bộ", async () => {
    const { publicKey } = await generateKeyPair("ES256");
    const dir = mkdtempSync(join(tmpdir(), "security-mcp-"));
    const jwksPath = join(dir, "jwks.json");
    writeFileSync(
      jwksPath,
      JSON.stringify({
        keys: [{ ...(await exportJWK(publicKey)), kid: "g1", alg: "ES256" }],
      }),
    );
    try {
      const env = {
        SECURITY_MCP_PROVIDER: "mock",
        SECURITY_MCP_ACCESS_ISSUERS: JSON.stringify({
          "https://gateway.test": jwksPath,
        }),
        SECURITY_MCP_ACCESS_AUDIENCE: "security-mcp",
        SECURITY_MCP_GRANT_ISSUERS: JSON.stringify({
          "https://platform.test": jwksPath,
        }),
      };
      expect(configFromEnv(env).options.writeGuard).toBeFunction();
      expect(
        configFromEnv({ ...env, SECURITY_MCP_GRANT_ISSUERS: undefined }).options
          .writeGuard,
      ).toBeUndefined();
      expect(() =>
        configFromEnv({
          ...env,
          SECURITY_MCP_GRANT_ISSUERS: "https://platform.test",
        }),
      ).toThrow();
      expect(() =>
        configFromEnv({
          ...env,
          SECURITY_MCP_PROVIDER: "core",
          SECURITY_CORE_API_URL: "https://core.test",
          SECURITY_CORE_API_TOKEN: "x",
          NODE_ENV: "production",
        }),
      ).toThrow(/production/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  test("readBodyText dừng đọc ngay khi vượt giới hạn", async () => {
    let pulls = 0;
    const endless = new ReadableStream<Uint8Array>({
      pull(controller) {
        pulls += 1;
        controller.enqueue(new Uint8Array(1024));
      },
    });
    expect(await readBodyText(new Response(endless), 4096)).toEqual({
      ok: false,
      reason: "too_large",
    });
    expect(pulls).toBeLessThan(10);
    const declared = new Request("http://x", {
      method: "POST",
      body: "{}",
      headers: { "content-length": "999999" },
    });
    expect(await readBodyText(declared, 4096)).toEqual({
      ok: false,
      reason: "too_large",
    });
  });

  test("Core trả response vượt giới hạn byte → PROVIDER_INVALID_RESPONSE", async () => {
    const huge = (async () =>
      new Response(
        new ReadableStream({
          pull: (c) => c.enqueue(new Uint8Array(1024 * 1024)),
        }),
      )) as unknown as typeof fetch;
    const provider = new RealSecurityProvider(
      new CoreClient({
        baseUrl: new URL("https://core.test/"),
        credential: () => "svc",
        fetch: huge,
      }),
    );
    expect(
      (await call("get_guard_status", { guard_id: "guard_001" }, { provider }))
        .error.code,
    ).toBe("PROVIDER_INVALID_RESPONSE");
  });
});

describe("HTTP server (Streamable HTTP, stateless)", async () => {
  const { privateKey, publicKey } = await generateKeyPair("ES256");
  const jwk = { ...(await exportJWK(publicKey)), kid: "k1", alg: "ES256" };
  // Issuer thứ hai có key riêng: token của nó không được verify bằng key của gateway và ngược lại.
  const other = await generateKeyPair("ES256");
  const otherJwk = {
    ...(await exportJWK(other.publicKey)),
    kid: "k2",
    alg: "ES256",
  };
  const verifyAccessToken = createAccessTokenVerifier({
    issuers: {
      "https://gateway.test": createLocalJWKSet({ keys: [jwk] }),
      "https://other.test": createLocalJWKSet({ keys: [otherJwk] }),
    },
    audience: "security-mcp",
  });
  const handler = createSecurityMcpHandler({
    ...mockOptions(),
    verifyAccessToken,
    maxBodyBytes: 4096,
    allowedOrigins: ["https://console.test"],
  });

  const token = (
    scope: string,
    signer: { issuer: string; key: CryptoKey; kid: string } = {
      issuer: "https://gateway.test",
      key: privateKey,
      kid: "k1",
    },
  ) =>
    new SignJWT({
      tenant_id: "tenant_demo",
      property_id: "property_demo",
      scope,
    })
      .setProtectedHeader({ alg: "ES256", kid: signer.kid })
      .setIssuer(signer.issuer)
      .setAudience("security-mcp")
      .setSubject("bot_security")
      .setIssuedAt()
      .setExpirationTime("5m")
      .sign(signer.key);

  const post = async (
    body: unknown,
    auth?: string,
    extraHeaders: Record<string, string> = {},
  ) =>
    handler(
      new Request("http://localhost/mcp", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          accept: "application/json, text/event-stream",
          "mcp-protocol-version": MCP_PROTOCOL_VERSION,
          ...(auth ? { authorization: `Bearer ${auth}` } : {}),
          ...extraHeaders,
        },
        body: typeof body === "string" ? body : JSON.stringify(body),
      }),
    );

  test("JWKS theo issuer: ghi issuer A nhưng ký bằng key của issuer B → 401", async () => {
    const list = { jsonrpc: "2.0", id: 1, method: "tools/list" };
    expect(
      (
        await post(
          list,
          await token("security:read", {
            issuer: "https://other.test",
            key: other.privateKey,
            kid: "k2",
          }),
        )
      ).status,
    ).toBe(200);
    expect(
      (
        await post(
          list,
          await token("security:read", {
            issuer: "https://gateway.test",
            key: other.privateKey,
            kid: "k2",
          }),
        )
      ).status,
    ).toBe(401);
    expect(
      (
        await post(
          list,
          await token("security:read", {
            issuer: "https://unknown.test",
            key: privateKey,
            kid: "k1",
          }),
        )
      ).status,
    ).toBe(401);
  });

  test("Origin ngoài allowlist → 403 trước khi xác thực; không có Origin hoặc Origin hợp lệ thì qua", async () => {
    const list = { jsonrpc: "2.0", id: 1, method: "tools/list" };
    const auth = await token("security:read");
    expect(
      (await post(list, auth, { origin: "https://evil.test" })).status,
    ).toBe(403);
    expect(
      (await post(list, undefined, { origin: "https://evil.test" })).status,
    ).toBe(403);
    expect(
      (await post(list, auth, { origin: "https://console.test" })).status,
    ).toBe(200);
  });

  test("giới hạn body tính theo byte UTF-8, không theo số ký tự", async () => {
    const auth = await token("security:read");
    // 1500 ký tự "ệ" = 4500 byte: dưới 4096 ký tự nhưng vượt 4096 byte.
    const body = JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
      params: { _meta: { pad: "ệ".repeat(1500) } },
    });
    expect(body.length).toBeLessThan(4096);
    expect((await post(body, auth)).status).toBe(413);
    const invalidUtf8 = new Request("http://localhost/mcp", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "application/json, text/event-stream",
        authorization: `Bearer ${auth}`,
      },
      body: new Uint8Array([0x7b, 0xff, 0x7d]),
    });
    expect((await handler(invalidUtf8)).status).toBe(400);
  });

  test("401 khi không có token, 403 khi token không có scope Security", async () => {
    expect(
      (await post({ jsonrpc: "2.0", id: 1, method: "tools/list" })).status,
    ).toBe(401);
    expect(
      (
        await post(
          { jsonrpc: "2.0", id: 1, method: "tools/list" },
          await token("openid"),
        )
      ).status,
    ).toBe(403);
  });

  test("initialize trả profile đã pin", async () => {
    const res = await post(
      {
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2099-01-01",
          capabilities: {},
          clientInfo: { name: "t", version: "1" },
        },
      },
      await token("security:read"),
    );
    const body = (await res.json()) as Row;
    expect(body.result.protocolVersion).toBe(MCP_PROTOCOL_VERSION);
  });

  test("tools/list và tools/call qua HTTP", async () => {
    const auth = await token("security:read");
    const list = (await (
      await post({ jsonrpc: "2.0", id: 2, method: "tools/list" }, auth)
    ).json()) as Row;
    expect(list.result.tools).toHaveLength(16);
    const res = await post(
      {
        jsonrpc: "2.0",
        id: 3,
        method: "tools/call",
        params: {
          name: "get_guard_status",
          arguments: { guard_id: "guard_002" },
        },
      },
      auth,
    );
    expect(res.headers.get("x-correlation-id")).toBeTruthy();
    const body = (await res.json()) as Row;
    expect(body.result.isError).toBe(false);
    expect(body.result.structuredContent.data.guard_id).toBe("guard_002");
  });

  test("body có key trùng → parse error trước khi tới tool", async () => {
    const res = await post(
      '{"jsonrpc":"2.0","id":1,"id":2,"method":"tools/list"}',
      await token("security:read"),
    );
    expect(res.status).toBe(400);
  });
});
