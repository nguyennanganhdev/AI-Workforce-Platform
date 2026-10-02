import { useState } from "react";

export type Inquiry = {
  id: string;
  status: string;
  state_version: number;
  created_at: string;
  question: string;
  resident: string;
};

/**
 * Resident questions the Reception agent had no source for. Each is a coordination session in
 * the management group chat; the answer typed here is relayed to the resident's conversation.
 */
export function Inquiries({
  items,
  disabled,
  onAnswer,
}: {
  items: Inquiry[];
  disabled: boolean;
  onAnswer: (inquiry: Inquiry, text: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  if (items.length === 0) return null;
  return (
    <section className="ws-card">
      <h2>Câu hỏi của cư dân chờ trả lời ({items.length})</h2>
      <p>
        Lễ tân chưa có nguồn để trả lời các câu này. Câu trả lời của Ban quản
        lý được gửi thẳng vào cuộc trò chuyện của cư dân.
      </p>
      {items.map((inquiry) => {
        const text = drafts[inquiry.id] ?? "";
        return (
          <article className="live-order" key={inquiry.id}>
            <small>
              {inquiry.resident} ·{" "}
              {new Date(inquiry.created_at).toLocaleString("vi-VN")}
            </small>
            <p>
              <strong>{inquiry.question}</strong>
            </p>
            <label>
              Trả lời cư dân
              <textarea
                value={text}
                maxLength={4000}
                onChange={(e) =>
                  setDrafts((all) => ({ ...all, [inquiry.id]: e.target.value }))
                }
              />
            </label>
            <div className="live-actions">
              <button
                disabled={disabled || !text.trim()}
                onClick={() => onAnswer(inquiry, text.trim())}
              >
                Gửi trả lời
              </button>
            </div>
          </article>
        );
      })}
    </section>
  );
}
