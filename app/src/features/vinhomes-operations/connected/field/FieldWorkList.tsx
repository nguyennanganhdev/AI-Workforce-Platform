import { useState } from "react";
import { IconChevronRight, IconClipboardCheck, IconMapPin } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { AFTER, STEPS, TABS, ended, placeOf, stateOf, stateText, stepOf, tabOf, type FieldOrder, type FieldTab, type FieldTicket } from "./model";

type Row = { ticket: FieldTicket; state: string; tab: FieldTab };
const EMPTY: Record<FieldTab, [string, string]> = {
  new: ["Không có việc mới", "Khi Ban quản lý giao việc, việc sẽ hiện ở đây."],
  doing: ["Bạn chưa có việc đang làm", "Nhận một việc ở mục Mới giao để bắt đầu."],
  waiting: ["Không có việc chờ xác nhận", "Việc đã gửi kết quả nằm ở đây cho tới khi cư dân xác nhận."],
  history: ["Chưa có việc đã hoàn tất", "Việc cư dân đã xác nhận sẽ được lưu ở đây."],
};
// A history short enough to read at a glance needs no search box.
const SEARCHABLE = 7;

function JobCard({ row, place, onOpen }: { row: Row; place: string; onOpen: () => void }) {
  const text = stateText(row.state);
  const step = stepOf(row.state);
  return (
    <button type="button" onClick={onOpen}
      className="flex w-full flex-col gap-2.5 rounded-xl border border-border bg-background p-4 text-left transition-transform active:scale-[0.99] focus-visible:border-ring focus-visible:outline-none">
      {["critical", "high"].includes(row.ticket.priority) && !ended(row.state) && (
        <Badge variant="destructive" className="w-fit">{row.ticket.priority === "critical" ? "Khẩn cấp" : "Ưu tiên cao"}</Badge>
      )}
      <span className="line-clamp-2 text-base font-semibold leading-snug text-foreground">{row.ticket.title}</span>
      <span className="flex items-center gap-1.5 text-sm text-muted-foreground"><IconMapPin className="size-4 shrink-0" stroke={1.75} />{place}</span>
      {row.tab === "doing" && (
        <span aria-hidden="true" className="flex gap-1">
          {STEPS.map((name, index) => <i key={name} className={cn("h-1 flex-1 rounded-full", index < step ? "bg-primary" : index === step ? "bg-primary/40" : "bg-border")} />)}
        </span>
      )}
      <span className="flex items-center justify-between gap-3 border-t border-border pt-2.5 text-sm">
        <span className="text-muted-foreground">{ended(row.state) ? AFTER[row.ticket.status]?.[0] || text.label : text.label}</span>
        <span className={cn("flex shrink-0 items-center gap-0.5 font-medium", text.next ? "text-primary" : "text-muted-foreground")}>
          {text.next || "Xem lại"}<IconChevronRight className="size-4" stroke={1.75} />
        </span>
      </span>
    </button>
  );
}

/**
 * "Việc của tôi": what was newly offered, what is being done, what waits for the resident, and the
 * history. It opens on the first of those that has something in it.
 */
export function FieldWorkList({ tickets, orders, buildings, history = false, onOpen }: {
  tickets: FieldTicket[]; orders: FieldOrder[]; buildings: { id: string; name: string }[]; history?: boolean; onOpen: (ticketId: string) => void;
}) {
  const [picked, setTab] = useState<FieldTab | "">(history ? "history" : "");
  const [query, setQuery] = useState("");
  const rows: Row[] = tickets.flatMap((ticket) => {
    const own = orders.filter((o) => o.ticket_id === ticket.id);
    if (!own.length) return [];
    // The order still being worked on speaks for the request; without one, the latest.
    const state = stateOf(own.find((o) => !ended(stateOf(o))) || own[0]);
    return [{ ticket, state, tab: tabOf(state, ticket.status) }];
  });
  const count = (tab: FieldTab) => rows.filter((r) => r.tab === tab).length;
  const tab = picked || TABS.map(([id]) => id).find((id) => id !== "history" && count(id)) || "new";
  const wanted = query.trim().toLocaleLowerCase("vi");
  const shown = rows.filter((r) => r.tab === tab && `${r.ticket.title} ${placeOf(r.ticket, buildings)}`.toLocaleLowerCase("vi").includes(wanted));
  return (
    <section aria-label="Việc của tôi" className="flex flex-col gap-4">
      <h1 className="pt-1 text-2xl font-semibold tracking-tight text-foreground">Việc của tôi</h1>
      <div role="tablist" aria-label="Nhóm công việc" className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 [scrollbar-width:none]">
        {TABS.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => { setTab(id); setQuery(""); }}
            className={cn("flex h-10 shrink-0 items-center gap-1 rounded-full border px-3 text-[13px] font-medium transition-colors",
              tab === id ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background text-foreground")}>
            {label}
            {id !== "history" && count(id) > 0 && <span className={cn("tabular-nums", tab === id ? "text-primary-foreground/80" : "text-muted-foreground")}>{count(id)}</span>}
          </button>
        ))}
      </div>
      {tab === "history" && count("history") >= SEARCHABLE && (
        <input type="search" aria-label="Tìm trong lịch sử" placeholder="Tìm theo nội dung hoặc vị trí" value={query} onChange={(e) => setQuery(e.target.value)}
          className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring" />
      )}
      <div role="tabpanel" className="flex flex-col gap-3">
        {shown.map((row) => <JobCard key={row.ticket.id} row={row} place={placeOf(row.ticket, buildings)} onOpen={() => onOpen(row.ticket.id)} />)}
        {!shown.length && (
          <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
            <IconClipboardCheck className="size-9 text-muted-foreground" stroke={1.25} />
            <h2 className="text-base font-semibold text-foreground">{wanted ? "Không tìm thấy việc phù hợp" : EMPTY[tab][0]}</h2>
            <p className="max-w-xs text-sm text-muted-foreground">{wanted ? "Thử từ khóa khác." : EMPTY[tab][1]}</p>
          </div>
        )}
      </div>
    </section>
  );
}
