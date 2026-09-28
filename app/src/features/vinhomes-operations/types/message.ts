/**
 * Canonical Communication & Timeline types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 11)
 */

export interface VhMessage {
  id: string;
  incident_id: string;
  body: string;
  author_type: 'RESIDENT' | 'STAFF' | 'MANAGER' | 'AGENT' | 'SYSTEM';
  author_id: string;
  author_name: string;
  author_avatar?: string;
  created_at: string;
}

export type BusinessEventType =
  | 'INCIDENT_CREATED'
  | 'TRIAGE_COMPLETED'
  | 'TASK_ASSIGNED'
  | 'WORK_ORDER_STARTED'
  | 'EVIDENCE_UPLOADED'
  | 'WORK_ORDER_COMPLETED'
  | 'QC_INSPECTED'
  | 'QC_FAILED_REDO_TRIGGERED'
  | 'ACTION_APPROVAL_REQUIRED'
  | 'ACTION_APPROVED'
  | 'INCIDENT_RESOLVED';

export interface VhBusinessEvent {
  id: string;
  tenant_id: string;
  incident_id: string | null;
  subject_type: 'INCIDENT' | 'TASK' | 'WORK_ORDER' | 'ACTION_APPROVAL' | 'QC_RESULT';
  subject_id: string;
  event_type: BusinessEventType;
  actor_type: 'HUMAN' | 'AGENT' | 'SYSTEM';
  actor_id: string;
  actor_name?: string;
  actor_version: string | null;
  data: Record<string, unknown>;
  correlation_id: string;
  occurred_at: string;
}
