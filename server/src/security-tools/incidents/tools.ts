/**
 * Khai báo tool Incident để src/tools.ts register (spec v0.3 §7). Handler là wrapper chung; P3 cung
 * cấp tên canonical, mode, schema ref, mô tả, annotation và kiểm tra runtime.
 */
import type { DomainToolDefinition } from "../tools";
import {
  incidentPageIssues,
  incidentRuntimeIssues,
  INCIDENT_SCHEMAS as S,
  searchIncidentsInputIssues,
} from "./schema";
import type { Incident, IncidentPage } from "./types";

const WRITE = { destructiveHint: true, idempotentHint: false } as const;
const incidentIssues = (data: unknown) =>
  incidentRuntimeIssues(data as Incident);

export const INCIDENT_TOOLS: readonly DomainToolDefinition[] = [
  {
    name: "get_incident",
    mode: "READ",
    inputSchema: S.GetIncidentInput,
    outputSchema: S.GetIncidentOutput,
    description:
      "Đọc một incident của property: loại, mô tả, trạng thái, mức độ, vị trí, version và related_counts (số dispatch/escalation/camera/evidence liên quan, dùng để quyết định có cần đọc tiếp hay không).",
    annotations: { readOnlyHint: true },
    outputIssues: incidentIssues,
  },
  {
    name: "search_incidents",
    mode: "READ",
    inputSchema: S.SearchIncidentsInput,
    outputSchema: S.SearchIncidentsOutput,
    description:
      "Tìm incident trong property theo location, severity, status và khoảng thời gian tạo [from, to). Các điều kiện kết hợp AND; không có điều kiện thì liệt kê toàn property. Sắp theo (created_at, incident_id), phân trang bằng cursor.",
    annotations: { readOnlyHint: true },
    inputIssues: searchIncidentsInputIssues,
    outputIssues: (data) => incidentPageIssues(data as IncidentPage),
  },
  {
    name: "create_incident",
    mode: "WRITE",
    inputSchema: S.CreateIncidentInput,
    outputSchema: S.CreateIncidentOutput,
    description:
      "Tạo incident mới ở trạng thái OPEN tại một location của property, gắn với ticket của phiên. Chỉ ActionExecutor gọi, cần execution grant.",
    annotations: WRITE,
    outputIssues: incidentIssues,
  },
  {
    name: "update_incident",
    mode: "WRITE",
    inputSchema: S.UpdateIncidentInput,
    outputSchema: S.UpdateIncidentOutput,
    description:
      "Cập nhật trạng thái, mức độ hoặc ghi chú của incident theo expected_version. Đổi trạng thái/mức độ phải có note; RESOLVED phải kèm evidence giải quyết của chính incident; CLOSED chỉ từ RESOLVED khi không còn dispatch mở hay escalation đang chờ. Chỉ ActionExecutor gọi, cần execution grant.",
    annotations: WRITE,
    outputIssues: incidentIssues,
  },
];
