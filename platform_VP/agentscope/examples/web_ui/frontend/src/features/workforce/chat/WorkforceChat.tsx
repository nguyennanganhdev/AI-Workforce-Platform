import { useState, type ReactNode } from "react";

export type ChatMember = { agent_id: string; name: string; version_id: string };
export type ChatMessage = { message_id: string; speaker: string; content: string };
export type ChatQuote = { id: string; label: string; amount_minor: number; currency: string; expired: boolean };
export type ChatView = {
  title: string;
  mode: "group" | "direct";
  messages: ChatMessage[];
  members: ChatMember[];
  available_members: ChatMember[];
  quotes: ChatQuote[];
  pending_question?: string;
  loading: boolean;
  status_label: string;
  error?: string;
  can_cancel: boolean;
  can_resume: boolean;
};
type Props = {
  view: ChatView;
  approvalCard?: ReactNode;
  onSend: (command: { client_message_id: string; content: string; target_agent_id?: string }) => Promise<void>;
  onAddMember: (agentId: string) => Promise<void>;
  onOpenDirect: (agentId: string) => Promise<void>;
  onSelectQuote: (quoteId: string) => Promise<void>;
  onCancel: () => Promise<void>;
  onResume: () => Promise<void>;
};

/** Controlled feature: the host supplies real API transport and scoped data. */
export function WorkforceChat(props: Props) {
  const { view } = props;
  const [content, setContent] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [retryCommand, setRetryCommand] = useState<Parameters<Props["onSend"]>[0]>();
  const messages = Array.from(new Map(view.messages.map((message) => [message.message_id, message])).values());

  async function act(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try { await action(); } catch { setError("Chưa thể hoàn tất thao tác. Hãy thử lại."); }
    finally { setBusy(false); }
  }

  async function send() {
    if (!content.trim()) return;
    // Preserve idempotency ID after network loss, but use a new ID after edits.
    const command = retryCommand ?? {
      client_message_id: crypto.randomUUID(), content,
      ...(target ? { target_agent_id: target } : {}),
    };
    setRetryCommand(command);
    await act(async () => {
      await props.onSend(command);
      setContent("");
      setRetryCommand(undefined);
    });
  }

  return <section aria-label={view.mode === "direct" ? "Chat riêng" : "Chat nhóm"}>
    <header><h2>{view.title}</h2><p role="status">{view.status_label}</p></header>
    {(view.error || error) && <p role="alert">{view.error || error}</p>}
    {view.loading && <p>Đang tải hội thoại…</p>}
    <ul aria-label="Thành viên">{view.members.map((member) => <li key={member.agent_id}>
      {member.name} <button disabled={busy} onClick={() => void act(() => props.onOpenDirect(member.agent_id))}>Chat riêng</button>
    </li>)}</ul>
    <ol aria-label="Tin nhắn">{messages.map((message) => <li key={message.message_id}>
      <strong>{message.speaker}</strong><p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
    </li>)}</ol>
    {view.pending_question && <aside aria-label="Câu hỏi đang chờ">{view.pending_question}</aside>}
    <ul aria-label="Phương án">{view.quotes.map((quote) => <li key={quote.id}>
      {quote.label}: {new Intl.NumberFormat("vi-VN", { style: "currency", currency: quote.currency }).format(quote.amount_minor / (10 ** (new Intl.NumberFormat("vi-VN", { style: "currency", currency: quote.currency }).resolvedOptions().maximumFractionDigits ?? 0)))}
      {quote.expired ? <span> — Báo giá hết hạn</span> : <button disabled={busy} onClick={() => void act(() => props.onSelectQuote(quote.id))}>Chọn</button>}
    </li>)}</ul>
    {props.approvalCard}
    <form onSubmit={(event) => { event.preventDefault(); void send(); }}>
      <label>Gửi tới <select value={target} disabled={busy || view.mode === "direct"} onChange={(event) => { setTarget(event.target.value); setRetryCommand(undefined); }}>
        <option value="">Người đang hỏi / điều phối</option>
        {view.members.map((member) => <option key={member.agent_id} value={member.agent_id}>@{member.name}</option>)}
      </select></label>
      <label>Tin nhắn <textarea value={content} disabled={busy} onChange={(event) => { setContent(event.target.value); setRetryCommand(undefined); }} /></label>
      <button disabled={busy || view.loading || !content.trim()}>Gửi</button>
    </form>
    <div>{view.available_members.filter((candidate) => !view.members.some((member) => member.agent_id === candidate.agent_id)).map((candidate) =>
      <button key={candidate.agent_id} disabled={busy} onClick={() => void act(() => props.onAddMember(candidate.agent_id))}>Thêm {candidate.name}</button>)}
    {view.can_cancel && <button disabled={busy} onClick={() => void act(props.onCancel)}>Dừng lượt xử lý</button>}
    {view.can_resume && <button disabled={busy} onClick={() => void act(props.onResume)}>Tiếp tục</button>}</div>
  </section>;
}
