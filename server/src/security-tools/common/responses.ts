/**
 * Envelope chung của mọi tool (từ điển schema §3, spec §3.2).
 *
 * Success READ: evidence=null. Success WRITE: evidence=WriteEvidence bắt buộc. Failure: data=null,
 * evidence=null, error=ToolError. `meta.executed_at` là lúc trả response; thời điểm commit nằm trong
 * evidence và không đổi khi replay.
 */
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { validate } from "../schema";
import { type ToolError, type ToolMode, toolError } from "./errors";

export type WriteEvidence = {
  evidence_id: string;
  provider: string;
  provider_reference_id: string;
  committed_at: string;
};

export type ResponseMeta = {
  correlation_id: string;
  executed_at: string;
  /** true khi trả lại kết quả của commit trước cùng idempotency key. */
  replayed: boolean;
};

export type ReadSuccess<T> = {
  success: true;
  data: T;
  evidence: null;
  error: null;
  meta: ResponseMeta;
};
export type WriteSuccess<T> = {
  success: true;
  data: T;
  evidence: WriteEvidence;
  error: null;
  meta: ResponseMeta;
};
export type Failure = {
  success: false;
  data: null;
  evidence: null;
  error: ToolError;
  meta: ResponseMeta;
};
export type ToolResponse<T = unknown> =
  | ReadSuccess<T>
  | WriteSuccess<T>
  | Failure;

/** Timestamp contract: UTC, đúng 3 chữ số mili giây. */
export const timestamp = (date: Date = new Date()): string =>
  date.toISOString();

export function responseMeta(
  correlationId: string,
  options: { replayed?: boolean; now?: Date } = {},
): ResponseMeta {
  return {
    correlation_id: correlationId,
    executed_at: timestamp(options.now),
    replayed: options.replayed ?? false,
  };
}

export function readSuccess<T>(data: T, meta: ResponseMeta): ReadSuccess<T> {
  return {
    success: true,
    data,
    evidence: null,
    error: null,
    meta: { ...meta, replayed: false },
  };
}

/** `meta.replayed` lấy từ provider/idempotency, không tự suy ở đây. */
export function writeSuccess<T>(
  data: T,
  evidence: WriteEvidence,
  meta: ResponseMeta,
): WriteSuccess<T> {
  return { success: true, data, evidence, error: null, meta };
}

export function failure(error: ToolError, meta: ResponseMeta): Failure {
  return { success: false, data: null, evidence: null, error, meta };
}

export type OutputContract = {
  name: string;
  mode: ToolMode;
  outputSchema: string;
};

export type FinalizedResponse = {
  response: ToolResponse;
  /** Lý do response gốc bị thay (đường dẫn + keyword, không có giá trị) để log; rỗng nếu hợp lệ. */
  issues: string[];
};

/**
 * Validate toàn bộ envelope theo output schema của tool trước khi trả.
 *
 * Envelope đi qua một vòng JSON trước khi validate, nên thứ được validate cũng chính là thứ được
 * serialize: không còn undefined, getter, toJSON hay prototype lạ lọt qua. Không hợp lệ thì
 * thay bằng Failure PROVIDER_INVALID_RESPONSE (success từ provider) hoặc INTERNAL_ERROR (failure do
 * MCP tự tạo sai), không bao giờ trả success giả. `runtimeIssues` là kiểm tra thêm mà JSON Schema
 * không diễn đạt được (ví dụ camera boundary), chỉ chạy cho success.
 */
export function finalizeResponse(
  contract: OutputContract,
  response: ToolResponse,
  runtimeIssues?: (data: unknown) => string[],
): FinalizedResponse {
  const plain = JSON.parse(JSON.stringify(response)) as ToolResponse;
  const checked = validate(contract.outputSchema, plain);
  const issues = checked.ok ? [] : checked.issues;
  if (checked.ok && plain.success && runtimeIssues)
    issues.push(...runtimeIssues(plain.data));
  if (issues.length === 0) return { response: plain, issues };

  const code = response.success
    ? "PROVIDER_INVALID_RESPONSE"
    : "INTERNAL_ERROR";
  const message = response.success
    ? `Dữ liệu ${contract.name} từ provider không đúng contract.`
    : "Lỗi nội bộ khi tạo response.";
  const replacement = failure(
    toolError(code, message, { mode: contract.mode }),
    { ...plain.meta, replayed: false },
  );
  const fallback = validate(contract.outputSchema, replacement);
  if (!fallback.ok) {
    // Chỉ xảy ra khi meta/correlation_id hỏng: lỗi lập trình của wrapper.
    throw new Error(
      `Không tạo được Failure hợp lệ cho ${contract.name}: ${fallback.issues.join("; ")}`,
    );
  }
  return { response: replacement, issues };
}

/** structuredContent và text là cùng một object đã validate; isError = !success. */
export function toCallToolResult(response: ToolResponse): CallToolResult {
  return {
    structuredContent: response as unknown as Record<string, unknown>,
    content: [{ type: "text", text: JSON.stringify(response) }],
    isError: !response.success,
  };
}
