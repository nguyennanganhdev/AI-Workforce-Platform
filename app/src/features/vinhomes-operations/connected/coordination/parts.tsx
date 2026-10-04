import { useEffect, useRef, useState, type ReactNode } from "react";
import { IconSend } from "@tabler/icons-react";
import { AbstractAvatar } from "@/components/agents/abstract-avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const clock = (iso: string) => new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
const LONG = 700;

/** One thing somebody said. An agent's analysis is long, so it opens folded. */
export function Said({ who, at, mine = false, agent = false, tone = "plain", footer, children }: {
  who: string; at: string; mine?: boolean; agent?: boolean; tone?: "plain" | "accent"; footer?: ReactNode; children: string;
}) {
  const [open, setOpen] = useState(false);
  const long = children.length > LONG;
  return (
    <article className={cn("flex gap-3", mine && "flex-row-reverse")}>
      {agent ? <AbstractAvatar name={who} seed={who} size={32} /> : (
        <span aria-hidden="true" className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
          {who.trim().charAt(0).toUpperCase()}
        </span>
      )}
      <div className={cn("flex min-w-0 max-w-[min(42rem,85%)] flex-col gap-1", mine && "items-end")}>
        <p className="flex items-baseline gap-2 text-xs text-muted-foreground">
          <strong className="font-medium text-foreground">{who}</strong>
          <time dateTime={at}>{clock(at)}</time>
        </p>
        <div className={cn("whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm leading-relaxed",
          mine ? "bg-primary text-primary-foreground" : tone === "accent" ? "border border-primary/20 bg-primary/5 text-foreground" : "bg-muted text-foreground")}>
          {long && !open ? `${children.slice(0, LONG).trimEnd()}…` : children}
        </div>
        {long && (
          <button type="button" className="text-xs font-medium text-primary hover:underline" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? "Thu gọn" : "Xem đầy đủ"}
          </button>
        )}
        {footer && <p className="text-xs text-muted-foreground">{footer}</p>}
      </div>
    </article>
  );
}

/** A step of the session nobody said: a line between the messages. */
export function Note({ at, children }: { at?: string; children: ReactNode }) {
  return (
    <p className="flex items-center gap-3 text-xs text-muted-foreground">
      <span aria-hidden="true" className="h-px flex-1 bg-border" />
      <span>{children}{at ? ` · ${clock(at)}` : ""}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-border" />
    </p>
  );
}

/** The scrolling conversation. It follows the newest message unless the reader scrolled up. */
export function Transcript({ label, count, children }: { label: string; count: number; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  useEffect(() => {
    if (pinned.current && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [count]);
  return (
    <div ref={box} role="log" aria-label={label} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-6"
      onScroll={(e) => { const el = e.currentTarget; pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}>
      {children}
    </div>
  );
}

/** Where management writes. Enter sends, Shift+Enter breaks the line; a failed send keeps the text. */
export function Composer({ agents, agentLabel, placeholder, disabled, hint, error, onSend }: {
  agents: { id: string; name: string }[]; agentLabel?: string; placeholder: string; disabled?: boolean; hint?: string; error?: string;
  onSend: (text: string, agentId: string) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const [agentId, setAgentId] = useState("");
  const [sending, setSending] = useState(false);
  async function send() {
    if (!text.trim() || sending || disabled) return;
    setSending(true);
    if (await onSend(text.trim(), agentId)) setText("");
    setSending(false);
  }
  return (
    <form className="border-t border-border bg-background px-4 py-3 md:px-6" onSubmit={(e) => { e.preventDefault(); void send(); }}>
      {error && <p role="alert" className="mb-2 text-sm text-destructive">{error}</p>}
      <div className="flex items-end gap-2 rounded-lg border border-input bg-background p-2 focus-within:border-ring">
        {(agentLabel || agents.length > 1) && (
          <select aria-label="@Nhắc agent" value={agentId} disabled={disabled} onChange={(e) => setAgentId(e.target.value)}
            className="h-9 max-w-44 shrink-0 rounded-md border border-input bg-background px-2 text-sm text-foreground">
            {agentLabel && <option value="">{agentLabel}</option>}
            {agents.map((a) => <option key={a.id} value={a.id}>@{a.name}</option>)}
          </select>
        )}
        <textarea aria-label="Nội dung" rows={1} value={text} maxLength={2000} disabled={disabled} placeholder={placeholder}
          className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-snug text-foreground outline-none placeholder:text-muted-foreground"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} />
        <Button type="submit" size="icon" aria-label="Gửi tin nhắn" disabled={disabled || sending || !text.trim()}><IconSend /></Button>
      </div>
      {hint && <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p>}
    </form>
  );
}
