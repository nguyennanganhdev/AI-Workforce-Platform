/**
 * Gate R2 (spec §4): chỉ grant ES256 đúng issuer/audience/thời gian, khớp scope phiên, tool, key và
 * payload_hash mới chạy được lệnh. Mọi lần từ chối là NEVER/NOT_STARTED và không có side effect.
 * Kèm JCS (RFC 8785) cho đúng tập giá trị của ActionBinding.
 */
import { beforeEach, describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import {
  CanonicalizeError,
  canonicalize,
  GRANT_TYP,
  payloadHash,
} from "../../src/security-tools/common/execution-grant";
import {
  ACTOR,
  bindingOf,
  createHarness,
  expectFailure,
  KEYS,
  OTHER_ISSUER,
  type Row,
  session,
  sha256,
  signHs256,
  signRaw,
} from "./helpers/write-harness";

const h = createHarness();
beforeEach(() => h.reset());

const DISPATCH = {
  incident_id: "inc_01",
  guard_id: "guard_001",
  incident_version: 6,
};
const spec = (key: string, args: Row = DISPATCH) => ({
  action: "dispatch_guard" as const,
  args,
  key,
});
const now = () => Math.floor(h.clock.now().getTime() / 1000);

async function expectRefusedWithoutSideEffect(
  env: Row,
  code: string | string[],
) {
  const error = expectFailure(env, code);
  expect(error).toMatchObject({
    retry: "NEVER",
    operation_state: "NOT_STARTED",
    retry_after_ms: null,
  });
  expect(
    (await h.read("get_guard_status", { guard_id: "guard_001" })).data.status,
  ).toBe("AVAILABLE");
  const history = await h.read("get_dispatch_history", {
    incident_id: "inc_01",
  });
  expect(history.data.dispatches.map((d: Row) => d.guard_id)).not.toContain(
    "guard_001",
  );
}

describe("R2: grant hợp lệ (đối chứng)", () => {
  test("grant đúng chạy được lệnh, có evidence", async () => {
    const env = await h.write(spec("k_valid"));
    expect(env).toMatchObject({
      success: true,
      data: { status: "PENDING", guard_id: "guard_001" },
    });
    expect(env.evidence.evidence_id).toBeString();
  });

  test("grant hết hạn nhưng còn trong 30 giây lệch đồng hồ vẫn được nhận", async () => {
    const t = now();
    const token = await h.grant(spec("k_skew"), {
      iat: t - 130,
      nbf: t - 130,
      exp: t - 10,
    });
    expect((await h.write(spec("k_skew"), { token })).success).toBe(true);
  });

  test("iat/nbf ở tương lai trong 30 giây vẫn được nhận", async () => {
    const t = now();
    const token = await h.grant(spec("k_future_ok"), {
      iat: t + 20,
      nbf: t + 20,
      exp: t + 120,
    });
    expect((await h.write(spec("k_future_ok"), { token })).success).toBe(true);
  });
});

describe("R2: header và chữ ký", () => {
  test("thiếu grant → GRANT_MISSING", async () => {
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_missing"), { token: null }),
      "GRANT_MISSING",
    );
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_empty"), { token: "" }),
      "GRANT_MISSING",
    );
  });

  test("thiếu hoặc sai định dạng Idempotency-Key → VALIDATION_ERROR", async () => {
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_nokey"), { headerKey: null }),
      "VALIDATION_ERROR",
    );
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_badkey"), { headerKey: "key có dấu cách" }),
      "VALIDATION_ERROR",
    );
  });

  const headerCases: [string, Row][] = [
    ["alg ES384", { alg: "ES384" }],
    ["alg RS256", { alg: "RS256" }],
    ["typ JWT", { typ: "JWT" }],
    ["thiếu typ", { typ: undefined }],
    ["thiếu kid", { kid: undefined }],
    ["kid rỗng", { kid: "" }],
    ["kid không có trong JWKS", { kid: "kid-la" }],
    ["có jku", { jku: "https://attacker.test/jwks.json" }],
    ["có x5u", { x5u: "https://attacker.test/cert.pem" }],
    ["có jwk nhúng", { jwk: { kty: "EC", crv: "P-256", x: "AA", y: "AA" } }],
    ["có crit", { crit: ["exp"] }],
    ["có tham số lạ", { cty: "JWT" }],
  ];
  test.each(headerCases)("header %s → GRANT_INVALID", async (_label, patch) => {
    const token = await h.grant(spec("k_header"), {}, patch);
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_header"), { token }),
      "GRANT_INVALID",
    );
  });

  test("alg none không có chữ ký → GRANT_INVALID", async () => {
    const claims = h.claimsFor(spec("k_none"));
    const token = `${Buffer.from(JSON.stringify({ alg: "none", typ: GRANT_TYP })).toString("base64url")}.${Buffer.from(JSON.stringify(claims)).toString("base64url")}.`;
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_none"), { token }),
      "GRANT_INVALID",
    );
  });

  test("HS256 dùng public key làm secret → GRANT_INVALID", async () => {
    const token = await signHs256(
      { alg: "HS256", typ: GRANT_TYP, kid: "g1" },
      h.claimsFor(spec("k_hs")),
    );
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_hs"), { token }),
      "GRANT_INVALID",
    );
  });

  test("chữ ký bị sửa → GRANT_INVALID", async () => {
    const token = await h.grant(spec("k_sig"));
    const [head, body, sig] = token.split(".");
    const flipped = `${sig!.slice(0, -2)}${sig!.endsWith("AA") ? "BB" : "AA"}`;
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_sig"), { token: `${head}.${body}.${flipped}` }),
      "GRANT_INVALID",
    );
  });

  test("ghi issuer này nhưng ký bằng key của issuer khác trong allowlist → GRANT_INVALID", async () => {
    const token = await h.grant(
      spec("k_mix"),
      {},
      { kid: "g2" },
      KEYS.other.privateKey,
    );
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_mix"), { token }),
      "GRANT_INVALID",
    );
  });

  test("issuer khác trong allowlist với đúng key của nó thì hợp lệ", async () => {
    const token = await h.grant(
      spec("k_other_ok"),
      { iss: OTHER_ISSUER },
      { kid: "g2" },
      KEYS.other.privateKey,
    );
    expect((await h.write(spec("k_other_ok"), { token })).success).toBe(true);
  });

  test("grant dài quá 8192 ký tự → GRANT_INVALID", async () => {
    const token = await h.grant(spec("k_long"), { padding: "x".repeat(9000) });
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_long"), { token }),
      "GRANT_INVALID",
    );
  });

  test("chuỗi không phải JWS → GRANT_INVALID", async () => {
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_junk"), { token: "not.a.jws" }),
      "GRANT_INVALID",
    );
  });
});

describe("R2: claims", () => {
  const claimCases: [string, (t: number) => Row, string][] = [
    [
      "iss ngoài allowlist",
      () => ({ iss: "https://untrusted.test" }),
      "GRANT_INVALID",
    ],
    ["aud sai", () => ({ aud: "security-mcp" }), "GRANT_INVALID"],
    ["sub không phải caller", () => ({ sub: "someone_else" }), "GRANT_INVALID"],
    [
      "contract_version 0.2",
      () => ({ contract_version: "0.2" }),
      "GRANT_INVALID",
    ],
    ["claim lạ", () => ({ extra_claim: "x" }), "GRANT_INVALID"],
    [
      "payload_hash chữ hoa",
      (_t) => ({
        payload_hash: payloadHash(bindingOf(spec("k_claim"))).toUpperCase(),
      }),
      "GRANT_INVALID",
    ],
    [
      "hết hạn quá 30 giây",
      (t) => ({ iat: t - 200, nbf: t - 200, exp: t - 31 }),
      "GRANT_EXPIRED",
    ],
    [
      "nbf ở tương lai quá 30 giây",
      (t) => ({ iat: t, nbf: t + 31, exp: t + 120 }),
      "GRANT_INVALID",
    ],
    [
      "iat và nbf ở tương lai quá 30 giây",
      (t) => ({ iat: t + 31, nbf: t + 31, exp: t + 120 }),
      "GRANT_INVALID",
    ],
    [
      "thời hạn quá 300 giây",
      (t) => ({ iat: t, nbf: t, exp: t + 301 }),
      "GRANT_INVALID",
    ],
    [
      "nbf trước iat",
      (t) => ({ iat: t, nbf: t - 5, exp: t + 120 }),
      "GRANT_INVALID",
    ],
    ["exp không sau nbf", (t) => ({ iat: t, nbf: t, exp: t }), "GRANT_INVALID"],
    [
      "action của tool khác",
      () => ({ action: "cancel_dispatch" }),
      "GRANT_INVALID",
    ],
    [
      "actor khác actor đã duyệt",
      () => ({ actor: { actor_id: "usr_other", actor_type: "HUMAN" } }),
      "GRANT_INVALID",
    ],
    [
      "proposal_id khác bản đã duyệt",
      () => ({ proposal_id: "prop_other" }),
      "GRANT_INVALID",
    ],
  ];
  test.each(claimCases)("%s → %s", async (_label, patch, code) => {
    const token = await h.grant(spec("k_claim"), patch(now()));
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_claim"), { token }),
      code,
    );
  });

  for (const claim of [
    "iss",
    "aud",
    "sub",
    "jti",
    "iat",
    "nbf",
    "exp",
    "payload_hash",
    "actor",
    "proposal_id",
  ]) {
    test(`thiếu claim ${claim} → GRANT_INVALID`, async () => {
      const token = await signRaw(
        h.header(),
        h.claimsFor(spec("k_drop"), {}, [claim]),
      );
      await expectRefusedWithoutSideEffect(
        await h.write(spec("k_drop"), { token }),
        "GRANT_INVALID",
      );
    });
  }

  test.each([
    ["tenant", { tenant_id: "tenant_other" }],
    ["property", { property_id: "property_other" }],
    ["ticket", { ticket_id: "tkt_other" }],
    ["task", { task_id: "task_other" }],
  ] as const)(
    "grant lệch %s của phiên → SCOPE_MISMATCH",
    async (_label, patch) => {
      const token = await h.grant(spec("k_scope"), patch);
      await expectRefusedWithoutSideEffect(
        await h.write(spec("k_scope"), { token }),
        "SCOPE_MISMATCH",
      );
    },
  );

  test("sửa arguments sau khi duyệt → GRANT_INVALID", async () => {
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_tamper"), {
        sentArgs: { ...DISPATCH, guard_id: "guard_002" },
      }),
      "GRANT_INVALID",
    );
    expect(
      (await h.read("get_guard_status", { guard_id: "guard_002" })).data.status,
    ).toBe("AVAILABLE");
  });

  test("thêm field optional sau khi duyệt cũng đổi hash → GRANT_INVALID", async () => {
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_add"), {
        sentArgs: { ...DISPATCH, instruction: "Thêm sau duyệt" },
      }),
      "GRANT_INVALID",
    );
  });

  test("Idempotency-Key ở header lệch claim → GRANT_INVALID", async () => {
    const token = await h.grant(spec("k_claimkey"));
    await expectRefusedWithoutSideEffect(
      await h.write(spec("k_claimkey"), { token, headerKey: "k_header_khac" }),
      "GRANT_INVALID",
    );
  });

  test("grant của tool này dùng cho tool khác → GRANT_INVALID", async () => {
    const token = await h.grant(spec("k_cross"));
    const cancel = {
      action: "cancel_dispatch" as const,
      args: {
        dispatch_id: "dsp_0003",
        expected_version: 3,
        reason: "Dùng nhầm grant",
      },
      key: "k_cross",
    };
    const env = await h.write(cancel, { token });
    expectFailure(env, "GRANT_INVALID");
    expect(
      (await h.read("get_dispatch", { dispatch_id: "dsp_0003" })).data.status,
    ).toBe("ON_SITE");
  });

  test("caller chỉ có READ gọi WRITE → AUTH_ERROR trước khi xét grant", async () => {
    const { callTool } = await import("../../src/security-tools/tools");
    const id = h.identity(session(), await h.grant(spec("k_read")), "k_read");
    const res = await callTool(
      "dispatch_guard",
      DISPATCH,
      { ...id, caller: { ...id.caller, modes: new Set(["READ"]) } },
      {
        provider: h.provider,
        writeGuard: (await import("./helpers/write-harness")).writeGuard,
        now: h.clock.now,
        onOutputRejected: () => {},
      },
    );
    expectFailure(res.structuredContent as Row, "AUTH_ERROR");
  });
});

describe("R2: JCS và payload_hash (RFC 8785, tập giá trị của ActionBinding)", () => {
  test("key sắp theo code unit UTF-16, không theo code point", () => {
    const out = canonicalize({ דּ: 1, "\u{1F600}": 2, b: 3, ö: 4, a: 5 });
    expect(out).toBe('{"a":5,"b":3,"ö":4,"\u{1F600}":2,"דּ":1}');
  });

  test("Unicode giữ nguyên, ký tự điều khiển escape như JSON.stringify, không chuẩn hóa NFC", () => {
    expect(canonicalize({ note: "Hoàng — tầng B2" })).toBe(
      '{"note":"Hoàng — tầng B2"}',
    );
    expect(canonicalize("a\u000fb\n")).toBe('"a\\u000fb\\n"');
    expect(canonicalize("Huỳ")).not.toBe(canonicalize("Huỳ"));
  });

  test("-0 thành 0, integer an toàn giữ nguyên", () => {
    expect(canonicalize(-0)).toBe("0");
    expect(canonicalize({ v: 9007199254740991, z: 0, n: -1 })).toBe(
      '{"n":-1,"v":9007199254740991,"z":0}',
    );
  });

  test.each([
    ["số thực", 1.5],
    ["ngoài miền an toàn", 2 ** 53],
    ["NaN", Number.NaN],
    ["Infinity", Number.POSITIVE_INFINITY],
    ["null", null],
    ["undefined", undefined],
    ["surrogate lẻ trong string", "x\uD800"],
    ["surrogate lẻ trong key", { "\uDC00": 1 }],
    ["object không thuần", new Date(0)],
    ["lồng quá sâu", JSON.parse(`${"[".repeat(40)}1${"]".repeat(40)}`)],
  ])("từ chối %s", (_label, value) => {
    expect(() => canonicalize(value)).toThrow(CanonicalizeError);
  });

  test("thứ tự key không đổi hash; đổi bất kỳ field nào thì đổi hash", () => {
    const base = bindingOf(spec("k_hash"));
    const reordered = Object.fromEntries(
      Object.entries(base).reverse(),
    ) as typeof base;
    expect(payloadHash(reordered)).toBe(payloadHash(base));
    for (const changed of [
      { ...base, arguments: { ...DISPATCH, guard_id: "guard_002" } },
      { ...base, arguments: { ...DISPATCH, incident_version: 7 } },
      { ...base, idempotency_key: "k_other" },
      { ...base, ticket_id: "tkt_other" },
      { ...base, actor: { ...ACTOR, actor_id: "usr_other" } },
    ]) {
      expect(payloadHash(changed)).not.toBe(payloadHash(base));
    }
  });

  test("payload_hash là SHA-256 hex chữ thường của JCS(binding) mã hóa UTF-8", () => {
    const binding = bindingOf(
      spec("k_hex", { ...DISPATCH, instruction: "Kiểm tra cổng" }),
    );
    expect(payloadHash(binding)).toBe(sha256(canonicalize(binding)));
    expect(payloadHash(binding)).toMatch(/^[0-9a-f]{64}$/);
  });

  test("vector dùng chung: canonical và SHA-256 khớp cho cả 6 action WRITE", () => {
    const vectors: {
      name: string;
      input: unknown;
      canonical: string;
      sha256: string;
    }[] = JSON.parse(
      readFileSync(
        new URL("./fixtures/jcs-vectors.json", import.meta.url),
        "utf8",
      ),
    );
    expect(vectors.map((v) => v.name.replace("binding_", "")).sort()).toEqual([
      "acknowledge_emergency",
      "cancel_dispatch",
      "create_incident",
      "dispatch_guard",
      "escalate_emergency",
      "update_incident",
    ]);
    for (const v of vectors) {
      expect(canonicalize(v.input)).toBe(v.canonical);
      expect(payloadHash(v.input as never)).toBe(v.sha256);
    }
  });
});
