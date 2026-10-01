import { useCallback, useEffect, useRef, useState } from "react";
import "./connected.css";

type Ticket = {
  id: string;
  code: string;
  title: string;
  description: string;
  status: string;
  version: number;
  category_id: string;
  management_unit_id: string;
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
  const [me, setMe] = useState<Me>();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [jobs, setJobs] = useState<Order[]>([]);
  const [detail, setDetail] = useState<Detail>();
  const [catalog, setCatalog] = useState<Catalog>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState(false);
  const [actor, setActor] = useState("management");
  const [staff, setStaff] = useState("");
  const [note, setNote] = useState("");
  const [available, setAvailable] = useState<Staff[]>([]);
  const [file, setFile] = useState<File>();
  const [photos, setPhotos] = useState<{ id: string; original_name: string }[]>(
    [],
  );
  const [q, setQ] = useState("");
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
    setMe(identity);
    const [data, cat, mine] = await Promise.all([
      request<{ items: Ticket[] }>("/tickets?limit=100"),
      request<Catalog>("/catalogs"),
      request<{ items: Order[] }>("/my-work-orders?limit=100"),
    ]);
    setTickets(data.items);
    setCatalog(cat);
    setJobs(mine.items);
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
        if (active && r.dataMode === "faker-database") setLocal(true);
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
        } catch {
          setAvailable(catalog?.staff ?? []);
        }
      }
    });
  }
  const management = me?.role === "management" || me?.role === "admin";
  const selected = detail?.ticket;
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
    <div className="connected-operations">
      <header>
        <div>
          <p>VINHOMES OPERATIONS</p>
          <h1>Công việc & tiếp nhận</h1>
        </div>
        <div>
          <strong>{me?.user.name}</strong>
          <p>
            {me?.dataMode === "local-database"
              ? "Database local · tài khoản kiểm thử"
              : "Dữ liệu từ máy chủ"}
          </p>
          <a href="/operations/login">Tài khoản</a>
        </div>
      </header>
      {local && (
        <label className="local-actor">
          Phiên kiểm thử database{" "}
          <select
            value={actor}
            disabled={busy}
            onChange={(e) => {
              ticketId.current = "";
              setDetail(undefined);
              setMe(undefined);
              setTickets([]);
              setJobs([]);
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
      <div className="live-toolbar">
        <input
          aria-label="Tìm công việc"
          placeholder="Tìm mã hoặc nội dung…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button disabled={busy} onClick={() => void run(load)}>
          Tải lại
        </button>
      </div>
      <div className="live-columns">
        <section className="live-list">
          {(management
            ? tickets
            : tickets.filter((t) => jobs.some((j) => j.ticket_id === t.id))
          )
            .filter((t) =>
              `${t.code} ${t.title}`.toLowerCase().includes(q.toLowerCase()),
            )
            .map((t) => (
              <button
                key={t.id}
                onClick={() => void open(t.id)}
                aria-current={selected?.id === t.id}
              >
                <small>{t.code}</small>
                <strong>{t.title}</strong>
                <span>{labels[t.status] || t.status}</span>
              </button>
            ))}
          {me && !tickets.length && (
            <p>Chưa có yêu cầu trong phạm vi của bạn.</p>
          )}
        </section>
        <section className="live-detail">
          {selected && detail ? (
            <>
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
              {management && ["open", "triaging"].includes(selected.status) && (
                <div className="live-actions">
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        await post(`/tickets/${selected.id}/routing/ack`, {});
                      })
                    }
                  >
                    Tiếp nhận
                  </button>
                  <button
                    disabled={busy || !selected.category_id}
                    onClick={() =>
                      void run(async () => {
                        await post(`/tickets/${selected.id}/work-orders`, {
                          category_id: selected.category_id,
                          required_specialty_id: selected.category_id,
                          description: note.trim() || selected.description,
                          ticket_version: selected.version,
                        });
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
                            headers: local ? { "X-Demo-Actor": actor } : {},
                          },
                        );
                        if (!r.ok) throw new Error("Không tải được ảnh.");
                        const url = URL.createObjectURL(await r.blob());
                        const link = document.createElement("a");
                        link.href = url;
                        link.download = p.original_name;
                        link.click();
                        setTimeout(() => URL.revokeObjectURL(url), 1000);
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
                  arrived: ["in_progress", "Bắt đầu xử lý"],
                  in_progress: ["completed", "Gửi kết quả thi công"],
                };
                return (
                  <article className="live-order" key={order.id}>
                    <h3>Phiếu thi công</h3>
                    <small>{order.id}</small>
                    <p>{order.description}</p>
                    <strong>{labels[order.status] || order.status}</strong>
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
                    {!management && mine?.assignment_status === "offered" && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            await post(
                              `/assignments/${mine.assignment_id}/response`,
                              { status: "accepted" },
                            );
                          })
                        }
                      >
                        Nhận việc
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
                              onChange={(e) => setFile(e.target.files?.[0])}
                            />
                          </label>
                          <button
                            disabled={busy || !file}
                            onClick={() =>
                              void run(async () => {
                                if (!file) return;
                                const p = await request<{ fileId: string }>(
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
                                await post(`/tickets/${selected.id}/evidence`, {
                                  file_id: p.fileId,
                                  work_order_id: order.id,
                                  assignment_id: mine.assignment_id,
                                  purpose: "after",
                                  caption: note,
                                });
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
                                await post(`/work-orders/${order.id}/qc`, {
                                  outcome: "pass",
                                  criteria: [
                                    {
                                      name: "Kết quả hiện trường",
                                      passed: true,
                                    },
                                  ],
                                  note:
                                    note || "Đã kiểm tra kết quả hiện trường.",
                                });
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
                                await post(`/work-orders/${order.id}/redo`, {
                                  qc_result_id: qc.id,
                                  work_order_version: order.version,
                                  instruction: note,
                                });
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
      </div>
    </div>
  );
}
