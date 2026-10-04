/**
 * Schema Dispatch: tham chiếu JSON Schema v0.3 để wrapper P1 đăng ký validator, cộng kiểm tra
 * runtime mà JSON Schema không diễn đạt được. Cấu trúc tĩnh (field, enum, CANCELLED cần
 * reason/time, FAILED cần failure_code) đã nằm trong JSON Schema.
 */
import type { Dispatch } from "./types";

export const DISPATCH_SCHEMAS = {
  Dispatch: "common.schema.json#/$defs/Dispatch",
  DispatchSummary: "common.schema.json#/$defs/DispatchSummary",
  DispatchGuardInput: "common.schema.json#/$defs/DispatchGuardInput",
  GetDispatchInput: "common.schema.json#/$defs/GetDispatchInput",
  CancelDispatchInput: "common.schema.json#/$defs/CancelDispatchInput",
  DispatchGuardOutput: "security_mcp.schema.json#/$defs/DispatchGuardOutput",
  GetDispatchOutput: "security_mcp.schema.json#/$defs/GetDispatchOutput",
  CancelDispatchOutput: "security_mcp.schema.json#/$defs/CancelDispatchOutput",
} as const;

/** Ràng buộc giữa các giá trị trong một Dispatch. Timestamp cùng định dạng nên so chuỗi được. */
export function dispatchRuntimeIssues(d: Dispatch): string[] {
  const issues: string[] = [];
  if (d.updated_at < d.created_at) issues.push("updated_at trước created_at");
  if (d.cancelled_at !== null && d.status !== "CANCELLED")
    issues.push("cancelled_at chỉ có khi CANCELLED");
  if (d.cancelled_at !== null && d.cancelled_at < d.created_at)
    issues.push("cancelled_at trước created_at");
  if (d.failure_code !== null && d.status !== "FAILED")
    issues.push("failure_code chỉ có khi FAILED");
  return issues;
}
