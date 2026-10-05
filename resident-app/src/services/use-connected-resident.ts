import { useCallback, useEffect, useRef, useState } from "react";
import { uploadImage } from "../../../shared/direct-image-upload";
import {
  api,
  ApiError,
  allPages,
  requestView,
  withoutRequestCode,
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
  const refresh = useCallback(async () => {
    const revision = ++generation.current;
    const [p, chats, tickets, a, pending] = await Promise.all([
      api<Profile>("/resident/me"),
      allPages<Chat>("/resident/chats"),
      allPages<Ticket>("/resident/tickets"),
      api<{ items: Approval[] }>("/resident/approvals?limit=100"),
      api<{items: SupervisorInteraction[]}>("/resident/supervisor-interactions"),
    ]);
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
    const messages: Message[] = [];
    if (selected) {
      let seq = 0;
      while (true) {
        const page = await api<{ items: Message[] }>(
          `/resident/chats/${selected}/messages?afterSeq=${seq}&limit=100`,
        );
        messages.push(...page.items);
        if (page.items.length < 100) break;
        seq = page.items.at(-1)!.seq;
      }
      if (messages.length && path[0] === "chat")
        await api(`/resident/chats/${selected}/read`, {
          method: "POST",
          body: JSON.stringify({ sequence: messages.at(-1)!.seq }),
        });
    }
    if (selected !== active.current || revision !== generation.current) return;
    setProfile(p);
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
    const chatMessages = messages
      .filter((m) => m.body.text)
      .map((m) => ({
        id: m.id,
        role:
          m.sender_kind === "user"
            ? ("resident" as const)
            : ("assistant" as const),
        text: withoutRequestCode(m.body.text || ""),
        ...(m.body.fileIds?.length
          ? { photos: m.body.fileIds.map((id) => ({ id, name: "Ảnh đính kèm", url: `/api/business/resident/photos/${id}` })) }
          : {}),
      }));
    // Reception answers within the backend's three-minute dispatch limit, or the backend
    // stores a fallback reply. Older unanswered messages predate the agent.
    const last = messages.at(-1);
    awaiting.current =
      last?.sender_kind === "user" &&
      Date.now() - Date.parse(last.created_at) < 180_000;
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
      conversations: chats.map((c) => ({
        id: c.id,
        title: c.title || c.name,
        requestId: c.ticket_id,
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
    const load = () => {
      if (!lock.current)
        void refresh().catch((e) => {
          if (!disposed) fail(e);
        });
    };
    const route = () => {
      const parts = location.hash.slice(2).split("/");
      if (parts[0] === "chat" && parts[1]) active.current = parts[1];
      load();
    };
    route();
    window.addEventListener("hashchange", route);
    let ticks = 0;
    const timer = setInterval(() => {
      // Poll quickly only while the resident is waiting for the assistant.
      if (!document.hidden && (awaiting.current || ++ticks % 4 === 0)) load();
    }, 1250);
    return () => {
      disposed = true;
      clearInterval(timer);
      window.removeEventListener("hashchange", route);
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
  return {
    state,
    profile,
    error,
    busy,
    contact,
    setContact,
    setError,
    refresh: () => run(async () => {}, false),
    interaction: (id: string) => interactions.find(i => i.ticket_id === id),
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
      active.current = id;
      location.hash = `/chat/${id}`;
      void run(async () => {});
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
        const content = text.trim() || "Đính kèm ảnh phản ánh";
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
        const previous = drafts.current.get(id);
        if (text === "Báo sự cố")
          changeDraft({
            step: "description",
            description: "",
            location: "",
            photos,
          });
        else if (previous) {
          const next = {
            ...previous,
            photos: [...previous.photos, ...photos].slice(0, 3),
          };
          if (previous.step === "description") {
            next.description = text.trim();
            next.step = "location";
          } else if (previous.step === "location") {
            next.location = text.trim();
            next.step = "review";
          }
          changeDraft(next);
        } else if (photos.length)
          changeDraft({
            step: "location",
            description: text.trim(),
            location: "",
            photos,
          });
      }),
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
    decide: (
      id: string,
      accepted: boolean,
      reason?: string,
      kind = "customer_completion",
    ) =>
      run(async () => {
        const approval = approvals.find(
          (a) =>
            a.ticket_id === id && a.kind === kind && a.status === "pending",
        );
        if (!approval)
          throw new Error("Không còn yêu cầu xác nhận đang chờ. Hãy tải lại.");
        const detail = await api<TicketDetail>(`/resident/tickets/${id}`);
        const body = JSON.stringify({
          approved: accepted,
          note: reason || "Tôi xác nhận kết quả đã hoàn tất.",
          version: detail.ticket.version,
        });
        await api(`/resident/approvals/${approval.id}/decision`, {
          method: "POST",
          body,
          headers: { "Idempotency-Key": keyFor(`${approval.id}:${body}`) },
        });
      }),
  };
}
export type ConnectedResident = ReturnType<typeof useConnectedResident>;
