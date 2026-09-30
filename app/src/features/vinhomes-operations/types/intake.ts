/**
 * Canonical Intake & Triage types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 5)
 */
import type { LocationJson, IncidentSeverity } from './incident';

export type CaseStatus =
  | 'OPEN'
  | 'CLARIFYING'
  | 'READY'
  | 'TICKETED'
  | 'CLOSED'
  | 'CANCELLED';

export interface VhCase {
  id: string;
  tenant_id: string;
  resident_user_id: string;
  resident_name: string;
  resident_phone: string;
  apartment_id: string | null;
  status: CaseStatus;
  summary: string;
  opened_at: string;
  closed_at: string | null;
  version: number;
}

export interface VhResidentRequest {
  id: string;
  case_id: string;
  channel: 'APP' | 'HOTLINE' | 'PORTAL' | 'RECEPTION';
  request_type: 'REPORT' | 'INQUIRY' | 'FEEDBACK' | 'EMERGENCY';
  sanitized_content: string;
  submitted_by: string;
  created_at: string;
}

export type IssueCandidateStatus =
  | 'DETECTED'
  | 'NEEDS_CLARIFICATION'
  | 'READY'
  | 'MERGED'
  | 'DISCARDED'
  | 'MATERIALIZED';

export interface VhIssueCandidate {
  id: string;
  case_id: string;
  source_request_id: string | null;
  domain: string;
  category: string;
  severity: IncidentSeverity;
  normalized_summary: string;
  location_json: LocationJson;
  confidence: number; // 0.0 to 1.0 (from AI evaluation)
  status: IssueCandidateStatus;
  required_fields_json: string[];
  missing_fields_json: string[];
  merged_into_id?: string | null;
  materialized_incident_id?: string | null;
  /** Kênh gửi phản ánh; APP = app cư dân, được AI tự giao việc ngay khi BQL xác nhận. */
  source_channel?: VhResidentRequest['channel'];
  /** Ảnh cư dân gửi kèm (data URL, bản trải nghiệm). Không phải evidence TRƯỚC/SAU của phiếu thi công. */
  resident_photo_urls?: string[];
  created_at: string;
  updated_at: string;
}

export interface VhIssueRelation {
  source_issue_id: string;
  target_issue_id: string;
  relation_type: 'SPLIT_FROM' | 'MERGED_INTO' | 'RELATED' | 'DEPENDS_ON';
  reason: string;
}

export interface VhResidentReport {
  id: string;
  case_id: string;
  issue_candidate_id: string | null;
  incident_id: string;
  reporter_id: string;
  reporter_name: string;
  apartment_id: string | null;
  category: string;
  description: string;
  location_json: LocationJson;
  created_at: string;
}
