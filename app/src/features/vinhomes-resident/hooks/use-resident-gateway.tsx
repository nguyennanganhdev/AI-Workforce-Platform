/**
 * Resident gateway: the only way resident UI reads or changes ticket data.
 *
 * Demo adapter: tickets come from the operations store (the "backend" shared across tabs) and
 * conversations from the resident conversation store. Swapping this provider for one backed by the
 * resident API (GET /requests, POST /requests/{id}/confirm, …) leaves the components unchanged.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react';
import { useOperationsData } from '@/features/vinhomes-operations/hooks/use-operations-data';
import { reply, type AgentReply } from '../lib/reception-agent';
import { projectTicket } from '../lib/ticket-projection';
import { ticketCode, type OperationsSnapshot } from '../lib/snapshot';
import { appendMessages, updateConversations, useConversationState } from '../store/conversation-store';
import type { Conversation, ConversationMessage, PendingAction, Photo, ResidentProfile, ResidentTicketView } from '../types';

export const NEW_CONVERSATION_TITLE = 'Cuộc trò chuyện mới';

export interface ConversationSummary extends Conversation {
  ticket: ResidentTicketView | null;
  unread: number;
  lastMessage: ConversationMessage | null;
}

type ActionOf<T extends PendingAction['type']> = Extract<PendingAction, { type: T }>;

export interface ResidentGateway {
  profile: ResidentProfile;
  conversations: ConversationSummary[];
  tickets: ResidentTicketView[];
  totalUnread: number;
  getConversation: (id: string) => ConversationSummary | null;
  getMessages: (conversationId: string) => ConversationMessage[];
  getTicket: (caseId: string) => ResidentTicketView | null;
  conversationForCase: (caseId: string) => string | null;
  /** Creates a conversation when `conversationId` is null; returns the conversation id. */
  sendMessage: (conversationId: string | null, text: string, photos?: Photo[]) => string;
  newConversation: () => string;
  submitDraft: (conversationId: string) => void;
  cancelDraft: (conversationId: string) => void;
  markRead: (conversationId: string) => void;
  agreeQuote: (action: ActionOf<'AGREE_QUOTE'>) => void;
  requestQuoteChanges: (action: ActionOf<'AGREE_QUOTE'>) => void;
  cancelJob: (action: ActionOf<'AGREE_QUOTE'>) => void;
  sign: (action: ActionOf<'SIGN'>, signatureDataUrl: string) => void;
  dispute: (action: ActionOf<'SIGN'>, note: string) => void;
  confirmCompletion: (action: ActionOf<'CONFIRM_COMPLETION'>) => void;
  reportIssue: (action: ActionOf<'CONFIRM_COMPLETION'>, note: string) => void;
}

const GatewayContext = createContext<ResidentGateway | null>(null);

const newId = () => crypto.randomUUID();
const nowIso = () => new Date().toISOString();

function toMessages(conversationId: string, replies: AgentReply[], at: string): ConversationMessage[] {
  return replies.map((r) => ({ ...r, id: newId(), conversationId, role: 'agent' as const, createdAt: at }));
}

export function ResidentGatewayProvider({ profile, children }: { profile: ResidentProfile; children: ReactNode }) {
  const ops = useOperationsData();
  const state = useConversationState(profile.userId);

  const snapshot: OperationsSnapshot = useMemo(
    () => ({
      cases: ops.cases,
      issueCandidates: ops.issueCandidates,
      incidents: ops.incidents,
      workOrders: ops.workOrders,
      evidence: ops.evidence,
    }),
    [ops.cases, ops.issueCandidates, ops.incidents, ops.workOrders, ops.evidence],
  );

  const ticketMap = useMemo(() => {
    const map = new Map<string, ResidentTicketView>();
    for (const c of snapshot.cases) {
      if (c.resident_user_id !== profile.userId) continue;
      const view = projectTicket(c.id, snapshot);
      if (view) map.set(c.id, view);
    }
    return map;
  }, [snapshot, profile.userId]);

  const tickets = useMemo(
    () => [...ticketMap.values()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
    [ticketMap],
  );

  const messagesByConversation = useMemo(() => {
    const map = new Map<string, ConversationMessage[]>();
    for (const m of state.messages) {
      const list = map.get(m.conversationId);
      if (list) list.push(m);
      else map.set(m.conversationId, [m]);
    }
    return map;
  }, [state.messages]);

  const conversations = useMemo(
    () =>
      state.conversations
        .map((c): ConversationSummary => {
          const messages = messagesByConversation.get(c.id) ?? [];
          return {
            ...c,
            ticket: c.caseId ? ticketMap.get(c.caseId) ?? null : null,
            unread: messages.filter((m) => m.role === 'agent' && m.createdAt > c.lastReadAt).length,
            lastMessage: messages.at(-1) ?? null,
          };
        })
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
    [state.conversations, messagesByConversation, ticketMap],
  );

  // Reception agent consumer: every new public event of a ticket becomes one message in its conversation.
  useEffect(() => {
    const known = new Set(state.messages.map((m) => m.id));
    const at = nowIso();
    const fresh: ConversationMessage[] = [];
    for (const c of state.conversations) {
      const ticket = c.caseId ? ticketMap.get(c.caseId) : undefined;
      if (!ticket) continue;
      for (const e of ticket.events) {
        const id = `evt-${e.id}`;
        if (!e.notify || known.has(id)) continue;
        fresh.push({
          id,
          conversationId: c.id,
          role: 'agent',
          text: e.note ? `${e.message}\nGhi chú: ${e.note}` : e.message,
          ticketCaseId: ticket.pendingAction && e === ticket.events.at(-1) ? ticket.caseId : undefined,
          createdAt: at,
        });
      }
    }
    if (fresh.length === 0) return;
    try {
      updateConversations(profile.userId, (s) => appendMessages(s, fresh));
    } catch (e) {
      console.warn('Không lưu được thông báo của trợ lý', e);
    }
  }, [ticketMap, state.conversations, state.messages, profile.userId]);

  const getConversation = useCallback((id: string) => conversations.find((c) => c.id === id) ?? null, [conversations]);
  const getMessages = useCallback((id: string) => messagesByConversation.get(id) ?? [], [messagesByConversation]);
  const getTicket = useCallback((caseId: string) => ticketMap.get(caseId) ?? null, [ticketMap]);
  const conversationForCase = useCallback(
    (caseId: string) => state.conversations.find((c) => c.caseId === caseId)?.id ?? null,
    [state.conversations],
  );

  const newConversation = useCallback(() => {
    const id = newId();
    const at = nowIso();
    updateConversations(profile.userId, (s) => ({
      ...s,
      conversations: [
        ...s.conversations,
        { id, title: NEW_CONVERSATION_TITLE, caseId: null, draft: null, createdAt: at, updatedAt: at, lastReadAt: at },
      ],
    }));
    return id;
  }, [profile.userId]);

  const sendMessage = useCallback(
    (conversationId: string | null, text: string, photos: Photo[] = []) => {
      if (!text.trim() && photos.length === 0) throw new Error('Bạn nhập nội dung hoặc chọn ảnh nhé.');
      const id = conversationId ?? newConversation();
      const current = state.conversations.find((c) => c.id === id) ?? { draft: null, caseId: null };
      const ticket = current.caseId ? ticketMap.get(current.caseId) ?? null : null;
      const turn = reply(current, text, photos, { profile, ticket, openTickets: tickets.filter((t) => t.isOpen) });
      const at = nowIso();
      const residentMessage: ConversationMessage = {
        id: newId(),
        conversationId: id,
        role: 'resident',
        text: text.trim(),
        photos: photos.length ? photos : undefined,
        createdAt: at,
      };
      updateConversations(profile.userId, (s) => {
        const withMessages = appendMessages(s, [residentMessage, ...toMessages(id, turn.replies, at)]);
        return {
          ...withMessages,
          conversations: withMessages.conversations.map((c) =>
            c.id === id
              ? {
                  ...c,
                  draft: c.caseId ? c.draft : turn.draft,
                  title: c.title === NEW_CONVERSATION_TITLE && text.trim() ? text.trim().slice(0, 60) : c.title,
                  updatedAt: at,
                  lastReadAt: at,
                }
              : c,
          ),
        };
      });
      return id;
    },
    [newConversation, state.conversations, ticketMap, tickets, profile],
  );

  const submitDraft = useCallback(
    (conversationId: string) => {
      const conversation = state.conversations.find((c) => c.id === conversationId);
      const draft = conversation?.draft;
      if (!conversation || conversation.caseId) throw new Error('Cuộc trò chuyện này đã gửi yêu cầu.');
      if (draft?.step !== 'review') throw new Error('Vui lòng bổ sung mô tả và vị trí trước khi gửi.');
      const { caseId } = ops.createResidentCase({
        resident: {
          userId: profile.userId,
          name: profile.name,
          phone: profile.phone,
          towerCode: profile.towerCode,
          floor: profile.floor,
          apartmentCode: profile.apartmentCode,
        },
        description: draft.description,
        location: draft.location,
        photoUrls: draft.photos.map((p) => p.url),
      });
      const at = nowIso();
      const confirmation: ConversationMessage = {
        id: newId(),
        conversationId,
        role: 'agent',
        text: `Mình đã gửi yêu cầu ${ticketCode(caseId)} tới Ban quản lý tòa ${profile.towerCode}. Bạn theo dõi trạng thái ở thẻ bên dưới, có cập nhật mới mình sẽ báo ngay tại đây.`,
        ticketCaseId: caseId,
        createdAt: at,
      };
      updateConversations(profile.userId, (s) => {
        const withMessage = appendMessages(s, [confirmation]);
        return {
          ...withMessage,
          conversations: withMessage.conversations.map((c) =>
            c.id === conversationId
              ? { ...c, caseId, draft: null, title: draft.description.split('\n')[0].slice(0, 60), updatedAt: at, lastReadAt: at }
              : c,
          ),
        };
      });
    },
    [state.conversations, ops, profile],
  );

  const cancelDraft = useCallback(
    (conversationId: string) => {
      const at = nowIso();
      updateConversations(profile.userId, (s) => {
        const withMessage = appendMessages(s, [
          { id: newId(), conversationId, role: 'agent', text: 'Mình đã hủy bản nháp. Khi cần hỗ trợ, bạn cứ nhắn nhé.', createdAt: at },
        ]);
        return {
          ...withMessage,
          conversations: withMessage.conversations.map((c) => (c.id === conversationId ? { ...c, draft: null, lastReadAt: at } : c)),
        };
      });
    },
    [profile.userId],
  );

  const markRead = useCallback(
    (conversationId: string) => {
      const c = conversations.find((x) => x.id === conversationId);
      if (!c || c.unread === 0) return;
      const at = nowIso();
      updateConversations(profile.userId, (s) => ({
        ...s,
        conversations: s.conversations.map((x) => (x.id === conversationId ? { ...x, lastReadAt: at } : x)),
      }));
    },
    [conversations, profile.userId],
  );

  const fromApp = (action: PendingAction) => ({ fromResidentApp: true, expectedVersion: action.version });

  const value: ResidentGateway = {
    profile,
    conversations,
    tickets,
    totalUnread: conversations.reduce((n, c) => n + c.unread, 0),
    getConversation,
    getMessages,
    getTicket,
    conversationForCase,
    sendMessage,
    newConversation,
    submitDraft,
    cancelDraft,
    markRead,
    agreeQuote: (a) => ops.residentAgree(a.woId, fromApp(a)),
    requestQuoteChanges: (a) => ops.residentRequestChanges(a.woId, fromApp(a)),
    cancelJob: (a) => ops.residentCancel(a.woId, fromApp(a)),
    sign: (a, url) => ops.residentSign(a.woId, url, fromApp(a)),
    dispute: (a, note) => ops.residentDispute(a.woId, note, fromApp(a)),
    confirmCompletion: (a) => ops.residentConfirmCompletion(a.woId, fromApp(a)),
    reportIssue: (a, note) => {
      if (note.trim().length < 8) throw new Error('Bạn mô tả điều chưa được xử lý (ít nhất 8 ký tự) để nhân viên kiểm tra lại nhé.');
      ops.residentReportIssue(a.woId, note, fromApp(a));
    },
  };

  return <GatewayContext.Provider value={value}>{children}</GatewayContext.Provider>;
}

export function useResidentGateway(): ResidentGateway {
  const gateway = useContext(GatewayContext);
  if (!gateway) throw new Error('useResidentGateway must be used within ResidentGatewayProvider');
  return gateway;
}
