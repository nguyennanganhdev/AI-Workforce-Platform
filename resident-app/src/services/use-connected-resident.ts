import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  allPages,
  requestView,
  type Profile,
  type Chat,
  type Message,
  type Ticket,
  type TicketDetail,
  type Approval,
} from "./resident-api";
import type { Draft, Photo, ResidentState } from "./types";

const empty: ResidentState = {
  version: 1,
  requests: [],
  messages: [],
  conversations: [],
  draft: null,
};

export function useConnectedResident() {
  const [state, setState] = useState<ResidentState>(empty);
  const [profile, setProfile] = useState<Profile>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [contact, setContact] = useState({ unit: "", category: "", phone: "" });
  const current = useRef(state);
  current.current = state;
  const active = useRef("");
  const drafts = useRef(new Map<string, Draft>());
  const lock = useRef(false);
  const generation = useRef(0);
  const keys = useRef(new Map<string, string>());
  const keyFor = (value: string) => {
    if (!keys.current.has(value)) keys.current.set(value, crypto.randomUUID());
    return keys.current.get(value)!;
  };
  const refresh = useCallback(async () => {
    const revision = ++generation.current;
    const [p, chats, tickets, a] = await Promise.all([
      api<Profile>("/resident/me"),
      allPages<Chat>("/resident/chats"),
      allPages<Ticket>("/resident/tickets"),
      api<{ items: Approval[] }>("/resident/approvals?limit=100"),
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
    const chatMessages = messages.map((m) => ({
      id: m.id,
      role:
        m.sender_kind === "user"
          ? ("resident" as const)
          : ("assistant" as const),
      text: m.body.text || "",
    }));
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
      conversations: chats.map((c) => ({
        id: c.id,
        title: c.name,
        requestId: c.ticket_id,
        unread: c.id === selected && path[0] === "chat" ? 0 : c.unread_count,
        updatedAt: (c as Chat & { updated_at?: string }).updated_at || "",
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
    const timer = setInterval(() => {
      if (!document.hidden) load();
    }, 5000);
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
        const retryKey = `${id}:message:${content}`;
        await api(`/resident/chats/${id}/messages`, {
          method: "POST",
          body: JSON.stringify({
            text: content,
            client_message_id: keyFor(retryKey),
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
        for (const photo of d.photos) {
          const blob = await (await fetch(photo.url)).blob();
          files.push(
            await api<{ id: string }>(
              `/resident/chats/${active.current}/photos?filename=${encodeURIComponent(photo.name)}&mimeType=${encodeURIComponent(blob.type)}`,
              {
                method: "POST",
                headers: {
                  "Content-Type": "application/octet-stream",
                  "Idempotency-Key": keyFor(
                    `${active.current}:photo:${photo.id}`,
                  ),
                },
                body: blob,
              },
            ),
          );
        }
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
