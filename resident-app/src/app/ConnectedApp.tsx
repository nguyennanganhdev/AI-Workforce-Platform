import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { RequestDetail, Requests } from "../features/requests/Requests";
import {
  api,
  allPages,
  ApiError,
  requestView,
  type Profile,
  type Chat,
  type Message,
  type Ticket,
  type TicketDetail,
  type Approval,
} from "../services/resident-api";
import "./connected.css";

export function ConnectedApp() {
  const [profile, setProfile] = useState<Profile>();
  const [chats, setChats] = useState<Chat[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [chatId, setChatId] = useState("");
  const [selectedTicketId, setSelectedTicketId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [detail, setDetail] = useState<TicketDetail>();
  const [page, setPage] = useState("assistant");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState({
    title: "",
    description: "",
    location: "",
    phone: "",
    unit: "",
    category: "",
  });
  const [photos, setPhotos] = useState<File[]>([]);
  const [compose, setCompose] = useState(false);
  const [review, setReview] = useState(false);
  const roomDrafts = useRef(new Map<string, { draft: typeof draft; photos: File[]; text: string; compose: boolean; review: boolean }>());
  const currentDraft = useRef({ draft, photos, text, compose, review });
  currentDraft.current = { draft, photos, text, compose, review };
  const previousRoom = useRef("");
  useEffect(() => {
    if (previousRoom.current) roomDrafts.current.set(previousRoom.current, currentDraft.current);
    const saved = roomDrafts.current.get(chatId);
    setDraft(saved?.draft ?? { title: "", description: "", location: "", phone: "", unit: "", category: "" });
    setPhotos(saved?.photos ?? []);
    setText(saved?.text ?? "");
    setCompose(saved?.compose ?? false);
    setReview(saved?.review ?? false);
    previousRoom.current = chatId;
  }, [chatId]);
  const submitting = useRef(false);
  const retry = useRef(new Map<string, string>());
  const keyFor = (input: string) => {
    let key = retry.current.get(input);
    if (!key) {
      key = crypto.randomUUID();
      retry.current.set(input, key);
    }
    return key;
  };
  const refresh = useCallback(async () => {
    const [p, c, t, a] = await Promise.all([
      api<Profile>("/resident/me"),
      allPages<Chat>("/resident/chats"),
      allPages<Ticket>("/resident/tickets"),
      api<{ items: Approval[] }>("/resident/approvals?limit=100"),
    ]);
    setProfile(p);
    setChats(c);
    setTickets(t);
    setApprovals(a.items);
  }, []);
  const fail = (e: unknown) => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      setProfile(undefined);
      setChats([]);
      setTickets([]);
      setMessages([]);
      setApprovals([]);
      setDetail(undefined);
    }
    setError(e instanceof Error ? e.message : "Không kết nối được máy chủ.");
  };
  useEffect(() => {
    let stopped = false;
    const load = async () => {
      try {
        if (!stopped) await refresh();
      } catch (e) {
        if (!stopped) fail(e);
      }
    };
    void load();
    const timer = setInterval(() => {
      if (!document.hidden && !submitting.current) void load();
    }, 5000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [refresh]);
  useEffect(() => {
    const change = () => {
      const [route, id] = location.hash.slice(2).split("/");
      setPage(route || "assistant");
      if (route === "chat") {
        setChatId(id || "");
        setMessages([]);
      }
      if (route === "requests" && id) {
        setPage("detail");
        setSelectedTicketId(id);
        setDetail(undefined);
      }
    };
    change();
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    let stopped = false;
    const load = async () => {
      try {
        if (page === "detail") {
          const id = selectedTicketId;
          if (id) {
            const next = await api<TicketDetail>(`/resident/tickets/${id}`);
            if (!stopped) setDetail(next);
          }
        }
        if (page === "chat" && chatId) {
          const collected: Message[] = [];
          let seq = 0;
          while (true) {
            const next = await api<{ items: Message[] }>(
              `/resident/chats/${chatId}/messages?afterSeq=${seq}&limit=100`,
            );
            collected.push(...next.items);
            if (next.items.length < 100) break;
            seq = next.items.at(-1)!.seq;
          }
          if (!stopped) {
            setMessages(collected);
            if (collected.length)
              await api(`/resident/chats/${chatId}/read`, {
                method: "POST",
                body: JSON.stringify({ sequence: collected.at(-1)!.seq }),
              });
          }
        }
      } catch (e) {
        if (!stopped) fail(e);
      }
    };
    void load();
    const timer = setInterval(() => {
      if (!document.hidden && !submitting.current) void load();
    }, 5000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [page, chatId, selectedTicketId]);
  async function run(action: () => Promise<void>) {
    if (submitting.current) return false;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  const newChat = () =>
    run(async () => {
      const chat = await api<Chat>("/resident/chats", {
        method: "POST",
        body: JSON.stringify({ title: "Hội thoại mới" }),
      });
      setCompose(false);
      setReview(false);
      setText("");
      setPhotos([]);
      setDraft({
        title: "",
        description: "",
        location: "",
        phone: "",
        unit: "",
        category: "",
      });
      location.hash = `/chat/${chat.id}`;
    });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!review) {
      setReview(true);
      return;
    }
    await run(async () => {
      const unit = profile?.units.find((u) => u.id === draft.unit);
      if (!unit) throw new Error("Chọn căn hộ đã được xác minh.");
      const uploaded = [];
      for (const photo of photos) {
        const digest = Array.from(
          new Uint8Array(
            await crypto.subtle.digest("SHA-256", await photo.arrayBuffer()),
          ),
        )
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");
        uploaded.push(
          await api<{ id: string }>(
            `/resident/chats/${chatId}/photos?filename=${encodeURIComponent(photo.name)}&mimeType=${encodeURIComponent(photo.type)}`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/octet-stream",
                "Idempotency-Key": keyFor(`${chatId}:${photo.name}:${digest}`),
              },
              body: photo,
            },
          ),
        );
      }
      const body = JSON.stringify({
        domain_id: unit.domain_id,
        building_id: unit.building_id,
        unit_id: unit.id,
        category_id: draft.category,
        title: draft.title.trim(),
        description: draft.description.trim(),
        contact_name: profile!.user.name,
        contact_phone: draft.phone.trim(),
        location: draft.location.trim(),
        request_kind: "incident",
        file_ids: uploaded.map((p) => p.id),
      });
      const ticket = await api<Ticket>(`/resident/chats/${chatId}/tickets`, {
        method: "POST",
        body,
        headers: { "Idempotency-Key": keyFor(`${chatId}:${body}`) },
      });
      setCompose(false);
      setReview(false);
      setPhotos([]);
      location.hash = `/requests/${ticket.id}`;
    });
  }
  const decision = async (
    approval: Approval,
    accepted: boolean,
    reason?: string,
  ) =>
    run(async () => {
      if (!detail) return;
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
      setDetail(await api(`/resident/tickets/${detail.ticket.id}`));
    });
  const completion = approvals.find(
    (a) =>
      a.ticket_id === detail?.ticket.id &&
      a.kind === "customer_completion" &&
      a.status === "pending",
  );
  const consent = approvals.find(
    (a) =>
      a.ticket_id === detail?.ticket.id &&
      a.kind === "customer_repair" &&
      a.status === "pending",
  );
  const current = chats.find((c) => c.id === chatId);
  return (
    <div className="connected-resident">
      <header className="app-header">
        <a className="brand" href="#/">
          nhà.
        </a>
        <span>{profile?.user.name || "Cư dân"}</span>
        <span className="demo-chip">
          {profile?.dataMode === "local-database"
            ? "Database local · tài khoản kiểm thử"
            : "Dữ liệu từ Ban quản lý"}
        </span>
      </header>
      <nav className="connected-nav">
        <a href="#/">Trợ lý</a>
        <a href="#/requests">Yêu cầu của tôi</a>
        <a href="#/profile">Tài khoản & căn hộ</a>
        <button disabled={busy} onClick={() => void run(refresh)}>
          Tải lại
        </button>
      </nav>
      {error && (
        <div className="error-banner" role="alert">
          {error} <button onClick={() => void run(refresh)}>Thử lại</button>
        </div>
      )}
      {!profile ? (
        <section className="white-card">
          <h1>Kết nối tài khoản cư dân</h1>
          <p>{error || "Đang tải thông tin tài khoản…"}</p>
          <a href="/login">Đăng nhập</a>
        </section>
      ) : (
        <>
          {!profile.units.length && (
            <p role="status" className="error-banner">
              Tài khoản chưa có căn hộ được xác minh. Liên hệ Ban quản lý để
              liên kết căn hộ.
            </p>
          )}
          {page === "profile" && (
            <section className="white-card">
              <h1>{profile.user.name}</h1>
              <p>{profile.user.email}</p>
              {profile.units.map((u) => (
                <p key={u.id}>
                  {u.site_name} · {u.building_name} · Căn {u.code}
                </p>
              ))}
              <button
                onClick={() =>
                  void run(async () => {
                    const r = await fetch("/api/auth/sign-out", {
                      method: "POST",
                      credentials: "include",
                      headers: { "Content-Type": "application/json" },
                      body: "{}",
                    });
                    if (!r.ok) throw new Error("Chưa đăng xuất được.");
                    location.assign("/login");
                  })
                }
              >
                Đăng xuất
              </button>
            </section>
          )}
          {(page === "assistant" || page === "chat") && (
            <section className="page-section stack">
              <div className="button-row">
                <h1>Hội thoại của bạn</h1>
                <button
                  className="primary-button"
                  disabled={busy}
                  onClick={() => void newChat()}
                >
                  Chat mới
                </button>
              </div>
              <div className="connected-chat-list">
                {chats.map((c) => (
                  <a
                    key={c.id}
                    href={`#/chat/${c.id}`}
                    aria-current={c.id === chatId ? "page" : undefined}
                  >
                    {c.name}
                    {c.unread_count > 0 ? ` · ${c.unread_count} tin mới` : ""}
                  </a>
                ))}
              </div>
              {page === "chat" && chatId && (
                <>
                  <section className="white-card stack">
                    {messages.map((m) => (
                      <div key={m.id}>
                        <strong>
                          {m.sender_kind === "user" ? "Bạn" : "Trợ lý"}
                        </strong>
                        <p className="preserve">{m.body.text}</p>
                      </div>
                    ))}
                    {!messages.length && (
                      <p>
                        Mô tả vấn đề hoặc gửi phản ánh để Ban quản lý tiếp nhận.
                      </p>
                    )}
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        void run(async () => {
                          const body = {
                            text: text.trim(),
                            client_message_id: keyFor(
                              `${chatId}:message:${text}`,
                            ),
                          };
                          const message = await api<Message>(
                            `/resident/chats/${chatId}/messages`,
                            { method: "POST", body: JSON.stringify(body) },
                          );
                          setMessages((previous) => [
                            ...previous.filter((m) => m.id !== message.id),
                            message,
                          ]);
                          retry.current.delete(`${chatId}:message:${text}`);
                          setText("");
                        });
                      }}
                    >
                      <label>
                        Tin nhắn
                        <textarea
                          value={text}
                          onChange={(e) => setText(e.target.value)}
                          required
                          maxLength={10000}
                        />
                      </label>
                      <button
                        className="primary-button"
                        disabled={busy || !text.trim()}
                      >
                        Gửi tin nhắn
                      </button>
                    </form>
                  </section>
                  {current?.ticket_id ? (
                    <a
                      className="primary-button"
                      href={`#/requests/${current.ticket_id}`}
                    >
                      Theo dõi yêu cầu
                    </a>
                  ) : (
                    <button
                      className="primary-button"
                      disabled={busy || !profile.units.length}
                      onClick={() => setCompose(!compose)}
                    >
                      Lập phản ánh
                    </button>
                  )}
                  {compose && !current?.ticket_id && (
                    <form className="white-card stack" onSubmit={submit}>
                      <h2>
                        {review
                          ? "Kiểm tra trước khi gửi"
                          : "Nội dung phản ánh"}
                      </h2>
                      <fieldset disabled={busy || review}>
                        <label>
                          Căn hộ
                          <select
                            required
                            value={draft.unit}
                            onChange={(e) =>
                              setDraft({ ...draft, unit: e.target.value })
                            }
                          >
                            <option value="">Chọn căn hộ</option>
                            {profile.units.map((u) => (
                              <option key={u.id} value={u.id}>
                                {u.building_name} · {u.code}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Nhóm dịch vụ
                          <select
                            required
                            value={draft.category}
                            onChange={(e) =>
                              setDraft({ ...draft, category: e.target.value })
                            }
                          >
                            <option value="">Chọn nhóm</option>
                            {profile.categories.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        {(
                          [
                            ["title", "Tiêu đề"],
                            ["description", "Mô tả"],
                            ["location", "Vị trí cụ thể"],
                            ["phone", "Số điện thoại liên hệ"],
                          ] as const
                        ).map(([field, label]) => (
                          <label key={field}>
                            {label}
                            <textarea
                              required
                              minLength={field === "phone" ? 10 : 3}
                              maxLength={
                                field === "description"
                                  ? 10000
                                  : field === "title"
                                    ? 300
                                    : field === "location"
                                      ? 500
                                      : 30
                              }
                              value={draft[field]}
                              onChange={(e) =>
                                setDraft({ ...draft, [field]: e.target.value })
                              }
                            />
                          </label>
                        ))}
                        <label>
                          Ảnh (tối đa 3 ảnh, 10 MB mỗi ảnh)
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            multiple
                            onChange={(e) => {
                              const selected = Array.from(e.target.files || []);
                              if (
                                selected.length > 3 ||
                                selected.some((f) => f.size > 10 * 1024 * 1024)
                              ) {
                                setError(
                                  "Chọn tối đa 3 ảnh, mỗi ảnh không quá 10 MB.",
                                );
                                e.target.value = "";
                                return;
                              }
                              setPhotos(selected);
                            }}
                          />
                        </label>
                      </fieldset>
                      <p>{photos.map((p) => p.name).join(", ")}</p>
                      {review && (
                        <button
                          type="button"
                          onClick={() => setReview(false)}
                          disabled={busy}
                        >
                          Chỉnh sửa
                        </button>
                      )}
                      <button className="primary-button" disabled={busy}>
                        {busy
                          ? "Đang gửi…"
                          : review
                            ? "Gửi phản ánh"
                            : "Kiểm tra nội dung"}
                      </button>
                    </form>
                  )}
                </>
              )}
            </section>
          )}
          {page === "requests" && (
            <Requests
              requests={tickets.map((t) =>
                requestView(
                  { ticket: t, events: [], photos: [] },
                  approvals.some(
                    (a) =>
                      a.ticket_id === t.id &&
                      a.kind === "customer_completion" &&
                      a.status === "pending",
                  ),
                ),
              )}
              onOpen={(id) => {
                location.hash = `/requests/${id}`;
              }}
              onReport={() => void newChat()}
            />
          )}
          {page === "detail" &&
            (detail ? (
              <>
                <fieldset disabled={busy}>
                  <RequestDetail
                    request={requestView(detail, !!completion)}
                    connected
                    onResolve={(accepted, reason) =>
                      completion
                        ? decision(completion, accepted, reason)
                        : Promise.resolve(false)
                    }
                  />
                </fieldset>
                {consent && (
                  <section className="white-card">
                    <h2>Đồng ý phương án sửa chữa</h2>
                    <p>{consent.request_detail.note}</p>
                    <button
                      disabled={busy}
                      onClick={() =>
                        void decision(
                          consent,
                          true,
                          "Tôi đồng ý phương án sửa chữa.",
                        )
                      }
                    >
                      Đồng ý
                    </button>
                    <button
                      disabled={busy}
                      onClick={() =>
                        void decision(
                          consent,
                          false,
                          "Tôi chưa đồng ý phương án sửa chữa.",
                        )
                      }
                    >
                      Chưa đồng ý
                    </button>
                  </section>
                )}
              </>
            ) : (
              <p>Đang tải yêu cầu…</p>
            ))}
        </>
      )}
    </div>
  );
}
