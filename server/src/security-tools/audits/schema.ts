/**
 * Schema Audit: tham chiếu JSON Schema v0.3 cho wrapper, cộng kiểm tra runtime (§6.3, §7) mà JSON
 * Schema không diễn đạt được: thứ tự trang và liên kết event ↔ evidence trong cùng một bản ghi.
 */
import type { DispatchHistoryPage, EvidencePage, TimelinePage } from "./types";

export const AUDIT_SCHEMAS = {
  EvidenceItem: "common.schema.json#/$defs/EvidenceItem",
  SecurityEvent: "common.schema.json#/$defs/SecurityEvent",
  GetIncidentEvidenceInput:
    "common.schema.json#/$defs/GetIncidentEvidenceInput",
  GetDispatchHistoryInput: "common.schema.json#/$defs/GetDispatchHistoryInput",
  GetSecurityEventTimelineInput:
    "common.schema.json#/$defs/GetSecurityEventTimelineInput",
  GetIncidentEvidenceOutput:
    "security_mcp.schema.json#/$defs/GetIncidentEvidenceOutput",
  GetDispatchHistoryOutput:
    "security_mcp.schema.json#/$defs/GetDispatchHistoryOutput",
  GetSecurityEventTimelineOutput:
    "security_mcp.schema.json#/$defs/GetSecurityEventTimelineOutput",
} as const;

type Ordered = { created_at: string };

/** Trang sắp `(created_at, id)` tăng dần, không trùng, mọi bản ghi cùng một incident (§7). */
function orderIssues<T extends Ordered & { incident_id: string }>(
  items: readonly T[],
  key: string,
  idOf: (item: T) => string,
): string[] {
  const issues: string[] = [];
  items.forEach((item, index) => {
    const previous = items[index - 1];
    if (!previous) return;
    const sorted =
      previous.created_at < item.created_at ||
      (previous.created_at === item.created_at && idOf(previous) < idOf(item));
    if (!sorted)
      issues.push(`/${key}/${index}: không tăng dần theo (created_at, id)`);
    if (previous.incident_id !== item.incident_id)
      issues.push(`/${key}/${index}: lẫn bản ghi của incident khác`);
  });
  return issues;
}

export function evidencePageIssues(page: EvidencePage): string[] {
  return orderIssues(page.evidence, "evidence", (e) => e.evidence_id);
}

export function dispatchHistoryIssues(page: DispatchHistoryPage): string[] {
  return orderIssues(page.dispatches, "dispatches", (d) => d.dispatch_id);
}

/** EVIDENCE_ADDED phải trỏ đúng evidence của chính event (§6.3), cộng thứ tự trang. */
export function timelinePageIssues(page: TimelinePage): string[] {
  const issues = orderIssues(page.events, "events", (e) => e.event_id);
  page.events.forEach((event, index) => {
    if (
      event.event_type === "EVIDENCE_ADDED" &&
      event.data.evidence_id !== event.evidence_id
    ) {
      issues.push(
        `/events/${index}: EVIDENCE_ADDED.data.evidence_id khác evidence_id của event`,
      );
    }
  });
  return issues;
}
