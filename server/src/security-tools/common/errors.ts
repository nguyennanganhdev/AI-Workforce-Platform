/**
 * Mã lỗi và ToolError theo spec v0.3 §5.1. Nguồn cấu trúc là common.schema.json#/$defs/ToolError.
 *
 * Gọi `toolError` thay vì tự điền retry/operation_state: bảng §5.1 và schema output của từng tool
 * chỉ chấp nhận một số tổ hợp, điền tay rất dễ lệch.
 */

export type ErrorCode =
  | "VALIDATION_ERROR"
  | "AUTH_ERROR"
  | "SCOPE_MISMATCH"
  | "GRANT_MISSING"
  | "GRANT_EXPIRED"
  | "GRANT_INVALID"
  | "IDEMPOTENCY_CONFLICT"
  | "IDEMPOTENCY_IN_PROGRESS"
  | "IDEMPOTENCY_RESULT_EXPIRED"
  | "INVALID_STATE_TRANSITION"
  | "CONFLICT"
  | "NOT_FOUND"
  | "GUARD_NOT_AVAILABLE"
  | "CONTACT_NOT_AVAILABLE"
  | "EMERGENCY_NOT_ELIGIBLE"
  | "ACK_NOT_AUTHORIZED"
  | "PROVIDER_ERROR"
  | "PROVIDER_TIMEOUT"
  | "PROVIDER_INVALID_RESPONSE"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR";

export type RetryMode = "NEVER" | "BACKOFF" | "SAME_KEY" | "RECONCILE";
export type OperationState =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "UNKNOWN"
  | "FAILED";
export type ToolMode = "READ" | "WRITE";

export type ToolError = {
  code: ErrorCode;
  message: string;
  retry: RetryMode;
  /** Chỉ khác null khi retry là BACKOFF hoặc SAME_KEY. */
  retry_after_ms: number | null;
  operation_state: OperationState;
};

/** Các mã mà retry/operation_state phụ thuộc mode tool và việc đã biết kết quả commit hay chưa. */
export const PROVIDER_ERROR_CODES = [
  "PROVIDER_TIMEOUT",
  "PROVIDER_ERROR",
  "PROVIDER_INVALID_RESPONSE",
  "INTERNAL_ERROR",
] as const satisfies readonly ErrorCode[];

export type ToolErrorOptions = {
  /**
   * Mode của tool đang chạy. Chỉ ảnh hưởng PROVIDER_* và INTERNAL_ERROR; bỏ trống coi là READ.
   * Wrapper luôn truyền mode, provider WRITE cũng phải truyền.
   */
  mode?: ToolMode;
  /**
   * Chỉ dùng cho WRITE + PROVIDER_ERROR: "NOT_COMMITTED" khi Core xác nhận chắc chắn không commit
   * (NEVER/FAILED). Mặc định "UNKNOWN": chưa biết kết quả, executor phải đối soát (RECONCILE/UNKNOWN).
   * PROVIDER_TIMEOUT, PROVIDER_INVALID_RESPONSE, INTERNAL_ERROR ở WRITE luôn là chưa biết kết quả.
   */
  outcome?: "UNKNOWN" | "NOT_COMMITTED";
  /** RATE_LIMITED: thời gian chờ server cấp, 0–60000. Mặc định 1000. */
  retryAfterMs?: number;
};

const MAX_MESSAGE = 2000;
const MAX_RETRY_AFTER_MS = 60_000;
const IN_PROGRESS_RETRY_AFTER_MS = 1000;

type Policy = Pick<ToolError, "retry" | "retry_after_ms" | "operation_state">;

const NEVER_NOT_STARTED: Policy = {
  retry: "NEVER",
  retry_after_ms: null,
  operation_state: "NOT_STARTED",
};
const NEVER_FAILED: Policy = {
  retry: "NEVER",
  retry_after_ms: null,
  operation_state: "FAILED",
};
const RECONCILE_UNKNOWN: Policy = {
  retry: "RECONCILE",
  retry_after_ms: null,
  operation_state: "UNKNOWN",
};

/** Bảng §5.1. Không có default: thêm ErrorCode mới mà quên ở đây sẽ lỗi typecheck. */
export function retryPolicy(
  code: ErrorCode,
  options: ToolErrorOptions = {},
): Policy {
  const write = options.mode === "WRITE";
  switch (code) {
    case "VALIDATION_ERROR":
    case "AUTH_ERROR":
    case "SCOPE_MISMATCH":
    case "GRANT_MISSING":
    case "GRANT_EXPIRED":
    case "GRANT_INVALID":
    case "IDEMPOTENCY_CONFLICT":
    case "NOT_FOUND":
      return NEVER_NOT_STARTED;
    case "INVALID_STATE_TRANSITION":
    case "CONFLICT":
    case "GUARD_NOT_AVAILABLE":
    case "CONTACT_NOT_AVAILABLE":
    case "EMERGENCY_NOT_ELIGIBLE":
    case "ACK_NOT_AUTHORIZED":
      return NEVER_FAILED;
    case "IDEMPOTENCY_IN_PROGRESS":
      // Schema cố định 1000ms cho mã này.
      return {
        retry: "SAME_KEY",
        retry_after_ms: IN_PROGRESS_RETRY_AFTER_MS,
        operation_state: "IN_PROGRESS",
      };
    case "IDEMPOTENCY_RESULT_EXPIRED":
      return RECONCILE_UNKNOWN;
    case "RATE_LIMITED":
      return {
        retry: "BACKOFF",
        retry_after_ms: clampRetryAfter(options.retryAfterMs),
        operation_state: "NOT_STARTED",
      };
    case "PROVIDER_TIMEOUT":
      // READ chưa có side effect nên thử lại được; WRITE không biết đã commit chưa.
      return write ? RECONCILE_UNKNOWN : backoff();
    case "PROVIDER_ERROR":
      if (!write) return backoff();
      return options.outcome === "NOT_COMMITTED"
        ? NEVER_FAILED
        : RECONCILE_UNKNOWN;
    case "PROVIDER_INVALID_RESPONSE":
    case "INTERNAL_ERROR":
      // Response hỏng có thể xảy ra sau commit; không tạo thất bại chắc chắn cho WRITE.
      return write ? RECONCILE_UNKNOWN : NEVER_NOT_STARTED;
  }
}

/** Tạo ToolError với retry/operation_state/retry_after_ms đúng §5.1. */
export function toolError(
  code: ErrorCode,
  message: string,
  options: ToolErrorOptions = {},
): ToolError {
  return {
    code,
    message: clampMessage(message),
    ...retryPolicy(code, options),
  };
}

/** Đổi mode của một ToolError đã có (ví dụ lỗi provider tạo ở READ được dùng lại cho WRITE). */
export function withMode(error: ToolError, mode: ToolMode): ToolError {
  return toolError(error.code, error.message, {
    mode,
    outcome: error.operation_state === "FAILED" ? "NOT_COMMITTED" : "UNKNOWN",
    retryAfterMs: error.retry_after_ms ?? undefined,
  });
}

/**
 * Lỗi mang ToolError để throw trong wrapper/provider. Message đã an toàn để trả cho caller;
 * không đưa raw body, stack hay dữ liệu provider vào đây.
 */
export class ToolFailure extends Error {
  constructor(readonly error: ToolError) {
    super(error.message);
    this.name = "ToolFailure";
  }
}

export function fail(
  code: ErrorCode,
  message: string,
  options?: ToolErrorOptions,
): never {
  throw new ToolFailure(toolError(code, message, options));
}

/** Exception lạ thành INTERNAL_ERROR với message cố định, không lộ chi tiết nội bộ. */
export function toToolError(error: unknown, mode: ToolMode): ToolError {
  if (error instanceof ToolFailure) return error.error;
  return toolError("INTERNAL_ERROR", "Lỗi nội bộ khi xử lý tool.", { mode });
}

function backoff(): Policy {
  return {
    retry: "BACKOFF",
    retry_after_ms: IN_PROGRESS_RETRY_AFTER_MS,
    operation_state: "NOT_STARTED",
  };
}

function clampRetryAfter(value: number | undefined): number {
  if (value === undefined || !Number.isFinite(value))
    return IN_PROGRESS_RETRY_AFTER_MS;
  return Math.min(MAX_RETRY_AFTER_MS, Math.max(0, Math.round(value)));
}

function clampMessage(message: string): string {
  const trimmed = message.trim();
  if (trimmed.length === 0) return "Lỗi không có mô tả.";
  return trimmed.length > MAX_MESSAGE
    ? `${cutAtCodePoint(trimmed, MAX_MESSAGE - 1)}…`
    : trimmed;
}

/** Cắt không để lại nửa cặp surrogate: Unicode không hợp lệ làm hỏng JSON/JCS phía sau. */
export function cutAtCodePoint(text: string, maxLength: number): string {
  const cut = text.slice(0, maxLength);
  const last = cut.charCodeAt(cut.length - 1);
  return last >= 0xd800 && last <= 0xdbff ? cut.slice(0, -1) : cut;
}
