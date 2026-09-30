/**
 * Resident app view models. These are the shapes a resident API would return; the demo builds them
 * from the operations store (see lib/ticket-projection.ts) so the UI does not depend on staff types.
 */
import type { QuoteLine, ResidentChannel } from '@/features/vinhomes-operations/types/field-flow';

export interface ResidentProfile {
  userId: string;
  name: string;
  phone: string;
  projectName: string;
  towerCode: string;
  floor: number;
  apartmentCode: string;
  /** VD "S2.02 · 1208" */
  apartmentLabel: string;
}

export interface Photo {
  id: string;
  name: string;
  /** data URL (bản trải nghiệm); API thật trả URL ký ngắn hạn. */
  url: string;
}

export interface ResidentDraft {
  step: 'description' | 'location' | 'review';
  description: string;
  location: string;
  photos: Photo[];
}

/** Một cửa sổ chat. Gắn tối đa một yêu cầu (ticket) sau khi cư dân gửi phản ánh. */
export interface Conversation {
  id: string;
  title: string;
  caseId: string | null;
  draft: ResidentDraft | null;
  createdAt: string;
  updatedAt: string;
  lastReadAt: string;
}

export interface ConversationMessage {
  id: string;
  conversationId: string;
  role: 'resident' | 'agent';
  text: string;
  photos?: Photo[];
  /** Hiển thị thẻ yêu cầu ngay dưới tin nhắn. */
  ticketCaseId?: string;
  /** Gợi ý mở cuộc trò chuyện mới (cửa sổ này đã gắn với một yêu cầu khác). */
  suggestNewConversation?: boolean;
  createdAt: string;
}

export type TicketStatus =
  | 'received'
  | 'dispatching'
  | 'on_the_way'
  | 'inspecting'
  | 'in_progress'
  | 'paused'
  | 'waiting_you'
  | 'finishing'
  | 'rework'
  | 'escalated'
  | 'completed'
  | 'cancelled';

export type TicketTone = 'neutral' | 'info' | 'attention' | 'success' | 'muted' | 'danger';

export interface QuoteView {
  lines: QuoteLine[];
  agreedLines: QuoteLine[];
  additionalLines: QuoteLine[];
  laborCost: number;
  total: number;
  warrantyMonths: number;
  noCharge: boolean;
}

export type PendingAction =
  | { type: 'AGREE_QUOTE'; woId: string; version: number; channel: ResidentChannel | null; quote: QuoteView }
  | { type: 'SIGN'; woId: string; version: number; channel: ResidentChannel | null; quote: QuoteView }
  | { type: 'CONFIRM_COMPLETION'; woId: string; version: number; autoCompleteAt: string | null };

export interface TicketPublicEvent {
  /** Ổn định giữa các lần suy ra, dùng làm khóa idempotent cho thông báo. */
  id: string;
  caseId: string;
  type: string;
  /** Dòng ngắn trên timeline. */
  label: string;
  /** Câu trợ lý gửi vào cuộc trò chuyện. */
  message: string;
  note?: string;
  at: string;
  /** false: chỉ hiện trên timeline, không nhắn vào chat. */
  notify: boolean;
}

export interface ResidentTicketView {
  caseId: string;
  code: string;
  title: string;
  description: string;
  location: string;
  photos: string[];
  status: TicketStatus;
  statusLabel: string;
  tone: TicketTone;
  /** Dòng phụ: bước tiếp theo hoặc người phụ trách. */
  detail: string;
  teamLabel: string | null;
  assignee: { name: string; phone: string | null } | null;
  pendingAction: PendingAction | null;
  /** Kết quả nhân viên gửi (ghi chú + ảnh sau khi xử lý). */
  resolution: { note: string; photos: string[] } | null;
  events: TicketPublicEvent[];
  isOpen: boolean;
  createdAt: string;
  updatedAt: string;
}
