/**
 * Khai báo tool Emergency để P1 register (spec v0.3 §7). Xem dispatch/tools.ts.
 */
import {
  type P4ToolDefinition,
  READ_ANNOTATIONS,
  WRITE_ANNOTATIONS,
} from "../dispatch/tools";
import { EMERGENCY_SCHEMAS as S } from "./schema";

export const EMERGENCY_TOOLS: readonly P4ToolDefinition[] = [
  {
    name: "get_emergency_protocol",
    mode: "READ",
    inputSchema: S.GetEmergencyProtocolInput,
    outputSchema: S.GetEmergencyProtocolOutput,
    description:
      "Lấy quy trình khẩn cấp đã publish của property cho đúng loại sự cố và mức P0/P1.",
    annotations: READ_ANNOTATIONS,
  },
  {
    name: "get_escalation_contacts",
    mode: "READ",
    inputSchema: S.GetEscalationContactsInput,
    outputSchema: S.GetEscalationContactsOutput,
    description:
      "Danh sách đầu mối khẩn cấp của property theo mức P0/P1, sắp theo priority. Không có số điện thoại/email.",
    annotations: READ_ANNOTATIONS,
  },
  {
    name: "escalate_emergency",
    mode: "WRITE",
    inputSchema: S.EscalateEmergencyInput,
    outputSchema: S.EscalateEmergencyOutput,
    description:
      "Tạo escalation (PENDING) tới một contact đã duyệt; severity lấy từ incident. Chỉ ActionExecutor gọi, cần execution grant.",
    annotations: WRITE_ANNOTATIONS,
  },
  {
    name: "acknowledge_emergency",
    mode: "WRITE",
    inputSchema: S.AcknowledgeEmergencyInput,
    outputSchema: S.AcknowledgeEmergencyOutput,
    description:
      "Ghi nhận người trực đã xác nhận escalation bằng ack receipt đã xác thực. Chỉ workflow platform gọi qua ActionExecutor.",
    annotations: WRITE_ANNOTATIONS,
  },
  {
    name: "get_emergency_escalation",
    mode: "READ",
    inputSchema: S.GetEmergencyEscalationInput,
    outputSchema: S.GetEmergencyEscalationOutput,
    description: "Đọc một escalation và trạng thái gửi/xác nhận của nó.",
    annotations: READ_ANNOTATIONS,
  },
  {
    name: "get_incident_escalations",
    mode: "READ",
    inputSchema: S.GetIncidentEscalationsInput,
    outputSchema: S.GetIncidentEscalationsOutput,
    description: "Danh sách escalation của một incident, cũ tới mới.",
    annotations: READ_ANNOTATIONS,
  },
];
