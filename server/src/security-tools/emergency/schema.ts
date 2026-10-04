/**
 * Schema Emergency: tham chiếu JSON Schema v0.3 cho wrapper P1, cộng kiểm tra runtime (§2.2, §6.2).
 */
import type { EmergencyEscalation, EmergencyProtocol } from "./types";

export const EMERGENCY_SCHEMAS = {
  EmergencyProtocol: "common.schema.json#/$defs/EmergencyProtocol",
  EscalationContact: "common.schema.json#/$defs/EscalationContact",
  EmergencyEscalation: "common.schema.json#/$defs/EmergencyEscalation",
  GetEmergencyProtocolInput:
    "common.schema.json#/$defs/GetEmergencyProtocolInput",
  GetEscalationContactsInput:
    "common.schema.json#/$defs/GetEscalationContactsInput",
  EscalateEmergencyInput: "common.schema.json#/$defs/EscalateEmergencyInput",
  AcknowledgeEmergencyInput:
    "common.schema.json#/$defs/AcknowledgeEmergencyInput",
  GetEmergencyEscalationInput:
    "common.schema.json#/$defs/GetEmergencyEscalationInput",
  GetIncidentEscalationsInput:
    "common.schema.json#/$defs/GetIncidentEscalationsInput",
  GetEmergencyProtocolOutput:
    "security_mcp.schema.json#/$defs/GetEmergencyProtocolOutput",
  GetEscalationContactsOutput:
    "security_mcp.schema.json#/$defs/GetEscalationContactsOutput",
  EscalateEmergencyOutput:
    "security_mcp.schema.json#/$defs/EscalateEmergencyOutput",
  AcknowledgeEmergencyOutput:
    "security_mcp.schema.json#/$defs/AcknowledgeEmergencyOutput",
  GetEmergencyEscalationOutput:
    "security_mcp.schema.json#/$defs/GetEmergencyEscalationOutput",
  GetIncidentEscalationsOutput:
    "security_mcp.schema.json#/$defs/GetIncidentEscalationsOutput",
} as const;

/** order liên tiếp 1..n, không trùng — JSON Schema không kiểm được. */
export function protocolRuntimeIssues(p: EmergencyProtocol): string[] {
  const orders = p.steps.map((s) => s.order).sort((a, b) => a - b);
  return orders.every((o, i) => o === i + 1)
    ? []
    : [
        `steps.order phải liên tiếp 1..${p.steps.length}, đang là [${orders.join(", ")}]`,
      ];
}

/** Ràng buộc thời gian giữa các field của một escalation. */
export function escalationRuntimeIssues(e: EmergencyEscalation): string[] {
  const issues: string[] = [];
  if (e.ack_deadline_at <= e.created_at)
    issues.push("ack_deadline_at phải sau created_at");
  if (e.updated_at < e.created_at) issues.push("updated_at trước created_at");
  if (e.notified_at !== null && e.notified_at < e.created_at)
    issues.push("notified_at trước created_at");
  if (e.acknowledged_at !== null) {
    if (e.notified_at === null || e.acknowledged_at < e.notified_at)
      issues.push("acknowledged_at trước notified_at");
    if (e.acknowledged_at >= e.ack_deadline_at)
      issues.push("ACK phải trước ack_deadline_at (timeout thắng từ deadline)");
  }
  return issues;
}
