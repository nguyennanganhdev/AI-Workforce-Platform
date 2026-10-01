/**
 * Kiểu Emergency — P4 sở hữu ProtocolStep, EmergencyProtocol, EscalationContact,
 * EmergencyEscalation (spec v0.3 §2.2, §10). Nguồn cấu trúc là schema/common.schema.json.
 */
import type { Actor } from "../common/context"; // P1
import type { IncidentType } from "../incidents/types"; // P3

export type EmergencySeverity = "P0" | "P1";
export type ContactRole = "SECURITY_SUPERVISOR" | "PROPERTY_MANAGER" | "EMERGENCY_COORDINATOR";
export type ContactAvailability = "ON_DUTY" | "OFF_DUTY" | "UNKNOWN";
export type ContactChannel = "PHONE" | "SMS" | "PUSH" | "EMAIL";
export type EscalationStatus = "PENDING" | "NOTIFIED" | "ACKNOWLEDGED" | "FAILED" | "ACK_TIMEOUT";
export type EscalationFailureCode = "DELIVERY_FAILED" | "PROVIDER_REJECTED";

export type ProtocolStep = {
  order: number;
  action: string;
  responsible_role: ContactRole;
  required: boolean;
  time_limit_minutes: number | null;
};

export type EmergencyProtocol = {
  protocol_id: string;
  version: number;
  incident_type: IncidentType;
  severity: EmergencySeverity;
  steps: ProtocolStep[];
  ack_timeout_seconds: number;
};

export type EscalationContact = {
  contact_id: string;
  role: ContactRole;
  /** Số nhỏ ưu tiên cao. */
  priority: number;
  availability: ContactAvailability;
  supported_severities: EmergencySeverity[];
  channels: ContactChannel[];
};

export type EmergencyEscalation = {
  escalation_id: string;
  incident_id: string;
  /** Snapshot từ incident lúc tạo. */
  severity: EmergencySeverity;
  protocol_id: string;
  protocol_version: number;
  contact_id: string;
  reason: string;
  status: EscalationStatus;
  version: number;
  notification_reference_id: string | null;
  notified_at: string | null;
  ack_deadline_at: string;
  acknowledged_at: string | null;
  acknowledged_by: Actor | null;
  ack_receipt_id: string | null;
  failure_code: EscalationFailureCode | null;
  created_at: string;
  updated_at: string;
};

/** Receipt ACK bất biến Core tạo khi người trực xác nhận (§6.2). Dữ liệu nội bộ, không phải DTO public. */
export type AckReceipt = {
  ack_receipt_id: string;
  escalation_id: string;
  contact_id: string;
  actor: Actor;
  /** Core đóng dấu, caller không backdate. */
  received_at: string;
};

export type GetEmergencyProtocolInput = { incident_type: IncidentType; severity: EmergencySeverity };
export type GetEscalationContactsInput = { severity: EmergencySeverity; limit?: number; cursor?: string };
export type EscalateEmergencyInput = {
  incident_id: string;
  incident_version: number;
  protocol_id: string;
  protocol_version: number;
  contact_id: string;
  reason: string;
};
export type AcknowledgeEmergencyInput = { escalation_id: string; expected_version: number; ack_receipt_id: string };
export type GetEmergencyEscalationInput = { escalation_id: string };
export type GetIncidentEscalationsInput = { incident_id: string; limit?: number; cursor?: string };
