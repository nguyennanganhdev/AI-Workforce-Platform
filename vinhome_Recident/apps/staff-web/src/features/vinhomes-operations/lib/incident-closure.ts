/**
 * Điều kiện để một sự cố được đánh dấu đã xử lý / đóng.
 * Dùng chung cho resolveIncident và managerApproveAndCloseSession để không còn đường đóng nào bỏ qua kiểm tra.
 */
import type { VhTask } from '../types/task';
import type { VhWorkOrder } from '../types/work-order';
import type { VhQcResult } from '../types/qc';
import type { VhActionApproval } from '../types/action';
import type { FieldStage } from '../types/field-flow';
import { getStageMeta } from './field-flow';

/** Field-flow stages that count as finished for the incident. */
const FIELD_FINISHED: FieldStage[] = ['DONE', 'COMPLETED_BY_RESIDENT', 'COMPLETED_AUTO', 'CANCELLED_BY_RESIDENT'];

function latestAttempt(wos: VhWorkOrder[]): VhWorkOrder {
  return [...wos].sort(
    (a, b) => (b.attempt_no || 1) - (a.attempt_no || 1) || (b.created_at || '').localeCompare(a.created_at || ''),
  )[0];
}

/** Returns the first blocking reason, or null when the incident can be closed. */
export function getIncidentClosureBlocker(
  incidentId: string,
  data: { tasks: VhTask[]; workOrders: VhWorkOrder[]; qcResults: VhQcResult[]; approvals: VhActionApproval[] },
): string | null {
  const incidentTasks = data.tasks.filter((t) => t.incident_id === incidentId);
  const incidentWos = data.workOrders.filter((w) => w.incident_id === incidentId);

  for (const t of incidentTasks) {
    const taskWos = incidentWos.filter((w) => w.task_id === t.id);
    if (taskWos.length === 0) {
      if (t.status !== 'DONE' && t.status !== 'CANCELLED') return `Nhiệm vụ "${t.title}" chưa hoàn thành.`;
      continue;
    }
    const latest = latestAttempt(taskWos);

    // Luồng hiện trường mới: hoàn thành qua cư dân xác nhận / tự động 72h / vệ sinh & an ninh xong ngay
    if (latest.field_flow) {
      if (!FIELD_FINISHED.includes(latest.field_flow.stage)) {
        return `Phiếu ${latest.id} của nhiệm vụ "${t.title}" chưa hoàn thành (${getStageMeta(latest.field_flow.stage).label}).`;
      }
      continue;
    }

    // Luồng cũ: cần phiếu COMPLETED và QC PASS
    if (t.status !== 'DONE') return `Nhiệm vụ "${t.title}" chưa hoàn thành.`;
    if (latest.status !== 'COMPLETED') return `Phiếu thi công mới nhất (${latest.id}) của nhiệm vụ "${t.title}" chưa hoàn tất.`;
    const qc = data.qcResults.find((q) => q.work_order_id === latest.id);
    if (!qc) return `Phiếu thi công ${latest.id} chưa có kết quả nghiệm thu.`;
    if (qc.outcome !== 'PASS') return `Kết quả nghiệm thu phiếu ${latest.id} chưa đạt (${qc.outcome}).`;
  }

  const pendingApprovals = data.approvals.filter((a) => a.action_request?.incident_id === incidentId && a.status === 'PENDING');
  if (pendingApprovals.length > 0) return `Còn ${pendingApprovals.length} đề xuất chi phí đang chờ duyệt.`;

  return null;
}
