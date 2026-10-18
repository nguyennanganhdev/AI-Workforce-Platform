import { useState } from "react";
import { IconBell, IconCheck, IconChevronRight } from "@tabler/icons-react";
import type { ResidentNotification } from "../../services/types";

export function NotificationCenter({ items, unread, busy, more, onMore, onRead, onOpen }: {
  items: ResidentNotification[]; unread: number; busy: boolean; more: boolean;
  onMore: () => unknown; onRead: (ids: string[]) => unknown;
  onOpen: (item: ResidentNotification) => unknown;
}) {
  const [filter,setFilter]=useState<"all" | "unread">("all");
  const visible=items.filter(n => filter==="all" || !n.read_at);
  const unreadIds=visible.filter(n => !n.read_at).map(n => n.id);
  return <section className="page-section stack notification-center" aria-label="Thông báo của bạn">
    <div className="notification-controls">
      <div className="notification-filters" aria-label="Lọc thông báo">
        <button aria-pressed={filter==="all"} onClick={() => setFilter("all")}>Tất cả</button>
        <button aria-pressed={filter==="unread"} onClick={() => setFilter("unread")}>Chưa đọc {unread>0 && <span>{unread}</span>}</button>
      </div>
      <button className="text-button" disabled={busy || !unreadIds.length} onClick={() => onRead(unreadIds)}><IconCheck size={16} aria-hidden="true" /> Đọc các mục hiển thị</button>
    </div>
    <p className="page-description">Thông báo và trạng thái đã đọc được lưu theo tài khoản của bạn.</p>
    {visible.map(n => <article className={`notification-entry${n.read_at ? " is-read" : ""}`} key={n.id}>
      <button className="notification-card" onClick={() => onOpen(n)}>
        <span className="icon-tile"><IconBell size={21} aria-hidden="true" /></span>
        <span><strong>{n.payload.title || "Cập nhật dành cho bạn"}</strong><p>{n.payload.message || n.payload.text || "Có cập nhật mới từ hệ thống."}</p>
          <time dateTime={n.created_at}>{new Date(n.created_at).toLocaleString("vi-VN",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}</time>
        </span>
        {!n.read_at && <span className="notification-unread-dot" aria-label="Chưa đọc" />}
        {(n.channel_id || n.ticket_id || n.payload.channelId || n.payload.ticketId) && <IconChevronRight size={18} aria-hidden="true" />}
      </button>
      <div className="notification-read-row">{n.read_at ? <span><IconCheck size={14} aria-hidden="true" /> Đã đọc</span> :
        <button className="text-button" disabled={busy} onClick={() => onRead([n.id])}>Đánh dấu đã đọc</button>}</div>
    </article>)}
    {!visible.length && <div className="empty-state"><IconBell /><h3>{filter==="unread" ? "Bạn đã đọc hết thông báo" : "Chưa có thông báo"}</h3><p>Cập nhật mới sẽ xuất hiện tại đây.</p></div>}
    {more && <button className="secondary-button" disabled={busy} onClick={onMore}>Xem thông báo cũ hơn</button>}
  </section>;
}
