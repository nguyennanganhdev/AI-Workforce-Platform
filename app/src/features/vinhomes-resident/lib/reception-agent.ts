/**
 * Reception agent of the demo: rule-based replies and the report draft flow
 * (mô tả → vị trí → kiểm tra trước khi gửi), ported from resident-app/src/services/resident-service.ts.
 * The real agent (agent-reception) replaces this; the UI only depends on AgentTurn.
 */
import { looksLikeIssue, normalizeVi } from '@/features/vinhomes-operations/lib/resident-intake';
import type { ConversationMessage, Photo, ResidentDraft, ResidentProfile, ResidentTicketView } from '../types';

export const MAX_MESSAGE_LENGTH = 2000;
export const MAX_PHOTOS = 3;

export type AgentReply = Pick<ConversationMessage, 'text' | 'ticketCaseId' | 'suggestNewConversation'>;

export interface AgentTurn {
  draft: ResidentDraft | null;
  replies: AgentReply[];
}

export interface AgentContext {
  profile: ResidentProfile;
  /** Yêu cầu gắn với cửa sổ chat này (nếu đã gửi phản ánh). */
  ticket: ResidentTicketView | null;
  openTickets: ResidentTicketView[];
}

const say = (text: string, extra?: Omit<AgentReply, 'text'>): AgentReply => ({ text, ...extra });

const REPORT_INTENT = /\b(bao su co|bao hong|bao phan anh|gui phan anh|phan anh su co)\b/;
const PROGRESS_INTENT = /\b(tien do|trang thai|yeu cau cua toi|den chua|bao gio|khi nao|sao roi|xu ly chua|xong chua)\b/;
const MY_APARTMENT = /\b(can ho cua toi|tai can ho|trong can ho|nha toi|nha minh|can ho minh)\b/;

export function myApartmentLocation(profile: ResidentProfile) {
  return `Căn hộ ${profile.apartmentLabel}`;
}

function faq(key: string): string | null {
  if (/\b(gio yen tinh|noi quy|quy dinh)\b/.test(key)) {
    return 'Theo nội quy tòa nhà, giờ yên tĩnh từ 22:00 đến 06:00. Thi công trong căn hộ cần đăng ký với Ban quản lý và chỉ làm trong giờ hành chính.';
  }
  if (/\b(tien ich|be boi|ho boi|gym|phong tap|cong vien)\b/.test(key)) {
    return 'Bể bơi và phòng tập mở 06:00 đến 21:00 hằng ngày, dùng thẻ cư dân để vào. Đặt sân và lớp học sẽ có trong bản sau.';
  }
  if (/\b(ban quan ly|lien he|hotline|so dien thoai)\b/.test(key)) {
    return 'Bạn có thể nhắn ngay tại đây, mình sẽ chuyển tới Ban quản lý tòa của bạn. Việc khẩn cấp (cháy, ngập, mắc kẹt thang máy) vui lòng gọi hotline trực 24/7 của tòa nhà.';
  }
  if (/\b(phi dich vu|phi quan ly|hoa don|thanh toan)\b/.test(key)) {
    return 'Phí quản lý được thông báo đầu mỗi tháng. Tra cứu và thanh toán hóa đơn chưa có trong bản trải nghiệm này.';
  }
  return null;
}

/** One resident message in, the agent's replies and the next draft out. Throws on invalid input. */
export function reply(
  conversation: { draft: ResidentDraft | null; caseId: string | null },
  text: string,
  photos: Photo[],
  ctx: AgentContext,
): AgentTurn {
  const clean = text.trim();
  if (clean.length > MAX_MESSAGE_LENGTH) throw new Error('Tin nhắn tối đa 2.000 ký tự.');
  if (photos.length + (conversation.draft?.photos.length ?? 0) > MAX_PHOTOS) {
    throw new Error('Mỗi phản ánh đính kèm tối đa 3 ảnh.');
  }
  const key = normalizeVi(clean);

  // Cửa sổ đã gắn một yêu cầu: trò chuyện xoay quanh yêu cầu đó.
  if (conversation.caseId) {
    const t = ctx.ticket;
    if (!t) return { draft: null, replies: [say('Mình chưa tải được thông tin yêu cầu. Bạn thử lại sau ít phút nhé.')] };
    if (PROGRESS_INTENT.test(key)) {
      return { draft: null, replies: [say(`${t.code} · ${t.statusLabel}. ${t.detail}`, { ticketCaseId: t.caseId })] };
    }
    if (REPORT_INTENT.test(key) || (looksLikeIssue(clean) && !t.isOpen)) {
      return {
        draft: null,
        replies: [
          say(`Cuộc trò chuyện này đang theo dõi yêu cầu ${t.code}. Để báo sự cố khác, bạn mở cuộc trò chuyện mới nhé.`, {
            suggestNewConversation: true,
          }),
        ],
      };
    }
    const answer = faq(key);
    if (answer) return { draft: null, replies: [say(answer)] };
    return {
      draft: null,
      replies: [
        say(
          photos.length
            ? `Mình đã nhận ${photos.length} ảnh bổ sung cho yêu cầu ${t.code} và lưu trong cuộc trò chuyện này.`
            : `Mình đã ghi lại lời nhắn cho yêu cầu ${t.code}. Có cập nhật mới từ nhân viên, mình sẽ báo bạn ngay tại đây.`,
        ),
      ],
    };
  }

  const draft = conversation.draft ? structuredClone(conversation.draft) : null;
  if (draft) {
    draft.photos.push(...photos);
    if (draft.step === 'description') {
      if (clean.length < 8) {
        return { draft, replies: [say('Bạn mô tả thêm sự cố giúp mình nhé. Ví dụ: “Vòi nước dưới bồn rửa đang bị rò”.')] };
      }
      draft.description = clean;
      draft.step = 'location';
      return { draft, replies: [say('Mình đã ghi nhận nội dung. Sự cố xảy ra ở đâu? Bạn chọn căn hộ của mình hoặc nhập vị trí cụ thể.')] };
    }
    if (draft.step === 'location') {
      if (MY_APARTMENT.test(key)) {
        draft.location = myApartmentLocation(ctx.profile);
      } else if (clean.length < 3) {
        return { draft, replies: [say('Bạn cho mình biết vị trí cụ thể nhé, ví dụ căn hộ, tầng hoặc khu vực chung.')] };
      } else {
        draft.location = clean;
      }
      draft.step = 'review';
      return { draft, replies: [say('Bạn kiểm tra thông tin bên dưới nhé. Yêu cầu chỉ được gửi khi bạn bấm “Gửi yêu cầu”.')] };
    }
    if (clean) draft.description += `\nBổ sung: ${clean}`;
    return { draft, replies: [say('Mình đã bổ sung thông tin. Bạn kiểm tra lại trước khi gửi nhé.')] };
  }

  if (REPORT_INTENT.test(key) || looksLikeIssue(clean) || photos.length) {
    // "Báo sự cố điện", "Phản ánh tiếng ồn": only the kind of issue, ask what happened first.
    const generic = (REPORT_INTENT.test(key) || /^phan anh\b/.test(key)) && clean.length < 22;
    const next: ResidentDraft = {
      step: generic || clean.length < 8 ? 'description' : 'location',
      description: generic || clean.length < 8 ? '' : clean,
      location: '',
      photos: [...photos],
    };
    return {
      draft: next,
      replies: [
        say(
          next.step === 'description'
            ? 'Mình sẵn sàng hỗ trợ. Bạn đang gặp sự cố gì? Mô tả ngắn và gửi ảnh nếu có nhé.'
            : 'Mình sẽ giúp bạn gửi yêu cầu hỗ trợ. Sự cố xảy ra ở đâu? Bạn chọn căn hộ của mình hoặc nhập vị trí cụ thể.',
        ),
      ],
    };
  }

  if (PROGRESS_INTENT.test(key)) {
    const open = ctx.openTickets;
    return {
      draft: null,
      replies: open.length
        ? [
            say(`Bạn có ${open.length} yêu cầu đang xử lý:`),
            ...open.slice(0, 5).map((t) => say(`${t.code} · ${t.statusLabel}`, { ticketCaseId: t.caseId })),
          ]
        : [say('Bạn chưa có yêu cầu nào đang xử lý. Khi cần hỗ trợ, bạn mô tả sự cố để mình gửi Ban quản lý nhé.')],
    };
  }

  const answer = faq(key);
  if (answer) return { draft: null, replies: [say(answer)] };

  return {
    draft: null,
    replies: [
      say(
        'Mình có thể giúp bạn báo sự cố (điện, nước, vệ sinh, an ninh…), xem tiến độ yêu cầu hoặc giải đáp nội quy, tiện ích. Bạn cần hỗ trợ gì?',
      ),
    ],
  };
}
