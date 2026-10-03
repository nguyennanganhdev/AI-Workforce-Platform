/**
 * Quy tắc đối soát Audit (spec v0.3 §6.3, §8.6). Hàm thuần, chỉ đọc: không tạo event bù, không suy
 * bằng chứng từ phỏng đoán. Dùng cho mock provider, Core và skill incident_audit_review.
 */
import type { EvidenceItem, SecurityEvent } from "./types";

export type AuditGap = {
  code: "MISSING_ACTION_EVIDENCE";
  event_id: string;
  evidence_id: string;
};

/**
 * Event có evidence_id không nằm trong danh sách evidence đã đọc. Chỉ kết luận khi đã đọc hết trang
 * evidence (`evidenceComplete`); chưa hết trang thì không khẳng định evidence không tồn tại.
 */
export function missingEvidence(
  events: readonly SecurityEvent[],
  evidence: readonly EvidenceItem[],
  evidenceComplete: boolean,
): AuditGap[] {
  if (!evidenceComplete) return [];
  const known = new Set(evidence.map((e) => e.evidence_id));
  return events
    .filter((event) => !known.has(event.evidence_id))
    .map((event) => ({
      code: "MISSING_ACTION_EVIDENCE" as const,
      event_id: event.event_id,
      evidence_id: event.evidence_id,
    }));
}

/** ACTION_RECEIPT phải có action, key, provider và reference (§2.2); dùng khi nạp dữ liệu từ nguồn. */
export function evidenceIssues(item: EvidenceItem): string[] {
  if (item.evidence_type !== "ACTION_RECEIPT") return [];
  const missing = (
    ["action", "idempotency_key", "provider", "provider_reference_id"] as const
  ).filter((field) => item[field] === null);
  return missing.map((field) => `ACTION_RECEIPT thiếu ${field}`);
}
