import { useState } from "react";
import type { PlatformApproval, PlatformBooking, PlatformQuote } from "../../services/types";

const vnd = (n: number) => `${n.toLocaleString("vi-VN")}đ`;
const OUTCOME = {
  approved: "Bạn đã đồng ý.",
  rejected: "Bạn đã không đồng ý.",
  expired: "Yêu cầu này đã hết hạn trả lời.",
};

/** What the assistant asks to do in the resident's name: read it, then agree or not, once. */
export function ApprovalCard({ approval, busy, onDecide }: {
  approval: PlatformApproval;
  busy?: boolean;
  onDecide: (id: string, approve: boolean) => unknown;
}) {
  return (
    <section className="question-card" aria-label="Cần bạn đồng ý">
      <strong>Cần bạn đồng ý</strong>
      <p className="preserve">{approval.text}</p>
      {approval.items && (
        <ul className="approval-costs">
          {approval.items.map((item, index) => (
            <li key={index}>
              <span>{item.label}</span>
              <span>{vnd(item.amount)}</span>
            </li>
          ))}
          {approval.total !== undefined && (
            <li>
              <strong>Tổng cộng</strong>
              <strong>{vnd(approval.total)}</strong>
            </li>
          )}
        </ul>
      )}
      {approval.status === "pending" ? (
        <div className="button-row">
          <button className="primary-button" disabled={busy} onClick={() => onDecide(approval.id, true)}>
            Đồng ý
          </button>
          <button className="secondary-button" disabled={busy} onClick={() => onDecide(approval.id, false)}>
            Không đồng ý
          </button>
        </div>
      ) : (
        <p role="status">{OUTCOME[approval.status]}</p>
      )}
    </section>
  );
}

/** Yes at once, or no with what is wrong: a refusal goes only with a reason someone can act on. */
function YesOrReason({ id, yes, no, ask, busy, onAnswer }: {
  id: string;
  yes: string;
  no: string;
  ask: string;
  busy?: boolean;
  onAnswer: (accepted: boolean, reason?: string) => unknown;
}) {
  const [refusing, setRefusing] = useState(false);
  const [reason, setReason] = useState("");
  return refusing ? (
    <form
      className="question-item"
      onSubmit={(event) => {
        event.preventDefault();
        if (reason.trim().length >= 8) void onAnswer(false, reason.trim());
      }}
    >
      <label htmlFor={id}>{ask}</label>
      <input
        id={id}
        value={reason}
        minLength={8}
        maxLength={2000}
        required
        placeholder="Mô tả ngắn, ít nhất 8 ký tự…"
        onChange={(event) => setReason(event.target.value)}
      />
      <div className="button-row">
        <button type="button" className="secondary-button" onClick={() => setRefusing(false)}>
          Quay lại
        </button>
        <button type="submit" className="primary-button" disabled={busy || reason.trim().length < 8}>
          Gửi
        </button>
      </div>
    </form>
  ) : (
    <div className="button-row">
      <button className="primary-button" disabled={busy} onClick={() => onAnswer(true)}>
        {yes}
      </button>
      <button className="secondary-button" disabled={busy} onClick={() => setRefusing(true)}>
        {no}
      </button>
    </div>
  );
}

const QUOTE_OUTCOME = {
  approved: "Bạn đã đồng ý báo giá",
  rejected: "Bạn không đồng ý báo giá",
  expired: "Báo giá đã hết hạn",
};

/** The technician's quote as a bill. The resident's own tap decides, here and nowhere else in the chat. */
export function QuoteCard({ quote, busy, onDecide }: {
  quote: PlatformQuote;
  busy?: boolean;
  onDecide: (id: string, accepted: boolean, reason?: string) => unknown;
}) {
  return (
    <section className="question-card" aria-label="Báo giá sửa chữa">
      <strong>Báo giá sửa chữa</strong>
      <ul className="approval-costs">
        {quote.lines.map((line, index) => (
          <li key={index}>
            <span>
              {line.name} × {line.quantity} {line.unit}
            </span>
            <span>{vnd(line.amount)}</span>
          </li>
        ))}
        <li>
          <span>Tiền công</span>
          <span>{vnd(quote.laborCost)}</span>
        </li>
        <li>
          <strong>Tổng cộng</strong>
          <strong>{vnd(quote.total)}</strong>
        </li>
      </ul>
      {quote.warrantyMonths > 0 && <p>Bảo hành {quote.warrantyMonths} tháng</p>}
      {quote.status === "pending" ? (
        <YesOrReason
          id={`quote-reason-${quote.id}`}
          yes="Đồng ý báo giá"
          no="Không đồng ý"
          ask="Vì sao bạn không đồng ý?"
          busy={busy}
          onAnswer={(accepted, reason) => onDecide(quote.id, accepted, reason)}
        />
      ) : (
        <p role="status">{QUOTE_OUTCOME[quote.status]}</p>
      )}
    </section>
  );
}

const clock = (iso: string) => new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
const day = (iso: string) => new Date(iso).toLocaleDateString("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });

/** A booking the assistant offers. The place is taken by the resident's tap and by nothing else: it may cost money. */
export function BookingCard({ booking, busy, onConfirm }: {
  booking: PlatformBooking;
  busy?: boolean;
  onConfirm: (id: string) => unknown;
}) {
  return (
    <section className="question-card" aria-label="Đặt tiện ích">
      <strong>Đặt {booking.amenity}</strong>
      <ul className="approval-costs">
        <li>
          <span>Thời gian</span>
          <span>
            {clock(booking.startAt)} đến {clock(booking.endAt)}, {day(booking.startAt)}
          </span>
        </li>
        <li>
          <span>Khu vực</span>
          <span>{booking.area}</span>
        </li>
        <li>
          <span>Số người</span>
          <span>{booking.guests}</span>
        </li>
        <li>
          <strong>Phí</strong>
          <strong>{booking.total > 0 ? vnd(booking.total) : "Miễn phí"}</strong>
        </li>
      </ul>
      {booking.status === "pending" ? (
        <div className="button-row">
          <button type="button" className="primary-button" disabled={busy} onClick={() => onConfirm(booking.id)}>
            Xác nhận đặt chỗ
          </button>
        </div>
      ) : (
        <p role="status">
          {booking.status === "expired"
            ? "Thẻ đặt chỗ đã hết hạn. Bạn nhắn lại để được đặt lượt khác."
            : booking.bookingStatus === "pending_payment"
              ? "Đã giữ chỗ. Bạn thanh toán ở mục Tiện ích để hoàn tất."
              : "Bạn đã đặt chỗ."}
        </p>
      )}
    </section>
  );
}

/** The technician reported the result; the resident closes the request, or says what is still wrong. */
export function CompletionCard({ busy, onResolve }: {
  busy?: boolean;
  onResolve: (accepted: boolean, reason?: string) => unknown;
}) {
  return (
    <section className="question-card" aria-label="Xác nhận hoàn thành">
      <strong>Nhân viên đã gửi kết quả nghiệm thu. Bạn xác nhận hoàn thành chứ?</strong>
      <YesOrReason
        id="completion-reason"
        yes="Xác nhận hoàn thành"
        no="Chưa đạt"
        ask="Điều gì chưa đạt?"
        busy={busy}
        onAnswer={onResolve}
      />
    </section>
  );
}
