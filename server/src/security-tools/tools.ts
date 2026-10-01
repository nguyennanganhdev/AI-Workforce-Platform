/**
 * Đăng ký 22 tool và wrapper chung (spec v0.3 §3, §4, §9).
 *
 * Mọi tool/call đi cùng một đường: tool có trong catalog → authorize theo mode của caller →
 * validate input (JSON Schema + kiểm tra runtime của domain) → WRITE: verify grant/hash qua
 * `writeGuard` → provider với deadline → envelope → validate output → CallToolResult.
 * Domain handler không có đường nào bỏ qua wrapper.
 *
 * Danh mục lấy từ `x-tools` trong security_mcp.schema.json (tên, mode, schema). Domain cung cấp mô
 * tả/annotation/kiểm tra runtime qua *_TOOLS; khai báo domain lệch contract thì throw lúc nạp module.
 */
import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  type CallToolResult,
  CallToolRequestSchema,
  ErrorCode as JsonRpcErrorCode,
  ListToolsRequestSchema,
  McpError,
  type Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { CAMERA_TOOLS } from "./cameras/tools";
import { type RawWriteHeaders, type RequestIdentity, readContext, type WriteContext, writeContext } from "./common/context";
import { type ToolError, type ToolMode, toolError, toToolError } from "./common/errors";
import { failure, finalizeResponse, readSuccess, responseMeta, type ToolResponse, toCallToolResult, writeSuccess } from "./common/responses";
import { DISPATCH_TOOLS } from "./dispatch/tools";
import { EMERGENCY_TOOLS } from "./emergency/tools";
import { GUARD_TOOLS } from "./guards/tools";
import {
  isReadTool,
  isWriteTool,
  type ProviderCallOptions,
  type ProviderFailure,
  READ_TOOL_NAMES,
  type SecurityProvider,
  type ToolInput,
  type VerifiedWrite,
  WRITE_TOOL_NAMES,
  type WriteToolName,
} from "./providers/provider";
import { bundleSchema, TOOL_CONTRACTS, type ToolContract, validate } from "./schema";

/** Tổng budget MCP cho một call (§5): Core tối đa 20 giây, cả call tối đa 25 giây. */
export const TOOL_BUDGET_MS = 25_000;

export type ToolAnnotations = { readOnlyHint?: boolean; destructiveHint?: boolean; idempotentHint?: boolean };

/** Khai báo tool của domain. Cùng shape với P4ToolDefinition, thêm hai hook runtime tùy chọn. */
export type DomainToolDefinition = {
  name: string;
  mode: ToolMode;
  inputSchema: string;
  outputSchema: string;
  description: string;
  annotations: ToolAnnotations;
  /** Ràng buộc input JSON Schema không diễn đạt được (ví dụ from < to). */
  inputIssues?: (input: Record<string, unknown>) => string[];
  /** Kiểm tra data của success sau khi đã qua output schema (ví dụ camera boundary). */
  outputIssues?: (data: unknown) => string[];
};

/** Domain đã có khai báo trên nhánh này. Khi merge P3 thêm `...INCIDENT_TOOLS, ...AUDIT_TOOLS`. */
const DOMAIN_TOOLS: readonly DomainToolDefinition[] = [...GUARD_TOOLS, ...CAMERA_TOOLS, ...DISPATCH_TOOLS, ...EMERGENCY_TOOLS];

export type RegisteredTool = ToolContract & Omit<DomainToolDefinition, keyof ToolContract>;

// Phải khai báo trước SECURITY_TOOLS: buildRegistry chạy ngay lúc nạp module.
const DEFAULT_ANNOTATIONS: Record<ToolMode, ToolAnnotations> = {
  READ: { readOnlyHint: true },
  // Dedup phụ thuộc key ở transport nên WRITE không idempotent theo arguments (§3.2).
  WRITE: { destructiveHint: true, idempotentHint: false },
};

export const SECURITY_TOOLS: readonly RegisteredTool[] = buildRegistry(TOOL_CONTRACTS, DOMAIN_TOOLS);
const BY_NAME = new Map(SECURITY_TOOLS.map((tool) => [tool.name, tool]));

// ---------------------------------------------------------------------------------------------
// Chỗ cắm verify grant cho WRITE (common/execution-grant.ts + common/idempotency.ts)
// ---------------------------------------------------------------------------------------------

export type WriteGuardRequest = {
  tool: WriteToolName;
  /** Arguments đã qua validate, đúng object sẽ gửi provider. Hash đúng object này, không sửa. */
  arguments: Record<string, unknown>;
  context: WriteContext;
  /** X-Security-Execution-Grant và Idempotency-Key ở dạng thô. */
  headers: RawWriteHeaders;
  now: Date;
};

export type WriteGuardResult = { ok: true; write: VerifiedWrite } | { ok: false; error: ToolError };

/**
 * Verify JWS (ES256, kid, iss/aud/sub, thời gian), claims khớp context/action/key, dựng
 * ActionBinding và so payload_hash. Lỗi trả ToolError GRANT_* / IDEMPOTENCY_* / SCOPE_MISMATCH.
 * Không cấu hình thì WRITE bị ẩn trong tools/list và bị từ chối ở tools/call (deployment chỉ READ).
 */
export type WriteGuard = (request: WriteGuardRequest) => Promise<WriteGuardResult>;

export type SecurityToolsOptions = {
  provider: SecurityProvider;
  writeGuard?: WriteGuard;
  budgetMs?: number;
  now?: () => Date;
  /** Ghi lý do output bị thay. Chỉ nhận tên tool và đường dẫn lỗi, không có giá trị. */
  onOutputRejected?: (tool: string, issues: string[]) => void;
};

// ---------------------------------------------------------------------------------------------
// tools/list và tools/call
// ---------------------------------------------------------------------------------------------

const bundled = new Map<string, Tool>();

/** Tool caller được phép thấy. Bot chỉ có READ không thấy WRITE; kiểm lại ở tools/call. */
export function listTools(identity: RequestIdentity, options: Pick<SecurityToolsOptions, "writeGuard">): Tool[] {
  return SECURITY_TOOLS.filter((tool) => allowed(tool, identity, options)).map(exportTool);
}

/** Schema của từng input/output đã bundle độc lập; không còn $ref trỏ file local. */
export function exportTool(tool: RegisteredTool): Tool {
  let exported = bundled.get(tool.name);
  if (!exported) {
    exported = {
      name: tool.name,
      description: tool.description,
      inputSchema: bundleSchema(tool.inputSchema) as Tool["inputSchema"],
      outputSchema: bundleSchema(tool.outputSchema) as Tool["outputSchema"],
      annotations: tool.annotations,
    };
    bundled.set(tool.name, exported);
  }
  return exported;
}

export async function callTool(
  name: string,
  args: Record<string, unknown> | undefined,
  identity: RequestIdentity,
  options: SecurityToolsOptions,
): Promise<CallToolResult> {
  const tool = BY_NAME.get(name);
  // Tool không tồn tại là lỗi giao thức (JSON-RPC), không phải Failure nghiệp vụ (§3.2).
  if (!tool) throw new McpError(JsonRpcErrorCode.InvalidParams, `Unknown tool: ${name}`);

  const now = options.now ?? (() => new Date());
  let response: ToolResponse;
  try {
    response = await execute(tool, args ?? {}, identity, options, now);
  } catch (error) {
    response = failure(toToolError(error, tool.mode), responseMeta(identity.correlation_id, { now: now() }));
  }
  const { response: checked, issues } = finalizeResponse(tool, response, tool.outputIssues);
  if (issues.length > 0) (options.onOutputRejected ?? defaultOutputRejected)(tool.name, issues);
  return toCallToolResult(checked);
}

/** Gắn tools/list và tools/call vào một MCP Server đã dựng cho request đã xác thực. */
export function registerSecurityTools(server: Server, identity: RequestIdentity, options: SecurityToolsOptions): void {
  server.setRequestHandler(ListToolsRequestSchema, () => ({ tools: listTools(identity, options) }));
  server.setRequestHandler(CallToolRequestSchema, (request) =>
    callTool(request.params.name, request.params.arguments, identity, options),
  );
}

async function execute(
  tool: RegisteredTool,
  args: Record<string, unknown>,
  identity: RequestIdentity,
  options: SecurityToolsOptions,
  now: () => Date,
): Promise<ToolResponse> {
  const fail = (error: ToolError) => failure(error, responseMeta(identity.correlation_id, { now: now() }));
  const mode = tool.mode;

  if (!allowed(tool, identity, options)) {
    return fail(toolError("AUTH_ERROR", "Caller không có quyền gọi tool này.", { mode }));
  }

  const checked = validate(tool.inputSchema, args);
  const issues = checked.ok ? (tool.inputIssues?.(args) ?? []) : checked.issues;
  if (issues.length > 0) {
    return fail(toolError("VALIDATION_ERROR", `Input không hợp lệ: ${issues.join("; ")}`, { mode }));
  }

  const budget = options.budgetMs ?? TOOL_BUDGET_MS;
  const controller = new AbortController();
  const call: ProviderCallOptions = { signal: controller.signal, deadline: Date.now() + budget };

  if (isReadTool(tool.name)) {
    const result = await withDeadline(options.provider.read(tool.name, args as ToolInput<typeof tool.name>, readContext(identity), call), controller, budget, "READ");
    if (!result.ok) return fail(result.error);
    return readSuccess(result.data, responseMeta(identity.correlation_id, { now: now() }));
  }

  if (!isWriteTool(tool.name) || !options.writeGuard) {
    return fail(toolError("AUTH_ERROR", "WRITE chưa được bật.", { mode }));
  }
  const context = writeContext(identity);
  const guarded = await options.writeGuard({
    tool: tool.name,
    arguments: args,
    context,
    headers: identity.write_headers,
    now: now(),
  });
  if (!guarded.ok) return fail(guarded.error);
  const result = await withDeadline(options.provider.write(tool.name, args as ToolInput<typeof tool.name>, guarded.write, call), controller, budget, "WRITE");
  if (!result.ok) return failure(result.error, responseMeta(identity.correlation_id, { replayed: result.replayed ?? false, now: now() }));
  return writeSuccess(result.data, result.evidence, responseMeta(identity.correlation_id, { replayed: result.replayed, now: now() }));
}

/**
 * Hết budget thì hủy provider và trả PROVIDER_TIMEOUT: READ thử lại được, WRITE chưa biết đã commit
 * hay chưa (RECONCILE). Hủy không phải rollback.
 */
async function withDeadline<T>(
  work: Promise<T>,
  controller: AbortController,
  budgetMs: number,
  mode: ToolMode,
): Promise<T | ProviderFailure> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<ProviderFailure>((resolve) => {
    timer = setTimeout(() => {
      controller.abort();
      resolve({ ok: false, error: toolError("PROVIDER_TIMEOUT", "Tool vượt quá thời gian cho phép.", { mode }) });
    }, budgetMs);
  });
  try {
    return await Promise.race([work, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

function allowed(tool: RegisteredTool, identity: RequestIdentity, options: Pick<SecurityToolsOptions, "writeGuard">): boolean {
  if (!identity.caller.modes.has(tool.mode)) return false;
  return tool.mode === "READ" || options.writeGuard !== undefined;
}

function defaultOutputRejected(tool: string, issues: string[]): void {
  console.warn(`[security-mcp] output ${tool} không đúng contract`, issues);
}

function buildRegistry(contracts: readonly ToolContract[], domain: readonly DomainToolDefinition[]): RegisteredTool[] {
  const expected = new Map<string, ToolMode>([
    ...READ_TOOL_NAMES.map((name) => [name, "READ"] as const),
    ...WRITE_TOOL_NAMES.map((name) => [name, "WRITE"] as const),
  ]);
  if (contracts.length !== expected.size || contracts.some((c) => expected.get(c.name) !== c.mode)) {
    throw new Error("Danh mục tool trong providers/provider.ts lệch x-tools của security_mcp.schema.json");
  }
  const byName = new Map(domain.map((tool) => [tool.name, tool]));
  if (byName.size !== domain.length) throw new Error("Tool domain khai báo trùng tên");
  for (const tool of domain) {
    const contract = contracts.find((c) => c.name === tool.name);
    if (
      !contract ||
      contract.mode !== tool.mode ||
      contract.inputSchema !== tool.inputSchema ||
      contract.outputSchema !== tool.outputSchema
    ) {
      throw new Error(`Khai báo tool ${tool.name} lệch contract x-tools`);
    }
  }
  return contracts.map((contract) => {
    const tool = byName.get(contract.name);
    return {
      ...contract,
      description: tool?.description ?? `${contract.name} (${contract.mode}). Xem Security MCP contract v0.3 §7.`,
      annotations: tool?.annotations ?? DEFAULT_ANNOTATIONS[contract.mode],
      inputIssues: tool?.inputIssues,
      outputIssues: tool?.outputIssues,
    };
  });
}
