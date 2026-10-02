/**
 * Kiểu Incident — P3 sở hữu (spec v0.3 §2.2, §10). Nguồn cấu trúc là schema/common.schema.json
 * (#/$defs/Incident, IncidentType, IncidentStatus, Severity, RelatedCounts, *Input).
 */
import type { Location } from "../guards/types"; // P2

/** P0 nguy cấp … P3 thấp. Dispatcher/platform phân loại; agent chỉ đề xuất thay đổi có căn cứ. */
export type Severity = "P0" | "P1" | "P2" | "P3";

export type IncidentType =
  | "INTRUSION"
  | "THEFT"
  | "VIOLENCE"
  | "SUSPICIOUS_ACTIVITY"
  | "ACCESS_CONTROL"
  | "DISTURBANCE"
  | "FIRE"
  | "MEDICAL"
  | "OTHER";

export type IncidentStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";

/** Đếm trong cùng snapshot incident; chỉ để quyết định có fetch hay không, không là bằng chứng audit. */
export type RelatedCounts = {
  dispatches: number;
  escalations: number;
  cameras: number;
  evidence: number;
};

/** Cùng một shape cho get/search/create/update (§2.2). */
export type Incident = {
  incident_id: string;
  ticket_id: string;
  incident_type: IncidentType;
  description: string | null;
  status: IncidentStatus;
  severity: Severity;
  location: Location;
  /** Tăng mỗi lần incident đổi, kể cả khi related_counts đổi. */
  version: number;
  created_at: string;
  updated_at: string;
  related_counts: RelatedCounts;
};

export type GetIncidentInput = { incident_id: string };

export type SearchIncidentsInput = {
  location_id?: string;
  severity?: Severity;
  status?: IncidentStatus;
  /** `[from, to)` trên created_at; có cả hai thì from < to. */
  from?: string;
  to?: string;
  limit?: number;
  cursor?: string;
};

export type CreateIncidentInput = {
  incident_type: IncidentType;
  description: string;
  severity: Severity;
  location_id: string;
};

/** Patch không rỗng; đổi status/severity phải có note; RESOLVED phải có resolution_evidence_id. */
export type UpdateIncidentInput = {
  incident_id: string;
  expected_version: number;
  status?: IncidentStatus;
  severity?: Severity;
  note?: string;
  resolution_evidence_id?: string;
};

export type IncidentPage = {
  incidents: Incident[];
  next_cursor: string | null;
};
