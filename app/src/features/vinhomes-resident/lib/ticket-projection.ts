/**
 * Resident-facing projection of a ticket (Case) from the operations snapshot.
 * The server owns this in production; statuses are computed, never taken from the client.
 */
import { getFieldFlow, splitQuote } from '@/features/vinhomes-operations/lib/field-flow';
import { teamLabelOf } from '@/features/vinhomes-operations/lib/resident-intake';
import { quoteTotal, type FieldFlow, type FieldStage } from '@/features/vinhomes-operations/types/field-flow';
import type { PendingAction, QuoteView, ResidentTicketView, TicketStatus, TicketTone } from '../types';
import { linkCase, ticketCode, type OperationsSnapshot } from './snapshot';
import { deriveTicketEvents } from './ticket-events';

const STATUS_META: Record<TicketStatus, { label: string; tone: TicketTone }> = {
  received: { label: 'Đã tiếp nhận', tone: 'neutral' },
  dispatching: { label: 'Đang điều phối', tone: 'neutral' },
  on_the_way: { label: 'Nhân viên đang đến', tone: 'info' },
  inspecting: { label: 'Đang kiểm tra', tone: 'info' },
  in_progress: { label: 'Đang xử lý', tone: 'info' },
  paused: { label: 'Tạm dừng', tone: 'attention' },
  waiting_you: { label: 'Chờ bạn', tone: 'attention' },
  finishing: { label: 'Đang hoàn tất', tone: 'info' },
  rework: { label: 'Đang xử lý lại', tone: 'info' },
  escalated: { label: 'Chờ Ban quản lý', tone: 'danger' },
  completed: { label: 'Hoàn tất', tone: 'success' },
  cancelled: { label: 'Đã đóng', tone: 'muted' },
};

export function statusMeta(status: TicketStatus) {
  return STATUS_META[status];
}

function quoteView(flow: FieldFlow): QuoteView {
  const { agreed, additional } = splitQuote(flow.quote.lines);
  return {
    lines: flow.quote.lines,
    agreedLines: agreed,
    additionalLines: additional,
    laborCost: flow.quote.labor_cost,
    total: quoteTotal(flow.quote.lines, flow.quote.labor_cost),
    warrantyMonths: flow.quote.warranty_months,
    noCharge: flow.no_charge,
  };
}

const STAGE_STATUS: Record<FieldStage, TicketStatus> = {
  ASSIGNED: 'dispatching',
  DECLINED: 'dispatching',
  ACCEPTED: 'on_the_way',
  ON_SITE: 'inspecting',
  QUOTE_DRAFT: 'inspecting',
  AWAITING_RESIDENT_AGREEMENT: 'waiting_you',
  IN_PROGRESS: 'in_progress',
  PAUSED: 'paused',
  AWAITING_RESIDENT_SIGNATURE: 'waiting_you',
  REPORT_READY: 'finishing',
  AWAITING_COMPLETION: 'waiting_you',
  REWORK_REQUIRED: 'rework',
  DISPUTED: 'escalated',
  COMPLETED_BY_RESIDENT: 'completed',
  COMPLETED_AUTO: 'completed',
  DONE: 'completed',
  CANCELLED_BY_RESIDENT: 'cancelled',
};

export function projectTicket(caseId: string, snapshot: OperationsSnapshot): ResidentTicketView | null {
  const links = linkCase(caseId, snapshot);
  if (!links) return null;
  const { kase, candidate, incident, workOrders } = links;
  const events = deriveTicketEvents(caseId, snapshot);
  const current = workOrders.at(-1) ?? null;
  const flow = current ? getFieldFlow(current, incident?.category) : null;
  const text = candidate?.location_json.description ?? kase.summary;
  const [description, locationLine] = text.split('\nVị trí: ');

  let status: TicketStatus = 'received';
  let detail = 'Ban quản lý đang xem phản ánh của bạn.';
  let pendingAction: PendingAction | null = null;

  if (candidate?.status === 'DISCARDED' || kase.status === 'CANCELLED') {
    status = 'cancelled';
    detail = 'Ban quản lý đã đóng phản ánh.';
  } else if (incident && current && flow) {
    status = STAGE_STATUS[flow.stage];
    const name = current.executor_name ?? 'Nhân viên';
    switch (flow.stage) {
      case 'ASSIGNED':
        detail = `Đã giao cho ${name}, chờ nhân viên nhận việc.`;
        break;
      case 'DECLINED':
        detail = 'Đang tìm nhân viên khác phù hợp.';
        break;
      case 'ACCEPTED':
        detail = `${name} đang tới chỗ bạn.`;
        break;
      case 'ON_SITE':
      case 'QUOTE_DRAFT':
        detail = `${name} đang kiểm tra hiện trạng.`;
        break;
      case 'AWAITING_RESIDENT_AGREEMENT':
        detail = 'Xem danh mục sửa chữa và bấm đồng ý.';
        pendingAction = { type: 'AGREE_QUOTE', woId: current.id, version: current.version, channel: flow.resident_channel ?? null, quote: quoteView(flow) };
        break;
      case 'IN_PROGRESS':
        detail = `${name} đang xử lý.`;
        break;
      case 'PAUSED':
        detail = flow.pause_reason === 'RESIDENT_ABSENT' ? 'Nhân viên chưa gặp được bạn, cần hẹn lại.' : 'Công việc đang tạm dừng.';
        break;
      case 'AWAITING_RESIDENT_SIGNATURE':
        detail = 'Xem lại danh mục cuối và ký xác nhận.';
        pendingAction = { type: 'SIGN', woId: current.id, version: current.version, channel: flow.resident_channel ?? null, quote: quoteView(flow) };
        break;
      case 'REPORT_READY':
        detail = 'Nhân viên đang gửi báo cáo kết quả.';
        break;
      case 'AWAITING_COMPLETION':
        detail = 'Kiểm tra kết quả và xác nhận hoàn thành.';
        pendingAction = { type: 'CONFIRM_COMPLETION', woId: current.id, version: current.version, autoCompleteAt: flow.auto_complete_at };
        break;
      case 'REWORK_REQUIRED':
        detail = 'Đang tạo lượt xử lý lại.';
        break;
      case 'DISPUTED':
        detail = 'Ban quản lý sẽ liên hệ bạn về phần phát sinh.';
        break;
      case 'CANCELLED_BY_RESIDENT':
        detail = 'Bạn đã chọn không sửa.';
        break;
      default:
        detail = flow.completion_type === 'AUTO_72H' ? 'Tự động hoàn tất sau 72 giờ.' : 'Yêu cầu đã hoàn tất.';
    }
    if (incident.status === 'CLOSED' && status !== 'cancelled') {
      status = 'completed';
      pendingAction = null;
      detail = 'Yêu cầu đã hoàn tất.';
    }
  } else if (incident) {
    const handoff = incident.contractor_handoff;
    if (incident.status === 'CLOSED') {
      status = 'completed';
      detail = 'Yêu cầu đã hoàn tất.';
    } else if (handoff?.status === 'CONTACTED') {
      status = 'in_progress';
      detail = `Đã hẹn ${handoff.contractor_name ?? 'đơn vị xử lý'}${handoff.eta ? `, ngày ${handoff.eta}` : ''}.`;
    } else {
      status = 'dispatching';
      detail = handoff ? 'Ban quản lý đang liên hệ đơn vị chuyên môn.' : 'Ban quản lý đang điều phối người xử lý.';
    }
  }

  const resolutionPhotos = current
    ? snapshot.evidence.flatMap((e) => (e.work_order_id === current.id && e.capture_phase === 'AFTER' && e.file_url ? [e.file_url] : []))
    : [];
  const resolutionNote = flow?.report_final_note || incident?.bql_resolution_note || incident?.contractor_handoff?.note || '';
  const meta = STATUS_META[status];
  const lastEventAt = events.at(-1)?.at ?? kase.opened_at;

  return {
    caseId,
    code: ticketCode(caseId),
    title: kase.summary,
    description: description ?? kase.summary,
    location: locationLine ?? '',
    photos: candidate?.resident_photo_urls ?? [],
    status,
    statusLabel: meta.label,
    tone: meta.tone,
    detail,
    teamLabel: candidate ? teamLabelOf(candidate.category) : null,
    assignee: current?.executor_name ? { name: current.executor_name, phone: current.executor_phone ?? null } : null,
    pendingAction,
    resolution: resolutionNote || resolutionPhotos.length ? { note: resolutionNote, photos: resolutionPhotos } : null,
    events,
    isOpen: status !== 'completed' && status !== 'cancelled',
    createdAt: kase.opened_at,
    updatedAt: lastEventAt,
  };
}
