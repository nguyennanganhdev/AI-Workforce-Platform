import { useState } from "react";
import {
  IconPlus,
  IconMessageCircle,
  IconChevronRight,
  IconX,
} from "@tabler/icons-react";
import type { ResidentState } from "../../services/types";
import "./conversations.css";

/** Time today, otherwise the day: enough to tell conversations apart at a glance. */
function when(iso: string) {
  const date = new Date(iso);
  if (!iso || Number.isNaN(date.getTime())) return "";
  return date.toDateString() === new Date().toDateString()
    ? date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
}
export function ConversationList({
  state,
  onSelect,
  onNew,
}: {
  state: ResidentState;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const rooms = [...(state.conversations ?? [])]
    // A conversation nobody wrote in is only worth showing while it is open.
    .filter(
      (c) =>
        c.id === state.activeConversationId ||
        c.requestId ||
        c.draft ||
        c.preview ||
        c.messages.length,
    )
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  const matches = (c: (typeof rooms)[number]) =>
    `${c.title} ${c.requestCode ?? ""} ${c.preview ?? ""}`
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase());
  const unread = rooms.reduce((n, c) => n + c.unread, 0);
  return (
    <section className="resident-rooms" aria-label="Hội thoại của bạn">
      <div className="resident-rooms-bar">
        <button onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          <IconMessageCircle size={19} /> Hội thoại{" "}
          {unread > 0 && <b>{unread}</b>}
        </button>
        <button onClick={onNew}>
          <IconPlus size={18} /> Chat mới
        </button>
      </div>
      {open && (
        <div className="resident-rooms-list">
          <div className="resident-rooms-search">
            <input
              aria-label="Tìm hội thoại"
              placeholder="Tìm nội dung hoặc mã yêu cầu"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button
              aria-label="Đóng danh sách hội thoại"
              onClick={() => setOpen(false)}
            >
              <IconX size={18} />
            </button>
          </div>
          {rooms.filter(matches).map((c) => (
            <button
              key={c.id}
              className={c.id === state.activeConversationId ? "selected" : ""}
              onClick={() => {
                onSelect(c.id);
                setOpen(false);
              }}
            >
              <span>
                <strong>{c.title}</strong>
                <small>
                  {c.requestCode
                    ? `${c.requestCode} · ${c.requestStatus}`
                    : c.draft
                      ? "Đang soạn phản ánh"
                      : (c.preview ??
                        c.messages.at(-1)?.text ??
                        "Chưa có tin nhắn")}
                </small>
              </span>
              <time dateTime={c.updatedAt}>{when(c.updatedAt)}</time>
              {c.unread > 0 && (
                <b aria-label={`${c.unread} tin chưa đọc`}>{c.unread}</b>
              )}
              <IconChevronRight size={16} />
            </button>
          ))}
          {!rooms.some(matches) && <p>Không tìm thấy cuộc trò chuyện.</p>}
        </div>
      )}
    </section>
  );
}
