import { chatTurn } from "./chat-turn";
import { useCallback, useEffect, useRef, useState } from "react";
import { uploadImage } from "../../../../packages/shared/direct-image-upload";
import {
  api,
  ApiError,
  allPages,
  requestView,
  withoutRequestCode,
  approvalOf,
  quoteOf,
  bookingOf,
  type Profile,
  type Chat,
  type Message,
  type Ticket,
  type TicketDetail,
  type Approval,
} from "./resident-api";
import {
  statusLabels,
  type Draft,
  type Photo,
  type ResidentState,
  type ResidentNotification,
  type TurnState,
  type ChatMessage,
} from "./types";

const empty: ResidentState = {
  version: 1,
  requests: [],
  messages: [],
  conversations: [],
  draft: null,
};
export type SupervisorInteraction = {ticket_id: string; pending_kind: 'information' | 'plan_approval'; ticket_version: number;
  question: string; plan_id?: string; title?: string; proposal?: {steps: string[]; conditions: string; expected_duration: string;
    cost?: {amount: number; currency: string} | null}};

export function useConnectedResident() {
  const [state, setState] = useState<ResidentState>(empty);
  const [profile, setProfile] = useState<Profile>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notifications, setNotifications] = useState<ResidentNotification[]>([]);
  const [notificationUnread, setNotificationUnread] = useState(0);
  const [notificationOffset, setNotificationOffset] = useState<number | null>(null);
  const [archivedChats, setArchivedChats] = useState<Chat[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [interactions, setInteractions] = useState<SupervisorInteraction[]>([]);
  const [contact, setContact] = useState({ unit: "", category: "", phone: "" });
  const current = useRef(state);
  current.current = state;
  const active = useRef("");
  const drafts = useRef(new Map<string, Draft>());
  const lock = useRef(false);
  const awaiting = useRef(false);
  const generation = useRef(0);
  const keys = useRef(new Map<string, string>());
  const answered = useRef(new Map<string, boolean>());
  /** Booking cards confirmed here, shown as booked until the next read says so. */
  const booked = useRef(new Set<string>());
  const messageCache = useRef(new Map<string, Message[]>());
  const nextNotificationPage = useRef<number | null>(null);
  const notificationsInitialized = useRef(false);
  const overview = useRef<{ at: number; data: [Profile, Chat[], Ticket[], {items: Approval[]},
    {items: SupervisorInteraction[]}, {items: ResidentNotification[]; unreadCount: number; nextOffset: number | null}, Chat[]] } | null>(null);
  const keyFor = (value: string) => {
    if (!keys.current.has(value)) keys.current.set(value, crypto.randomUUID());
    return keys.current.get(value)!;
  };
  /** Store a picked photo with its chat. The same photo stored again is the same file, not a second one. */
  const store = async (chat: string, photo: Photo) => {
    const blob = await (await fetch(photo.url)).blob();
    const stored = await uploadImage(api, `/resident/chats/${chat}/direct-uploads`,
      `/resident/chats/${chat}/photos?filename=${encodeURIComponent(photo.name)}&mimeType=${encodeURIComponent(blob.type)}`,
      blob, photo.name, keyFor(`${chat}:photo:${photo.id}`));
    return stored.fileId;
  };
  const refresh = useCallback(async (quick = false) => {
    const revision = ++generation.current;
    const summary = quick && overview.current && Date.now()-overview.current.at<5000 ? overview.current.data : await Promise.all([
      api<Profile>("/resident/me"),
      allPages<Chat>("/resident/chats"),
      allPages<Ticket>("/resident/tickets"),
      api<{ items: Approval[] }>("/resident/approvals?limit=100"),
      api<{items: SupervisorInteraction[]}>("/resident/supervisor-interactions"),
      api<{items: ResidentNotification[]; unreadCount: number; nextOffset: number | null}>("/my/notifications?limit=100"),
      allPages<Chat>("/resident/chats?archived=true"),
    ]);
    overview.current={at:quick && overview.current && summary===overview.current.data ? overview.current.at : Date.now(),data:summary};
    const [p, chats, tickets, a, pending, notices, archived] = summary;
    if (
      p.dataMode !== "database" &&
      import.meta.env.VITE_ALLOW_DEMO_BACKEND !== "true"
    ) {
      throw new Error(
        "Backend đang dùng tài khoản demo. Cần khởi động backend với xác thực thật trước khi sử dụng.",
      );
    }
    const selected = active.current;
    setInteractions(
      pending.items.map((i) => ({
        ...i,
        question: withoutRequestCode(i.question),
      })),
    );
    const path = location.hash.slice(2).split("/");
    const detailId = path[0] === "requests" ? path[1] : undefined;
    const detail = detailId
      ? await api<TicketDetail>(`/resident/tickets/${detailId}`)
      : undefined;
    const cached=messageCache.current.get(selected) ?? [];
    // Approval/quote/booking cards have mutable server state even without a new sequence.
    const messages: Message[] = cached.some(m => m.body.platform) ? [] : [...cached];
    let turnState: TurnState | undefined;
    if (selected) {
      let seq = messages.at(-1)?.seq ?? 0;
      while (true) {
        const page = await api<{ items: Message[] }>(
          `/resident/chats/${selected}/messages?afterSeq=${seq}&limit=100`,
        );
        messages.push(...page.items);
        if (page.items.length < 100) break;
        seq = page.items.at(-1)!.seq;
      }
      messageCache.current.set(selected,messages);
      turnState = await api<TurnState>(`/resident/chats/${selected}/turn-state`);
      if (messages.length && path[0] === "chat" && selected===active.current && !document.hidden && document.hasFocus())
        await api(`/resident/chats/${selected}/read`, {
          method: "POST",
          body: JSON.stringify({ sequence: messages.at(-1)!.seq }),
        });
    }
    if (selected !== active.current || revision !== generation.current) return;
    setProfile(p);
    setNotifications((previous) => [...notices.items,...previous.filter(n => !notices.items.some(i => i.id===n.id))]);
    setNotificationUnread(notices.unreadCount);
    if (!notificationsInitialized.current) {nextNotificationPage.current=notices.nextOffset;notificationsInitialized.current=true;}
    setNotificationOffset(nextNotificationPage.current);
    setArchivedChats(archived);
    setApprovals(a.items);
    const requests = tickets.map((t) =>
      requestView(
        detail?.ticket.id === t.id
          ? detail
          : { ticket: t, events: [], photos: [] },
        a.items.some(
          (x) =>
            x.ticket_id === t.id &&
            x.kind === "customer_completion" &&
            x.status === "pending",
        ),
      ),
    );
    // An approval that was answered arrives again as a later message: one card, the latest.
    const latest = new Map(
      messages.flatMap((m) => (m.body.platform ? [[m.body.platform.approval_id, m.id]] : [])),
    );
    const chatMessages: ChatMessage[] = messages
      .filter(
        (m) =>
          (m.body.text || m.body.fileIds?.length || m.body.platform) &&
          (!m.body.platform || latest.get(m.body.platform.approval_id) === m.id),
      )
      .map((m) => ({
        id: m.id,
        role:
          m.sender_kind === "user"
            ? ("resident" as const)
            : ("assistant" as const),
        text: withoutRequestCode(m.body.text || ""),
        createdAt: m.created_at,
        delivery: m.sender_kind === "user" ? messages.some(r => r.reply_to_id===m.id) ? "answered" as const : "sent" as const : undefined,
        reception: m.body.reception,
        ...(m.body.fileIds?.length
          ? { photos: m.body.fileIds.map((id) => ({ id, name: "Ảnh đính kèm", url: `/api/business/resident/photos/${id}` })) }
          : {}),
        ...(m.body.platform
          ? { approval: approvalOf(m.body, answered.current), quote: quoteOf(m.body), booking: bookingOf(m.body, booked.current) }
          : {}),
      }));
    // Reception answers within the backend's three-minute dispatch limit, or the backend
    // stores a fallback reply. Older unanswered messages predate the agent.
    awaiting.current = !!turnState && ["queued","processing","waiting_platform"].includes(turnState.status);
    const linked = chats.find((c) => c.id === selected)?.ticket_id;
    if (linked)
      chatMessages.push({
        id: `ticket-${linked}`,
        role: "assistant",
        text: "Theo dõi tiến độ phản ánh của bạn.",
        ...{ requestId: linked },
      });
    setState({
      version: 1,
      requests,
      messages: chatMessages,
      draft: drafts.current.get(selected) ?? null,
      activeConversationId: selected,
      awaitingReply: awaiting.current,
      turnState,
      conversations: chats.map((c) => ({
        id: c.id,
        title: c.title || c.name,
        requestId: c.ticket_id,
        confirmClose: c.confirm_close,
        requestStatus: c.ticket_id
          ? statusLabels[
              requests.find((r) => r.id === c.ticket_id)?.status ?? "received"
            ]
          : undefined,
        preview: c.last_message
          ? withoutRequestCode(c.last_message)
          : undefined,
        unread: c.id === selected && path[0] === "chat" ? 0 : c.unread_count,
        updatedAt: c.last_message_at || c.created_at,
        messages: c.id === selected ? chatMessages : [],
        draft: drafts.current.get(c.id) ?? null,
      })),
    });
  }, []);
  const fail = (e: unknown) => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      setProfile(undefined);
      setState(empty);
      setApprovals([]);
      active.current = "";
      drafts.current.clear();
      messageCache.current.clear();
      setNotifications([]); setNotificationUnread(0); setArchivedChats([]);
    }
    // No session at all: the sign-in page is the only useful place to be.
    if (e instanceof ApiError && e.status === 401) {
      location.assign("/login");
      return;
    }
    setError(e instanceof Error ? e.message : "Không kết nối được máy chủ.");
  };
  const run = async (action: () => Promise<void>, requireProfile = true) => {
    if (lock.current) return false;
    if (requireProfile && !profile) {
      setError("Bạn cần đăng nhập và kết nối backend thật trước khi thao tác.");
      return false;
    }
    generation.current++;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await action();
      try {
        await refresh();
      } catch (e) {
        fail(e);
        // A committed command must not be presented as failed because the subsequent read failed.
        return requireProfile;
      }
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  useEffect(() => {
    let disposed = false;
    let loading=false;
    const load = (quick = false) => {
      if (!lock.current && !loading) {
        loading=true;
        void refresh(quick).catch(e => {if (!disposed) fail(e);}).finally(() => {loading=false;});
      }
    };
    const route = () => {
      const parts = location.hash.slice(2).split("/");
      if (parts[0] === "chat" && parts[1]) active.current = parts[1];
      load();
    };
    route();
    window.addEventListener("hashchange", route);
    window.addEventListener("focus", route);
    let ticks = 0;
    const timer = setInterval(() => {
      // Poll quickly only while the resident is waiting for the assistant.
      if (!document.hidden && (awaiting.current || ++ticks % 4 === 0)) load(awaiting.current);
    }, 1250);
    return () => {
      disposed = true;
      clearInterval(timer);
      window.removeEventListener("hashchange", route);
      window.removeEventListener("focus", route);
    };
  }, [refresh]);
  const create = async () => {
    const c = await api<Chat>("/resident/chats", {
      method: "POST",
      body: JSON.stringify({ title: "Hội thoại mới" }),
    });
    active.current = c.id;
    location.hash = `/chat/${c.id}`;
    return c.id;
  };
  const changeDraft = (draft: Draft | null) => {
    if (draft) drafts.current.set(active.current, draft);
    else drafts.current.delete(active.current);
    setState((s) => ({ ...s, draft }));
  };
  /** Records the resident's decision on one pending approval, against the request as it is now. */
  const answer = (pending: (a: Approval) => boolean, approved: boolean, note: string) =>
    run(async () => {
      const approval = approvals.find((a) => a.status === "pending" && pending(a));
      if (!approval)
        throw new Error("Không còn yêu cầu xác nhận đang chờ. Hãy tải lại.");
      const detail = await api<TicketDetail>(`/resident/tickets/${approval.ticket_id}`);
      const body = JSON.stringify({ approved, note, version: detail.ticket.version });
      await api(`/resident/approvals/${approval.id}/decision`, {
        method: "POST",
        body,
        headers: { "Idempotency-Key": keyFor(`${approval.id}:${body}`) },
      });
    });
  return {
    state,
    profile,
    error,
    busy,
    contact,
    notifications,
    notificationUnread,
    notificationOffset,
    archivedChats,
    markNotificationsRead: (ids: string[]) => run(async () => {
      if (!ids.length) return;
      for (let start=0;start<ids.length;start+=100) {
        const batch=ids.slice(start,start+100);
        const result=await api<{items:{id:string;read_at:string}[]}>("/my/notifications/read", {method:"POST",body:JSON.stringify({ids:batch})});
        setNotifications(previous => previous.map(n => {const updated=result.items.find(i => i.id===n.id);return updated ? {...n,read_at:updated.read_at} : n;}));
      }
    }),
    moreNotifications: () => run(async () => {
      if (nextNotificationPage.current===null) return;
      const page=await api<{items: ResidentNotification[]; nextOffset: number | null}>(`/my/notifications?limit=100&offset=${nextNotificationPage.current}`);
      setNotifications(previous => [...previous,...page.items.filter(n => !previous.some(p => p.id===n.id))]);
      nextNotificationPage.current=page.nextOffset;
      setNotificationOffset(page.nextOffset);
    }),
    archiveChat: (id: string) => run(async () => {
      await api(`/resident/chats/${id}`,{method:"DELETE"});
      drafts.current.delete(id);messageCache.current.delete(id);
      if (active.current===id) {active.current="";awaiting.current=false;location.hash="/";}
    }),
    restoreChat: (id: string) => run(async () => {
      await api(`/resident/chats/${id}/restore`,{method:"POST"});
    }),
    setContact,
    setError,
    refresh: () => run(async () => {}, false),
    interaction: (id: string) => interactions.find(i => i.ticket_id === id),
    /** The question management asks in the open conversation, to answer right there. */
    question: () => {
      const ticket = state.conversations?.find((c) => c.id === state.activeConversationId)?.requestId;
      const pending = interactions.find((i) => i.ticket_id === ticket && i.pending_kind === "information");
      return pending?.question;
    },
    openChatOf: (ticketId: string) => {
      const chat = state.conversations?.find(c => c.requestId===ticketId) ?? archivedChats.find(c => c.ticket_id===ticketId);
      if (!chat) return;
      // A linked request can reopen a conversation removed from the personal list.
      void run(async () => {await api(`/resident/chats/${chat.id}/restore`,{method:"POST"});active.current=chat.id;location.hash=`/chat/${chat.id}`;});
    },
    respondSupervisor: (item: SupervisorInteraction, decision: 'information' | 'approve' | 'reject' | 'request_changes', note: string) =>
      run(async () => {
        const body = {decision, note: note.trim(), ticket_version: item.ticket_version};
        const signature = `${item.ticket_id}:supervisor:${JSON.stringify(body)}`;
        await api(`/resident/tickets/${item.ticket_id}/supervisor-response`, {method:'POST',
          body: JSON.stringify({...body, request_id: keyFor(signature)})});
        keys.current.delete(signature);
      }),
    newChat: () =>
      run(async () => {
        await create();
      }),
    select: (id: string) => {
      void run(async () => {
        await api(`/resident/chats/${id}/restore`,{method:"POST"});
        active.current=id;location.hash=`/chat/${id}`;
      });
    },
    resume: () => {
      if (active.current) location.hash = `/chat/${active.current}`;
      else
        void run(async () => {
          await create();
        });
    },
    send: (text: string, photos: Photo[] = []) =>
      run(async () => {
        if (text === "Xem yêu cầu của tôi") {
          location.hash = "/requests";
          return;
        }
        if (text === "Hỏi về tiện ích") {
          location.hash = "/amenities";
          return;
        }
        if (text === "Thông tin tòa nhà") {
          location.hash = "/building";
          return;
        }
        let id = active.current;
        if (
          !id ||
          (text === "Báo sự cố" &&
            current.current.conversations?.find((c) => c.id === id)?.requestId)
        )
          id = await create();
        location.hash = `/chat/${id}`;
        const turn = chatTurn(text, photos, drafts.current.get(id) ?? null);
        if (turn.kind === "open") return;
        if (turn.kind === "form") {
          changeDraft(turn.draft);
          return;
        }
        const content = turn.text;
        // The photos go with the message: Reception files the request from the conversation, and a
        // photo kept only in this browser would never reach the request it was taken for.
        const fileIds: string[] = [];
        for (const photo of photos) fileIds.push(await store(id, photo));
        const retryKey = `${id}:message:${content}:${fileIds.join(",")}`;
        await api(`/resident/chats/${id}/messages`, {
          method: "POST",
          body: JSON.stringify({
            text: content,
            client_message_id: keyFor(retryKey),
            ...(fileIds.length ? { file_ids: fileIds } : {}),
          }),
        });
        keys.current.delete(retryKey);
      }),
    // Reception leads the conversation. The form is the way around it when it could not answer.
    startForm: () =>
      changeDraft({ step: "description", description: "", location: "", photos: [] }),
    editDraft: () => {
      const d = drafts.current.get(active.current);
      if (d) changeDraft({ ...d, step: "description" });
    },
    cancelDraft: () => changeDraft(null),
    submit: () =>
      run(async () => {
        const d = drafts.current.get(active.current);
        const unit = profile?.units.find((u) => u.id === contact.unit);
        if (!d || !unit || !contact.category || !contact.phone.trim())
          throw new Error(
            "Chọn căn hộ, nhóm dịch vụ và số điện thoại liên hệ trước khi gửi.",
          );
        if (!d.description.trim() || !d.location.trim())
          throw new Error("Vui lòng bổ sung mô tả và vị trí cụ thể.");
        const files = [];
        for (const photo of d.photos) files.push({ id: await store(active.current, photo) });
        const body = JSON.stringify({
          domain_id: unit.domain_id,
          building_id: unit.building_id,
          unit_id: unit.id,
          category_id: contact.category,
          title: d.description.trim().slice(0, 300),
          description: d.description.trim(),
          location: d.location.trim(),
          contact_name: profile!.user.name,
          contact_phone: contact.phone.trim(),
          request_kind: "incident",
          file_ids: files.map((f) => f.id),
        });
        const t = await api<Ticket>(
          `/resident/chats/${active.current}/tickets`,
          {
            method: "POST",
            body,
            headers: { "Idempotency-Key": keyFor(`${active.current}:${body}`) },
          },
        );
        changeDraft(null);
        location.hash = `/requests/${t.id}`;
      }),
    consent: (id: string) =>
      approvals.find(
        (a) =>
          a.ticket_id === id &&
          a.kind === "customer_repair" &&
          a.status === "pending",
      ),
    /** The resident's answer to what the platform's agent asked before acting. */
    decidePlatform: (approvalId: string, approve: boolean) =>
      run(async () => {
        const body = JSON.stringify({ approve });
        await api(`/resident/platform/approvals/${approvalId}/decision`, {
          method: "POST",
          body,
          headers: { "Idempotency-Key": keyFor(`${approvalId}:${body}`) },
        });
        answered.current.set(approvalId, approve);
      }),
    decide: (
      id: string,
      accepted: boolean,
      reason?: string,
      kind = "customer_completion",
    ) =>
      answer(
        (a) => a.ticket_id === id && a.kind === kind,
        accepted,
        reason || "Tôi xác nhận kết quả đã hoàn tất.",
      ),
    /** The resident's tap on a booking card: this, and nothing the assistant does, books the place. */
    confirmBooking: (cardId: string) =>
      run(async () => {
        await api(`/resident/platform/bookings/${cardId}/confirm`, {
          method: "POST",
          headers: { "Idempotency-Key": keyFor(`booking:${cardId}`) },
        });
        booked.current.add(cardId);
      }),
    /** The resident's answer on the quote card of the chat: the same decision as on the request page. */
    decideQuote: (approvalId: string, accepted: boolean, reason?: string) =>
      answer((a) => a.id === approvalId, accepted, reason || "Tôi đồng ý báo giá."),
  };
}
export type ConnectedResident = ReturnType<typeof useConnectedResident>;
