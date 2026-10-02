/**
 * Quy tắc nghiệp vụ Incident theo spec v0.3 §6.1.
 *
 * Hàm thuần: nhận trạng thái đã đọc, trả quyết định. Core API quyết định cuối trong transaction; mock
 * provider dùng các hàm này để có cùng semantics. Không có transition ngầm; đổi status của incident
 * không tự đổi Ticket/Case, dispatch COMPLETED không tự làm incident RESOLVED.
 */
import type { EvidenceItem } from "../audits/types";
import type { Rejection } from "../dispatch/service"; // P4
import type { Location } from "../guards/types"; // P2
import type {
  CreateIncidentInput,
  Incident,
  IncidentStatus,
  UpdateIncidentInput,
} from "./types";

export const INCIDENT_TRANSITIONS: Readonly<
  Record<IncidentStatus, readonly IncidentStatus[]>
> = {
  OPEN: ["IN_PROGRESS", "RESOLVED"],
  IN_PROGRESS: ["RESOLVED"],
  RESOLVED: ["IN_PROGRESS", "CLOSED"],
  CLOSED: [],
};

/** Trạng thái còn xử lý được: dispatch/escalate được, đổi severity được. */
export const ACTIVE_INCIDENT_STATUSES: readonly IncidentStatus[] = [
  "OPEN",
  "IN_PROGRESS",
];

/**
 * Loại evidence được nhận làm bằng chứng giải quyết. ACTION_RECEIPT chỉ chứng minh một lệnh đã chạy
 * (điều động, gửi thông báo...), không chứng minh sự cố đã được giải quyết (§6.1).
 */
export const RESOLUTION_EVIDENCE_TYPES: readonly EvidenceItem["evidence_type"][] =
  ["OPERATOR_NOTE", "EXTERNAL_REFERENCE"];

export const canTransitionIncident = (
  from: IncidentStatus,
  to: IncidentStatus,
) => INCIDENT_TRANSITIONS[from].includes(to);

/**
 * Incident mới từ payload đã duyệt: luôn OPEN, severity từ payload, location đã tra đúng scope, ticket
 * lấy từ context tin cậy. version 0 và related_counts 0: bước ghi audit cùng transaction (evidence
 * ACTION_RECEIPT đầu tiên) đưa version lên 1 và evidence lên 1.
 */
export function createIncident(args: {
  incidentId: string;
  ticketId: string;
  input: CreateIncidentInput;
  location: Location;
  now: string;
}): Incident {
  return {
    incident_id: args.incidentId,
    ticket_id: args.ticketId,
    incident_type: args.input.incident_type,
    description: args.input.description,
    status: "OPEN",
    severity: args.input.severity,
    location: args.location,
    version: 0,
    created_at: args.now,
    updated_at: args.now,
    related_counts: { dispatches: 0, escalations: 0, cameras: 0, evidence: 0 },
  };
}

/**
 * Precondition cho command `update_incident` MỚI (replay cùng key không đi qua đây — §5). Input đã
 * qua JSON Schema (patch không rỗng, note khi đổi status/severity, RESOLVED có resolution_evidence_id).
 *
 * - `evidence`: evidence của chính incident này, đã lọc theo scope. ID ngoài danh sách coi như không tồn tại.
 * - `openDispatches` / `waitingEscalations`: số dispatch PENDING/EN_ROUTE/ON_SITE và escalation
 *   PENDING/NOTIFIED của incident, để chặn CLOSED.
 */
export function checkUpdateIncident(args: {
  incident: Incident;
  input: UpdateIncidentInput;
  evidence: readonly EvidenceItem[];
  openDispatches: number;
  waitingEscalations: number;
}): Rejection {
  const { incident, input } = args;
  // CLOSED là trạng thái cuối: không update kể cả note; audit bổ sung đi quy trình platform riêng.
  if (incident.status === "CLOSED")
    return {
      code: "INVALID_STATE_TRANSITION",
      reason: "Incident đã CLOSED, không cập nhật được",
    };
  if (incident.version !== input.expected_version) {
    return {
      code: "CONFLICT",
      reason: `expected_version ${input.expected_version} đã cũ (hiện ${incident.version})`,
    };
  }

  const target = input.status ?? incident.status;
  if (input.status !== undefined) {
    if (input.status === incident.status) {
      // Caller muốn chỉ ghi note thì bỏ field status.
      return {
        code: "INVALID_STATE_TRANSITION",
        reason: `Incident đã ở ${incident.status}`,
      };
    }
    if (!canTransitionIncident(incident.status, input.status)) {
      return {
        code: "INVALID_STATE_TRANSITION",
        reason: `${incident.status} → ${input.status} không hợp lệ`,
      };
    }
  }

  if (input.resolution_evidence_id !== undefined) {
    if (input.status !== "RESOLVED") {
      return {
        code: "VALIDATION_ERROR",
        reason: "resolution_evidence_id chỉ dùng khi chuyển sang RESOLVED",
      };
    }
    const item = args.evidence.find(
      (e) => e.evidence_id === input.resolution_evidence_id,
    );
    // Evidence của incident/scope khác trả như không tồn tại, không lộ sự tồn tại của nó.
    if (!item)
      return {
        code: "NOT_FOUND",
        reason: "Không tìm thấy evidence của incident này",
      };
    if (!RESOLUTION_EVIDENCE_TYPES.includes(item.evidence_type)) {
      return {
        code: "VALIDATION_ERROR",
        reason: `Evidence ${item.evidence_type} không chứng minh sự cố đã được giải quyết`,
      };
    }
  }

  if (input.severity !== undefined) {
    if (input.severity === incident.severity)
      return {
        code: "INVALID_STATE_TRANSITION",
        reason: `Severity đã là ${incident.severity}`,
      };
    const reopen = incident.status === "RESOLVED" && target === "IN_PROGRESS";
    if (!ACTIVE_INCIDENT_STATUSES.includes(incident.status) && !reopen) {
      return {
        code: "INVALID_STATE_TRANSITION",
        reason: `Không đổi severity khi incident đang ${incident.status}`,
      };
    }
  }

  if (target === "CLOSED") {
    if (
      !args.evidence.some((e) =>
        RESOLUTION_EVIDENCE_TYPES.includes(e.evidence_type),
      )
    ) {
      return {
        code: "INVALID_STATE_TRANSITION",
        reason: "Chưa có bằng chứng giải quyết để đóng incident",
      };
    }
    if (args.openDispatches > 0 || args.waitingEscalations > 0) {
      return {
        code: "INVALID_STATE_TRANSITION",
        reason: "Còn dispatch mở hoặc escalation đang chờ",
      };
    }
  }
  return null;
}

/**
 * Áp patch đã qua `checkUpdateIncident`. Không tăng version/updated_at: bước ghi audit cùng
 * transaction tăng đúng một lần cho cả lệnh (đổi related_counts cũng nằm trong lần tăng đó).
 */
export function applyUpdate(
  incident: Incident,
  input: UpdateIncidentInput,
): Incident {
  return {
    ...incident,
    status: input.status ?? incident.status,
    severity: input.severity ?? incident.severity,
  };
}

/** Data của event INCIDENT_UPDATED (common.schema.json#/$defs/INCIDENT_UPDATEDData). */
export function incidentUpdatedEvent(
  before: Incident,
  after: Incident,
  note: string | undefined,
) {
  return {
    previous_status: before.status,
    status: after.status,
    previous_severity: before.severity,
    severity: after.severity,
    note: note ?? null,
  };
}
