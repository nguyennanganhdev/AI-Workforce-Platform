/**
 * Provider thật: map tool sang Core API (spec v0.3 §9).
 *
 * READ: một scoped query mỗi tool; Core lọc scope, sort, ký cursor. Dữ liệu camera đi qua boundary
 * ngay tại adapter (§6.3) trước khi tới wrapper; wrapper validate toàn bộ output lần nữa.
 * WRITE: chưa nối Core command — xem `write`.
 */
import { toCameraSummary, toIncidentCamera } from "../cameras/boundary";
import type { CoreClient } from "../client";
import type { ReadContext } from "../common/context";
import { ToolFailure, toolError, toToolError } from "../common/errors";
import type {
  ProviderCallOptions,
  ReadResult,
  ReadToolName,
  SecurityProvider,
  ToolData,
  ToolInput,
  VerifiedWrite,
  WriteResult,
  WriteToolName,
} from "./provider";

/** Hậu xử lý theo tool sau khi Core trả data. Tool không có ở đây chỉ qua validate của wrapper. */
const ADAPTERS: Partial<Record<ReadToolName, (data: unknown) => unknown>> = {
  get_camera_metadata: toCameraSummary,
  search_cameras: (data) => cameraPage(data, toCameraSummary),
  get_cameras_by_location: (data) => cameraPage(data, toCameraSummary),
  get_incident_cameras: (data) => cameraPage(data, toIncidentCamera),
};

export class RealSecurityProvider implements SecurityProvider {
  readonly name = "core_api";

  constructor(private readonly core: CoreClient) {}

  async read<T extends ReadToolName>(
    tool: T,
    input: ToolInput<T>,
    context: ReadContext,
    options: ProviderCallOptions,
  ): Promise<ReadResult<ToolData<T>>> {
    const result = await this.core.query(context, { name: tool, arguments: input as Record<string, unknown> }, options);
    if (!result.ok) return result;
    const adapt = ADAPTERS[tool];
    if (!adapt) return { ok: true, data: result.data as ToolData<T> };
    try {
      return { ok: true, data: adapt(result.data) as ToolData<T> };
    } catch (error) {
      return { ok: false, error: toToolError(error, "READ") };
    }
  }

  /**
   * P1-WRITE (common/execution-grant.ts, common/idempotency.ts, client.ts phần command): gọi
   * "execute approved command" với WriteContext + ActionBinding + approval reference, map
   * getOperation cho replay/IN_PROGRESS/UNKNOWN. Tới lúc đó deployment chỉ bật READ (§11), nên trả
   * lỗi trước khi gửi bất cứ gì lên Core.
   */
  async write<T extends WriteToolName>(
    _tool: T,
    _input: ToolInput<T>,
    _invocation: VerifiedWrite,
    _options: ProviderCallOptions,
  ): Promise<WriteResult<ToolData<T>>> {
    return {
      ok: false,
      error: toolError("AUTH_ERROR", "Deployment này chưa bật WRITE tới Core API.", { mode: "WRITE" }),
    };
  }
}

function cameraPage<T>(data: unknown, item: (raw: unknown) => T): { cameras: T[]; next_cursor: string | null } {
  const page = data as { cameras?: unknown; next_cursor?: unknown } | null;
  const keys = page && typeof page === "object" ? Object.keys(page) : [];
  if (
    !page ||
    keys.length !== 2 ||
    !Array.isArray(page.cameras) ||
    !(page.next_cursor === null || typeof page.next_cursor === "string")
  ) {
    throw new ToolFailure(toolError("PROVIDER_INVALID_RESPONSE", "Trang camera từ provider không đúng contract."));
  }
  return { cameras: page.cameras.map(item), next_cursor: page.next_cursor };
}
