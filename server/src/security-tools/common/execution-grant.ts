/**
 * Verify execution grant và ActionBinding cho WRITE (spec v0.3 §4).
 *
 * `createWriteGuard` trả hàm cắm vào `SecurityToolsOptions.writeGuard` (xem tools.ts). Chuỗi kiểm:
 * header → chữ ký ES256 + iss/aud/typ/thời gian → claims đúng schema → claims khớp context tin cậy,
 * tool và Idempotency-Key → dựng lại ActionBinding từ chính arguments đã validate → so payload_hash.
 * Mọi lỗi fail closed, không có lệnh nào được gửi xuống provider.
 *
 * Không lưu gì: jti, idempotency và approval record thuộc Core (§5). Grant hết hạn nhưng cùng
 * binding/key được platform cấp lại, nên ở đây không có kiểm "jti đã dùng".
 */
import { createHash, timingSafeEqual } from "node:crypto";
import {
  createRemoteJWKSet,
  decodeJwt,
  decodeProtectedHeader,
  errors as joseErrors,
  type JWTVerifyGetKey,
  jwtVerify,
} from "jose";
import { validate } from "../schema/index";
import type { WriteGuard, WriteGuardResult } from "../tools";
import { type Actor, isId } from "./context";
import { type ErrorCode, toolError } from "./errors";

export const GRANT_TYP = "security-execution-grant+jwt";
export const GRANT_AUDIENCE = "security-mcp-write";
export const CONTRACT_VERSION = "0.3";
/** `exp - iat` tối đa, giây (§4). */
export const MAX_GRANT_LIFETIME_SEC = 300;
/** Lệch đồng hồ cho phép, giây; cố định, không nới theo request (§4). */
export const CLOCK_SKEW_SEC = 30;
/** WriteMetadata.execution_grant tối đa 8192 ký tự. */
const MAX_GRANT_LENGTH = 8192;

const GRANT_CLAIMS_REF = "common.schema.json#/$defs/GrantClaims";
const ACTION_BINDING_REF = "common.schema.json#/$defs/ActionBinding";

export type WriteAction =
  | "create_incident"
  | "update_incident"
  | "dispatch_guard"
  | "cancel_dispatch"
  | "escalate_emergency"
  | "acknowledge_emergency";

/** Payload của grant sau khi verify. Nguồn cấu trúc: common.schema.json#/$defs/GrantClaims. */
export type GrantClaims = {
  iss: string;
  aud: typeof GRANT_AUDIENCE;
  sub: string;
  jti: string;
  iat: number;
  nbf: number;
  exp: number;
  contract_version: typeof CONTRACT_VERSION;
  tenant_id: string;
  property_id: string;
  ticket_id: string;
  task_id: string;
  actor: Actor;
  proposal_id: string;
  action: WriteAction;
  idempotency_key: string;
  /** SHA-256 lowercase hex của JCS(ActionBinding). */
  payload_hash: string;
};

/** Thứ platform đã duyệt. Nguồn cấu trúc: common.schema.json#/$defs/ActionBinding. */
export type ActionBinding = {
  contract_version: typeof CONTRACT_VERSION;
  proposal_id: string;
  tenant_id: string;
  property_id: string;
  ticket_id: string;
  task_id: string;
  actor: Actor;
  action: WriteAction;
  idempotency_key: string;
  arguments: Record<string, unknown>;
};

// ---------------------------------------------------------------------------------------------
// Canonicalization (RFC 8785 JCS) và hash
// ---------------------------------------------------------------------------------------------

export class CanonicalizeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CanonicalizeError";
  }
}

const MAX_DEPTH = 32;

/**
 * JCS cho đúng tập giá trị của ActionBinding: object, mảng, string, integer an toàn, boolean.
 * Với tập này JCS là: key sắp theo thứ tự code unit UTF-16, string theo serialization của ECMAScript
 * (RFC 8785 §3.2.2), integer in thập phân không dấu cộng. Mọi thứ ngoài tập đó bị từ chối thay vì
 * đoán: số thực, số ngoài miền an toàn, NaN/Infinity, null (không hợp lệ ở WRITE input), Unicode
 * không hợp lệ (surrogate lẻ).
 *
 * Hash đúng arguments đã validate. Không default, trim hay coerce trước khi gọi hàm này.
 */
export function canonicalize(value: unknown): string {
  return serialize(value, 0);
}

function serialize(value: unknown, depth: number): string {
  if (depth > MAX_DEPTH) throw new CanonicalizeError("Dữ liệu lồng quá sâu");
  switch (typeof value) {
    case "string":
      if (!value.isWellFormed())
        throw new CanonicalizeError("Unicode không hợp lệ");
      return JSON.stringify(value);
    case "number":
      if (!Number.isSafeInteger(value))
        throw new CanonicalizeError("Số phải là integer trong miền an toàn");
      return String(value); // -0 thành "0", đúng JCS
    case "boolean":
      return value ? "true" : "false";
    case "object": {
      if (value === null) throw new CanonicalizeError("null không hợp lệ");
      if (Array.isArray(value)) {
        const items: string[] = [];
        for (let i = 0; i < value.length; i++)
          items.push(serialize(value[i], depth + 1));
        return `[${items.join(",")}]`;
      }
      const prototype = Object.getPrototypeOf(value);
      if (prototype !== Object.prototype && prototype !== null)
        throw new CanonicalizeError("Chỉ nhận object thuần");
      const record = value as Record<string, unknown>;
      // sort() mặc định so theo code unit UTF-16, đúng thứ tự JCS yêu cầu.
      const members = Object.keys(record)
        .sort()
        .map((key) => {
          if (!key.isWellFormed())
            throw new CanonicalizeError("Unicode không hợp lệ");
          return `${JSON.stringify(key)}:${serialize(record[key], depth + 1)}`;
        });
      return `{${members.join(",")}}`;
    }
    default:
      throw new CanonicalizeError(`Kiểu ${typeof value} không có trong JSON`);
  }
}

/** payload_hash: JCS → UTF-8 → SHA-256 → hex chữ thường (§4). */
export function payloadHash(binding: ActionBinding): string {
  return createHash("sha256")
    .update(canonicalize(binding), "utf8")
    .digest("hex");
}

function sameHash(a: string, b: string): boolean {
  const left = Buffer.from(a, "hex");
  const right = Buffer.from(b, "hex");
  return left.length === right.length && timingSafeEqual(left, right);
}

// ---------------------------------------------------------------------------------------------
// Write guard
// ---------------------------------------------------------------------------------------------

/**
 * Public key của một issuer: JWKS URL HTTPS cấu hình sẵn (cache, refresh khi gặp kid mới do jose xử
 * lý, fail closed khi không verify được), hoặc key resolver (test dùng createLocalJWKSet).
 * URL không bao giờ lấy từ request/token.
 */
export type IssuerKeys = URL | JWTVerifyGetKey;

export type GrantVerifierConfig = {
  /**
   * Allowlist issuer, mỗi issuer đi với key riêng của nó (§4: JWKS theo issuer allowlist). `iss` so
   * khớp chính xác; grant ghi issuer này chỉ được verify bằng key của issuer đó.
   */
  issuers: Readonly<Record<string, IssuerKeys>>;
};

const ALLOWED_HEADER_PARAMS = new Set(["alg", "typ", "kid"]);

export function createWriteGuard(config: GrantVerifierConfig): WriteGuard {
  const resolvers = new Map<string, JWTVerifyGetKey>();
  for (const [issuer, keys] of Object.entries(config.issuers)) {
    if (keys instanceof URL && keys.protocol !== "https:") {
      throw new Error("JWKS URL của execution grant phải là HTTPS");
    }
    resolvers.set(
      issuer,
      keys instanceof URL ? createRemoteJWKSet(keys) : keys,
    );
  }
  if (resolvers.size === 0)
    throw new Error("Cần ít nhất một issuer cho execution grant");

  return async (request) => {
    const { context, headers, tool, now } = request;
    const reject = (code: ErrorCode, message: string): WriteGuardResult => ({
      ok: false,
      error: toolError(code, message, { mode: "WRITE" }),
    });

    const token = headers.execution_grant;
    if (token === null || token === "")
      return reject("GRANT_MISSING", "Thiếu execution grant.");
    const key = headers.idempotency_key;
    if (key === null || !isId(key))
      return reject(
        "VALIDATION_ERROR",
        "Idempotency-Key thiếu hoặc sai định dạng.",
      );
    if (token.length > MAX_GRANT_LENGTH)
      return reject("GRANT_INVALID", "Execution grant không hợp lệ.");

    // Header chặt: đúng alg/typ/kid, không có jku/x5u/jwk/crit hay tham số lạ.
    let header: ReturnType<typeof decodeProtectedHeader>;
    try {
      header = decodeProtectedHeader(token);
    } catch {
      return reject("GRANT_INVALID", "Execution grant không hợp lệ.");
    }
    const headerOk =
      header.alg === "ES256" &&
      header.typ === GRANT_TYP &&
      typeof header.kid === "string" &&
      header.kid.length > 0 &&
      Object.keys(header).every((name) => ALLOWED_HEADER_PARAMS.has(name));
    if (!headerOk)
      return reject("GRANT_INVALID", "Execution grant không hợp lệ.");

    // `iss` đọc trước khi verify chỉ để chọn key của issuer; jwtVerify bên dưới ép khớp chính xác và
    // chữ ký phải đúng key đó, nên grant không thể mượn key của issuer khác.
    let issuer: string | undefined;
    try {
      issuer = decodeJwt(token).iss;
    } catch {
      return reject("GRANT_INVALID", "Execution grant không hợp lệ.");
    }
    const getKey =
      typeof issuer === "string" ? resolvers.get(issuer) : undefined;
    if (issuer === undefined || getKey === undefined)
      return reject("GRANT_INVALID", "Execution grant không hợp lệ.");

    let payload: Record<string, unknown>;
    try {
      ({ payload } = await jwtVerify(token, getKey, {
        algorithms: ["ES256"],
        typ: GRANT_TYP,
        issuer,
        audience: GRANT_AUDIENCE,
        currentDate: now,
        clockTolerance: CLOCK_SKEW_SEC,
        requiredClaims: ["iss", "aud", "sub", "jti", "iat", "nbf", "exp"],
      }));
    } catch (error) {
      if (error instanceof joseErrors.JWTExpired)
        return reject("GRANT_EXPIRED", "Execution grant đã hết hạn.");
      // Mọi lỗi còn lại, kể cả không lấy được key, đều fail closed. Không lộ lý do cho caller.
      return reject("GRANT_INVALID", "Execution grant không hợp lệ.");
    }

    // Claims: id, hằng số (aud, contract_version), payload_hash, field lạ... đều do schema kiểm.
    if (!validate(GRANT_CLAIMS_REF, payload).ok)
      return reject("GRANT_INVALID", "Execution grant không hợp lệ.");
    const claims = payload as unknown as GrantClaims;

    const nowSec = Math.floor(now.getTime() / 1000);
    const timeError = checkTimes(claims, nowSec);
    if (timeError)
      return reject(
        timeError,
        timeError === "GRANT_EXPIRED"
          ? "Execution grant đã hết hạn."
          : "Execution grant không hợp lệ.",
      );

    if (claims.sub !== context.principal_id)
      return reject("GRANT_INVALID", "Grant không cấp cho caller này.");
    if (
      claims.tenant_id !== context.tenant_id ||
      claims.property_id !== context.property_id ||
      claims.ticket_id !== context.ticket_id ||
      claims.task_id !== context.task_id
    ) {
      return reject("SCOPE_MISMATCH", "Grant không khớp scope của phiên.");
    }
    if (claims.action !== tool)
      return reject("GRANT_INVALID", "Grant không cấp cho action này.");
    if (claims.idempotency_key !== key)
      return reject("GRANT_INVALID", "Idempotency-Key không khớp grant.");

    // Dựng lại binding từ claims đã verify + đúng arguments sẽ gửi provider, rồi so hash.
    const binding: ActionBinding = {
      contract_version: claims.contract_version,
      proposal_id: claims.proposal_id,
      tenant_id: claims.tenant_id,
      property_id: claims.property_id,
      ticket_id: claims.ticket_id,
      task_id: claims.task_id,
      actor: claims.actor,
      action: claims.action,
      idempotency_key: claims.idempotency_key,
      arguments: request.arguments,
    };
    if (!validate(ACTION_BINDING_REF, binding).ok)
      return reject("VALIDATION_ERROR", "ActionBinding không hợp lệ.");
    let hash: string;
    try {
      hash = payloadHash(binding);
    } catch (error) {
      if (error instanceof CanonicalizeError)
        return reject(
          "VALIDATION_ERROR",
          `Arguments không canonicalize được: ${error.message}.`,
        );
      throw error;
    }
    if (!sameHash(hash, claims.payload_hash))
      return reject("GRANT_INVALID", "Payload không khớp grant đã duyệt.");

    return {
      ok: true,
      write: { context, idempotency_key: key, claims, binding },
    };
  };
}

/** Quy tắc thời gian §4: iat ≤ nbf < exp, exp - iat ≤ 300, iat/nbf ≤ now+30, now < exp+30. */
function checkTimes(
  claims: GrantClaims,
  nowSec: number,
): "GRANT_INVALID" | "GRANT_EXPIRED" | null {
  const { iat, nbf, exp } = claims;
  if (!(iat <= nbf && nbf < exp)) return "GRANT_INVALID";
  if (exp - iat > MAX_GRANT_LIFETIME_SEC) return "GRANT_INVALID";
  if (iat > nowSec + CLOCK_SKEW_SEC || nbf > nowSec + CLOCK_SKEW_SEC)
    return "GRANT_INVALID";
  if (nowSec >= exp + CLOCK_SKEW_SEC) return "GRANT_EXPIRED";
  return null;
}
