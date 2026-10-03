import { initialState } from "../mocks/seed";
import {
  loadState as loadLegacy,
  saveState,
  reply as legacyReply,
  submitDraft as legacySubmit,
  resolveRequest as legacyResolve,
} from "./resident-service";
import type {
  ResidentState,
  ResidentConversation,
  Photo,
  RequestStatus,
} from "./types";

function empty(): ResidentConversation {
  return {
    id: crypto.randomUUID(),
    title: "Cuộc trò chuyện mới",
    messages: [],
    draft: null,
    unread: 0,
    updatedAt: new Date().toISOString(),
  };
}
export function normalizeConversations(state: ResidentState): ResidentState {
  if (
    state.conversations?.length &&
    state.conversations.some((c) => c.id === state.activeConversationId)
  )
    return state;
  // Preserve the entire historical transcript; give existing tickets their own rooms.
  const history = {
    ...empty(),
    title: state.messages.length
      ? "Lịch sử trao đổi trước đây"
      : "Cuộc trò chuyện mới",
    messages: state.messages,
    draft: state.draft,
  };
  return {
    ...state,
    conversations: [
      history,
      ...state.requests.map((r) => ({
        ...empty(),
        title: r.title,
        requestId: r.id,
        messages: [
          {
            id: crypto.randomUUID(),
            role: "assistant" as const,
            text: "Bạn có thể tiếp tục trao đổi về yêu cầu này tại đây.",
            requestId: r.id,
          },
        ],
      })),
    ],
    activeConversationId: history.id,
  };
}
export function activeRoom(state: ResidentState) {
  const s = normalizeConversations(state);
  return s.conversations!.find((c) => c.id === s.activeConversationId)!;
}
export function reconcileConversations(
  previous: ResidentState,
  next: ResidentState,
): ResidentState {
  const s = normalizeConversations(next);
  // Switching rooms already selects its own projected transcript.
  const active = activeRoom(s);
  const first = s.messages.find((m) => m.role === "resident" && m.text.trim());
  return {
    ...s,
    conversations: s.conversations!.map((c) =>
      c.id === active.id
        ? {
            ...c,
            messages: s.messages,
            draft: s.draft,
            title:
              c.title === "Cuộc trò chuyện mới" && first
                ? first.text.slice(0, 70)
                : c.title,
            updatedAt:
              previous.messages === next.messages
                ? c.updatedAt
                : new Date().toISOString(),
          }
        : c,
    ),
  };
}
export function loadConversations(storage: Pick<Storage, "getItem">) {
  const s = loadLegacy(storage);
  if (s.conversations !== undefined) {
    if (
      !Array.isArray(s.conversations) ||
      !s.conversations.length ||
      s.conversations.some((c) => !c || typeof c.id !== "string") ||
      new Set(s.conversations.map((c) => c.id)).size !== s.conversations.length
    )
      throw new Error(
        "Lịch sử hội thoại không hợp lệ. Hãy đặt lại dữ liệu trải nghiệm.",
      );
    const linked = s.conversations
      .filter((c) => c.requestId)
      .map((c) => c.requestId);
    if (new Set(linked).size !== linked.length)
      throw new Error("Một ticket không thể thuộc nhiều hội thoại.");
    for (const c of s.conversations) {
      if (
        !c ||
        typeof c.id !== "string" ||
        typeof c.title !== "string" ||
        !Number.isInteger(c.unread) ||
        c.unread < 0 ||
        !Number.isFinite(Date.parse(c.updatedAt)) ||
        (c.requestId !== undefined &&
          !s.requests.some((r) => r.id === c.requestId))
      )
        throw new Error("Hội thoại không hợp lệ.");
      // Reuse the existing nested message/photo/draft validator.
      loadLegacy({
        getItem: () =>
          JSON.stringify({ ...s, messages: c.messages, draft: c.draft }),
      });
    }
    if (!s.conversations.some((c) => c.id === s.activeConversationId))
      throw new Error("Không tìm thấy hội thoại đang mở.");
  }
  return normalizeConversations(s);
}
export function newConversation(state: ResidentState) {
  const s = reconcileConversations(state, state);
  const room = empty();
  return {
    ...s,
    conversations: [room, ...s.conversations!],
    activeConversationId: room.id,
    messages: room.messages,
    draft: null,
  };
}
export function selectConversation(state: ResidentState, id: string) {
  const s = reconcileConversations(state, state);
  const c = s.conversations!.find((c) => c.id === id);
  if (!c) throw new Error("Không tìm thấy cuộc trò chuyện.");
  return {
    ...s,
    activeConversationId: id,
    messages: c.messages,
    draft: c.draft,
    conversations: s.conversations!.map((room) =>
      room.id === id ? { ...room, unread: 0 } : room,
    ),
  };
}
export function reply(
  state: ResidentState,
  text: string,
  photos: Photo[] = [],
) {
  const s = normalizeConversations(state);
  const c = activeRoom(s);
  if (!c.requestId) return legacyReply(s, text, photos);
  if (!text.trim() && !photos.length) return s;
  if (text.length > 2000 || photos.length > 3)
    throw new Error("Tin nhắn tối đa 2.000 ký tự và 3 ảnh.");
  return {
    ...s,
    messages: [
      ...s.messages,
      {
        id: crypto.randomUUID(),
        role: "resident" as const,
        text: text.trim(),
        photos,
      },
      {
        id: crypto.randomUUID(),
        role: "assistant" as const,
        text: "Bổ sung đã lưu trong hội thoại mẫu của yêu cầu này. Chọn “Chat mới” nếu bạn cần báo một vấn đề khác.",
        requestId: c.requestId,
      },
    ],
  };
}
export function submitDraft(state: ResidentState) {
  const s = normalizeConversations(state);
  if (activeRoom(s).requestId)
    throw new Error("Mỗi hội thoại chỉ có một yêu cầu. Hãy tạo chat mới.");
  const next = legacySubmit(s);
  const request = next.requests[0];
  return {
    ...next,
    conversations: s.conversations!.map((c) =>
      c.id === s.activeConversationId
        ? { ...c, requestId: request.id, title: request.title }
        : c,
    ),
  };
}
export function resolveRequest(
  state: ResidentState,
  id: string,
  accepted: boolean,
  reason = "",
) {
  const s = normalizeConversations(state);
  const target = s.conversations!.find((c) => c.requestId === id);
  const result = legacyResolve(
    { ...s, messages: target?.messages ?? [] },
    id,
    accepted,
    reason,
  );
  if (!target) return { ...s, requests: result.requests };
  return {
    ...s,
    requests: result.requests,
    messages:
      target.id === s.activeConversationId ? result.messages : s.messages,
    conversations: s.conversations!.map((c) =>
      c.id === target.id
        ? {
            ...c,
            messages: result.messages,
            updatedAt: new Date().toISOString(),
            unread: c.id === s.activeConversationId ? 0 : c.unread + 1,
          }
        : c,
    ),
  };
}
export function receiveTicketEvent(
  state: ResidentState,
  id: string,
  text: string,
  status?: RequestStatus,
) {
  const s = reconcileConversations(state, state);
  const c = s.conversations!.find((c) => c.requestId === id);
  if (!c || !text.trim())
    throw new Error("Không tìm thấy hội thoại cho ticket.");
  if (s.requests.find((r) => r.id === id)?.status === "completed")
    throw new Error("Yêu cầu đã hoàn tất, không thể mô phỏng mở lại.");
  const message = {
    id: crypto.randomUUID(),
    role: "assistant" as const,
    text: `[Sự kiện mẫu] ${text}`,
    requestId: id,
  };
  const now = new Date().toISOString();
  return {
    ...s,
    requests: s.requests.map((r) =>
      r.id === id
        ? {
            ...r,
            status: status ?? r.status,
            events: [...r.events, { at: now, label: text }],
          }
        : r,
    ),
    conversations: s.conversations!.map((room) =>
      room.id === c.id
        ? {
            ...room,
            messages: [...room.messages, message],
            unread: room.unread + 1,
            updatedAt: now,
          }
        : room,
    ),
    messages:
      c.id === s.activeConversationId ? [...s.messages, message] : s.messages,
  };
}
export function resetConversations() {
  return normalizeConversations(initialState());
}
export { saveState };
