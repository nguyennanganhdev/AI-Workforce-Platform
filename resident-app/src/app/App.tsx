import { useEffect, useRef, useState } from "react";
import {
  IconArrowLeft,
  IconBell,
  IconChevronDown,
  IconHome,
  IconLayoutGrid,
  IconMessageCircle,
  IconSparkles,
  IconX,
} from "@tabler/icons-react";
import { LeafMark } from "../components/Illustrations";
import { Assistant, Composer } from "../features/assistant/Assistant";
import { ConversationList } from "../features/assistant/ConversationList";
import {
  normalizeConversations,
  reconcileConversations,
  newConversation,
  selectConversation,
  activeRoom,
  receiveTicketEvent,
} from "../services/conversations";

import { RequestDetail, Requests } from "../features/requests/Requests";
import { SupervisorResponse } from "../features/requests/SupervisorResponse";
import {
  Amenities,
  Building,
  Notifications,
  Profile,
  Utilities,
  type UtilityPage,
} from "../features/utilities/Utilities";
import { initialState, resident as demoResident } from "../mocks/seed";
import {
  loadConversations as loadState,
  reply,
  resolveRequest,
  saveState,
  submitDraft,
} from "../services/conversations";
import type { Photo, ResidentState } from "../services/types";

type Route = {
  page: "assistant" | UtilityPage | "detail";
  id?: string;
  conversation?: boolean;
};
const titles: Record<Route["page"], string> = {
  assistant: "Trợ lý cư dân",
  utilities: "Tiện ích",
  requests: "Yêu cầu của tôi",
  notifications: "Thông báo",
  profile: "Tài khoản & căn hộ",
  building: "Thông tin tòa nhà",
  amenities: "Tiện ích khu dân cư",
  detail: "Chi tiết yêu cầu",
};
function readRoute(): Route {
  const path = location.hash.slice(1).split("/").filter(Boolean);
  if (path[0] === "chat")
    return { page: "assistant", conversation: true, id: path[1] };
  if (path[0] === "requests" && path[1]) return { page: "detail", id: path[1] };
  if (
    path[0] &&
    [
      "utilities",
      "requests",
      "notifications",
      "profile",
      "building",
      "amenities",
    ].includes(path[0])
  )
    return { page: path[0] as UtilityPage };
  return { page: "assistant" };
}

import type { ConnectedResident } from "../services/use-connected-resident";
import type { Approval } from "../services/resident-api";

export function App({ live }: { live?: ConnectedResident }) {
  const resident = live
    ? {
        name: live.profile?.user.name || "Cư dân",
        apartment: live.profile?.units[0]?.code || "Chưa liên kết",
        project: live.profile?.units[0]?.site_name || "Không gian cư dân",
      }
    : demoResident;
  const initials = resident.name
    .split(" ")
    .slice(-2)
    .map((n) => n[0])
    .join("");
  const [loaded] = useState(() => {
    if (live) return { state: live.state, error: "" };
    try {
      return { state: loadState(localStorage), error: "" };
    } catch (e) {
      return {
        state: normalizeConversations(initialState()),
        error:
          e instanceof Error
            ? e.message
            : "Không đọc được dữ liệu trên thiết bị.",
      };
    }
  });
  const [previewState, setState] = useState(loaded.state);
  const state = live?.state ?? previewState;
  const stateRef = useRef(state);
  const composerInputs = useRef<
    Record<string, { text: string; photos: Photo[] }>
  >({});
  const [previewError, setPreviewError] = useState(loaded.error);
  const error = live?.error ?? previewError;
  const setError = live?.setError ?? setPreviewError;
  const [route, setRoute] = useState<Route>(readRoute);
  const scroll = useRef<HTMLElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const previousPage = useRef(route.page);
  const [resetOpen, setResetOpen] = useState(false);
  const resetDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const change = () => setRoute(readRoute());
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    document.title = `${titles[route.page]} — Nhà`;
    scroll.current?.scrollTo({ top: 0 });
    if (previousPage.current !== route.page) title.current?.focus();
    previousPage.current = route.page;
  }, [route.page, route.id, route.conversation]);
  useEffect(() => {
    const viewport = window.visualViewport;
    const update = () =>
      document.documentElement.style.setProperty(
        "--app-height",
        `${viewport?.height ?? window.innerHeight}px`,
      );
    update();
    viewport?.addEventListener("resize", update);
    return () => {
      viewport?.removeEventListener("resize", update);
      document.documentElement.style.removeProperty("--app-height");
    };
  }, []);
  useEffect(() => {
    if (resetOpen) resetDialog.current?.showModal();
    else resetDialog.current?.close();
  }, [resetOpen]);
  useEffect(() => {
    if (
      !live &&
      route.conversation &&
      route.id &&
      route.id !== stateRef.current.activeConversationId
    ) {
      commit((s) => selectConversation(s, route.id!));
    }
  }, [route.conversation, route.id]);

  function navigate(page: Route["page"], id?: string) {
    location.hash =
      page === "assistant"
        ? "/"
        : page === "detail"
          ? `/requests/${id}`
          : `/${page}`;
  }
  function commit(transform: (previous: ResidentState) => ResidentState) {
    try {
      const next = reconcileConversations(
        stateRef.current,
        transform(stateRef.current),
      );
      saveState(localStorage, next);
      stateRef.current = next;
      setState(next);
      setError("");
      return true;
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Chưa thể hoàn thành. Bạn thử lại nhé.",
      );
      return false;
    }
  }
  const openConversation = () => {
    if (live) {
      live.resume();
      return;
    }
    commit((s) => selectConversation(s, activeRoom(s).id));
    location.hash = "/chat";
  };
  const send = (text: string, photos: Photo[] = []) => {
    if (live) return live.send(text, photos);
    const saved = commit((previous) => reply(previous, text, photos));
    if (saved) openConversation();
    return saved;
  };
  const openRequest = (id: string) => navigate("detail", id);
  const report = () => {
    if (live) {
      void live.send("Báo sự cố");
      return;
    }
    if (activeRoom(stateRef.current).requestId) commit(newConversation);
    openConversation();
    if (!stateRef.current.draft) send("Báo sự cố");
  };
  const activeTab = route.page === "assistant" ? "assistant" : "utilities";
  const pending = state.requests.filter(
    (r) => r.status === "confirmation",
  ).length;
  const unread = (state.conversations ?? []).reduce((n, c) => n + c.unread, 0);
  const detail = state.requests.find((r) => r.id === route.id);
  const nav = (
    <>
      {[
        { page: "assistant", label: "Trợ lý", icon: IconMessageCircle },
        { page: "utilities", label: "Tiện ích", icon: IconLayoutGrid },
      ].map(({ page, label, icon: Icon }) => (
        <a
          key={page}
          href={page === "assistant" ? "#/" : "#/utilities"}
          className={activeTab === page ? "active" : ""}
          aria-current={activeTab === page ? "page" : undefined}
        >
          <span>
            <Icon size={23} stroke={activeTab === page ? 1.9 : 1.6} />
          </span>
          <strong>{label}</strong>
        </a>
      ))}
    </>
  );

  return (
    <div className="app-shell">
      <aside className="desktop-sidebar">
        <a href="#/" className="brand">
          <span className="brand-mark">
            <IconHome size={23} stroke={1.8} />
          </span>
          <span>
            nhà<span className="brand-period">.</span>
            <small>RESIDENT COMPANION</small>
          </span>
        </a>
        <div className="sidebar-label">KHÔNG GIAN CỦA BẠN</div>
        <nav aria-label="Điều hướng chính">{nav}</nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <LeafMark />
            <h3>
              Sống an tâm.
              <br />
              Tận hưởng mỗi ngày.
            </h3>
            <p>
              Một người bạn nhỏ
              <br />
              cho ngôi nhà của bạn.
            </p>
          </div>
          <button
            className="sidebar-profile"
            onClick={() => navigate("profile")}
          >
            <span className="avatar">{initials}</span>
            <span>
              <strong>{resident.name}</strong>
              <small>Căn hộ {resident.apartment}</small>
            </span>
            <IconChevronDown size={16} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="app-header">
          <div className="header-location">
            <span className="location-icon">
              <IconHome size={21} stroke={1.7} />
            </span>
            <button onClick={() => navigate("profile")}>
              <span className="eyebrow">CHÀO MỪNG VỀ NHÀ</span>
              <strong>
                {resident.project}
                <IconChevronDown size={14} />
              </strong>
            </button>
          </div>
          <div className="header-actions">
            <span className="demo-chip">
              {live
                ? live.profile?.dataMode === "local-database"
                  ? "Database local"
                  : live.profile
                    ? "Đã kết nối"
                    : "Đang kết nối"
                : "Bản trải nghiệm"}
            </span>
            <button
              className="icon-button notification-button"
              aria-label={`Thông báo, ${unread} tin nhắn chưa đọc, ${pending} yêu cầu chờ xác nhận`}
              onClick={() => navigate("notifications")}
            >
              <IconBell size={22} stroke={1.6} />
              {(pending > 0 || unread > 0) && <i />}
            </button>
            <button
              className="avatar header-avatar"
              aria-label={`Tài khoản của ${resident.name}`}
              onClick={() => navigate("profile")}
            >
              {initials}
            </button>
          </div>
        </header>
        {route.page === "assistant" && (
          <ConversationList
            state={state}
            onNew={() => {
              if (live) {
                void live.newChat();
                return;
              }
              if (commit(newConversation))
                location.hash = `/chat/${stateRef.current.activeConversationId}`;
            }}
            onSelect={(id) => {
              if (live) {
                live.select(id);
                return;
              }
              if (commit((s) => selectConversation(s, id)))
                location.hash = `/chat/${id}`;
            }}
          />
        )}
        {route.page === "assistant" && route.conversation && (
          <div className="conversation-toolbar">
            <button
              className="icon-button"
              aria-label="Thoát cuộc trò chuyện, về trang Trợ lý"
              onClick={() => navigate("assistant")}
            >
              <IconArrowLeft size={21} />
            </button>
            <div>
              <strong>Cuộc trò chuyện</strong>
              <span>Lịch sử và bản nháp được giữ lại</span>
            </div>
          </div>
        )}
        {route.page !== "assistant" && (
          <div className="page-toolbar">
            {route.page !== "utilities" && (
              <button
                className="icon-button"
                aria-label="Quay lại"
                onClick={() =>
                  navigate(route.page === "detail" ? "requests" : "utilities")
                }
              >
                <IconArrowLeft size={21} />
              </button>
            )}
            <h1 ref={title} tabIndex={-1}>
              {titles[route.page]}
            </h1>
          </div>
        )}
        {route.page === "assistant" && (
          <h2 className="sr-only" ref={title} tabIndex={-1}>
            Trợ lý cư dân
          </h2>
        )}
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button
              aria-label="Đóng thông báo lỗi"
              onClick={() => setError("")}
            >
              <IconX size={18} />
            </button>
          </div>
        )}
        {live && !live.profile && (
          <div className="error-banner" role="status">
            {live.error || "Đang kết nối tài khoản…"}{" "}
            <a href="/login">Đăng nhập</a>
            <button onClick={() => void live.refresh()}>Thử lại</button>
          </div>
        )}
        <main className="main-scroll" ref={scroll} id="main-content">
          {route.page === "assistant" && (
            <Assistant
              key={state.activeConversationId}
              state={state}
              connected={!!live}
              busy={live?.busy}
              residentName={resident.name}
              apartment={resident.apartment}
              draftFields={
                live && state.draft?.step === "review" ? (
                  <div className="resident-contact-fields">
                    <label>
                      Căn hộ
                      <select
                        value={live.contact.unit}
                        onChange={(e) =>
                          live.setContact({
                            ...live.contact,
                            unit: e.target.value,
                          })
                        }
                      >
                        <option value="">Chọn căn hộ</option>
                        {live.profile?.units.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.building_name} · {u.code}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Nhóm dịch vụ
                      <select
                        value={live.contact.category}
                        onChange={(e) =>
                          live.setContact({
                            ...live.contact,
                            category: e.target.value,
                          })
                        }
                      >
                        <option value="">Chọn nhóm dịch vụ</option>
                        {live.profile?.categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Số điện thoại liên hệ
                      <input
                        type="tel"
                        maxLength={30}
                        value={live.contact.phone}
                        onChange={(e) =>
                          live.setContact({
                            ...live.contact,
                            phone: e.target.value,
                          })
                        }
                      />
                    </label>
                  </div>
                ) : undefined
              }
              conversation={!!route.conversation}
              onResume={openConversation}
              onSend={send}
              onOpen={openRequest}
              onRequests={() => navigate("requests")}
              onSubmit={() => {
                if (live) {
                  void live.submit();
                  return;
                }
                commit(submitDraft);
              }}
              onEditDraft={() => {
                if (live) {
                  live.editDraft();
                  return;
                }
                commit((s) => ({
                  ...s,
                  draft: s.draft ? { ...s.draft, step: "description" } : null,
                }));
              }}
              onCancelDraft={() => {
                if (live) {
                  live.cancelDraft();
                  return;
                }
                commit((s) => ({ ...s, draft: null }));
              }}
            />
          )}
          {route.page === "utilities" && (
            <Utilities
              onNavigate={navigate}
              pending={
                state.requests.filter((r) => r.status !== "completed").length
              }
            />
          )}
          {route.page === "requests" && (
            <Requests
              requests={state.requests}
              onOpen={openRequest}
              onReport={report}
            />
          )}
          {route.page === "detail" &&
            (detail ? (
              <>
                <RequestDetail
                  key={detail.id}
                  request={detail}
                  connected={!!live}
                  onResolve={(accepted, reason) =>
                    live
                      ? live.decide(detail.id, accepted, reason)
                      : commit((s) =>
                          resolveRequest(s, detail.id, accepted, reason),
                        )
                  }
                />
                {live?.interaction(detail.id) && <SupervisorResponse key={`${detail.id}:${live.interaction(detail.id)!.ticket_version}`}
                  item={live.interaction(detail.id)!} busy={live.busy} onRespond={(decision, note) => live.respondSupervisor(live.interaction(detail.id)!, decision, note)} />}
                {live?.consent(detail.id) && !live.interaction(detail.id) && (
                  <section className="white-card resident-consent">
                    <h3>Phương án sửa chữa cần bạn xác nhận</h3>
                    <p>{live.consent(detail.id)?.request_detail.note}</p>
                    <RepairQuote
                      quote={live.consent(detail.id)!.request_detail}
                    />
                    <div className="button-row">
                      <button
                        className="primary-button"
                        disabled={live.busy}
                        onClick={() =>
                          void live.decide(
                            detail.id,
                            true,
                            "Tôi đồng ý phương án sửa chữa.",
                            "customer_repair",
                          )
                        }
                      >
                        Đồng ý phương án
                      </button>
                      <button
                        className="secondary-button"
                        disabled={live.busy}
                        onClick={() =>
                          void live.decide(
                            detail.id,
                            false,
                            "Tôi chưa đồng ý phương án sửa chữa.",
                            "customer_repair",
                          )
                        }
                      >
                        Chưa đồng ý
                      </button>
                    </div>
                  </section>
                )}
                {!live && (
                  <section className="resident-ticket-event">
                    <strong>Sự kiện ticket · bản mô phỏng</strong>
                    <p>
                      Kiểm tra thẻ ticket và tin chưa đọc theo đúng hội thoại;
                      chưa gửi thông báo thật.
                    </p>
                    <button
                      disabled={detail.status === "completed"}
                      onClick={() =>
                        commit((s) =>
                          receiveTicketEvent(
                            s,
                            detail.id,
                            "Yêu cầu đã được chuyển đến đội nhân viên",
                            "processing",
                          ),
                        )
                      }
                    >
                      Mô phỏng đã điều phối
                    </button>
                    <button
                      disabled={detail.status === "completed"}
                      onClick={() =>
                        commit((s) =>
                          receiveTicketEvent(
                            s,
                            detail.id,
                            "Nhân viên đã hoàn thành, mời bạn xác nhận",
                            "confirmation",
                          ),
                        )
                      }
                    >
                      Mô phỏng chờ xác nhận
                    </button>
                    <button
                      onClick={() => {
                        const room = state.conversations?.find(
                          (c) => c.requestId === detail.id,
                        );
                        if (
                          room &&
                          commit((s) => selectConversation(s, room.id))
                        )
                          location.hash = `/chat/${room.id}`;
                      }}
                    >
                      Mở hội thoại của ticket
                    </button>
                  </section>
                )}
              </>
            ) : (
              <div className="empty-state">
                <IconClipboardFallback />
                <h2>Không tìm thấy yêu cầu</h2>
                <p>Yêu cầu không tồn tại trên thiết bị này.</p>
                <button
                  className="primary-button"
                  onClick={() => navigate("requests")}
                >
                  Xem yêu cầu của tôi
                </button>
              </div>
            ))}
          {route.page === "notifications" && (
            <>
              {(state.conversations ?? []).some((c) => c.unread > 0) && (
                <div className="page-section stack">
                  {(state.conversations ?? [])
                    .filter((c) => c.unread > 0)
                    .map((c) => (
                      <button
                        key={c.id}
                        className="notification-card"
                        onClick={() => {
                          if (live) {
                            live.select(c.id);
                            return;
                          }
                          if (commit((s) => selectConversation(s, c.id)))
                            location.hash = `/chat/${c.id}`;
                        }}
                      >
                        <span>
                          <strong>
                            {c.unread} tin chưa đọc · {c.title}
                          </strong>
                          <p>{c.preview ?? c.messages.at(-1)?.text}</p>
                        </span>
                      </button>
                    ))}
                </div>
              )}
              <Notifications requests={state.requests} onOpen={openRequest} />
            </>
          )}
          {route.page === "profile" && (
            <Profile
              connectedProfile={live?.profile}
              connected={!!live}
              onReset={() => setResetOpen(true)}
            />
          )}
          {route.page === "building" && (
            <Building connectedProfile={live?.profile} connected={!!live} />
          )}
          {route.page === "amenities" && <Amenities connected={!!live} />}
        </main>
        {route.page === "assistant" && (
          <Composer
            key={state.activeConversationId}
            onSend={send}
            connected={!!live}
            busy={live?.busy}
            draft={state.draft}
            initialInput={composerInputs.current[state.activeConversationId!]}
            onInputChange={(value) => {
              composerInputs.current[state.activeConversationId!] = value;
            }}
          />
        )}
        <nav className="mobile-nav" aria-label="Điều hướng chính">
          {nav}
        </nav>
      </div>
      <dialog
        ref={resetDialog}
        className="reset-dialog"
        onCancel={() => setResetOpen(false)}
        onClose={() => setResetOpen(false)}
      >
        <h2>Bắt đầu lại bản trải nghiệm?</h2>
        <p>
          Hội thoại, ảnh và yêu cầu đã tạo trên trình duyệt này sẽ được xóa và
          thay bằng dữ liệu mẫu.
        </p>
        <div className="button-row">
          <button
            autoFocus
            className="secondary-button"
            onClick={() => setResetOpen(false)}
          >
            Giữ dữ liệu
          </button>
          <button
            className="primary-button"
            onClick={() => {
              if (commit(() => initialState())) {
                setResetOpen(false);
                navigate("assistant");
              }
            }}
          >
            Đặt lại
          </button>
        </div>
      </dialog>
    </div>
  );
}

function IconClipboardFallback() {
  return <IconSparkles size={30} />;
}

function RepairQuote({ quote }: { quote: Approval["request_detail"] }) {
  if (quote.total === undefined) return null;
  const vnd = (n: number) => `${n.toLocaleString("vi-VN")}đ`;
  return (
    <ul>
      {quote.lines?.map((line, index) => (
        <li key={index}>
          {line.name} × {line.quantity} {line.unit}: {vnd(line.amount)}
        </li>
      ))}
      <li>Tiền công: {vnd(quote.labor_cost ?? 0)}</li>
      <li>
        <strong>Tổng cộng: {vnd(quote.total)}</strong>
      </li>
      {!!quote.warranty_months && (
        <li>Bảo hành: {quote.warranty_months} tháng</li>
      )}
    </ul>
  );
}
