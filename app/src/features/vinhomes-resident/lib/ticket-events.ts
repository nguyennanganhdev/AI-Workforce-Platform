/**
 * Public ticket events, derived from the operations snapshot.
 *
 * Event ids are deterministic (`<subject>:<type>[:<discriminator>]`) so deriving twice yields the
 * same ids: the reception-agent consumer posts each id at most once, which is what the backend's
 * event table + idempotent consumer will do. Names follow §8 of
 * docs/vinhomes-operations-staff-field-flow.md. Only resident-safe data goes in: no internal
 * notes, costs approvals or staff-only ids.
 */
import { getFieldFlow, formatVnd } from '@/features/vinhomes-operations/lib/field-flow';
import {
  CLEANING_PAUSE_REASON_LABELS,
  PAUSE_REASON_LABELS,
  quoteTotal,
  type CleaningPauseReason,
  type PauseReason,
} from '@/features/vinhomes-operations/types/field-flow';
import type { TicketPublicEvent } from '../types';
import { linkCase, ticketCode, type OperationsSnapshot } from './snapshot';

const PAUSE_LABELS: Record<PauseReason | CleaningPauseReason, string> = { ...PAUSE_REASON_LABELS, ...CLEANING_PAUSE_REASON_LABELS };

export function deriveTicketEvents(caseId: string, snapshot: OperationsSnapshot): TicketPublicEvent[] {
  const links = linkCase(caseId, snapshot);
  if (!links) return [];
  const { kase, candidate, incident, workOrders } = links;
  const events: TicketPublicEvent[] = [];
  const push = (e: Omit<TicketPublicEvent, 'caseId' | 'notify'> & { notify?: boolean }) =>
    events.push({ caseId, notify: true, ...e });

  push({
    id: `${caseId}:case.received`,
    type: 'case.received',
    label: 'Đã tiếp nhận phản ánh',
    message: `Mình đã tạo yêu cầu ${ticketCode(caseId)} và chuyển tới Ban quản lý tòa ${candidate?.location_json.towerCode ?? ''}.`.trim(),
    at: kase.opened_at,
    notify: false,
  });

  if (candidate?.status === 'DISCARDED') {
    push({
      id: `${candidate.id}:case.discarded`,
      type: 'case.discarded',
      label: 'Phản ánh đã được đóng',
      message: 'Ban quản lý đã xem và đóng phản ánh này. Nếu sự cố vẫn còn, bạn mở cuộc trò chuyện mới để báo lại nhé.',
      at: candidate.updated_at,
    });
  }

  if (incident) {
    const dispatched = workOrders.length > 0;
    push({
      id: `${incident.id}:incident.created`,
      type: 'incident.created',
      label: 'Ban quản lý đã xác nhận sự cố',
      message: dispatched
        ? 'Ban quản lý đã xác nhận sự cố và giao cho nhân viên phụ trách.'
        : 'Ban quản lý đã xác nhận sự cố và đang điều phối người xử lý.',
      at: incident.created_at,
    });

    const handoff = incident.contractor_handoff;
    if (handoff) {
      push({
        id: `${incident.id}:contractor.pending`,
        type: 'contractor.pending',
        label: 'Cần đơn vị chuyên môn',
        message: 'Sự cố cần đơn vị chuyên môn xử lý. Ban quản lý đang liên hệ và sẽ báo lịch hẹn cho bạn.',
        at: incident.created_at,
      });
      if (handoff.contacted_at) {
        push({
          id: `${incident.id}:contractor.contacted`,
          type: 'contractor.contacted',
          label: `Đã hẹn ${handoff.contractor_name ?? 'đơn vị xử lý'}`,
          message: `Đã có đơn vị xử lý: ${handoff.contractor_name ?? 'đơn vị chuyên môn'}, dự kiến ngày ${handoff.eta ?? '(chưa chốt)'}.`,
          at: handoff.contacted_at,
        });
      }
      if (handoff.resolved_at) {
        push({
          id: `${incident.id}:contractor.resolved`,
          type: 'contractor.resolved',
          label: 'Đơn vị chuyên môn đã khắc phục',
          message: 'Đơn vị chuyên môn đã khắc phục xong sự cố.',
          note: handoff.note ?? undefined,
          at: handoff.resolved_at,
        });
      }
    }
  }

  for (const wo of workOrders) {
    const flow = getFieldFlow(wo, incident?.category);
    const name = wo.executor_name ?? 'Nhân viên';
    const phone = wo.executor_phone ? ` (${wo.executor_phone})` : '';
    const total = quoteTotal(flow.quote.lines, flow.quote.labor_cost);

    push({
      id: `${wo.id}:job.assigned`,
      type: 'job.assigned',
      label: wo.attempt_no > 1 ? `Lượt xử lý lại, giao cho ${name}` : `Đã giao cho ${name}`,
      message:
        wo.attempt_no > 1
          ? `Mình đã tạo lượt xử lý lại và giao cho ${name}${phone}.`
          : `Yêu cầu của bạn đã được giao cho ${name}${phone}.`,
      at: wo.created_at,
    });
    if (flow.accepted_at) {
      push({
        id: `${wo.id}:job.accepted`,
        type: 'job.accepted',
        label: 'Nhân viên đã nhận việc',
        message: `${name} đã nhận việc và đang tới chỗ bạn.`,
        at: flow.accepted_at,
      });
    }
    if (flow.arrived_at) {
      push({
        id: `${wo.id}:job.arrived`,
        type: 'job.arrived',
        label: 'Nhân viên đã đến nơi',
        message: `${name} đã đến nơi và đang kiểm tra.`,
        at: flow.arrived_at,
      });
    }
    if (flow.stage === 'AWAITING_RESIDENT_AGREEMENT') {
      push({
        id: `${wo.id}:quote.awaiting:${total}`,
        type: 'quote.awaiting',
        label: 'Chờ bạn đồng ý danh mục sửa chữa',
        message: `${name} đã lập danh mục sửa chữa ${formatVnd(total)}. Bạn xem và bấm đồng ý để bắt đầu sửa nhé.`,
        at: wo.updated_at,
      });
    }
    if (flow.agreement) {
      push({
        id: `${wo.id}:quote.agreed`,
        type: 'quote.agreed',
        label: `Đã đồng ý danh mục ${formatVnd(flow.agreement.total)}`,
        message: `Đã ghi nhận bạn đồng ý danh mục ${formatVnd(flow.agreement.total)}. ${name} bắt đầu sửa.`,
        at: flow.agreement.agreed_at,
      });
    } else if (flow.started_at && flow.kind === 'REPAIR') {
      push({
        id: `${wo.id}:job.started`,
        type: 'job.started',
        label: 'Bắt đầu xử lý (không phát sinh chi phí)',
        message: `${name} bắt đầu xử lý, không phát sinh chi phí.`,
        at: flow.started_at,
      });
    }
    if (flow.stage === 'PAUSED' && flow.pause_reason) {
      const absent = flow.pause_reason === 'RESIDENT_ABSENT';
      push({
        id: `${wo.id}:job.paused:${flow.pause_reason}:${wo.version}`,
        type: 'job.paused',
        label: `Tạm dừng: ${PAUSE_LABELS[flow.pause_reason]}`,
        message: absent
          ? `${name} chưa gặp được bạn tại căn hộ. Bạn nhắn thời gian thuận tiện để mình hẹn lại nhé.`
          : `Công việc tạm dừng (${PAUSE_LABELS[flow.pause_reason].toLowerCase()}). Mình sẽ báo ngay khi tiếp tục.`,
        at: wo.updated_at,
      });
    }
    if (flow.stage === 'AWAITING_RESIDENT_SIGNATURE') {
      push({
        id: `${wo.id}:signature.awaiting:${total}`,
        type: 'signature.awaiting',
        label: 'Chờ bạn ký xác nhận',
        message: `${name} đã sửa xong. Bạn xem lại danh mục cuối (${formatVnd(total)}) và ký xác nhận nhé.`,
        at: wo.updated_at,
      });
    }
    if (flow.signature) {
      push({
        id: `${wo.id}:signature.signed`,
        type: 'signature.signed',
        label: 'Đã ký xác nhận',
        message: 'Đã ghi nhận chữ ký xác nhận của bạn.',
        at: flow.signature.signed_at,
      });
    }
    if (flow.stage === 'DISPUTED') {
      push({
        id: `${wo.id}:job.disputed`,
        type: 'job.disputed',
        label: 'Chuyển Ban quản lý giải quyết',
        message: 'Mình đã chuyển ý kiến của bạn về phần phát sinh cho Ban quản lý. Ban quản lý sẽ liên hệ bạn.',
        at: wo.updated_at,
      });
    }
    if (flow.submitted_at && flow.kind === 'REPAIR') {
      push({
        id: `${wo.id}:report.submitted`,
        type: 'report.submitted',
        label: 'Nhân viên đã gửi báo cáo',
        message: 'Nhân viên đã gửi báo cáo kết quả. Bạn kiểm tra và bấm “Xác nhận hoàn thành” nhé. Nếu chưa đạt, bạn báo lại trong 72 giờ.',
        note: flow.report_final_note || undefined,
        at: flow.submitted_at,
      });
    }
    if (flow.completed_at) {
      const done: Record<string, [string, string, string]> = {
        COMPLETED_BY_RESIDENT: ['resident.confirmed', 'Bạn đã xác nhận hoàn thành', 'Cảm ơn bạn đã xác nhận. Yêu cầu đã hoàn tất.'],
        COMPLETED_AUTO: ['job.completed_auto', 'Tự động hoàn thành sau 72 giờ', 'Yêu cầu đã tự động hoàn tất sau 72 giờ.'],
        REWORK_REQUIRED: ['resident.reported_issue', 'Bạn báo kết quả chưa đạt', 'Mình đã ghi nhận kết quả chưa đạt và tạo lượt xử lý lại.'],
        CANCELLED_BY_RESIDENT: ['job.cancelled', 'Bạn chọn không sửa', 'Đã ghi nhận bạn không muốn sửa nữa. Yêu cầu được đóng.'],
        DONE:
          flow.kind === 'CLEANING'
            ? [
                'cleaning.completed',
                'Đã làm sạch',
                flow.sign_required ? 'Khu vực đã được làm sạch. Sàn còn ướt, bạn đi lại cẩn thận nhé.' : 'Khu vực đã được làm sạch.',
              ]
            : ['security.completed', 'Đội an ninh đã xử lý', 'Đội an ninh đã đến xử lý phản ánh của bạn.'],
      };
      const d = done[flow.stage];
      if (d) {
        push({
          id: `${wo.id}:${d[0]}`,
          type: d[0],
          label: d[1],
          message: d[2],
          note: flow.stage === 'REWORK_REQUIRED' ? flow.rework_note ?? undefined : undefined,
          at: flow.completed_at,
        });
      }
    }
  }

  if (incident?.closed_at && !events.some((e) => e.type === 'resident.confirmed' || e.type === 'contractor.resolved')) {
    push({
      id: `${incident.id}:incident.closed`,
      type: 'incident.closed',
      label: 'Sự cố đã đóng',
      message: 'Ban quản lý đã xử lý xong và đóng sự cố.',
      note: incident.bql_resolution_note,
      at: incident.closed_at,
    });
  }

  return events.sort((a, b) => a.at.localeCompare(b.at) || a.id.localeCompare(b.id));
}
