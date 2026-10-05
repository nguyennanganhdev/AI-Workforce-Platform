import { useCallback, useEffect, useRef, useState } from "react";
import { uploadImage } from "../../../../../shared/direct-image-upload";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate } from "@tanstack/react-router";
import { roomSessionsQueryOptions, roomsQueryOptions } from "@/lib/rooms/queries";
import { Coordination } from "./coordination/Coordination";
import { sessionState } from "./coordination/model";
import { AgentsPage } from "./ManagedAgents";
import { ConnectionsPage } from "./Connections";
import {
  ConnectedOperationsShell,
  connectedPages,
} from "../layout/connected-operations-shell";
import { WorkspaceFrame } from "../workspace/WorkspaceFrame";
import { AccountsPage } from "./admin/Accounts";
import { AuditPage, ModelsPage, UnitsPage } from "./admin/Platform";
import "./connected.css";
import { FieldJob, type FieldActions } from "./field/FieldJob";
import { FieldWorkList } from "./field/FieldWorkList";
import { placeOf, stateOf } from "./field/model";
import { Inquiries, LearnedAnswers, type Inquiry, type LearnedAnswer } from "./Inquiries";
import { OperationsDashboardView } from "../components/operations-dashboard";
import { LiveReportsPage } from "../workspace/LiveReportsPage";
import { WorkListView } from "../workspace/WorkPage";
import type { WorkItem } from "../workspace/work-items";

type Ticket = {
  id: string;
  code: string;
  title: string;
  description: string;
  status: string;
  version: number;
  category_id: string;
  management_unit_id: string;
  priority: string;
  building_id: string | null;
  unit_code?: string | null;
  resolution_due_at: string | null;
  updated_at: string;
};
type Order = {
  id: string;
  ticket_id: string;
  status: string;
  version: number;
  description: string;
  category_id: string;
  assignment_id?: string;
  assignment_status?: string;
};
type Detail = {
  ticket: Ticket;
  workOrders: Order[];
  events: { id: string; event_type: string; occurred_at: string }[];
};
type Session = {
  session: {
    id: string;
    status: string;
    state_version: number;
    supervisor_name: string;
    // Written by the backend when the Supervisor runtime accepts the ticket and reports its state.
    supervisor?: { acceptedAt?: string } | null;
    runtime?: { phase: string; pauseReason?: string | null } | null;
  } | null;
  // What the Supervisor's room did: the specialists it invited, their tasks and their replies.
  room?: {
    members: string[];
    tasks: { description: string; status: string; agent: string }[];
    replies: { id: string; agent: string; text: string; created_at: string }[];
    // What management asked an agent inside this session, and whether it was answered yet.
    questions: { id: string; agent: string; text: string; status: string }[];
    // The plan the Supervisor proposed from those replies. Management decides it, then the resident.
    plan?: {
      id: string;
      title: string;
      status: string;
      version: number;
      management_note?: string | null;
      proposal: {
        steps: string[];
        performer_role: string;
        expected_duration: string;
        conditions: string;
        cost?: { amount: number; currency: string } | null;
      };
    } | null;
  };
  missing?: string;
  awaitingManagementApproval?: boolean;
};
// What the resident reported first, then before and after the work.
const PHOTO_ORDER = ["", "issue", "before", "after", "other"];
const PHOTO_PURPOSE: Record<string, string> = { issue: "Phản ánh", before: "Trước khi sửa", after: "Sau khi sửa" };
type Me = {
  user: { id: string; name: string };
  role: string;
  dataMode: string;
};
type Staff = { id: string; name?: string; employee_code: string };
type Catalog = {
  staff: Staff[];
  serviceCategories: { id: string; name: string }[];
  buildings: { id: string; name: string; code: string }[];
};
const labels: Record<string, string> = {
  open: "Mới tiếp nhận",
  triaging: "Đang phân loại",
  assigned: "Đã giao việc",
  in_progress: "Đang xử lý",
  resolved: "Chờ cư dân xác nhận",
  closed: "Hoàn tất",
  cancelled: "Đã hủy",
  queued: "Chờ phân công",
  offered: "Đã mời nhận việc",
  accepted: "Đã nhận việc",
  en_route: "Đang di chuyển",
  arrived: "Đã đến hiện trường",
  completed: "Đã thi công xong",
  awaiting_approval: "Chờ đồng ý",
  rejected: "Từ chối",
};
// The backend's priority as the P0–P3 codes the shared operations screens show and filter by.
const SEVERITY: Record<string, string> = { critical: "P0", high: "P1", normal: "P2", low: "P3" };

export function ConnectedOperations() {
  const path = useLocation().pathname.split("/")[2] || "";
  const linkedTicket = new URLSearchParams(useLocation().searchStr).get('ticket');
  const [history, setHistory] = useState(path === "completed-tasks");
  const [stats, setStats] = useState<{approvals: {status: string; count: number}[]}>();
  useEffect(() => setHistory(path === "completed-tasks"), [path]);
  const [me, setMe] = useState<Me>();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [jobs, setJobs] = useState<Order[]>([]);
  const [detail, setDetail] = useState<Detail>();
  const [session, setSession] = useState<Session>();
  const [catalog, setCatalog] = useState<Catalog>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Unknown until the health check answers; nothing is loaded before that, so the first
  // request already carries the demo actor when the backend is a local demo.
  const [local, setLocal] = useState<boolean>();
  const [actor, setActor] = useState(
    () => sessionStorage.getItem("operations.local-actor") || "management",
  );
  const [staff, setStaff] = useState("");
  const [note, setNote] = useState("");
  const [available, setAvailable] = useState<Staff[]>([]);
  const [photos, setPhotos] = useState<{ id: string; original_name: string; purpose?: string }[]>(
    [],
  );
  const [orders, setOrders] = useState<Order[]>([]);
  // Closed for the resident, but the coordination session still needs management.
  const [awaitingClosure, setAwaitingClosure] = useState<string[]>([]);
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [learned, setLearned] = useState<LearnedAnswer[]>([]);
  const [conversation, setConversation] = useState<
    { id: string; sender_kind: string; text: string; created_at: string }[]
  >([]);
  const locked = useRef(false);
  const ticketId = useRef("");
  const request = useCallback(
    async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
      const response = await fetch(`/api/business${path}`, {
        ...init,
        credentials: "include",
        headers: {
          ...(typeof init.body === "string"
            ? { "Content-Type": "application/json" }
            : {}),
          ...(local ? { "X-Demo-Actor": actor } : {}),
          ...init.headers,
        },
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          setMe(undefined);
          setTickets([]);
          setJobs([]);
          setDetail(undefined);
        }
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : `Không thực hiện được thao tác (${response.status}).`,
        );
      }
      return body as T;
    },
    [actor, local],
  );
  const load = useCallback(async () => {
    const identity = await request<Me>("/operations/me");
    if (
      identity.dataMode !== "database" &&
      import.meta.env.VITE_ALLOW_DEMO_BACKEND !== "true"
    ) {
      throw new Error(
        "Backend đang dùng tài khoản demo. Cần khởi động backend với xác thực thật trước khi sử dụng.",
      );
    }
    setMe(identity);
    const pages = async <T,>(path: string): Promise<T[]> => {
      const result: T[] = [];
      let offset: number | null = 0;
      while (offset !== null) {
        const page: { items: T[]; nextOffset: number | null } = await request(
          `${path}?limit=100&offset=${offset}`,
        );
        result.push(...page.items);
        offset = page.nextOffset ?? null;
      }
      return result;
    };
    const [data, cat, mine, allOrders, dashboard, closures, questions, knowledge] = await Promise.all([
      pages<Ticket>("/tickets"),
      request<Catalog>("/catalogs"),
      request<{ items: Order[] }>("/my-work-orders?limit=100"),
      pages<Order>("/work-orders"),
      request<{approvals: {status: string; count: number}[]}>("/dashboard"),
      request<{ ticketIds: string[] }>("/sessions/awaiting-approval"),
      request<{ items: Inquiry[] }>("/sessions/inquiries"),
      request<{ items: LearnedAnswer[] }>("/knowledge/candidates"),
    ]);
    setInquiries(questions.items);
    setLearned(knowledge.items);
    setAwaitingClosure(closures.ticketIds);
    setStats(dashboard);
    setTickets(data);
    setCatalog(cat);
    setJobs(mine.items);
    setOrders(allOrders);
    if (ticketId.current) {
      const d = await request<Detail>(`/tickets/${ticketId.current}`);
      setDetail(d);
      setSession(await request<Session>(`/tickets/${ticketId.current}/session`));
      setConversation((await request<{ items: typeof conversation }>(`/tickets/${ticketId.current}/conversation`)).items);
      const p = await request<{
        items: { id: string; original_name: string; purpose?: string }[];
      }>(`/tickets/${ticketId.current}/files`);
      setPhotos(p.items);
    }
  }, [request]);
  useEffect(() => {
    let active = true;
    fetch("/api/business/health")
      .then((r) => r.json())
      .then((r) => {
        if (active)
          setLocal(
            r.dataMode === "faker-database" &&
              import.meta.env.VITE_ALLOW_DEMO_BACKEND === "true",
          );
      })
      .catch(() => {
        if (active) setLocal(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (local === undefined) return;
    let stopped = false;
    const poll = async () => {
      try {
        if (!stopped) await load();
      } catch (e) {
        if (!stopped)
          setError(
            e instanceof Error ? e.message : "Không kết nối được backend.",
          );
      }
    };
    void poll();
    const timer = setInterval(() => {
      if (!document.hidden && !locked.current) void poll();
    }, 5000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [load, local]);
  useEffect(() => {
    ticketId.current = "";
    setDetail(undefined);
    setSession(undefined);
    setConversation([]);
    setPhotos([]);
  }, [path]);
  async function run(action: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Không thực hiện được thao tác.",
      );
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  const post = (path: string, body: unknown) =>
    request(path, { method: "POST", body: JSON.stringify(body) });
  async function open(id: string) {
    ticketId.current = id;
    setDetail(undefined);
    setSession(undefined);
    setConversation([]);
    setPhotos([]);
    setStaff("");
    setAvailable([]);
    await run(async () => {
      const d = await request<Detail>(`/tickets/${id}`);
      setDetail(d);
      setSession(await request<Session>(`/tickets/${id}/session`));
      setConversation((await request<{ items: typeof conversation }>(`/tickets/${id}/conversation`)).items);
      if (d.ticket.category_id && me?.role !== "staff") {
        try {
          const a = await request<{ items: Staff[] }>(
            `/staff/available?managementUnitId=${d.ticket.management_unit_id}&categoryId=${d.ticket.category_id}`,
          );
          setAvailable(a.items);
        } catch (e) {
          setAvailable([]);
          throw e;
        }
      }
    });
  }
  useEffect(() => {
    if (linkedTicket && me && ticketId.current !== linkedTicket) void open(linkedTicket);
  }, [linkedTicket, me?.user.id]);
  const management = me?.role === "management" || me?.role === "admin";
  const navigate = useNavigate();
  // Management lands on the coordination room: that is where requests wait for a decision.
  useEffect(() => {
    if (management && path === "") void navigate({ to: "/operations/team", replace: true });
  }, [management, path, navigate]);
  // An administrator's page opened by someone else used to draw the work list under that page's
  // title ("Nhật ký" over a list of jobs). It goes to the account's own start page instead.
  const adminOnly = ["units", "connections", "models", "audit"].includes(path);
  useEffect(() => {
    if (me && me.role !== "admin" && adminOnly)
      void navigate({ to: management ? "/operations/team" : "/operations/my-tasks", replace: true });
  }, [me, adminOnly, management, navigate]);
  const rooms = useQuery({ ...roomsQueryOptions(), enabled: management });
  const roomId = rooms.data?.items[0]?.id || "";
  const waiting = useQuery({ ...roomSessionsQueryOptions(roomId), enabled: management && !!roomId });
  const notices = management
    ? (waiting.data || []).filter((s) => sessionState(s).group === "attention")
      .map((s) => ({ id: s.id, title: s.ticket_title, note: sessionState(s).label, to: `/operations/team?session=${encodeURIComponent(s.id)}` }))
    // A technician is told about the work offered to it until it accepts.
    : jobs.filter((j) => stateOf(j) === "offered").map((j) => ({ id: j.id, title: tickets.find((t) => t.id === j.ticket_id)?.title || "Công việc mới",
        note: "Việc mới chờ bạn nhận", to: `/operations/my-tasks?ticket=${encodeURIComponent(j.ticket_id)}` }));
  const coordinating = management && path === "team";
  // The administrator's own pages: what it sets up for management to work with.
  const adminPage = me?.role !== "admin" ? null : path === "accounts" ? <AccountsPage /> : path === "units" ? <UnitsPage />
    : path === "connections" ? <ConnectionsPage /> : path === "models" ? <ModelsPage /> : path === "audit" ? <AuditPage /> : null;
  const plan = session?.room?.plan;
  const selected = detail?.ticket;
  const visible = tickets.filter((t) => {
    if (path === "triage" && !["open", "triaging"].includes(t.status))
      return false;
    if (
      path === "qc" &&
      !orders.some((o) => o.ticket_id === t.id && o.status === "completed")
    )
      return false;
    return true;
  });
  const unavailable = [
    "accounts",
    "security",
    "sanitation",
    "contractor",
    "approvals",
    "evidence",
  ].includes(path);
  // What someone on site does to an order. Each runs once, then the lists are read again.
  const fieldActions: FieldActions = {
    accept: (order, minutes) => void run(async () => {
      await post(`/assignments/${order.assignment_id}/response`, { status: "accepted", eta_at: new Date(Date.now() + minutes * 60000).toISOString() });
    }),
    reject: (order, reason) => void run(async () => {
      await post(`/assignments/${order.assignment_id}/response`, { status: "rejected", rejection_reason: reason });
      ticketId.current = "";
      setDetail(undefined);
    }),
    advance: (order, status, text) => void run(async () => {
      await request(`/work-orders/${order.id}/status`, { method: "PATCH", body: JSON.stringify({ version: order.version, status, note: text || labels[status] }) });
    }),
    quote: (order, text, quote) => void run(async () => {
      await post(`/work-orders/${order.id}/repair-proposal`, { version: order.version, note: text, ...quote });
    }),
    consent: (order, approved) => void run(async () => {
      await post(`/work-orders/${order.id}/repair-proposal/onsite-decision`, { version: order.version, approved });
    }),
    photo: (order, picture, purpose, caption) => void run(async () => {
      const base = `/tickets/${order.ticket_id}`;
      const stored = await uploadImage(request, `${base}/direct-uploads`,
        `${base}/files?filename=${encodeURIComponent(picture.name)}&mimeType=${encodeURIComponent(picture.type)}&purpose=${purpose}`,
        picture, picture.name, crypto.randomUUID(), purpose);
      await post(`${base}/evidence`, { file_id: stored.fileId, work_order_id: order.id, assignment_id: order.assignment_id, purpose, caption });
    }),
  };
  // Shown above the page in either frame: the demo actor of a local database, and what went wrong.
  const banners = (
    <>
        {local && (
          <label className="local-actor">
            Phiên kiểm thử database{" "}
            <select
              value={actor}
              disabled={busy}
              onChange={(e) => {
                sessionStorage.setItem(
                  "operations.local-actor",
                  e.target.value,
                );
                ticketId.current = "";
                setDetail(undefined);
                setMe(undefined);
                setTickets([]);
                setJobs([]);
                setOrders([]);
                setActor(e.target.value);
                setError("");
              }}
            >
              <option value="management">Ban quản lý</option>
              <option value="technical">Nhân viên kỹ thuật</option>
              <option value="security">Nhân viên an ninh</option>
            </select>
          </label>
        )}
        {error && (
          <div role="alert" className="live-error">
            {error}
            <button onClick={() => void run(load)}>Thử lại</button>
          </div>
        )}
    </>
  );
  return (
    <ConnectedOperationsShell name={me?.user.name} management={management} administrator={me?.role === "admin"} field={me?.role === "staff"} notices={notices} flush={coordinating}
      // The list already opens on what is newly offered; inside a job, another offer is announced above it.
      banner={me?.role === "staff" ? (selected ? notices.filter((n) => !n.to.endsWith(encodeURIComponent(selected.id))) : []) : undefined}
      alerts={tickets.filter(t => t.priority === 'critical' && !['closed', 'cancelled'].includes(t.status)).map(t => ({id: t.id, title: t.title, location_json: {towerCode: catalog?.buildings.find(b => b.id === t.building_id)?.code}}))}>
      {coordinating ? <Coordination userId={me?.user.id || ""} /> : path === "agents" && management ? <AgentsPage />
        : adminPage ? adminPage : me?.role === "staff" ? (
          <div className="flex flex-col gap-4">
            {banners}
            {selected && detail ? (
              <FieldJob key={selected.id} ticket={selected} place={placeOf(selected, catalog?.buildings || [])} busy={busy} request={request} actions={fieldActions}
                orders={detail.workOrders.flatMap((order) => { const mine = jobs.find((j) => j.id === order.id); return mine ? [{ ...order, ...mine }] : []; })}
                plan={plan?.status === "approved" ? plan : undefined} conversation={conversation}
                photos={photos.map((p) => ({ id: p.id, name: p.original_name, purpose: p.purpose || "", src: `/api/business/files/${p.id}/content?inline=true${local ? `&demoActor=${actor}` : ""}` }))}
                onBack={() => { ticketId.current = ""; setDetail(undefined); }} />
            ) : (
              // An offer that was refused or ran out is no longer this person's work.
              <FieldWorkList tickets={tickets} orders={jobs.filter((j) => !["rejected", "expired"].includes(j.assignment_status || ""))}
                buildings={catalog?.buildings || []} history={path === "completed-tasks"} onOpen={(id) => void open(id)} />
            )}
          </div>
        ) :
      <WorkspaceFrame
        contentOnly={!selected && !unavailable}
        title={management ? connectedPages[path] || "Không gian làm việc" : ''}
        description={
          me?.dataMode === "local-database"
            ? "Kết nối database local · tài khoản kiểm thử"
            : management ? "Điều phối và theo dõi công việc trong phạm vi được cấp." : ''
        }
        connectedAccount={{
          role: me?.role === "admin" ? "admin" : management ? "manager" : "staff",
          scope: "được cấp trên hệ thống",
        }}
      >
        {banners}
        {unavailable ? (
          <section className="ws-card">
            <h2>Chức năng chưa được nối đầy đủ</h2>
            <p>
              Luồng này chưa được nghiệm thu trên giao diện kết nối. Dùng danh
              mục công việc để tiếp nhận, phân công và xử lý phản ánh.
            </p>
          </section>
        ) : path === "reports" ? (
          <LiveReportsPage buildings={catalog?.buildings || []} categories={catalog?.serviceCategories || []} />
        ) : (
          <>
            {path === "" && !selected ? (
              <OperationsDashboardView roleTitle={me?.role === 'admin' ? 'Quản trị hệ thống' : 'Ban quản lý'}
                kpis={[
                  {label: 'Khẩn cấp P0', value: tickets.filter(t => t.priority === 'critical' && !['closed', 'cancelled'].includes(t.status)).length, note: 'Phản ánh khẩn cấp chưa đóng', to: '/operations/incidents', action: 'Xem phản ánh'},
                  {label: 'Đang thực hiện', value: orders.filter(o => o.status === 'in_progress').length, unit: `/ ${orders.length} phiếu`, note: 'Phiếu thi công trong phạm vi được cấp', to: '/operations/work-orders', action: 'Xem phiếu thi công'},
                  {label: 'Chờ nghiệm thu', value: orders.filter(o => o.status === 'completed').length, note: 'Phiếu thi công đã hoàn thành cần xem xét', to: '/operations/qc', action: 'Xem hồ sơ'},
                  {label: 'Chờ phê duyệt', value: Number(stats?.approvals.find(a => a.status === 'pending')?.count || 0), note: 'Yêu cầu phê duyệt trong phạm vi công việc', to: '/operations/work-orders', action: 'Xem công việc'},
                ]}
                watched={tickets.filter(t => !['closed', 'cancelled'].includes(t.status)).slice(0, 6).map(t => ({
                  id: t.code, title: t.title, category: catalog?.serviceCategories.find(c => c.id === t.category_id)?.name || 'Chưa phân loại',
                  severity: SEVERITY[t.priority], stage: labels[t.status] || t.status, sla_due_at: t.resolution_due_at,
                  location_json: {towerCode: catalog?.buildings.find(b => b.id === t.building_id)?.code || 'Chưa xác định'},
                }))}
                zones={(catalog?.buildings || []).map(b => ({tower: b.name, note: `${tickets.filter(t => t.building_id === b.id && !['closed', 'cancelled'].includes(t.status)).length} phản ánh đang mở`}))} />
            ) : !selected && (
              <>
              {(path === "triage" || path === "kanban") && management && (
                <LearnedAnswers items={learned} disabled={busy}
                  onDecide={(item, decision) =>
                    void run(async () => {
                      await post(`/knowledge/candidates/${item.id}/decision`, { decision });
                    })
                  } />
              )}
              {(path === "triage" || path === "kanban") && management && (
                <Inquiries items={inquiries} disabled={busy}
                  onAnswer={(inquiry, text) =>
                    void run(async () => {
                      await post(`/sessions/${inquiry.id}/answer`, { version: inquiry.state_version, text });
                    })
                  } />
              )}
              <WorkListView key={path} title={connectedPages[path]} manager={management} history={history} onHistory={setHistory}
                initialBoard={path === 'kanban'} connectedAccount={{role: management ? 'manager' : 'staff', scope: 'được cấp trên hệ thống'}}
                rows={visible.map((t): WorkItem => ({key: t.id, ticket: t.id, ticketId: "", title: t.title,
                  place: catalog?.buildings.find(b => b.id === t.building_id)?.name || 'Chưa xác định vị trí',
                  severity: SEVERITY[t.priority], department: catalog?.serviceCategories.find(c => c.id === t.category_id)?.name || 'Chưa phân loại',
                  assignee: '', status: awaitingClosure.includes(t.id) ? 'Chờ BQL duyệt đóng' : labels[t.status] || t.status, updatedAt: t.updated_at,
                  phase: awaitingClosure.includes(t.id) && management ? 'waiting' : ['closed', 'cancelled'].includes(t.status) ? 'history' : t.status === 'resolved' ? 'waiting' : t.status === 'in_progress' ? 'active' : 'new',
                }))} onOpen={row => void open(row.ticket!)} />
              </>
            )}
            <div>
              {selected && (
                <section className="ws-card live-detail">
                  {selected && detail ? (
                    <>
                      <button
                        onClick={() => {
                          ticketId.current = "";
                          setDetail(undefined);
                        }}
                      >
                        ← Về danh sách công việc
                      </button>
                      <h2>{selected.title}</h2>
                      <p>{selected.description}</p>
                      <p>
                        {selected.priority === 'critical' ? 'Khẩn cấp · ' : ''}{labels[selected.status]}
                      </p>
                      {management && !["closed", "cancelled"].includes(selected.status) && (
                        <label>
                          Ghi chú thao tác
                          <textarea
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            maxLength={2000}
                          />
                        </label>
                      )}
                      {management &&
                        ["open", "triaging"].includes(selected.status) && (
                          <div className="live-actions">
                            <button
                              disabled={busy}
                              onClick={() =>
                                void run(async () => {
                                  await post(
                                    `/tickets/${selected.id}/routing/ack`,
                                    {},
                                  );
                                })
                              }
                            >
                              Tiếp nhận
                            </button>
                            <button
                              disabled={busy || !selected.category_id}
                              onClick={() =>
                                void run(async () => {
                                  await post(
                                    `/tickets/${selected.id}/work-orders`,
                                    {
                                      category_id: selected.category_id,
                                      required_specialty_id:
                                        selected.category_id,
                                      description:
                                        note.trim() || selected.description,
                                      ticket_version: selected.version,
                                    },
                                  );
                                })
                              }
                            >
                              Tạo phiếu thi công
                            </button>
                          </div>
                        )}
                      {photos.length > 0 && (
                        <>
                          <h3>Ảnh phản ánh và kết quả</h3>
                          <div className="live-photos">
                            {[...photos].sort((x, y) => PHOTO_ORDER.indexOf(x.purpose || "") - PHOTO_ORDER.indexOf(y.purpose || "")).map((p) => {
                              const source = `/api/business/files/${p.id}/content?inline=true${local ? `&demoActor=${actor}` : ""}`;
                              return (
                                <a key={p.id} href={source} target="_blank" rel="noreferrer">
                                  <img src={source} alt={p.original_name} loading="lazy" />
                                  <span>{PHOTO_PURPOSE[p.purpose || ""] || "Ảnh khác"}</span>
                                </a>
                              );
                            })}
                          </div>
                        </>
                      )}
                      {conversation.length > 0 && (
                        <details className="live-order">
                          <summary>Trao đổi ban đầu của cư dân ({conversation.length})</summary>
                          <ol>
                            {conversation.map((m) => (
                              <li key={m.id}>
                                <time>{new Date(m.created_at).toLocaleString("vi-VN")}</time>{" "}
                                · <strong>{m.sender_kind === "user" ? "Cư dân" : "Lễ tân"}:</strong> {m.text}
                              </li>
                            ))}
                          </ol>
                        </details>
                      )}
                      {/* The session itself lives in the coordination room: management opens it there. */}
                      {management && session?.session && (
                        <p><a href={`/operations/team?session=${encodeURIComponent(session.session.id)}`}>Mở phiên điều phối của yêu cầu này →</a></p>
                      )}
                      {detail.workOrders.map((order) => (
                          <article className="live-order" key={order.id}>
                            <h3>Phiếu thi công</h3>
                            {order.description !== selected.description && <p>{order.description}</p>}
                            <strong>
                              {labels[order.status] || order.status}
                            </strong>
                            {order.status === "queued" && (
                              <div className="live-actions">
                                <select
                                  aria-label="Nhân viên nhận việc"
                                  value={staff}
                                  onChange={(e) => setStaff(e.target.value)}
                                >
                                  <option value="">Chọn nhân viên</option>
                                  {available.map((s) => (
                                    <option key={s.id} value={s.id}>
                                      {s.name || s.employee_code}
                                    </option>
                                  ))}
                                </select>
                                <button
                                  disabled={busy || !staff}
                                  onClick={() =>
                                    void run(async () => {
                                      await post(
                                        `/work-orders/${order.id}/assignments`,
                                        {
                                          staff_id: staff,
                                          work_order_version: order.version,
                                          offer_expires_at: new Date(
                                            Date.now() + 30 * 60 * 1000,
                                          ).toISOString(),
                                        },
                                      );
                                    })
                                  }
                                >
                                  Phân công
                                </button>
                              </div>
                            )}
                            {order.status === "completed" &&
                              // Once QC passed the ticket is resolved and waits for the resident.
                              !["resolved", "closed"].includes(selected.status) && (
                                <div className="live-actions">
                                  <button
                                    disabled={busy}
                                    onClick={() =>
                                      void run(async () => {
                                        await post(
                                          `/work-orders/${order.id}/qc`,
                                          {
                                            outcome: "pass",
                                            criteria: [
                                              {
                                                name: "Kết quả hiện trường",
                                                passed: true,
                                              },
                                            ],
                                            note:
                                              note ||
                                              "Đã kiểm tra kết quả hiện trường.",
                                          },
                                        );
                                      })
                                    }
                                  >
                                    Nghiệm thu đạt
                                  </button>
                                  <button
                                    disabled={busy || !note.trim()}
                                    onClick={() =>
                                      void run(async () => {
                                        const qc = (await post(
                                          `/work-orders/${order.id}/qc`,
                                          {
                                            outcome: "fail",
                                            criteria: [
                                              {
                                                name: "Kết quả hiện trường",
                                                passed: false,
                                              },
                                            ],
                                            redo_required: true,
                                            note,
                                          },
                                        )) as { id: string };
                                        await post(
                                          `/work-orders/${order.id}/redo`,
                                          {
                                            qc_result_id: qc.id,
                                            work_order_version: order.version,
                                            instruction: note,
                                          },
                                        );
                                      })
                                    }
                                  >
                                    Không đạt · tạo lượt làm lại
                                  </button>
                                </div>
                              )}
                          </article>
                      ))}
                      {management && <details className="live-order"><summary>Lịch sử xử lý</summary>
                      <ol>
                        {detail.events.map((e) => (
                          <li key={e.id}>
                            <time>
                              {new Date(e.occurred_at).toLocaleString("vi-VN")}
                            </time>{" "}
                            · {e.event_type}
                          </li>
                        ))}
                      </ol>
                      </details>}
                    </>
                  ) : (
                    <p>Chọn một công việc để xem chi tiết và xử lý.</p>
                  )}
                </section>
              )}
            </div>
          </>
        )}
      </WorkspaceFrame>}
    </ConnectedOperationsShell>
  );
}
