/**
 * Schema Incident: tham chiếu JSON Schema v0.3 cho wrapper đăng ký validator, cộng kiểm tra runtime
 * mà JSON Schema không diễn đạt được. Patch rỗng, note bắt buộc và RESOLVED cần evidence đã nằm
 * trong UpdateIncidentInput của JSON Schema.
 */
import type { Incident, IncidentPage } from "./types";

export const INCIDENT_SCHEMAS = {
  Incident: "common.schema.json#/$defs/Incident",
  GetIncidentInput: "common.schema.json#/$defs/GetIncidentInput",
  SearchIncidentsInput: "common.schema.json#/$defs/SearchIncidentsInput",
  CreateIncidentInput: "common.schema.json#/$defs/CreateIncidentInput",
  UpdateIncidentInput: "common.schema.json#/$defs/UpdateIncidentInput",
  GetIncidentOutput: "security_mcp.schema.json#/$defs/GetIncidentOutput",
  SearchIncidentsOutput:
    "security_mcp.schema.json#/$defs/SearchIncidentsOutput",
  CreateIncidentOutput: "security_mcp.schema.json#/$defs/CreateIncidentOutput",
  UpdateIncidentOutput: "security_mcp.schema.json#/$defs/UpdateIncidentOutput",
} as const;

/** `from < to` khi có cả hai (§7). Timestamp cùng định dạng UTC mili giây nên so chuỗi được. */
export function searchIncidentsInputIssues(
  input: Record<string, unknown>,
): string[] {
  const { from, to } = input;
  return typeof from === "string" && typeof to === "string" && !(from < to)
    ? ["from phải nhỏ hơn to"]
    : [];
}

/** Ràng buộc giữa các field của một Incident. */
export function incidentRuntimeIssues(incident: Incident): string[] {
  return incident.updated_at < incident.created_at
    ? ["updated_at trước created_at"]
    : [];
}

/** Trang search: từng incident hợp lệ và sắp `(created_at, incident_id)` tăng dần, không trùng (§7). */
export function incidentPageIssues(page: IncidentPage): string[] {
  const issues: string[] = [];
  page.incidents.forEach((incident, index) => {
    for (const issue of incidentRuntimeIssues(incident))
      issues.push(`/incidents/${index}: ${issue}`);
    const previous = page.incidents[index - 1];
    if (previous && !before(previous, incident))
      issues.push(
        `/incidents/${index}: không tăng dần theo (created_at, incident_id)`,
      );
  });
  return issues;
}

const before = (a: Incident, b: Incident) =>
  a.created_at < b.created_at ||
  (a.created_at === b.created_at && a.incident_id < b.incident_id);
