/**
 * Canonical QC and Checklist types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 10)
 */

export type QcOutcome = 'PASS' | 'FAIL' | 'INCONCLUSIVE';

export interface VhChecklistCriterion {
  id: string;
  code: string;
  label: string;
  description?: string;
  required: boolean;
  type: 'BOOLEAN' | 'NUMERIC_RANGE' | 'IMAGE_CONFIRMATION' | 'TEXT';
  acceptableMin?: number;
  acceptableMax?: number;
}

export interface VhChecklist {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  category: string;
  status: 'ACTIVE' | 'ARCHIVED';
}

export interface VhChecklistVersion {
  id: string;
  checklist_id: string;
  name?: string;
  version_no: number;
  version?: number;
  criteria_json: VhChecklistCriterion[];
  status: 'PUBLISHED' | 'DRAFT' | 'DEPRECATED';
  published_at: string;
  created_by: string;
}

export interface VhQcResult {
  id: string;
  work_order_id: string;
  checklist_version_id?: string;
  outcome: QcOutcome;
  criteria: Array<{
    criterion_id: string;
    label: string;
    passed: boolean;
    note?: string;
  }>;
  failed_criteria: string[];
  redo_required: boolean;
  note: string | null;
  checked_by: string;
  checked_by_name?: string;
  checked_at: string;
}

export interface VhQcResultEvidence {
  qc_result_id: string;
  evidence_ref_id: string;
}
