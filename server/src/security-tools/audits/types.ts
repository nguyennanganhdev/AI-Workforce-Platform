/**
 * Kiểu Audit — P3 sở hữu EvidenceItem và SecurityEvent (spec v0.3 §2.2, §6.3, §10). Nguồn cấu trúc
 * là schema/common.schema.json. DispatchSummary thuộc P4, import chứ không khai báo lại.
 */
import type { Actor } from "../common/context"; // P1
import type { DispatchStatus, DispatchSummary } from "../dispatch/types"; // P4
import type { EscalationStatus } from "../emergency/types"; // P4
import type { IncidentStatus, Severity } from "../incidents/types";

export type EvidenceType =
  | "ACTION_RECEIPT"
  | "OPERATOR_NOTE"
  | "EXTERNAL_REFERENCE";

export type EvidenceAction =
  | "create_incident"
  | "update_incident"
  | "dispatch_guard"
  | "cancel_dispatch"
  | "escalate_emergency"
  | "acknowledge_emergency";

/** Append-only, cùng scope với incident cha. ACTION_RECEIPT bắt buộc action, key, provider và reference. */
export type EvidenceItem = {
  evidence_id: string;
  incident_id: string;
  evidence_type: EvidenceType;
  actor: Actor;
  provider: string | null;
  provider_reference_id: string | null;
  action: EvidenceAction | null;
  idempotency_key: string | null;
  summary: string | null;
  created_at: string;
};

/** Data có shape riêng cho từng loại event; không có object tùy ý (§2.2). */
export type SecurityEventData = {
  INCIDENT_CREATED: { status: "OPEN"; severity: Severity };
  INCIDENT_UPDATED: {
    previous_status: IncidentStatus;
    status: IncidentStatus;
    previous_severity: Severity;
    severity: Severity;
    note: string | null;
  };
  DISPATCH_CREATED: {
    dispatch_id: string;
    guard_id: string;
    status: "PENDING";
  };
  DISPATCH_STATUS_CHANGED: {
    dispatch_id: string;
    previous_status: DispatchStatus;
    status: DispatchStatus;
    reason: string | null;
  };
  ESCALATION_CREATED: {
    escalation_id: string;
    contact_id: string;
    status: "PENDING";
  };
  ESCALATION_STATUS_CHANGED: {
    escalation_id: string;
    previous_status: EscalationStatus;
    status: EscalationStatus;
    reason: string | null;
  };
  EVIDENCE_ADDED: { evidence_id: string; evidence_type: EvidenceType };
};

export type SecurityEventType = keyof SecurityEventData;

export type SecurityEvent = {
  [K in SecurityEventType]: {
    event_id: string;
    incident_id: string;
    event_type: K;
    actor: Actor;
    created_at: string;
    /** Mọi event đều trỏ tới evidence có thật của cùng incident. */
    evidence_id: string;
    data: SecurityEventData[K];
  };
}[SecurityEventType];

export type GetIncidentEvidenceInput = {
  incident_id: string;
  limit?: number;
  cursor?: string;
};
export type GetDispatchHistoryInput = {
  incident_id: string;
  limit?: number;
  cursor?: string;
};
export type GetSecurityEventTimelineInput = {
  incident_id: string;
  limit?: number;
  cursor?: string;
};

export type EvidencePage = {
  evidence: EvidenceItem[];
  next_cursor: string | null;
};
export type DispatchHistoryPage = {
  dispatches: DispatchSummary[];
  next_cursor: string | null;
};
export type TimelinePage = {
  events: SecurityEvent[];
  next_cursor: string | null;
};
