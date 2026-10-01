/**
 * Danh tính caller và context sau authentication (spec v0.3 §3.1).
 *
 * ReadContext/WriteContext là DTO nội bộ, chỉ dựng từ access token đã verify; không bao giờ lấy từ
 * arguments, `_meta` hay header scope thô (X-Tenant-Id...). Grant và Idempotency-Key giữ nguyên
 * dạng thô để common/execution-grant.ts verify, ở đây không tự diễn giải.
 */
import { createRemoteJWKSet, errors as joseErrors, type JWTPayload, type JWTVerifyGetKey, jwtVerify } from "jose";
import { fail, type ToolMode } from "./errors";

export type Actor = {
  actor_id: string;
  actor_type: "HUMAN" | "SERVICE";
};

export type ReadContext = {
  tenant_id: string;
  property_id: string;
  /** READ không bắt buộc ticket/task; task khác null thì ticket phải khác null. */
  ticket_id: string | null;
  task_id: string | null;
  correlation_id: string;
  principal_id: string;
};

export type WriteContext = {
  tenant_id: string;
  property_id: string;
  ticket_id: string;
  task_id: string;
  correlation_id: string;
  principal_id: string;
};

/** Caller đã xác thực. Chỉ index.ts tạo, sau khi verify access token. */
export type AuthenticatedCaller = {
  principal_id: string;
  tenant_id: string;
  property_id: string;
  ticket_id: string | null;
  task_id: string | null;
  /** Mode tool được phép gọi, từ claim `scope`. ActionExecutor là principal duy nhất có WRITE. */
  modes: ReadonlySet<ToolMode>;
};

/** Hai header WRITE ở dạng thô; null khi request không gửi. */
export type RawWriteHeaders = {
  execution_grant: string | null;
  idempotency_key: string | null;
};

/** Mọi thứ wrapper cần về một HTTP request đã qua authentication. */
export type RequestIdentity = {
  caller: AuthenticatedCaller;
  correlation_id: string;
  write_headers: RawWriteHeaders;
};

/** Giá trị `scope` trong access token tương ứng từng mode tool. */
export const SECURITY_SCOPES: Readonly<Record<ToolMode, string>> = {
  READ: "security:read",
  WRITE: "security:write",
};

export const HEADERS = {
  correlationId: "x-correlation-id",
  executionGrant: "x-security-execution-grant",
  idempotencyKey: "idempotency-key",
} as const;

const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

export const isId = (value: unknown): value is string => typeof value === "string" && ID_PATTERN.test(value);

export function readContext(identity: RequestIdentity): ReadContext {
  const { caller } = identity;
  return {
    tenant_id: caller.tenant_id,
    property_id: caller.property_id,
    ticket_id: caller.ticket_id,
    task_id: caller.task_id,
    correlation_id: identity.correlation_id,
    principal_id: caller.principal_id,
  };
}

/** WRITE cần ticket và task trong context tin cậy; thiếu thì không gửi command. */
export function writeContext(identity: RequestIdentity): WriteContext {
  const { caller } = identity;
  if (caller.ticket_id === null || caller.task_id === null) {
    fail("AUTH_ERROR", "Access token không có ticket/task nên không được gọi WRITE.", { mode: "WRITE" });
  }
  return {
    tenant_id: caller.tenant_id,
    property_id: caller.property_id,
    ticket_id: caller.ticket_id,
    task_id: caller.task_id,
    correlation_id: identity.correlation_id,
    principal_id: caller.principal_id,
  };
}

/** Gateway gửi X-Correlation-Id; sai format hoặc thiếu thì MCP tự tạo. Chỉ để trace, không cấp quyền. */
export function correlationIdFrom(headers: Headers): string {
  const value = headers.get(HEADERS.correlationId);
  return isId(value) ? value : `corr_${crypto.randomUUID()}`;
}

export function rawWriteHeaders(headers: Headers): RawWriteHeaders {
  return {
    execution_grant: headers.get(HEADERS.executionGrant),
    idempotency_key: headers.get(HEADERS.idempotencyKey),
  };
}

// ---------------------------------------------------------------------------------------------
// Access token
// ---------------------------------------------------------------------------------------------

export type AccessTokenConfig = {
  /** Issuer được tin, so khớp chính xác. */
  issuers: readonly string[];
  /** Audience của resource server này (MCP Authorization: token phải đúng audience). */
  audience: string;
  /** JWKS của issuer: URL HTTPS cấu hình sẵn, hoặc key resolver (test dùng createLocalJWKSet). */
  keys: URL | JWTVerifyGetKey;
  algorithms?: readonly string[];
  /** Lệch đồng hồ cho phép, giây. Mặc định 30 như grant (§4). */
  clockToleranceSec?: number;
};

export class AuthenticationError extends Error {
  constructor(
    /** 401: không có/không verify được token. 403: token hợp lệ nhưng không có quyền Security MCP. */
    readonly status: 401 | 403,
    message: string,
  ) {
    super(message);
    this.name = "AuthenticationError";
  }
}

export type AccessTokenVerifier = (authorization: string | null) => Promise<AuthenticatedCaller>;

/**
 * Verify `Authorization: Bearer <access-token>` do trusted gateway mint.
 *
 * Claim bắt buộc: sub, tenant_id, property_id, scope. ticket_id/task_id có thể thiếu hoặc null.
 * Một token chỉ một tenant/property; caller không tự mở rộng scope.
 */
export function createAccessTokenVerifier(config: AccessTokenConfig): AccessTokenVerifier {
  if (config.keys instanceof URL && config.keys.protocol !== "https:") {
    throw new Error("JWKS URL của access token phải là HTTPS");
  }
  const getKey = config.keys instanceof URL ? createRemoteJWKSet(config.keys) : config.keys;
  const options = {
    issuer: [...config.issuers],
    audience: config.audience,
    algorithms: [...(config.algorithms ?? ["ES256", "RS256"])],
    clockTolerance: config.clockToleranceSec ?? 30,
    requiredClaims: ["sub", "exp"],
  };

  return async (authorization) => {
    const token = bearerToken(authorization);
    let payload: JWTPayload;
    try {
      ({ payload } = await jwtVerify(token, getKey, options));
    } catch (error) {
      // Không trả chi tiết lý do (alg/kid/issuer) cho caller.
      if (error instanceof joseErrors.JOSEError) throw new AuthenticationError(401, "Access token không hợp lệ.");
      throw error;
    }
    return callerFromClaims(payload);
  };
}

/** Dựng caller từ claims đã verify chữ ký. Tách riêng để test không cần ký token. */
export function callerFromClaims(payload: JWTPayload): AuthenticatedCaller {
  const { sub, tenant_id, property_id } = payload;
  if (!isId(sub) || !isId(tenant_id) || !isId(property_id)) {
    throw new AuthenticationError(401, "Access token thiếu principal hoặc scope tenant/property.");
  }
  const ticket = optionalId(payload.ticket_id);
  const task = optionalId(payload.task_id);
  if (ticket === undefined || task === undefined || (task !== null && ticket === null)) {
    throw new AuthenticationError(401, "ticket_id/task_id trong access token không hợp lệ.");
  }
  const granted = typeof payload.scope === "string" ? new Set(payload.scope.split(" ")) : new Set<string>();
  const modes = new Set<ToolMode>();
  for (const mode of ["READ", "WRITE"] as const) {
    if (granted.has(SECURITY_SCOPES[mode])) modes.add(mode);
  }
  if (modes.size === 0) throw new AuthenticationError(403, "Access token không có quyền Security MCP.");
  return { principal_id: sub, tenant_id, property_id, ticket_id: ticket, task_id: task, modes };
}

function bearerToken(authorization: string | null): string {
  const match = authorization?.match(/^Bearer ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$/);
  if (!match?.[1]) throw new AuthenticationError(401, "Thiếu Bearer access token.");
  return match[1];
}

/** undefined = sai kiểu; null = không có. */
function optionalId(value: unknown): string | null | undefined {
  if (value === undefined || value === null) return null;
  return isId(value) ? value : undefined;
}
