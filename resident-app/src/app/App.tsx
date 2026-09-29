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

import { RequestDetail, Requests } from "../features/requests/Requests";
import {
  Amenities,
  Building,
  Notifications,
  Profile,
  Utilities,
  type UtilityPage,
} from "../features/utilities/Utilities";
import { initialState, resident } from "../mocks/seed";
import {
  loadState,
  reply,
  resolveRequest,
  saveState,
  submitDraft,
} from "../services/resident-service";
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
  if (path[0] === "chat") return { page: "assistant", conversation: true };
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

export function App() {
  const [loaded] = useState(() => {
    try {
      return { state: loadState(localStorage), error: "" };
    } catch (e) {
      return {
        state: initialState(),
        error:
          e instanceof Error
            ? e.message
            : "Không đọc được dữ liệu trên thiết bị.",
      };
    }
  });
  const [state, setState] = useState(loaded.state);
  const stateRef = useRef(state);
  const [error, setError] = useState(loaded.error);
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
      const next = transform(stateRef.current);
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
    location.hash = "/chat";
  };
  const send = (text: string, photos: Photo[] = []) => {
    const saved = commit((previous) => reply(previous, text, photos));
    if (saved) openConversation();
    return saved;
  };
  const openRequest = (id: string) => navigate("detail", id);
  const report = () => {
    openConversation();
    if (!stateRef.current.draft) send("Báo sự cố");
  };
  const activeTab = route.page === "assistant" ? "assistant" : "utilities";
  const pending = state.requests.filter(
    (r) => r.status === "confirmation",
  ).length;
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
            <span className="avatar">MA</span>
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
            <span className="demo-chip">Bản trải nghiệm</span>
            <button
              className="icon-button notification-button"
              aria-label={`Thông báo${pending ? `, ${pending} yêu cầu chờ xác nhận` : ""}`}
              onClick={() => navigate("notifications")}
            >
              <IconBell size={22} stroke={1.6} />
              {pending > 0 && <i />}
            </button>
            <button
              className="avatar header-avatar"
              aria-label="Tài khoản của Minh An"
              onClick={() => navigate("profile")}
            >
              MA
            </button>
          </div>
        </header>
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
        <main className="main-scroll" ref={scroll} id="main-content">
          {route.page === "assistant" && (
            <Assistant
              state={state}
              conversation={!!route.conversation}
              onResume={openConversation}
              onSend={send}
              onOpen={openRequest}
              onRequests={() => navigate("requests")}
              onSubmit={() => {
                commit(submitDraft);
              }}
              onEditDraft={() => {
                commit((s) => ({
                  ...s,
                  draft: s.draft ? { ...s.draft, step: "description" } : null,
                }));
              }}
              onCancelDraft={() => {
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
              <RequestDetail
                key={detail.id}
                request={detail}
                onResolve={(accepted, reason) =>
                  commit((s) => resolveRequest(s, detail.id, accepted, reason))
                }
              />
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
            <Notifications requests={state.requests} onOpen={openRequest} />
          )}
          {route.page === "profile" && (
            <Profile onReset={() => setResetOpen(true)} />
          )}
          {route.page === "building" && <Building />}
          {route.page === "amenities" && <Amenities />}
        </main>
        {route.page === "assistant" && (
          <Composer onSend={send} draft={state.draft} />
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
