import { IconCheck, IconChevronRight, IconHandStop, IconX } from "@tabler/icons-react";
import { statusLabels, type ResidentRequest } from "../../services/types";

/** Where a handed-over request stands, as five steps the resident can read at a glance. */
const STEPS = ["Đã tiếp nhận", "Đánh giá và điều phối", "Đang xử lý", "Chờ bạn xác nhận", "Hoàn tất"] as const;

const REACHED: Record<ResidentRequest["status"], number> = {
  received: 1,
  processing: 2,
  confirmation: 3,
  completed: 5,
  cancelled: 0,
};

const clock = (iso: string) => {
  const at = new Date(iso);
  return Number.isNaN(at.getTime())
    ? ""
    : at.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
};

/**
 * Pinned above the conversation of a request. `working`: management's assistant is answering now.
 * `needsYou`: a card in the chat waits for the resident (a quote, an agreement, a question, the result).
 */
export function RequestProgress({ request, working, needsYou, onOpen }: {
  request: ResidentRequest;
  working?: boolean;
  needsYou?: string;
  onOpen?: (id: string) => void;
}) {
  const cancelled = request.status === "cancelled";
  const reached = REACHED[request.status];
  const latest = request.events.at(-1);
  return (
    <section className={`request-progress ${cancelled ? "cancelled" : ""}`} aria-label="Tiến độ yêu cầu">
      <header>
        <div>
          <strong>{request.title}</strong>
          <span className={`status ${request.status}`}>
            <i />
            {statusLabels[request.status]}
          </span>
        </div>
        {onOpen && (
          <button type="button" className="request-progress-open" onClick={() => onOpen(request.id)}>
            Chi tiết <IconChevronRight size={15} aria-hidden="true" />
          </button>
        )}
      </header>
      {cancelled ? (
        <p className="request-progress-note"><IconX size={15} aria-hidden="true" /> Yêu cầu đã hủy.</p>
      ) : (
        <ol className="request-steps">
          {STEPS.map((label, index) => {
            const done = index < reached;
            const current = index === reached && reached < STEPS.length;
            return (
              <li key={label} className={done ? "done" : current ? "current" : ""} aria-current={current ? "step" : undefined}>
                <span className="request-step-dot">{done ? <IconCheck size={12} stroke={3} aria-hidden="true" /> : index + 1}</span>
                <span className="request-step-label">{label}</span>
              </li>
            );
          })}
        </ol>
      )}
      {needsYou && (
        <p className="request-progress-needs" role="status">
          <IconHandStop size={16} aria-hidden="true" /> Cần bạn: {needsYou}
        </p>
      )}
      {!needsYou && working && (
        <p className="request-progress-live" role="status">
          <i aria-hidden="true" /> Ban quản lý đang xử lý và sẽ trả lời ngay trong cuộc trò chuyện này.
        </p>
      )}
      {latest && (
        <p className="request-progress-note">
          <span>{latest.label}</span>
          {latest.note && <span> · {latest.note}</span>}
          {clock(latest.at) && <time dateTime={latest.at}> · {clock(latest.at)}</time>}
        </p>
      )}
    </section>
  );
}
