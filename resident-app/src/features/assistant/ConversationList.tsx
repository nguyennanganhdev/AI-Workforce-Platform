import { useState } from "react";
import {
  IconPlus,
  IconMessageCircle,
  IconChevronRight,
  IconX,
} from "@tabler/icons-react";
import type { ResidentState } from "../../services/types";
import "./conversations.css";
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
  const rooms = [...(state.conversations ?? [])].sort((a, b) =>
    b.updatedAt.localeCompare(a.updatedAt),
  );
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
          {rooms
            .filter((c) =>
              `${c.title} ${c.requestId ?? ""}`
                .toLocaleLowerCase()
                .includes(search.toLocaleLowerCase()),
            )
            .map((c) => (
              <button
                key={c.id}
                className={
                  c.id === state.activeConversationId ? "selected" : ""
                }
                onClick={() => {
                  onSelect(c.id);
                  setOpen(false);
                }}
              >
                <span>
                  <strong>{c.title}</strong>
                  <small>
                    {c.requestId ??
                      (c.draft ? "Đang soạn phản ánh" : "Trao đổi với trợ lý")}
                  </small>
                </span>
                {c.unread > 0 && (
                  <b aria-label={`${c.unread} tin chưa đọc`}>{c.unread}</b>
                )}
                <IconChevronRight size={16} />
              </button>
            ))}
          {!rooms.some((c) =>
            `${c.title} ${c.requestId ?? ""}`
              .toLocaleLowerCase()
              .includes(search.toLocaleLowerCase()),
          ) && <p>Không tìm thấy cuộc trò chuyện.</p>}
        </div>
      )}
    </section>
  );
}
