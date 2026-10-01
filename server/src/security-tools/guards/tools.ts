/**
 * Khai báo tool Guard để src/tools.ts register (spec v0.3 §7). Handler là wrapper chung; P2 cung cấp
 * tên canonical, mode, schema ref, mô tả, annotation và kiểm tra output runtime.
 */
import type { DomainToolDefinition } from "../tools";
import { availableGuardsIssues, GUARD_SCHEMAS as S } from "./schema";
import type { GuardPage } from "./types";

export const GUARD_TOOLS: readonly DomainToolDefinition[] = [
  {
    name: "get_available_guards",
    mode: "READ",
    inputSchema: S.GetAvailableGuardsInput,
    outputSchema: S.GetAvailableGuardsOutput,
    description:
      "Danh sách bảo vệ của property đang AVAILABLE và không có lệnh điều động mở, để chọn người cho một location. Sắp theo guard_id. Chỉ là bản đọc: không giữ chỗ, guard có thể bận trước khi điều động.",
    annotations: { readOnlyHint: true },
    outputIssues: (data) => availableGuardsIssues(data as GuardPage),
  },
  {
    name: "get_guard_status",
    mode: "READ",
    inputSchema: S.GetGuardStatusInput,
    outputSchema: S.GetGuardStatusOutput,
    description: "Trạng thái hiện tại và vị trí gần nhất (nếu biết) của một bảo vệ trong property.",
    annotations: { readOnlyHint: true },
  },
];
