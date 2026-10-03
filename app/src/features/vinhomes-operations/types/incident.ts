/**
 * Canonical Incident types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 6: vh_incident)
 */

export type IncidentStatus = 'NEW' | 'OPEN' | 'RESOLVED' | 'CLOSED';

export type IncidentStage =
  | 'INTAKE'
  | 'TRIAGE'
  | 'PLANNING'
  | 'EXECUTION'
  | 'QC'
  | 'RESIDENT_CONFIRMATION';

export type IncidentSeverity = 'P0' | 'P1' | 'P2' | 'P3';

export interface LocationJson {
  towerCode?: string;
  floor?: number | string;
  apartmentCode?: string;
  areaCode?: string;
  description?: string;
}

export interface VhIncident {
  id: string;
  tenant_id: string;
  project_id: string;
  tower_id: string | null;
  category: string;
  title: string;
  location_json: LocationJson;
  severity: IncidentSeverity;
  status: IncidentStatus;
  stage: IncidentStage;
  owner_user_id: string | null;
  sla_due_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  /** Sự cố cần nhà thầu: AI chuyển BQL, BQL tự liên hệ ngoài hệ thống (docs mục 14) */
  contractor_handoff?: ContractorHandoff;
  /** Ghi chú khi BQL tự xử lý và đóng một ngoại lệ (tranh chấp, hộ không hợp tác…) */
  bql_resolution_note?: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ContractorHandoff {
  status: 'PENDING' | 'CONTACTED' | 'RESOLVED';
  /** Gợi ý của AI từ hồ sơ thiết bị */
  warranty: { under_warranty: boolean; contractor_name: string | null; expires_at: string | null } | null;
  contractor_name: string | null;
  eta: string | null;
  contacted_at: string | null;
  resolved_at: string | null;
  note: string | null;
}

export interface VhIncidentRelation {
  source_incident_id: string;
  target_incident_id: string;
  relation_type: 'RELATED' | 'DUPLICATE' | 'CAUSED_BY' | 'BLOCKS' | 'RECURRING_WITH';
  reason: string;
  created_by: string;
  created_at: string;
}
