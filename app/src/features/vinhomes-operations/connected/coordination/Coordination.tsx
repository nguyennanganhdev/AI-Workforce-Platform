import { PageToolbar } from "../PageToolbar";
import { useEffect, useRef, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { IconBuilding, IconClock, IconDroplet, IconLayoutColumns, IconList, IconSearch, IconShield, IconSnowflake, IconTool, IconBolt } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { roomQueryOptions, roomSessionsQueryOptions, roomsQueryOptions, type RoomSession } from "@/lib/rooms/queries";
import { StatusBadge } from "../ui";
import { dueText, lifecycleStep, LIFECYCLE, sessionState, stateTone } from "./model";
import { requestCatalogQueryOptions, requestPlace, requestsQueryOptions, type RequestCatalog, type RequestTicket } from "./request-data";
import { SessionThread } from "./SessionThread";
import "./requests.css";

type Entry = { ticket: RequestTicket; session: RoomSession; roomId: string; hasSession: boolean };
function categoryIcon(title: string) {
  if (/nước|vòi|bồn|rò/i.test(title)) return IconDroplet;
  if (/điện|đèn|nóng/i.test(title)) return IconBolt;
  if (/điều hòa|điều hoà/i.test(title)) return IconSnowflake;
  if (/an ninh|xe|camera/i.test(title)) return IconShield;
  return IconTool;
}
function RequestRow({ entry, catalog, onOpen, card = false }: { entry: Entry; catalog?: RequestCatalog; onOpen: () => void; card?: boolean }) {
  const Icon = categoryIcon(entry.ticket.title), due = dueText(entry.ticket.resolution_due_at);
  const state = sessionState(entry.session), place = requestPlace(entry.ticket, catalog);
  return <button type="button" className={`ops-request-row${card ? " ops-request-card" : ""}`} onClick={onOpen}>
    <span className="ops-request-icon" aria-hidden="true"><Icon size={20} stroke={1.75} /></span>
    <span className="ops-request-identity"><strong>{entry.ticket.title}</strong>{place && <span>{place}</span>}</span>
    <StatusBadge tone={stateTone(entry.session)}>{state.label}</StatusBadge>
    {due && <span className={`ops-request-due tone-${due.tone}`}><IconClock size={16} stroke={1.75} />{due.label}</span>}
  </button>;
}

/** One request object, with a list and lifecycle board. Opening it gives the conversation the full page. */
export function Coordination({ userId, tickets: suppliedTickets, catalog: suppliedCatalog }: { userId: string; tickets?: RequestTicket[]; catalog?: RequestCatalog }) {
  const listed = useQuery(roomsQueryOptions());
  const rooms = listed.data?.items || [];
  const sessionLists = useQueries({ queries: rooms.map(room => roomSessionsQueryOptions(room.id)) });
  const tickets = useQuery({ ...requestsQueryOptions(), enabled: suppliedTickets === undefined });
  const catalog = useQuery({ ...requestCatalogQueryOptions(), enabled: suppliedCatalog === undefined });
  const cat = suppliedCatalog ?? catalog.data;
  const [selected, select] = useState(() => new URLSearchParams(location.search).get("session") || new URLSearchParams(location.search).get("ticket") || "");
  const [view, setView] = useState<"list" | "board">("list");
  const [finished, setFinished] = useState(false);
  const [building, setBuilding] = useState("all"), [category, setCategory] = useState("all"), [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string[]>([]);
  const list = useRef<HTMLDivElement>(null);
  const sessions = sessionLists.flatMap((result, i) => (result.data || []).map(session => ({ session, roomId: rooms[i].id })));
  const sourceTickets = suppliedTickets ?? tickets.data ?? [];
  const known = new Set(sourceTickets.map(ticket => ticket.id));
  const entries: Entry[] = sourceTickets.map(ticket => {
    const found = sessions.find(item => item.session.ticket_id === ticket.id);
    return { ticket, roomId: found?.roomId || "", hasSession: !!found, session: found?.session || {
      id: ticket.id, ticket_id: ticket.id, ticket_code: ticket.code, ticket_title: ticket.title,
      status: ticket.status === "cancelled" ? "cancelled" : ticket.status === "closed" ? "completed" : "queued", ticket_status: ticket.status,
      plan_status: null, manual: true, created_at: ticket.created_at || ticket.updated_at, updated_at: ticket.updated_at,
    } };
  });
  // A room may be readable before the ticket catalog has refreshed; keep its authorized sessions visible.
  for (const item of sessions) if (!known.has(item.session.ticket_id)) entries.push({ ...item, hasSession: true, ticket: {
    id: item.session.ticket_id, code: item.session.ticket_code, title: item.session.ticket_title, description: "", status: item.session.ticket_status,
    version: 0, priority: "normal", category_id: "", management_unit_id: "", building_id: null, updated_at: item.session.updated_at,
  } });
  const current = entries.find(entry => entry.session.id === selected || entry.ticket.id === selected);
  const room = useQuery(roomQueryOptions(current?.roomId || ""));
  function show(entry?: Entry) {
    const value = entry ? entry.session.id : "";
    select(value);
    const params = new URLSearchParams(location.search);
    params.delete("ticket"); params.delete("session");
    if (entry) params.set(entry.hasSession ? "session" : "ticket", value);
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
  }
  useEffect(() => {
    const sync = () => { const params = new URLSearchParams(location.search); select(params.get("session") || params.get("ticket") || ""); };
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  const filtered = entries.filter(entry => {
    const state = sessionState(entry.session);
    return (finished ? state.group === "done" : state.group !== "done") && (building === "all" || entry.ticket.building_id === building)
      && (category === "all" || entry.ticket.category_id === category)
      && `${entry.ticket.title} ${entry.ticket.code} ${requestPlace(entry.ticket, cat)}`.toLocaleLowerCase("vi").includes(query.trim().toLocaleLowerCase("vi"));
  }).sort((a, b) => (Date.parse(a.ticket.resolution_due_at || "") || Infinity) - (Date.parse(b.ticket.resolution_due_at || "") || Infinity));
  const error = listed.error || tickets.error || sessionLists.find(item => item.error)?.error;
  const loading = listed.isPending || (suppliedTickets === undefined && tickets.isPending) || sessionLists.some(item => item.isPending);
  const retry = () => { void listed.refetch(); void tickets.refetch(); sessionLists.forEach(item => void item.refetch()); };
  if (current) return <div className="ops-requests ops-request-detail"><SessionThread key={current.ticket.id} userId={userId}
    roomId={current.roomId} session={current.session} hasSession={current.hasSession} ticket={current.ticket} catalog={cat}
    messages={room.data?.messages || []} agents={room.data?.agents || []} onBack={() => show()} /></div>;
  return <div className="ops-requests">
    <PageToolbar><div className="ops-requests-toolbar">
      <h1>Yêu cầu</h1>
      <div className="ops-segmented" aria-label="Cách xem yêu cầu">
        <button type="button" aria-pressed={view === "list"} onClick={() => setView("list")}><IconList size={16} />Danh sách</button>
        <button type="button" aria-pressed={view === "board"} onClick={() => setView("board")}><IconLayoutColumns size={16} />Bảng</button>
      </div>
      <div className="ops-requests-filters">
        <Select value={building} onValueChange={value => setBuilding(value || "all")}><SelectTrigger aria-label="Lọc theo tòa"><IconBuilding size={16} /><SelectValue>{building === "all" ? "Tòa" : cat?.buildings.find(item => item.id === building)?.code}</SelectValue></SelectTrigger><SelectContent><SelectItem value="all">Tất cả tòa</SelectItem>{cat?.buildings?.map(item => <SelectItem key={item.id} value={item.id}>{item.code || item.name}</SelectItem>)}</SelectContent></Select>
        <Select value={category} onValueChange={value => setCategory(value || "all")}><SelectTrigger aria-label="Lọc theo loại"><SelectValue>{category === "all" ? "Loại" : cat?.serviceCategories.find(item => item.id === category)?.name}</SelectValue></SelectTrigger><SelectContent><SelectItem value="all">Tất cả loại</SelectItem>{cat?.serviceCategories?.map(item => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}</SelectContent></Select>
        <label className="ops-request-search"><IconSearch size={16} /><Input aria-label="Tìm yêu cầu" placeholder="Tìm căn hộ, cư dân" value={query} onChange={event => setQuery(event.target.value)} /></label>
        <Button variant={finished ? "secondary" : "ghost"} onClick={() => setFinished(!finished)} aria-pressed={finished}>Đã xong</Button>
      </div>
    </div></PageToolbar>
    <div ref={list} className="ops-requests-content" onKeyDown={event => {
      if (event.target instanceof HTMLInputElement || !["j", "k"].includes(event.key.toLowerCase())) return;
      const rows = Array.from(list.current?.querySelectorAll<HTMLButtonElement>(".ops-request-row") || []);
      const index = rows.indexOf(document.activeElement as HTMLButtonElement);
      rows[Math.max(0, Math.min(rows.length - 1, index + (event.key.toLowerCase() === "j" ? 1 : -1)))]?.focus(); event.preventDefault();
    }}>
      {error && <div className="ops-request-empty" role="alert"><p>{error.message}</p><Button variant="outline" onClick={retry}>Thử lại</Button></div>}
      {loading ? <div aria-label="Đang tải yêu cầu" className="ops-request-loading">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      : view === "board" ? <div className="ops-request-board">{LIFECYCLE.map((label, index) => {
        const items = filtered.filter(entry => lifecycleStep(entry.session) === index);
        return <section key={label} aria-label={label}><h2>{label}<span>{items.length}</span></h2>{items.map(entry => <RequestRow key={entry.ticket.id} entry={entry} catalog={cat} card onOpen={() => show(entry)} />)}</section>;
      })}</div> : (finished ? [["done", "Đã xong"]] : [["attention", "Cần bạn xử lý"], ["running", "Agent đang xử lý"]]).map(([group, label]) => {
        const items = filtered.filter(entry => sessionState(entry.session).group === group);
        const shown = expanded.includes(group) ? items : items.slice(0, group === "running" ? 4 : 5);
        return <section className="ops-request-group" key={group} aria-label={label}><h2>{label}<span data-attention={group === "attention"}>{items.length}</span>{group === "running" && <small>bạn chưa cần làm gì</small>}</h2>
          {items.length ? <div className="ops-request-list">{shown.map(entry => <RequestRow key={entry.ticket.id} entry={entry} catalog={cat} onOpen={() => show(entry)} />)}{shown.length < items.length && <button type="button" className="ops-request-more" onClick={() => setExpanded([...expanded, group])}>Xem thêm {items.length - shown.length} yêu cầu</button>}</div>
          : <p className="ops-request-empty">{group === "attention" ? "Không còn việc nào chờ bạn." : query || building !== "all" || category !== "all" ? "Không có yêu cầu phù hợp với bộ lọc." : group === "done" ? "Chưa có yêu cầu đã xong." : "Chưa có yêu cầu đang được xử lý."}</p>}
        </section>;
      })}
    </div>
  </div>;
}
