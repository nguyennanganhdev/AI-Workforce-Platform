/**
 * Canonical Evidence & File types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 10: vh_evidence_ref & vh_file_object)
 */

export type CapturePhase = 'BEFORE' | 'AFTER' | 'QC' | 'OTHER';

export type EvidenceKind = 'IMAGE' | 'VIDEO' | 'AUDIO' | 'DOCUMENT' | 'SENSOR_LOG';

export interface VhFileObject {
  id: string;
  storage_provider: string;
  storage_key: string;
  mime_type: string;
  size_bytes: number;
  checksum: string;
  created_at: string;
}

export interface VhEvidenceRef {
  id: string;
  incident_id: string;
  task_id: string | null;
  work_order_id: string | null;
  file_id: string;
  kind: EvidenceKind;
  capture_phase: CapturePhase;
  metadata: {
    caption?: string;
    locationNote?: string;
    deviceInfo?: string;
    geoCoordinates?: { lat: number; lng: number };
    [key: string]: unknown;
  };
  file_url?: string;
  uploaded_by: string;
  created_at: string;
}
