/**
 * Schema Guard: tham chiếu JSON Schema v0.3 cho wrapper đăng ký validator, cộng kiểm tra runtime
 * mà JSON Schema không diễn đạt được.
 */
import type { GuardPage } from "./types";

export const GUARD_SCHEMAS = {
  Location: "common.schema.json#/$defs/Location",
  GuardStatus: "common.schema.json#/$defs/GuardStatus",
  GuardSummary: "common.schema.json#/$defs/GuardSummary",
  GetAvailableGuardsInput: "common.schema.json#/$defs/GetAvailableGuardsInput",
  GetGuardStatusInput: "common.schema.json#/$defs/GetGuardStatusInput",
  GetAvailableGuardsOutput:
    "security_mcp.schema.json#/$defs/GetAvailableGuardsOutput",
  GetGuardStatusOutput: "security_mcp.schema.json#/$defs/GetGuardStatusOutput",
} as const;

/** get_available_guards chỉ trả guard AVAILABLE, sắp guard_id tăng dần, không trùng (§6.1, §7). */
export function availableGuardsIssues(page: GuardPage): string[] {
  const issues: string[] = [];
  page.guards.forEach((guard, index) => {
    if (guard.status !== "AVAILABLE")
      issues.push(`/guards/${index}: status khác AVAILABLE`);
    const previous = page.guards[index - 1];
    if (previous && previous.guard_id >= guard.guard_id)
      issues.push(`/guards/${index}: không tăng dần theo guard_id`);
  });
  return issues;
}
