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

export interface Location {
  location_id: string;
  building: string | null;
  floor: string | null;
  zone: string | null;
}

export interface RelatedCounts {
  dispatches: number;
  escalations: number;
  cameras: number;
  evidence: number;
}

export interface Incident {
  incident_id: string;
  ticket_id: string;
  incident_type: IncidentType;
  description: string | null;
  status: IncidentStatus;
  severity: Severity;
  location: Location;
  version: number;
  created_at: string;
  updated_at: string;
  related_counts: RelatedCounts;
}

export interface GetIncidentInput {
  incident_id: string;
}

export interface SearchIncidentsInput {
  location_id?: string;
  severity?: Severity;
  status?: IncidentStatus;
  from?: string;
  to?: string;
  limit?: number;
  cursor?: string;
}

export interface CreateIncidentInput {
  incident_type: IncidentType;
  description: string;
  severity: Severity;
  location_id: string;
}

export interface UpdateIncidentInput {
  incident_id: string;
  expected_version: number;
  status?: IncidentStatus;
  severity?: Severity;
  note?: string;
  resolution_evidence_id?: string;
}