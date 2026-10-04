/**
 * Khai báo tool Audit để src/tools.ts register (spec v0.3 §7). Ba tool chỉ đọc; get_dispatch_history
 * trả projection DispatchSummary do P4 định nghĩa.
 */
import type { DomainToolDefinition } from "../tools";
import {
  dispatchHistoryIssues,
  evidencePageIssues,
  AUDIT_SCHEMAS as S,
  timelinePageIssues,
} from "./schema";
import type { DispatchHistoryPage, EvidencePage, TimelinePage } from "./types";

export const AUDIT_TOOLS: readonly DomainToolDefinition[] = [
  {
    name: "get_incident_evidence",
    mode: "READ",
    inputSchema: S.GetIncidentEvidenceInput,
    outputSchema: S.GetIncidentEvidenceOutput,
    description:
      "Danh sách bằng chứng của một incident (biên nhận lệnh, ghi chú người vận hành, tham chiếu bên ngoài), sắp theo (created_at, evidence_id). Biên nhận lệnh chỉ chứng minh lệnh đã chạy, không chứng minh sự cố đã được giải quyết.",
    annotations: { readOnlyHint: true },
    outputIssues: (data) => evidencePageIssues(data as EvidencePage),
  },
  {
    name: "get_dispatch_history",
    mode: "READ",
    inputSchema: S.GetDispatchHistoryInput,
    outputSchema: S.GetDispatchHistoryOutput,
    description:
      "Lịch sử các lệnh điều động bảo vệ của một incident (tóm tắt), sắp theo (created_at, dispatch_id).",
    annotations: { readOnlyHint: true },
    outputIssues: (data) => dispatchHistoryIssues(data as DispatchHistoryPage),
  },
  {
    name: "get_security_event_timeline",
    mode: "READ",
    inputSchema: S.GetSecurityEventTimelineInput,
    outputSchema: S.GetSecurityEventTimelineOutput,
    description:
      "Dòng thời gian sự kiện của một incident (tạo, cập nhật, điều động, báo khẩn, thêm bằng chứng), sắp theo (created_at, event_id). Mỗi sự kiện trỏ tới một evidence.",
    annotations: { readOnlyHint: true },
    outputIssues: (data) => timelinePageIssues(data as TimelinePage),
  },
];
