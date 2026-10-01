import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "@tanstack/react-router";
import {
  ConnectedOperationsShell,
  connectedPages,
} from "../layout/connected-operations-shell";
import { WorkspaceFrame } from "../workspace/WorkspaceFrame";
import { ConnectedAccounts } from "./ConnectedAccounts";
import "./connected.css";
import { OperationsDashboardView } from "../components/operations-dashboard";
import { LiveTeamPage } from "../workspace/LiveTeamPage";
import type { CaseStage } from "../workspace/model";
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

export function ConnectedOperations() {
  const path = useLocation().pathname.split("/")[2] || "";
  const linkedTicket = new URLSearchParams(useLocation().searchStr).get('ticket');
  const [history, setHistory] = useState(path === "completed-tasks");
  const [stats, setStats] = useState<{approvals: {status: string; count: number}[]}>();
  useEffect(() => setHistory(path === "completed-tasks"), [path]);
  const [eta, setEta] = useState("30");
  const [me, setMe] = useState<Me>();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [jobs, setJobs] = useState<Order[]>([]);
  const [detail, setDetail] = useState<Detail>();
  const [catalog, setCatalog] = useState<Catalog>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState(false);
  const [actor, setActor] = useState(
    () => sessionStorage.getItem("operations.local-actor") || "management",
  );
  const [staff, setStaff] = useState("");
  const [note, setNote] = useState("");
  const [available, setAvailable] = useState<Staff[]>([]);
  const [file, setFile] = useState<File>();
  const [photos, setPhotos] = useState<{ id: string; original_name: string }[]>(
    [],
  );
  const [orders, setOrders] = useState<Order[]>([]);
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
    const [data, cat, mine, allOrders, dashboard] = await Promise.all([
      pages<Ticket>("/tickets"),
      request<Catalog>("/catalogs"),
      request<{ items: Order[] }>("/my-work-orders?limit=100"),
      pages<Order>("/work-orders"),
      request<{approvals: {status: string; count: number}[]}>("/dashboard"),
    ]);
    setStats(dashboard);
    setTickets(data);
    setCatalog(cat);
    setJobs(mine.items);
    setOrders(allOrders);
    if (ticketId.current) {
      const d = await request<Detail>(`/tickets/${ticketId.current}`);
      setDetail(d);
      const p = await request<{
        items: { id: string; original_name: string }[];
      }>(`/tickets/${ticketId.current}/files`);
      setPhotos(p.items);
    }
  }, [request]);
  useEffect(() => {
    let active = true;
    fetch("/api/business/health")
      .then((r) => r.json())
      .then((r) => {
        if (
          active &&
          r.dataMode === "faker-database" &&
          import.meta.env.VITE_ALLOW_DEMO_BACKEND === "true"
        )
          setLocal(true);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
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
  }, [load]);
  useEffect(() => {
    ticketId.current = "";
    setDetail(undefined);
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
    setPhotos([]);
    setStaff("");
    setAvailable([]);
    await run(async () => {
      const d = await request<Detail>(`/tickets/${id}`);
      setDetail(d);
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
  const selected = detail?.ticket;
  const visible = tickets.filter((t) => {
    if (!management && !jobs.some((j) => j.ticket_id === t.id)) return false;
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
  const change = (order: Order, status: string) =>
    run(async () => {
      await request(`/work-orders/${order.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          version: order.version,
          status,
          note: note.trim() || labels[status],
        }),
      });
    });
  return (
    <ConnectedOperationsShell name={me?.user.name} management={management} administrator={me?.role === "admin"}
      alerts={tickets.filter(t => t.priority === 'P0' && !['closed', 'cancelled'].includes(t.status)).map(t => ({id: t.id, title: t.title, location_json: {towerCode: catalog?.buildings.find(b => b.id === t.building_id)?.code}}))}>
      <WorkspaceFrame
        contentOnly={!selected && !unavailable && path !== "team"}
        title={connectedPages[path] || "Không gian làm việc"}
        description={
          me?.dataMode === "local-database"
            ? "Kết nối database local · tài khoản kiểm thử"
            : "Điều phối và theo dõi công việc trong phạm vi được cấp."
        }
        connectedAccount={{
          role: me?.role === "admin" ? "admin" : management ? "manager" : "staff",
          scope: "được cấp trên hệ thống",
        }}
      >
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
        {path === "accounts" && me?.role === "admin" ? <ConnectedAccounts/> : unavailable ? (
          <section className="ws-card">
            <h2>Chức năng chưa được nối đầy đủ</h2>
            <p>
              Luồng này chưa được nghiệm thu trên giao diện kết nối. Dùng danh
              mục công việc để tiếp nhận, phân công và xử lý phản ánh.
            </p>
          </section>
        ) : path === "reports" ? (
          <LiveReportsPage buildings={catalog?.buildings || []} categories={catalog?.serviceCategories || []} />
        ) : path === "team" ? (
          <LiveTeamPage userId={me?.user.id || ''} tickets={tickets.map(t => ({id: t.id, title: t.title, severity: t.priority,
            stage: ({open: 'queued', triaging: 'queued', assigned: 'assigned', in_progress: 'working', resolved: 'awaiting-confirmation', closed: 'completed', cancelled: 'cancelled'} as Record<string, CaseStage>)[t.status] || 'queued',
          }))} />
        ) : (
          <>
            {path === "" && !selected ? (
              <OperationsDashboardView roleTitle={me?.role === 'admin' ? 'Quản trị hệ thống' : 'Ban quản lý'}
                kpis={[
                  {label: 'Khẩn cấp P0', value: tickets.filter(t => t.priority === 'P0' && !['closed', 'cancelled'].includes(t.status)).length, note: 'Phản ánh khẩn cấp chưa đóng', to: '/operations/incidents', action: 'Xem phản ánh'},
                  {label: 'Đang thực hiện', value: orders.filter(o => o.status === 'in_progress').length, unit: `/ ${orders.length} phiếu`, note: 'Phiếu thi công trong phạm vi được cấp', to: '/operations/work-orders', action: 'Xem phiếu thi công'},
                  {label: 'Chờ nghiệm thu', value: orders.filter(o => o.status === 'completed').length, note: 'Phiếu thi công đã hoàn thành cần xem xét', to: '/operations/qc', action: 'Xem hồ sơ'},
                  {label: 'Chờ phê duyệt', value: Number(stats?.approvals.find(a => a.status === 'pending')?.count || 0), note: 'Yêu cầu phê duyệt trong phạm vi công việc', to: '/operations/work-orders', action: 'Xem công việc'},
                ]}
                watched={tickets.filter(t => !['closed', 'cancelled'].includes(t.status)).slice(0, 6).map(t => ({
                  id: t.code, title: t.title, category: catalog?.serviceCategories.find(c => c.id === t.category_id)?.name || 'Chưa phân loại',
                  severity: t.priority, stage: labels[t.status] || t.status, sla_due_at: t.resolution_due_at,
                  location_json: {towerCode: catalog?.buildings.find(b => b.id === t.building_id)?.code || 'Chưa xác định'},
                }))}
                zones={(catalog?.buildings || []).map(b => ({tower: b.name, note: `${tickets.filter(t => t.building_id === b.id && !['closed', 'cancelled'].includes(t.status)).length} phản ánh đang mở`}))} />
            ) : !selected && (
              <WorkListView key={path} title={connectedPages[path]} manager={management} history={history} onHistory={setHistory}
                initialBoard={path === 'kanban'} connectedAccount={{role: management ? 'manager' : 'staff', scope: 'được cấp trên hệ thống'}}
                rows={visible.map((t): WorkItem => ({key: t.id, ticket: t.id, ticketId: t.code, title: t.title,
                  place: catalog?.buildings.find(b => b.id === t.building_id)?.name || 'Chưa xác định vị trí',
                  severity: t.priority, department: catalog?.serviceCategories.find(c => c.id === t.category_id)?.name || 'Chưa phân loại',
                  assignee: '', status: labels[t.status] || t.status, updatedAt: t.updated_at,
                  phase: ['closed', 'cancelled'].includes(t.status) ? 'history' : t.status === 'resolved' ? 'waiting' : t.status === 'in_progress' ? 'active' : 'new',
                }))} onOpen={row => void open(row.ticket!)} />
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
                      <small>{selected.code}</small>
                      <h2>{selected.title}</h2>
                      <p>{selected.description}</p>
                      <p>
                        {labels[selected.status]} · phiên bản {selected.version}
                      </p>
                      <label>
                        Ghi chú thao tác
                        <textarea
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          maxLength={2000}
                        />
                      </label>
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
                      <h3>Ảnh phản ánh</h3>
                      <div className="live-photos">
                        {photos.map((p) => (
                          <a
                            key={p.id}
                            href={`/api/business/files/${p.id}/content${local ? `?demoActor=${actor}` : ""}`}
                            onClick={(e) => {
                              e.preventDefault();
                              void run(async () => {
                                const r = await fetch(
                                  `/api/business/files/${p.id}/content`,
                                  {
                                    credentials: "include",
                                    headers: local
                                      ? { "X-Demo-Actor": actor }
                                      : {},
                                  },
                                );
                                if (!r.ok)
                                  throw new Error("Không tải được ảnh.");
                                const url = URL.createObjectURL(await r.blob());
                                const link = document.createElement("a");
                                link.href = url;
                                link.download = p.original_name;
                                link.click();
                                setTimeout(
                                  () => URL.revokeObjectURL(url),
                                  1000,
                                );
                              });
                            }}
                          >
                            {p.original_name}
                          </a>
                        ))}
                      </div>
                      {detail.workOrders.map((order) => {
                        const mine = jobs.find((j) => j.id === order.id);
                        const next: Record<string, [string, string]> = {
                          accepted: ["en_route", "Bắt đầu di chuyển"],
                          en_route: ["arrived", "Đã đến hiện trường"],
                          in_progress: ["completed", "Gửi kết quả thi công"],
                        };
                        return (
                          <article className="live-order" key={order.id}>
                            <h3>Phiếu thi công</h3>
                            <small>{order.id}</small>
                            <p>{order.description}</p>
                            <strong>
                              {labels[order.status] || order.status}
                            </strong>
                            {management && order.status === "queued" && (
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
                            {!management &&
                              mine?.assignment_status === "offered" && (
                                <div className="ws-row">
                                  <label>
                                    Thời gian đến (phút)
                                    <input
                                      type="number"
                                      min="1"
                                      max="1440"
                                      value={eta}
                                      onChange={(e) => setEta(e.target.value)}
                                    />
                                  </label>
                                  <button
                                    disabled={
                                      busy ||
                                      Number(eta) < 1 ||
                                      Number(eta) > 1440
                                    }
                                    onClick={() =>
                                      void run(async () => {
                                        await post(
                                          `/assignments/${mine.assignment_id}/response`,
                                          {
                                            status: "accepted",
                                            eta_at: new Date(
                                              Date.now() + Number(eta) * 60000,
                                            ).toISOString(),
                                          },
                                        );
                                      })
                                    }
                                  >
                                    Nhận việc
                                  </button>
                                </div>
                              )}
                            {!management &&
                              mine?.assignment_status === "accepted" &&
                              order.status === "arrived" && (
                                <button
                                  disabled={busy || note.trim().length < 8}
                                  onClick={() =>
                                    void run(async () => {
                                      await post(
                                        `/work-orders/${order.id}/repair-proposal`,
                                        {
                                          version: order.version,
                                          note: note.trim(),
                                        },
                                      );
                                    })
                                  }
                                >
                                  Gửi phương án cho cư dân
                                </button>
                              )}
                            {!management &&
                              mine?.assignment_status === "accepted" &&
                              order.status === "awaiting_approval" && (
                                <button
                                  disabled={busy}
                                  onClick={() =>
                                    void change(order, "in_progress")
                                  }
                                >
                                  Bắt đầu sau khi cư dân đồng ý
                                </button>
                              )}
                            {!management &&
                              mine?.assignment_status === "accepted" &&
                              next[order.status] && (
                                <button
                                  disabled={busy}
                                  onClick={() =>
                                    void change(order, next[order.status][0])
                                  }
                                >
                                  {next[order.status][1]}
                                </button>
                              )}
                            {!management &&
                              mine?.assignment_status === "accepted" &&
                              order.status === "in_progress" && (
                                <div className="live-actions">
                                  <label>
                                    Ảnh sau xử lý
                                    <input
                                      type="file"
                                      accept="image/jpeg,image/png,image/webp"
                                      onChange={(e) =>
                                        setFile(e.target.files?.[0])
                                      }
                                    />
                                  </label>
                                  <button
                                    disabled={busy || !file}
                                    onClick={() =>
                                      void run(async () => {
                                        if (!file) return;
                                        const p = await request<{
                                          fileId: string;
                                        }>(
                                          `/tickets/${selected.id}/files?filename=${encodeURIComponent(file.name)}&mimeType=${encodeURIComponent(file.type)}&purpose=after`,
                                          {
                                            method: "POST",
                                            headers: {
                                              "Content-Type":
                                                "application/octet-stream",
                                            },
                                            body: file,
                                          },
                                        );
                                        await post(
                                          `/tickets/${selected.id}/evidence`,
                                          {
                                            file_id: p.fileId,
                                            work_order_id: order.id,
                                            assignment_id: mine.assignment_id,
                                            purpose: "after",
                                            caption: note,
                                          },
                                        );
                                        setFile(undefined);
                                      })
                                    }
                                  >
                                    Lưu bằng chứng
                                  </button>
                                </div>
                              )}
                            {management &&
                              order.status === "completed" &&
                              selected.status !== "closed" && (
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
                        );
                      })}
                      <h3>Lịch sử</h3>
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
                    </>
                  ) : (
                    <p>Chọn một công việc để xem chi tiết và xử lý.</p>
                  )}
                </section>
              )}
            </div>
          </>
        )}
      </WorkspaceFrame>
    </ConnectedOperationsShell>
  );
}
