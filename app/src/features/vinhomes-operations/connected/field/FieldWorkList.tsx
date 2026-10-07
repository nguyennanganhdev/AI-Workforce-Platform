import { useState } from "react";
import { IconChevronRight, IconClipboardCheck, IconMapPin } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { AFTER, STEPS, TABS, ended, placeOf, stateOf, stateText, stepOf, tabOf, type FieldOrder, type FieldTab, type FieldTicket } from "./model";

type Row = { ticket: FieldTicket; order: FieldOrder; state: string; tab: FieldTab };
const EMPTY: Record<FieldTab, [string, string]> = {
  new: ["Hàng đợi đang trống", "Việc mới giao và việc đã nhận chờ bắt đầu sẽ hiện ở đây."],
  doing: ["Bạn chưa có việc đang làm", "Mở Hàng đợi, nhận việc rồi bắt đầu di chuyển."],
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
      className="flex min-w-0 w-full flex-col gap-2.5 rounded-xl border border-border bg-background p-4 text-left transition-colors active:bg-muted focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
      {["critical", "high"].includes(row.ticket.priority) && !ended(row.state) && (
        <Badge variant="destructive" className="w-fit">{row.ticket.priority === "critical" ? "Khẩn cấp" : "Ưu tiên cao"}</Badge>
      )}
      <span className="line-clamp-2 text-base font-semibold leading-snug text-foreground">{row.ticket.title}</span>
      {row.order.description && row.order.description !== row.ticket.description && <span className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">{row.order.description}</span>}
      <span className="flex items-start gap-1.5 text-sm text-muted-foreground"><IconMapPin aria-hidden="true" className="mt-0.5 size-4 shrink-0" stroke={1.75} /><span className="min-w-0 break-words">{place}</span></span>
      {row.tab === "doing" && (
        <span aria-hidden="true" className="flex gap-1">
          {STEPS.map((name, index) => <i key={name} className={cn("h-1 flex-1 rounded-full", index < step ? "bg-primary" : index === step ? "bg-primary/40" : "bg-border")} />)}
        </span>
      )}
      <span className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2.5 text-sm">
        <span className="text-muted-foreground">{row.state === "completed" ? AFTER[row.ticket.status]?.[0] || text.label : text.label}</span>
        <span className={cn("flex shrink-0 items-center gap-0.5 font-medium", text.next ? "text-primary" : "text-muted-foreground")}>
          {row.state === "accepted" ? "Xem việc" : text.next || "Xem lại"}<IconChevronRight aria-hidden="true" className="size-4" stroke={1.75} />
        </span>
      </span>
    </button>
  );
}

/**
 * "Việc của tôi": what was newly offered, what is being done, what waits for the resident, and the
 * history. The current work stays first; incoming work goes to the queue.
 */
export function FieldWorkList({ tickets, orders, buildings, history = false, onOpen }: {
  tickets: FieldTicket[]; orders: FieldOrder[]; buildings: { id: string; name: string }[]; history?: boolean; onOpen: (ticketId: string, orderId: string) => void;
}) {
  const [picked, setTab] = useState<FieldTab | "">(history ? "history" : "");
  const [query, setQuery] = useState("");
  const rows: Row[] = tickets.flatMap((ticket) => {
    const own = orders.filter((o) => o.ticket_id === ticket.id);
    return own.map((order) => {
      const state = stateOf(order);
      return { ticket, order, state, tab: tabOf(state, ticket.status) };
    });
  });
  const count = (tab: FieldTab) => rows.filter((r) => r.tab === tab).length;
  const tab = picked || TABS.map(([id]) => id).find((id) => id !== "history" && count(id)) || "new";
  const wanted = query.trim().toLocaleLowerCase("vi");
  const shown = rows.filter((r) => r.tab === tab && `${r.ticket.title} ${r.order.description} ${placeOf(r.ticket, buildings)}`.toLocaleLowerCase("vi").includes(wanted));
  return (
    <section aria-label="Việc của tôi" className="flex min-w-0 flex-col gap-4">
      <header><h1 className="pt-1 text-2xl font-semibold tracking-tight text-foreground">Việc của tôi</h1>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{count("doing") ? `Bạn đang xử lý ${count("doing")} việc. ${count("new") ? `${count("new")} việc trong hàng đợi.` : "Hàng đợi đang trống."}` : "Nhận và xử lý từng việc trong hàng đợi."}</p>
      </header>
      <Tabs value={tab} onValueChange={(value) => { setTab(value as FieldTab); setQuery(""); }} className="gap-4">
      <TabsList aria-label="Nhóm công việc" className="grid h-auto! w-full grid-cols-2 gap-2 bg-transparent p-0 sm:grid-cols-4">
        {TABS.map(([id, label]) => (
          <TabsTrigger key={id} value={id}
            className={cn("min-h-[44px] h-auto! min-w-0 gap-1.5 rounded-lg border px-2 py-2 text-sm font-medium transition-colors",
              tab === id ? "border-primary bg-primary! text-primary-foreground!" : "border-border bg-background text-foreground")}>
            {label}
            {count(id) > 0 && <span className={cn("tabular-nums", tab === id ? "text-primary-foreground/80" : "text-muted-foreground")}>{count(id)}</span>}
          </TabsTrigger>
        ))}
      </TabsList>
      {tab === "history" && count("history") >= SEARCHABLE && (
        <input type="search" aria-label="Tìm trong lịch sử" placeholder="Tìm theo nội dung hoặc vị trí" value={query} onChange={(e) => setQuery(e.target.value)}
          className="h-[44px] w-full rounded-lg border border-input bg-background px-3 text-base text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring" />
      )}
      <TabsContent value={tab} className="flex flex-col gap-3">
        {tab === "new" && count("doing") > 0 && <p className="rounded-lg border border-border bg-background p-3 text-sm leading-relaxed text-muted-foreground">Bạn có thể nhận việc mới vào hàng đợi. Hoàn tất việc đang làm trước khi bắt đầu việc tiếp theo.</p>}
        {shown.map((row) => <JobCard key={row.order.id} row={row} place={placeOf(row.ticket, buildings)} onOpen={() => onOpen(row.ticket.id, row.order.id)} />)}
        {!shown.length && (
          <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
            <IconClipboardCheck aria-hidden="true" className="size-9 text-muted-foreground" stroke={1.25} />
            <h2 className="text-base font-semibold text-foreground">{wanted ? "Không tìm thấy việc phù hợp" : EMPTY[tab][0]}</h2>
            <p className="max-w-xs text-sm text-muted-foreground">{wanted ? "Thử từ khóa khác." : EMPTY[tab][1]}</p>
          </div>
        )}
      </TabsContent>
      </Tabs>
    </section>
  );
}
