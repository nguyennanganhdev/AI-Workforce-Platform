import { useState } from "react";

export type TicketView = {
  workflow_id: string;
  external_ticket_id: string;
  title: string;
  status_label: string;
  next_action: "none" | "submit_reply" | "submit_approval" | "confirm_close" | "watch_events" | "watch_request" | "resolve_attention";
  state: string;
  revision: number;
  messages: { message_id: string; speaker: string; content: string }[];
  reconnecting: boolean;
};

export function TicketTimeline({ ticket, onClose }: {
  ticket: TicketView;
  onClose: (workflowId: string, expectedRevision: number) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const messages = Array.from(new Map(ticket.messages.map((message) => [message.message_id, message])).values());
  async function close() {
    if (busy || ticket.next_action !== "confirm_close" || ticket.state === "closed") return;
    setBusy(true);
    setError(undefined);
    try { await onClose(ticket.workflow_id, ticket.revision); }
    catch { setError("Chưa đóng được yêu cầu. Hãy tải lại trạng thái và thử lại."); }
    finally { setBusy(false); }
  }
  return <section aria-label={`Yêu cầu ${ticket.external_ticket_id}`}>
    <h3>{ticket.title}</h3><p role="status">{ticket.status_label}</p>
    {ticket.reconnecting && <p>Đang kết nối lại…</p>}
    {error && <p role="alert">{error}</p>}
    <ol>{messages.map((message) => <li key={message.message_id}>
      <strong>{message.speaker}</strong><p>{message.content}</p>
    </li>)}</ol>
    {ticket.next_action === "confirm_close" && ticket.state !== "closed" &&
      <button disabled={busy} onClick={() => void close()}>Xác nhận hoàn tất</button>}
  </section>;
}
