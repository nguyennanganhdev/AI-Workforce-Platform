import { useEffect, useRef, useState } from "react";
import { IconPlus, IconMessageCircle, IconChevronRight, IconX, IconTrash, IconRestore } from "@tabler/icons-react";
import type { ResidentState } from "../../services/types";
import "./conversations.css";

type Room = {id:string; title:string; updatedAt:string; preview?:string; unread?:number; requestStatus?:string};
function when(iso: string) {
  const date=new Date(iso);
  if (!iso || Number.isNaN(date.getTime())) return "";
  return date.toDateString()===new Date().toDateString() ? date.toLocaleTimeString("vi-VN",{hour:"2-digit",minute:"2-digit"}) : date.toLocaleDateString("vi-VN",{day:"2-digit",month:"2-digit"});
}
export function ConversationList({state,compact=false,onSelect,onNew,onDelete,onRestore,archived=[],busy=false}: {
  state: ResidentState; compact?: boolean; onSelect: (id:string) => void; onNew: () => void;
  onDelete?: (id:string) => Promise<boolean>; onRestore?: (id:string) => Promise<boolean>; archived?: Room[]; busy?: boolean;
}) {
  const [open,setOpen]=useState(false);
  const [search,setSearch]=useState("");
  const [trash,setTrash]=useState(false);
  const [deleting,setDeleting]=useState<Room | null>(null);
  const [notice,setNotice]=useState("");
  const dialog=useRef<HTMLDialogElement>(null);
  const container=useRef<HTMLElement>(null);
  const trigger=useRef<HTMLButtonElement>(null);
  useEffect(() => {if (deleting) dialog.current?.showModal(); else dialog.current?.close();},[deleting]);
  useEffect(() => {
    if (!open) return;
    const outside=(e:PointerEvent) => {if (!deleting && !container.current?.contains(e.target as Node)) setOpen(false);};
    const escape=(e:KeyboardEvent) => {if (e.key==="Escape" && !deleting) {setOpen(false);trigger.current?.focus();}};
    document.addEventListener("pointerdown",outside);document.addEventListener("keydown",escape);
    return () => {document.removeEventListener("pointerdown",outside);document.removeEventListener("keydown",escape);};
  },[open,deleting]);
  const rooms=[...(state.conversations ?? [])].filter(c => !c.archived && (c.id===state.activeConversationId || c.requestId || c.draft || c.preview || c.messages.length)).sort((a,b) => b.updatedAt.localeCompare(a.updatedAt));
  const unread=rooms.reduce((sum,c) => sum+c.unread,0);
  const matches=(c:Room) => `${c.title} ${c.preview ?? ""}`.toLocaleLowerCase().includes(search.toLocaleLowerCase());
  const visible: Room[]=(trash ? archived : rooms).filter(matches);
  return <section ref={container} className={`resident-rooms${compact ? " resident-rooms-compact" : ""}`} aria-label="Hội thoại của bạn">
    <div className="resident-rooms-bar">
      <button ref={trigger} onClick={() => setOpen(v => !v)} aria-expanded={open} aria-controls="resident-conversation-list" aria-label={`Hội thoại${unread ? `, ${unread} tin chưa đọc` : ""}`} title="Hội thoại">
        <IconMessageCircle size={19} aria-hidden="true" />{!compact && "Hội thoại"}{unread>0 && <b>{unread>99 ? "99+" : unread}</b>}
      </button>
      <button disabled={busy} onClick={() => {onNew();setOpen(false);}} aria-label="Chat mới" title="Chat mới"><IconPlus size={18} aria-hidden="true" />{!compact && "Chat mới"}</button>
    </div>
    {open && <div id="resident-conversation-list" className="resident-rooms-list">
      <div className="resident-rooms-search"><input autoFocus aria-label="Tìm hội thoại" placeholder="Tìm hội thoại" value={search} onChange={e => setSearch(e.target.value)} /><button aria-label="Đóng danh sách hội thoại" onClick={() => {setOpen(false);trigger.current?.focus();}}><IconX size={18} /></button></div>
      {!!onDelete && <div className="notification-filters"><button aria-pressed={!trash} onClick={() => setTrash(false)}>Hội thoại</button><button aria-pressed={trash} onClick={() => setTrash(true)}>Đã xóa ({archived.length})</button></div>}
      {notice && <p role="status" className="conversation-notice">{notice}</p>}
      {visible.map(c => <div key={c.id} className={`conversation-row${c.id===state.activeConversationId ? " selected" : ""}`}>
        <button className="conversation-open" disabled={busy} onClick={async () => {if (trash && !await onRestore?.(c.id)) return;onSelect(c.id);setOpen(false);}}>
          <span><strong>{c.title}</strong><small>{c.requestStatus || c.preview || "Cuộc trò chuyện của bạn"}</small></span>
          <time dateTime={c.updatedAt}>{when(c.updatedAt)}</time>
          {!!c.unread && <b aria-label={`${c.unread} tin chưa đọc`}>{c.unread>99 ? "99+" : c.unread}</b>}
          <IconChevronRight size={16} aria-hidden="true" />
        </button>
        {trash ? <button className="conversation-action" disabled={busy} aria-label={`Khôi phục ${c.title}`} onClick={async () => {if (await onRestore?.(c.id)) setNotice("Đã khôi phục hội thoại.");}}><IconRestore size={18} aria-hidden="true" /></button> :
          onDelete && <button className="conversation-action" disabled={busy} aria-label={`Xóa ${c.title}`} onClick={() => setDeleting(c)}><IconTrash size={18} aria-hidden="true" /></button>}
      </div>)}
      {!visible.length && <p className="conversation-empty">{trash ? "Chưa có hội thoại đã xóa." : "Không tìm thấy cuộc trò chuyện."}</p>}
    </div>}
    <dialog ref={dialog} className="reset-dialog conversation-delete-dialog" aria-labelledby="delete-conversation-title" onCancel={() => setDeleting(null)} onClose={() => setDeleting(null)}>
      <h2 id="delete-conversation-title">Xóa hội thoại khỏi danh sách?</h2><p>“{deleting?.title}” sẽ chuyển vào mục Đã xóa và có thể khôi phục. Yêu cầu và tiến độ xử lý liên quan vẫn được giữ lại. Bản nháp đang soạn sẽ bị bỏ.</p>
      <div className="button-row"><button autoFocus className="secondary-button" onClick={() => setDeleting(null)}>Giữ hội thoại</button><button className="primary-button" disabled={busy} onClick={async () => {if (deleting && await onDelete?.(deleting.id)) {setDeleting(null);setNotice("Đã chuyển hội thoại vào mục Đã xóa.");}}}>Xóa hội thoại</button></div>
    </dialog>
  </section>;
}
