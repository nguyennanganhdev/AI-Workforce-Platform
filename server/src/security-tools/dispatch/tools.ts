/**
 * Khai báo tool Dispatch để P1 register trong src/tools.ts (spec v0.3 §7). Handler = wrapper P1
 * (auth → authorize → validate → grant/hash nếu WRITE → provider). P4 cung cấp tên canonical,
 * mode, schema ref, mô tả và annotation.
 */
import { DISPATCH_SCHEMAS } from "./schema";

export type P4ToolDefinition = {
  name: string;
  mode: "READ" | "WRITE";
  inputSchema: string;
  outputSchema: string;
  description: string;
  /** WRITE: destructiveHint=true, idempotentHint=false (§3.2). */
  annotations: { readOnlyHint?: boolean; destructiveHint?: boolean; idempotentHint?: boolean };
};

export const WRITE_ANNOTATIONS = { destructiveHint: true, idempotentHint: false } as const;
export const READ_ANNOTATIONS = { readOnlyHint: true } as const;

export const DISPATCH_TOOLS: readonly P4ToolDefinition[] = [
  {
    name: "dispatch_guard",
    mode: "WRITE",
    inputSchema: DISPATCH_SCHEMAS.DispatchGuardInput,
    outputSchema: DISPATCH_SCHEMAS.DispatchGuardOutput,
    description:
      "Tạo lệnh điều động một bảo vệ tới incident (trạng thái PENDING). Location lấy từ incident. Chỉ ActionExecutor gọi, cần execution grant.",
    annotations: WRITE_ANNOTATIONS,
  },
  {
    name: "get_dispatch",
    mode: "READ",
    inputSchema: DISPATCH_SCHEMAS.GetDispatchInput,
    outputSchema: DISPATCH_SCHEMAS.GetDispatchOutput,
    description: "Đọc một lệnh điều động và trạng thái hiện tại của nó.",
    annotations: READ_ANNOTATIONS,
  },
  {
    name: "cancel_dispatch",
    mode: "WRITE",
    inputSchema: DISPATCH_SCHEMAS.CancelDispatchInput,
    outputSchema: DISPATCH_SCHEMAS.CancelDispatchOutput,
    description:
      "Hủy lệnh điều động đang mở (PENDING/EN_ROUTE/ON_SITE) kèm lý do. Chỉ ActionExecutor gọi, cần execution grant.",
    annotations: WRITE_ANNOTATIONS,
  },
];
