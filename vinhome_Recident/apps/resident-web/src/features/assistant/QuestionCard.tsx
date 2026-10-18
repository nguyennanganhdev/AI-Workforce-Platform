import { useState } from "react";
import { answerText, questionItems } from "../../services/chat-turn";

const QUICK = ["Có", "Không", "Chưa rõ"];

/**
 * What management asks, inside the conversation: every question with its own answer, sent together
 * as one message. The resident may still just type a reply in the box below instead.
 */
export function QuestionCard({ question, busy, onAnswer }: {
  question: string;
  busy?: boolean;
  onAnswer: (text: string) => boolean | Promise<boolean>;
}) {
  const { lead, items } = questionItems(question);
  const [answers, setAnswers] = useState<string[]>(() => items.map(() => ""));
  const set = (index: number, value: string) =>
    setAnswers((old) => old.map((answer, i) => (i === index ? value : answer)));
  const ready = items.length === 1 ? !!answers[0]?.trim() : answers.some((answer) => answer.trim());
  return (
    <form
      className="question-card"
      aria-label="Ban quản lý cần bạn xác nhận"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready && !busy) void onAnswer(answerText(items, answers));
      }}
    >
      <strong>Ban quản lý cần bạn xác nhận</strong>
      {lead && <p>{lead}</p>}
      {items.map((item, index) => (
        <div className="question-item" key={item}>
          <label htmlFor={`question-${index}`}>
            {items.length > 1 ? `${index + 1}. ${item}` : item}
          </label>
          <div className="question-quick">
            {QUICK.map((choice) => (
              <button
                type="button"
                key={choice}
                aria-pressed={answers[index] === choice}
                onClick={() => set(index, choice)}
              >
                {choice}
              </button>
            ))}
          </div>
          <input
            id={`question-${index}`}
            value={answers[index]}
            maxLength={300}
            placeholder="Hoặc ghi rõ hơn…"
            onChange={(event) => set(index, event.target.value)}
          />
        </div>
      ))}
      <button type="submit" className="primary-button" disabled={busy || !ready}>
        {busy ? "Đang gửi…" : "Gửi câu trả lời"}
      </button>
    </form>
  );
}
