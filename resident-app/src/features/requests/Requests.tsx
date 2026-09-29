import { useState } from "react";
import {
  IconArrowUpRight,
  IconCheck,
  IconChevronRight,
  IconClock,
  IconMapPin,
  IconSearch,
  IconTool,
} from "@tabler/icons-react";
import { statusLabels, type ResidentRequest } from "../../services/types";

export const dateLabel = (date: string) =>
  new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));

export function RequestCard({
  request,
  onOpen,
  compact = false,
}: {
  request: ResidentRequest;
  onOpen: (id: string) => void;
  compact?: boolean;
}) {
  return (
    <button
      className={`request-card ${compact ? "compact" : ""}`}
      onClick={() => onOpen(request.id)}
    >
      <span className="icon-tile blue">
        <IconTool size={21} stroke={1.7} />
      </span>
      <span className="request-copy">
        <span className="eyebrow">{request.id}</span>
        <strong>{request.title}</strong>
        <span className={`status ${request.status}`}>
          <i />
          {statusLabels[request.status]}
        </span>
      </span>
      <IconChevronRight size={18} className="muted shrink" />
    </button>
  );
}

export function Requests({
  requests,
  onOpen,
  onReport,
}: {
  requests: ResidentRequest[];
  onOpen: (id: string) => void;
  onReport: () => void;
}) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const filtered = requests.filter(
    (r) =>
      (filter === "all" ||
        (filter === "open"
          ? r.status !== "completed"
          : r.status === "completed")) &&
      `${r.id} ${r.title}`
        .toLocaleLowerCase("vi")
        .includes(search.toLocaleLowerCase("vi")),
  );
  return (
    <div className="page-section">
      <p className="page-description">
        Mọi phản ánh của bạn, được theo dõi ở một nơi.
      </p>
      <label className="search-field">
        <IconSearch size={20} />
        <input
          aria-label="Tìm yêu cầu"
          placeholder="Tìm theo nội dung hoặc mã yêu cầu"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      <div className="filter-row" aria-label="Lọc yêu cầu">
        {[
          ["all", "Tất cả"],
          ["open", "Đang mở"],
          ["completed", "Hoàn tất"],
        ].map(([value, label]) => (
          <button
            key={value}
            aria-pressed={filter === value}
            className={filter === value ? "selected" : ""}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="stack">
        {filtered.map((r) => (
          <RequestCard key={r.id} request={r} onOpen={onOpen} />
        ))}
      </div>
      {!filtered.length && (
        <div className="empty-state">
          <IconSearch size={32} />
          <h3>Chưa có yêu cầu phù hợp</h3>
          <p>Thử đổi bộ lọc hoặc bắt đầu một phản ánh mới.</p>
        </div>
      )}
      <button className="primary-button full" onClick={onReport}>
        Báo sự cố mới <IconArrowUpRight size={19} />
      </button>
    </div>
  );
}

export function RequestDetail({
  request,
  onResolve,
}: {
  request: ResidentRequest;
  onResolve: (accepted: boolean, reason?: string) => boolean;
}) {
  const [redo, setRedo] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <div className="page-section stack">
      <div className="detail-heading">
        <span className={`status ${request.status}`}>
          <i />
          {statusLabels[request.status]}
        </span>
        <span className="eyebrow">{request.id}</span>
        <h2>{request.title}</h2>
        <p>
          <IconMapPin size={16} />
          {request.location}
        </p>
      </div>
      <section className="white-card">
        <h3>Nội dung phản ánh</h3>
        <p className="preserve">{request.description}</p>
        {request.photos.length > 0 && (
          <div className="photo-grid">
            {request.photos.map((p) => (
              <a
                href={p.url}
                target="_blank"
                rel="noreferrer"
                key={p.id}
                aria-label={`Xem ảnh ${p.name}`}
              >
                <img src={p.url} alt={p.name} />
              </a>
            ))}
          </div>
        )}
        <span className="small muted">
          Đã gửi lúc {dateLabel(request.createdAt)}
        </span>
      </section>
      <section className="white-card">
        <h3>Tiến độ xử lý</h3>
        <ol className="timeline">
          {request.events.map((event, index) => (
            <li key={`${index}-${event.at}`}>
              <span
                className={`timeline-dot ${index === request.events.length - 1 ? "current" : ""}`}
              >
                {index === request.events.length - 1 ? (
                  <IconClock size={14} />
                ) : (
                  <IconCheck size={14} />
                )}
              </span>
              <div>
                <strong>{event.label}</strong>
                <time>{dateLabel(event.at)}</time>
                {event.note && <p>{event.note}</p>}
              </div>
            </li>
          ))}
        </ol>
      </section>
      {request.status === "confirmation" && (
        <section className="confirmation-card">
          <span className="icon-tile teal">
            <IconCheck size={23} />
          </span>
          <h3>Mọi thứ đã ổn rồi chứ?</h3>
          <p>Bạn kiểm tra kết quả và cho chúng mình biết nhé.</p>
          {redo ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (onResolve(false, reason)) setRedo(false);
              }}
            >
              <label className="field-label" htmlFor="redo-reason">
                Điều gì cần xử lý thêm?
              </label>
              <textarea
                id="redo-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                minLength={8}
                maxLength={2000}
                required
                placeholder="Mô tả vấn đề còn tồn tại…"
              />
              <div className="button-row">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setRedo(false)}
                >
                  Quay lại
                </button>
                <button className="primary-button" type="submit">
                  Gửi yêu cầu
                </button>
              </div>
            </form>
          ) : (
            <>
              <button
                className="primary-button full"
                onClick={() => onResolve(true)}
              >
                <IconCheck size={19} />
                Đã ổn, xác nhận hoàn tất
              </button>
              <button className="text-button" onClick={() => setRedo(true)}>
                Tôi cần được hỗ trợ thêm
              </button>
            </>
          )}
        </section>
      )}
      <p className="footnote">
        Dữ liệu trải nghiệm trên thiết bị của bạn. Chưa kết nối Ban quản lý.
      </p>
    </div>
  );
}
