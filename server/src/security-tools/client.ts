/**
 * Client gọi Core API (spec v0.3 §3.1, §5, §9).
 *
 * - Dùng credential riêng của Security MCP; KHÔNG chuyển tiếp access token của caller lên Core.
 * - Mỗi query mang ReadContext đã xác thực; Core tự lọc scope tenant/property, join và cursor.
 * - Request Core tối đa 20 giây và không vượt deadline của wrapper.
 * - Lỗi trả caller dùng message cố định theo mã, không chép body/message của Core.
 *
 * Spec chưa chốt URL Core ("tên hợp đồng, không giả định URL thực tế"); wire format dưới đây là
 * giả định của bản này, đổi ở một chỗ khi Core công bố endpoint:
 *
 *   POST {baseUrl}/security/v0.3/query
 *   body    { "context": ReadContext, "tool_call": { "name": string, "arguments": object } }
 *   200     { "data": <data của tool> }
 *   4xx/5xx { "error": { "code": ErrorCode } }   — 429 kèm header Retry-After (giây)
 *
 * Phần WRITE (execute approved command, getOperation) thuộc P1-WRITE, dùng lại `post`.
 */
import type { ReadContext } from "./common/context";
import { type ErrorCode, type ToolError, toolError } from "./common/errors";
import type { ProviderCallOptions, ReadResult, ReadToolName } from "./providers/provider";

export const CORE_REQUEST_TIMEOUT_MS = 20_000;
const MAX_RESPONSE_BYTES = 8 * 1024 * 1024;

export type CoreClientConfig = {
  /** Gốc Core API, HTTPS (http chỉ cho localhost khi dev). */
  baseUrl: URL;
  /** Service credential của MCP. Hàm để có thể xoay vòng token mà không dựng lại client. */
  credential: () => string | Promise<string>;
  requestTimeoutMs?: number;
  fetch?: typeof fetch;
};

/** Kết quả HTTP thô đã phân loại, dùng chung cho READ và WRITE. */
export type CoreHttpResult =
  | { kind: "ok"; status: number; body: unknown }
  | { kind: "error"; status: number; code: ErrorCode | null; retryAfterMs: number | null }
  | { kind: "timeout" }
  | { kind: "network" }
  | { kind: "invalid_body"; status: number };

/** Mã Core được phép trả cho READ, giữ nguyên mã; mã khác coi là lỗi provider. */
const READ_PASSTHROUGH: Partial<Record<ErrorCode, string>> = {
  VALIDATION_ERROR: "Core từ chối truy vấn vì tham số hoặc cursor không hợp lệ.",
  SCOPE_MISMATCH: "Truy vấn lệch scope được cấp.",
  NOT_FOUND: "Không tìm thấy dữ liệu trong property.",
  RATE_LIMITED: "Core đang giới hạn tần suất, thử lại sau.",
};

export class CoreClient {
  private readonly fetch: typeof fetch;
  private readonly timeoutMs: number;

  constructor(private readonly config: CoreClientConfig) {
    const local = config.baseUrl.hostname === "localhost" || config.baseUrl.hostname === "127.0.0.1";
    if (config.baseUrl.protocol !== "https:" && !(local && config.baseUrl.protocol === "http:")) {
      throw new Error("Core API phải dùng HTTPS");
    }
    this.fetch = config.fetch ?? fetch;
    this.timeoutMs = config.requestTimeoutMs ?? CORE_REQUEST_TIMEOUT_MS;
  }

  /** Scoped query cho một READ tool. */
  async query(
    context: ReadContext,
    call: { name: ReadToolName; arguments: Record<string, unknown> },
    options: ProviderCallOptions,
  ): Promise<ReadResult<unknown>> {
    const result = await this.post("security/v0.3/query", { context, tool_call: call }, context.correlation_id, options);
    if (result.kind === "ok") {
      const body = result.body;
      if (body !== null && typeof body === "object" && !Array.isArray(body) && "data" in body && Object.keys(body).length === 1) {
        return { ok: true, data: (body as { data: unknown }).data };
      }
      return { ok: false, error: readError("PROVIDER_INVALID_RESPONSE") };
    }
    return { ok: false, error: readFailure(result) };
  }

  /** POST JSON tới Core với credential của MCP. Không throw; mọi lỗi được phân loại. */
  async post(path: string, body: unknown, correlationId: string, options: ProviderCallOptions): Promise<CoreHttpResult> {
    const budget = Math.min(this.timeoutMs, options.deadline - Date.now());
    if (budget <= 0) return { kind: "timeout" };
    const timeout = AbortSignal.timeout(budget);
    const signal = AbortSignal.any([options.signal, timeout]);

    let response: Response;
    try {
      response = await this.fetch(new URL(path, withTrailingSlash(this.config.baseUrl)), {
        method: "POST",
        headers: {
          authorization: `Bearer ${await this.config.credential()}`,
          "content-type": "application/json",
          accept: "application/json",
          "x-correlation-id": correlationId,
        },
        body: JSON.stringify(body),
        signal,
        redirect: "error",
      });
    } catch {
      return signal.aborted ? { kind: "timeout" } : { kind: "network" };
    }

    let parsed: unknown;
    try {
      const text = await response.text();
      if (text.length > MAX_RESPONSE_BYTES) return { kind: "invalid_body", status: response.status };
      parsed = JSON.parse(text);
    } catch {
      if (signal.aborted) return { kind: "timeout" };
      return response.ok ? { kind: "invalid_body", status: response.status } : errorResult(response, null);
    }
    return response.ok ? { kind: "ok", status: response.status, body: parsed } : errorResult(response, parsed);
  }
}

function errorResult(response: Response, body: unknown): CoreHttpResult {
  const code = (body as { error?: { code?: unknown } } | null)?.error?.code;
  const retryAfter = Number(response.headers.get("retry-after"));
  return {
    kind: "error",
    status: response.status,
    code: typeof code === "string" ? (code as ErrorCode) : null,
    retryAfterMs: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter * 1000 : null,
  };
}

function readFailure(result: Exclude<CoreHttpResult, { kind: "ok" }>): ToolError {
  switch (result.kind) {
    case "timeout":
      return readError("PROVIDER_TIMEOUT");
    case "network":
      return readError("PROVIDER_ERROR");
    case "invalid_body":
      return readError("PROVIDER_INVALID_RESPONSE");
    case "error": {
      const code = result.status === 429 ? "RATE_LIMITED" : result.code;
      if (code && code in READ_PASSTHROUGH) {
        return toolError(code, READ_PASSTHROUGH[code]!, { mode: "READ", retryAfterMs: result.retryAfterMs ?? undefined });
      }
      // 401/403 ở đây là credential của MCP, không phải lỗi quyền của caller.
      return readError("PROVIDER_ERROR");
    }
  }
}

function readError(code: "PROVIDER_TIMEOUT" | "PROVIDER_ERROR" | "PROVIDER_INVALID_RESPONSE"): ToolError {
  const messages = {
    PROVIDER_TIMEOUT: "Core API không trả lời kịp.",
    PROVIDER_ERROR: "Core API tạm thời lỗi.",
    PROVIDER_INVALID_RESPONSE: "Core API trả dữ liệu không đúng định dạng.",
  };
  return toolError(code, messages[code], { mode: "READ" });
}

function withTrailingSlash(url: URL): URL {
  return url.pathname.endsWith("/") ? url : new URL(`${url.pathname}/`, url);
}
