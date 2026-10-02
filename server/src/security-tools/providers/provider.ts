/**
 * Contract provider dùng chung cho mock và real (spec v0.3 §9).
 *
 * Provider nhận input đã validate và context đã xác thực; trả data đúng kiểu hoặc ToolError, không
 * throw raw exception/body. Wrapper (tools.ts) map lỗi, thêm meta/envelope và validate output.
 */
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import type {
  CameraPage,
  CameraSummary,
  GetCameraMetadataInput,
  GetCamerasByLocationInput,
  GetIncidentCamerasInput,
  IncidentCameraPage,
  SearchCamerasInput,
} from "../cameras/types";
import type { ReadContext, WriteContext } from "../common/context";
import { type ToolError, fail } from "../common/errors";
import type { ActionBinding, GrantClaims } from "../common/execution-grant";
import type { WriteEvidence } from "../common/responses";
import type {
  GetAvailableGuardsInput,
  GetGuardStatusInput,
  GuardPage,
  GuardSummary,
} from "../guards/types";

export const READ_TOOL_NAMES = [
  "get_incident",
  "search_incidents",
  "get_available_guards",
  "get_guard_status",
  "get_dispatch",
  "get_emergency_protocol",
  "get_escalation_contacts",
  "get_emergency_escalation",
  "get_incident_escalations",
  "get_camera_metadata",
  "search_cameras",
  "get_cameras_by_location",
  "get_incident_cameras",
  "get_incident_evidence",
  "get_dispatch_history",
  "get_security_event_timeline",
] as const;

export const WRITE_TOOL_NAMES = [
  "create_incident",
  "update_incident",
  "dispatch_guard",
  "cancel_dispatch",
  "escalate_emergency",
  "acknowledge_emergency",
] as const;

export type ReadToolName = (typeof READ_TOOL_NAMES)[number];
export type WriteToolName = (typeof WRITE_TOOL_NAMES)[number];
export type ToolName = ReadToolName | WriteToolName;

/**
 * Kiểu input/data của từng tool. Domain chưa merge vào nhánh này thì rơi về kiểu chung; domain owner
 * bổ sung bằng declaration merging trong types.ts của mình, không cần sửa file này:
 *
 *   declare module "../providers/provider" {
 *     interface ToolIO { get_dispatch: { input: GetDispatchInput; data: Dispatch } }
 *   }
 */
export interface ToolIO {
  get_available_guards: { input: GetAvailableGuardsInput; data: GuardPage };
  get_guard_status: { input: GetGuardStatusInput; data: GuardSummary };
  get_camera_metadata: { input: GetCameraMetadataInput; data: CameraSummary };
  search_cameras: { input: SearchCamerasInput; data: CameraPage };
  get_cameras_by_location: {
    input: GetCamerasByLocationInput;
    data: CameraPage;
  };
  get_incident_cameras: {
    input: GetIncidentCamerasInput;
    data: IncidentCameraPage;
  };
}

export type ToolInput<T extends ToolName> = T extends keyof ToolIO
  ? ToolIO[T]["input"]
  : Record<string, unknown>;
export type ToolData<T extends ToolName> = T extends keyof ToolIO
  ? ToolIO[T]["data"]
  : unknown;

export type ProviderCallOptions = {
  /** Hủy khi hết budget của wrapper. Với WRITE, hủy không đồng nghĩa rollback. */
  signal: AbortSignal;
  /** Epoch ms; provider không được chờ quá mốc này. */
  deadline: number;
};

/**
 * Rejection typed: đúng một ToolError, không raw exception/body. `replayed` = true khi WRITE trả lại
 * failure terminal đã lưu của lần đầu (operation REJECTED, xem common/idempotency.ts).
 */
export type ProviderFailure = {
  ok: false;
  error: ToolError;
  replayed?: boolean;
};
export type ReadResult<T> = { ok: true; data: T } | ProviderFailure;
export type WriteResult<T> =
  | { ok: true; data: T; evidence: WriteEvidence; replayed: boolean }
  | ProviderFailure;

/** WRITE đã qua common/execution-grant.ts: claims đã verify, binding dựng lại và đã so payload_hash. */
export type VerifiedWrite = {
  context: WriteContext;
  idempotency_key: string;
  claims: Readonly<GrantClaims>;
  binding: Readonly<ActionBinding>;
};

export interface SecurityProvider {
  /** Tên ghi vào log/evidence, ví dụ "mock" hoặc "core_api". */
  readonly name: string;
  read<T extends ReadToolName>(
    tool: T,
    input: ToolInput<T>,
    context: ReadContext,
    options: ProviderCallOptions,
  ): Promise<ReadResult<ToolData<T>>>;
  write<T extends WriteToolName>(
    tool: T,
    input: ToolInput<T>,
    invocation: VerifiedWrite,
    options: ProviderCallOptions,
  ): Promise<WriteResult<ToolData<T>>>;
}

export const isReadTool = (name: string): name is ReadToolName =>
  (READ_TOOL_NAMES as readonly string[]).includes(name);
export const isWriteTool = (name: string): name is WriteToolName =>
  (WRITE_TOOL_NAMES as readonly string[]).includes(name);

// ---------------------------------------------------------------------------------------------
// Cursor và phân trang (spec §7)
// ---------------------------------------------------------------------------------------------

export const DEFAULT_PAGE_LIMIT = 50;
export const MAX_PAGE_LIMIT = 100;
export const CURSOR_TTL_MS = 15 * 60_000;

/** Những gì một cursor bị ràng buộc. Trang sau phải giữ nguyên tất cả, kể cả limit. */
export type CursorBinding = {
  tenant_id: string;
  property_id: string;
  principal_id: string;
  tool: ReadToolName;
  /** Input của tool trừ limit/cursor. */
  filters: Record<string, unknown>;
  limit: number;
  /** Định danh snapshot dữ liệu; đổi snapshot thì cursor cũ không dùng được. */
  snapshot: string;
};

export type CursorCodec = {
  encode(binding: CursorBinding, offset: number): string;
  /** Trả offset; cursor sai chữ ký/hết hạn/khác binding → ToolFailure VALIDATION_ERROR không lộ chi tiết. */
  decode(cursor: string, binding: CursorBinding): number;
};

/**
 * Cursor opaque ký HMAC-SHA256: `base64url(payload).base64url(mac)`. Payload chỉ chứa hash của
 * binding, offset và hạn dùng, nên cursor không lộ filter/principal. Real provider không dùng codec
 * này: Core ký/lưu cursor của mình (§7), MCP chuyển nguyên.
 */
export function createCursorCodec(options: {
  secret: string | Uint8Array;
  ttlMs?: number;
  now?: () => Date;
}): CursorCodec {
  const ttl = options.ttlMs ?? CURSOR_TTL_MS;
  const now = options.now ?? (() => new Date());
  const mac = (part: string) =>
    createHmac("sha256", options.secret).update(part).digest();

  return {
    encode(binding, offset) {
      const payload = Buffer.from(
        JSON.stringify({
          v: 1,
          b: bindingHash(binding),
          o: offset,
          x: now().getTime() + ttl,
        }),
      ).toString("base64url");
      return `${payload}.${mac(payload).toString("base64url")}`;
    },
    decode(cursor, binding) {
      const invalid = (): never =>
        fail(
          "VALIDATION_ERROR",
          "Cursor không hợp lệ, hết hạn hoặc không khớp truy vấn.",
        );
      const [payload, signature, extra] = cursor.split(".");
      if (!payload || !signature || extra !== undefined) return invalid();
      const expected = mac(payload);
      const given = Buffer.from(signature, "base64url");
      if (given.length !== expected.length || !timingSafeEqual(given, expected))
        return invalid();
      let parsed: { v?: unknown; b?: unknown; o?: unknown; x?: unknown };
      try {
        parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
      } catch {
        return invalid();
      }
      if (
        parsed.v !== 1 ||
        parsed.b !== bindingHash(binding) ||
        typeof parsed.x !== "number" ||
        parsed.x <= now().getTime() ||
        typeof parsed.o !== "number" ||
        !Number.isSafeInteger(parsed.o) ||
        parsed.o < 0
      ) {
        return invalid();
      }
      return parsed.o;
    },
  };
}

export type PageRequest = { limit?: number; cursor?: string };

/**
 * Cắt một trang từ danh sách đã sắp ổn định. Danh sách rỗng → [] và next_cursor=null; trang cuối
 * không có next_cursor.
 */
export function paginate<T>(
  items: readonly T[],
  input: PageRequest & Record<string, unknown>,
  binding: Omit<CursorBinding, "filters" | "limit">,
  codec: CursorCodec,
): { items: T[]; next_cursor: string | null } {
  const { limit: requested, cursor, ...filters } = input;
  const limit = Math.min(requested ?? DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT);
  const full: CursorBinding = { ...binding, filters, limit };
  const offset = cursor === undefined ? 0 : codec.decode(cursor, full);
  const page = items.slice(offset, offset + limit);
  const next = offset + limit;
  return {
    items: page,
    next_cursor:
      page.length > 0 && next < items.length ? codec.encode(full, next) : null,
  };
}

function bindingHash(binding: CursorBinding): string {
  return createHash("sha256")
    .update(stableStringify(binding))
    .digest("base64url");
}

/** JSON với key sắp xếp, chỉ để hash binding nội bộ (không phải JCS cho grant). */
function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value)
      .filter(([, v]) => v !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
    return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${stableStringify(v)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}
