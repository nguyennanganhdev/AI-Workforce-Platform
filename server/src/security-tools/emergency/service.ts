/**
 * Quy tắc nghiệp vụ Emergency theo spec v0.3 §6.2. Hàm thuần, cùng vai trò như dispatch/service.ts.
 *
 * MCP không chạy timer, không gửi thông báo, không tự chọn contact dự phòng. `applyNotificationResult`
 * và `applyExpire` mô tả command nội bộ Core do worker platform gọi, để mock provider có cùng semantics.
 */
import type { Actor } from "../common/context"; // P1
import type { Incident } from "../incidents/types"; // P3
import type { Rejection } from "../dispatch/service";
import type {
  AckReceipt,
  EmergencyEscalation,
  EmergencyProtocol,
  EscalationContact,
  EscalationFailureCode,
  EscalationStatus,
} from "./types";

export const ESCALATION_TRANSITIONS: Readonly<Record<EscalationStatus, readonly EscalationStatus[]>> = {
  PENDING: ["NOTIFIED", "FAILED", "ACK_TIMEOUT"],
  NOTIFIED: ["ACKNOWLEDGED", "FAILED", "ACK_TIMEOUT"],
  ACKNOWLEDGED: [],
  FAILED: [],
  ACK_TIMEOUT: [],
};

/** Escalation đang chờ: chặn tạo escalation mới cùng incident + contact. */
export const WAITING_ESCALATION_STATUSES: readonly EscalationStatus[] = ["PENDING", "NOTIFIED"];

const ESCALATABLE_INCIDENT_STATUSES: readonly string[] = ["OPEN", "IN_PROGRESS"];

export const isTerminalEscalation = (s: EscalationStatus) => ESCALATION_TRANSITIONS[s].length === 0;
export const isWaitingEscalation = (e: Pick<EmergencyEscalation, "status">) =>
  WAITING_ESCALATION_STATUSES.includes(e.status);

/** §6.2: priority tăng dần rồi contact_id tăng dần để phá hòa. */
export function sortContacts<T extends Pick<EscalationContact, "priority" | "contact_id">>(contacts: readonly T[]): T[] {
  return [...contacts].sort((a, b) =>
    a.priority !== b.priority ? a.priority - b.priority : a.contact_id < b.contact_id ? -1 : a.contact_id > b.contact_id ? 1 : 0,
  );
}

/** deadline = created_at + ack_timeout_seconds, tính cả thời gian gửi (§6.2). */
export function ackDeadline(createdAt: string, ackTimeoutSeconds: number): string {
  return new Date(Date.parse(createdAt) + ackTimeoutSeconds * 1000).toISOString();
}

/** Precondition cho command `escalate_emergency` MỚI. */
export function checkEscalate(args: {
  incident: Incident;
  incidentVersion: number;
  protocol: EmergencyProtocol | null;
  protocolVersion: number;
  contact: EscalationContact | null;
  existingForIncident: readonly Pick<EmergencyEscalation, "contact_id" | "status">[];
}): Rejection {
  const { incident, protocol, contact } = args;
  // Chặn cả khi gọi thẳng tool, bỏ qua skill.
  if (incident.severity !== "P0" && incident.severity !== "P1") {
    return { code: "EMERGENCY_NOT_ELIGIBLE", reason: `Incident ${incident.severity} không thuộc luồng khẩn cấp` };
  }
  if (!ESCALATABLE_INCIDENT_STATUSES.includes(incident.status)) {
    // §5.1: state không hợp lệ → INVALID_STATE_TRANSITION.
    return { code: "INVALID_STATE_TRANSITION", reason: `Incident đang ${incident.status}` };
  }
  if (incident.version !== args.incidentVersion) return { code: "CONFLICT", reason: "incident_version đã cũ" };
  if (protocol === null) return { code: "NOT_FOUND", reason: "Không có protocol trong property" };
  if (
    protocol.version !== args.protocolVersion ||
    protocol.incident_type !== incident.incident_type ||
    protocol.severity !== incident.severity
  ) {
    return { code: "CONFLICT", reason: "Protocol/version không còn khớp incident" };
  }
  if (contact === null) return { code: "NOT_FOUND", reason: "Không có contact trong property" };
  if (contact.availability !== "ON_DUTY" || !contact.supported_severities.includes(incident.severity)) {
    return { code: "CONTACT_NOT_AVAILABLE", reason: `Contact ${contact.contact_id} không khả dụng cho ${incident.severity}` };
  }
  if (args.existingForIncident.some((e) => e.contact_id === contact.contact_id && isWaitingEscalation(e))) {
    return { code: "CONFLICT", reason: "Đã có escalation đang chờ tới contact này" };
  }
  return null;
}

export function createEscalation(args: {
  escalationId: string;
  incident: Incident & { severity: "P0" | "P1" };
  protocol: EmergencyProtocol;
  contactId: string;
  reason: string;
  now: string;
}): EmergencyEscalation {
  return {
    escalation_id: args.escalationId,
    incident_id: args.incident.incident_id,
    severity: args.incident.severity,
    protocol_id: args.protocol.protocol_id,
    protocol_version: args.protocol.version,
    contact_id: args.contactId,
    reason: args.reason,
    status: "PENDING",
    version: 1,
    notification_reference_id: null,
    notified_at: null,
    ack_deadline_at: ackDeadline(args.now, args.protocol.ack_timeout_seconds),
    acknowledged_at: null,
    acknowledged_by: null,
    ack_receipt_id: null,
    failure_code: null,
    created_at: args.now,
    updated_at: args.now,
  };
}

/**
 * Precondition cho command `acknowledge_emergency` MỚI.
 * `grantActor`: actor trong execution grant đã verify. `now`: đồng hồ Core lúc commit.
 */
export function checkAcknowledge(args: {
  escalation: EmergencyEscalation;
  expectedVersion: number;
  receipt: AckReceipt | null;
  grantActor: Actor;
  now: string;
}): Rejection {
  const { escalation: e, receipt } = args;
  // §6.2: kiểm terminal trước expected_version.
  if (isTerminalEscalation(e.status)) return { code: "INVALID_STATE_TRANSITION", reason: `Escalation đã ${e.status}` };
  // Từ deadline trở đi timeout thắng; worker sẽ ghi ACK_TIMEOUT.
  if (args.now >= e.ack_deadline_at) {
    return { code: "INVALID_STATE_TRANSITION", reason: "Đã quá ack_deadline_at" };
  }
  if (e.status !== "NOTIFIED") {
    // §6.2: ACK chỉ hợp lệ từ NOTIFIED.
    return { code: "INVALID_STATE_TRANSITION", reason: "Chỉ ACK được escalation đã NOTIFIED" };
  }
  if (e.version !== args.expectedVersion) return { code: "CONFLICT", reason: "expected_version đã cũ" };
  if (
    receipt === null ||
    receipt.escalation_id !== e.escalation_id ||
    receipt.contact_id !== e.contact_id ||
    receipt.actor.actor_id !== args.grantActor.actor_id ||
    receipt.actor.actor_type !== args.grantActor.actor_type
  ) {
    return { code: "ACK_NOT_AUTHORIZED", reason: "Receipt không khớp escalation/contact/actor" };
  }
  if (receipt.received_at >= e.ack_deadline_at) {
    return { code: "INVALID_STATE_TRANSITION", reason: "Receipt nhận sau ack_deadline_at" };
  }
  return null;
}

export function applyAcknowledge(e: EmergencyEscalation, receipt: AckReceipt, now: string): EmergencyEscalation {
  return {
    ...e,
    status: "ACKNOWLEDGED",
    version: e.version + 1,
    acknowledged_at: receipt.received_at,
    // Lấy từ receipt đã verify, không lấy principal ActionExecutor (§6.2).
    acknowledged_by: receipt.actor,
    ack_receipt_id: receipt.ack_receipt_id,
    updated_at: now,
  };
}

type Applied = { ok: true; escalation: EmergencyEscalation } | { ok: false; rejection: NonNullable<Rejection> };

/**
 * Core `recordNotificationResult` (callback notification worker). Callback tới từ deadline trở đi
 * mà escalation còn chờ thì ghi ACK_TIMEOUT (§6.2).
 */
export function applyNotificationResult(
  e: EmergencyEscalation,
  r: {
    expectedVersion: number;
    result: "NOTIFIED" | "FAILED";
    providerReferenceId: string;
    failureCode?: EscalationFailureCode;
    now: string;
  },
): Applied {
  if (isTerminalEscalation(e.status)) {
    return { ok: false, rejection: { code: "INVALID_STATE_TRANSITION", reason: `Escalation đã ${e.status}` } };
  }
  if (e.version !== r.expectedVersion) return { ok: false, rejection: { code: "CONFLICT", reason: "expected_version đã cũ" } };
  if (r.result === "NOTIFIED" && e.status !== "PENDING") {
    return { ok: false, rejection: { code: "INVALID_STATE_TRANSITION", reason: `${e.status} → NOTIFIED không hợp lệ` } };
  }
  if (r.result === "FAILED" && !r.failureCode) {
    return { ok: false, rejection: { code: "VALIDATION_ERROR", reason: "FAILED cần failure_code" } };
  }
  const base = { ...e, version: e.version + 1, updated_at: r.now };
  if (r.now >= e.ack_deadline_at) return { ok: true, escalation: { ...base, status: "ACK_TIMEOUT" } };
  if (r.result === "NOTIFIED") {
    return {
      ok: true,
      escalation: { ...base, status: "NOTIFIED", notification_reference_id: r.providerReferenceId, notified_at: r.now },
    };
  }
  return { ok: true, escalation: { ...base, status: "FAILED", failure_code: r.failureCode ?? null } };
}

/** Core `expireEscalation` (SLA worker platform gọi). */
export function applyExpire(e: EmergencyEscalation, x: { expectedVersion: number; now: string }): Applied {
  if (!isWaitingEscalation(e)) {
    return { ok: false, rejection: { code: "INVALID_STATE_TRANSITION", reason: `Escalation đã ${e.status}` } };
  }
  if (e.version !== x.expectedVersion) return { ok: false, rejection: { code: "CONFLICT", reason: "expected_version đã cũ" } };
  if (x.now < e.ack_deadline_at) {
    return { ok: false, rejection: { code: "INVALID_STATE_TRANSITION", reason: "Chưa tới ack_deadline_at" } };
  }
  return { ok: true, escalation: { ...e, status: "ACK_TIMEOUT", version: e.version + 1, updated_at: x.now } };
}
