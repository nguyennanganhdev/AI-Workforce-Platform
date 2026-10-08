import { useEffect, useRef, useState, type ReactNode } from "react";
import { IconFile, IconPaperclip, IconSend, IconX } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Streamdown } from "streamdown";
import { Bot } from "lucide-react";
import { OpsSelect } from "../ui";
import { cn } from "@/lib/utils";

const clock = (iso: string) => new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
const LONG = 420;
const size = (bytes: number) => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

/** What is attached to a message: a photo is shown, any other file is a link that downloads it. */
export type SaidFile = { id: string; name: string; bytes: number; href: string; image?: string };
function Files({ files }: { files: SaidFile[] }) {
  return (
    <ul aria-label="Tệp đính kèm" className="flex flex-wrap gap-2">
      {files.map((file) => (
        <li key={file.id}>
          {file.image ? (
            <a href={file.image} target="_blank" rel="noreferrer" className="block">
              <img src={file.image} alt={file.name} loading="lazy" className="max-h-48 max-w-full rounded-md border border-border object-contain" />
            </a>
          ) : (
            <a href={file.href} download={file.name} className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground hover:bg-muted">
              <IconFile className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 truncate">{file.name}</span>
              <span className="shrink-0 text-xs text-muted-foreground">{size(file.bytes)}</span>
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

/** One thing somebody said. An agent's analysis is long, so it opens folded. */
export function Said({ who, at, mine = false, agent = false, tone = "plain", footer, files, children }: {
  who: string; at: string; mine?: boolean; agent?: boolean; tone?: "plain" | "accent"; footer?: ReactNode; files?: SaidFile[]; children: string;
}) {
  const [open, setOpen] = useState(false);
  const long = children.length > LONG;
  return (
    <article className={cn("coord-message ops-message", mine && "ops-message-mine")} data-agent={agent || undefined}>
      <span className={agent ? "ops-agent-avatar" : "ops-person-avatar"} aria-hidden="true">{agent ? <Bot size={16} /> : who.split(" ").map(word => word[0]).slice(-2).join("")}</span>
      <div className="ops-message-content">
        <p className="ops-message-author"><strong>{who}</strong><time dateTime={at}>{clock(at)}</time></p>
        {!!children && <div className="ops-message-bubble">{agent ? <Streamdown>{long && !open ? `${children.slice(0, LONG).trimEnd()}…` : children}</Streamdown> : <p>{long && !open ? `${children.slice(0, LONG).trimEnd()}…` : children}</p>}</div>}
        {!!files?.length && <Files files={files} />}
        {long && <button type="button" className="ops-text-action" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Thu gọn" : "Xem đầy đủ"}</button>}
        {footer && <p className="ops-message-footer">{footer}</p>}
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
    <div ref={box} role="log" aria-label={label} className="coord-transcript min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6"
      onScroll={(e) => { const el = e.currentTarget; pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}>
      <div className="mx-auto max-w-3xl space-y-7">{children}</div>
    </div>
  );
}

/**
 * Where management writes. Enter sends, Shift+Enter breaks the line; a failed send keeps the text and the files.
 * With `attach`, photos and text files can go on the message: `accept` is what the file dialog offers,
 * `refusal` says why a choice cannot be sent, and `withText` is for a place where files alone say nothing.
 */
export function Composer({ agents, agentLabel, placeholder, disabled, hint, error, attach, onSend }: {
  agents: { id: string; name: string }[]; agentLabel?: string; placeholder: string; disabled?: boolean; hint?: string; error?: string;
  attach?: { accept: string; refusal: (files: File[]) => string | null; withText?: boolean };
  onSend: (text: string, agentId: string, files: File[]) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const [agentId, setAgentId] = useState("");
  const [sending, setSending] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [refused, setRefused] = useState("");
  const picker = useRef<HTMLInputElement>(null);
  const sendable = !!text.trim() || (!!files.length && !attach?.withText);
  async function send() {
    if (!sendable || sending || disabled) return;
    setSending(true);
    try { if (await onSend(text.trim(), agentId, files)) { setText(""); setFiles([]); } }
    finally { setSending(false); }
  }
  function pick(picked: File[]) {
    const next = [...files, ...picked];
    const refusal = attach?.refusal(next) ?? null;
    setRefused(refusal ?? "");
    if (!refusal) setFiles(next);
  }
  return (
    <form className="coord-composer bg-background px-4 pb-4 pt-2 md:px-6" onSubmit={(e) => { e.preventDefault(); void send(); }}>
      <div className="mx-auto max-w-3xl">
      {(refused || error) && <p role="alert" className="mb-2 text-sm text-destructive">{refused || error}</p>}
      {!!files.length && (
        <ul aria-label="Tệp sẽ gửi" className="mb-2 flex flex-wrap gap-2">
          {files.map((file, index) => (
            <li key={`${file.name}:${index}`} className="flex items-center gap-1.5 rounded-md border border-border bg-muted px-2 py-1 text-xs text-foreground">
              <span className="max-w-48 truncate">{file.name}</span>
              <span className="text-muted-foreground">{size(file.size)}</span>
              <button type="button" aria-label={`Bỏ ${file.name}`} disabled={sending} className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                onClick={() => { setFiles(files.filter((_, i) => i !== index)); setRefused(""); }}><IconX className="size-3.5" /></button>
            </li>
          ))}
        </ul>
      )}
      <div className="coord-composer-box flex flex-wrap items-center gap-1 rounded-2xl border border-input bg-background p-2 shadow-sm focus-within:border-ring">
        {attach && (
          <>
            <input ref={picker} type="file" multiple hidden accept={attach.accept} aria-label="Chọn ảnh hoặc tệp"
              onChange={(e) => { pick([...(e.target.files ?? [])]); e.target.value = ""; }} />
            <Button type="button" size="icon" variant="ghost" aria-label="Đính kèm ảnh hoặc tệp" disabled={disabled || sending} onClick={() => picker.current?.click()}><IconPaperclip /></Button>
          </>
        )}
        {(agentLabel || agents.length > 1) && (
          <OpsSelect label="@Nhắc agent" value={agentId || (!agentLabel ? agents[0]?.id || "" : "auto")} disabled={disabled}
            onValueChange={value => setAgentId(value === "auto" ? "" : value)} options={[...(agentLabel ? [{ value: "auto", label: agentLabel }] : []), ...agents.map(agent => ({ value: agent.id, label: `@${agent.name}` }))]}
            placeholder={agentLabel || "Chọn agent"} />
        )}
        <Textarea aria-label="Nội dung" rows={1} value={text} maxLength={2000} disabled={disabled} placeholder={placeholder}
          className="coord-compose-text max-h-40 min-h-12 w-full resize-none bg-transparent px-2 py-2 text-[15px] leading-snug text-foreground outline-none placeholder:text-muted-foreground"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} />
        <Button type="submit" size="icon" aria-label="Gửi tin nhắn" disabled={disabled || sending || !sendable}><IconSend /></Button>
      </div>
      {hint && <p role="status" className="mt-1.5 px-2 text-xs text-muted-foreground">{hint}</p>}
      </div>
    </form>
  );
}
