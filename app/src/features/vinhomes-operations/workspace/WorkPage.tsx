import { useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import { useOperationsData } from "../hooks/use-operations-data";
import { TechnicianJobDetail } from "../components/technician/technician-job-detail";
import { WorkOrderDialog } from "../components/work-order-dialog";
import { useWorkspace } from "./use-workspace";
import { WorkspaceFrame } from "./WorkspaceFrame";
import { TicketDetail } from "./TicketDetail";
import { setAvailability } from "./service";
import {
  workItems,
  workPath,
  type WorkItem,
  type WorkPhase,
} from "./work-items";

export function WorkPage() {
  const w = useWorkspace(),
    legacy = useOperationsData();
  const location = useLocation(),
    navigate = useNavigate();
  const search = location.search as {
    ticket?: string;
    job?: string;
    task?: string;
    view?: string;
  };
  const [query, setQuery] = useState(""),
    [department, setDepartment] = useState(""),
    [phase, setPhase] = useState("all"),
    [board, setBoard] = useState(false);
  const [attempt, setAttempt] = useState<string | null>(null);
  const account = w.account;
  if (!account) return <p role="alert">Vui lòng đăng nhập lại.</p>;
  const manager = account.role === "manager",
    path = workPath(account.role),
    history = search.view === "history";
  const rows = workItems(account, w.state, legacy);
  const move = (next: Record<string, string>) => {
    navigate({ to: path, search: next });
    document.querySelector("main")?.scrollTo({ top: 0 });
  };
  const back = () => move(history ? { view: "history" } : {});
  const open = (row: WorkItem) =>
    move({
      ...(history ? { view: "history" } : {}),
      ...(row.ticket
        ? { ticket: row.ticket }
        : row.job
          ? { job: row.job! }
          : { task: row.task! }),
    });
  const selected = rows.find((r) =>
    search.ticket
      ? r.ticket === search.ticket
      : search.job
        ? r.job === search.job
        : search.task
          ? r.task === search.task
          : false,
  );
  const isDetail = !!(search.ticket || search.job || search.task);
  if (isDetail && !selected)
    return (
      <WorkspaceFrame
        title="Không tìm thấy công việc"
        description="Hồ sơ không tồn tại hoặc ngoài phạm vi được cấp."
      >
        <button onClick={back}>Về danh sách công việc</button>
      </WorkspaceFrame>
    );
  if (selected?.ticket)
    return (
      <TicketDetail
        key={selected.ticket}
        ticketId={selected.ticket}
        onBack={back}
      />
    );
  if (selected?.job)
    return (
      <TechnicianJobDetail
        key={selected.job}
        woId={selected.job}
        onBack={back}
      />
    );
  if (selected?.task) {
    const task = legacy.tasks.find((t) => t.id === selected.task)!;
    const attempts = legacy.workOrders
      .filter((t) => t.task_id === task.id)
      .sort((a, b) => b.attempt_no - a.attempt_no);
    const wo = attempts.find((t) => t.id === attempt);
    return (
      <WorkspaceFrame
        title={selected.title}
        description={`${selected.ticketId} · ${selected.place}`}
      >
        <button onClick={back}>← Phân công công việc</button>
        <section className="ws-card">
          <p>
            {selected.status} · {selected.assignee}
          </p>
          <h2>Hồ sơ thi công</h2>
          {attempts.map((a) => (
            <button
              className="ws-ticket"
              key={a.id}
              onClick={() => setAttempt(a.id)}
            >
              {a.id} · Lần {a.attempt_no} · {a.executor_name || "Chưa giao"} ·
              Xem hồ sơ, ảnh và kết quả
            </button>
          ))}
          {!attempts.length && <p>Chưa có phiếu thi công.</p>}
          <div className="ws-row">
            {task.status === "OPEN" && (
              <button
                onClick={() => legacy.updateTaskStatus(task.id, "IN_PROGRESS")}
              >
                Bắt đầu
              </button>
            )}
            {task.status === "IN_PROGRESS" && (
              <>
                <button
                  onClick={() => legacy.updateTaskStatus(task.id, "BLOCKED")}
                >
                  Tạm hoãn
                </button>
                {!attempts.length && (
                  <button
                    onClick={() => legacy.updateTaskStatus(task.id, "DONE")}
                  >
                    Hoàn thành
                  </button>
                )}
              </>
            )}
            {task.status === "BLOCKED" && (
              <button
                onClick={() => legacy.updateTaskStatus(task.id, "IN_PROGRESS")}
              >
                Tiếp tục làm
              </button>
            )}
          </div>
        </section>
        {wo && (
          <WorkOrderDialog
            key={wo.id}
            workOrder={wo}
            onClose={() => setAttempt(null)}
          />
        )}
      </WorkspaceFrame>
    );
  }
  const phases: { id: WorkPhase; label: string }[] = [
    { id: "new", label: manager ? "Chờ / đã phân công" : "Việc mới giao" },
    { id: "active", label: "Đang xử lý" },
    { id: "waiting", label: "Chờ xác nhận / phê duyệt" },
    { id: "history", label: "Đã đóng" },
  ];
  const visible = rows.filter(
    (r) =>
      (r.phase === "history") === history &&
      (!department || r.department === department) &&
      (phase === "all" || r.phase === phase) &&
      `${r.title} ${r.ticketId} ${r.place} ${r.assignee}`
        .toLocaleLowerCase()
        .includes(query.trim().toLocaleLowerCase()),
  );
  const card = (r: WorkItem) => (
    <button
      key={r.key}
      data-work-key={r.key}
      className="ws-ticket work-item"
      onClick={() => open(r)}
    >
      <span className="ws-status" data-status={r.severity}>
        {r.severity} · {r.department}
      </span>
      <strong>{r.title}</strong>
      <p>
        {r.ticketId} · {r.place}
      </p>
      <small>
        {r.assignee} · {r.status}
      </small>
      <span className="work-item-link">Xem và xử lý →</span>
    </button>
  );
  return (
    <WorkspaceFrame
      title={manager ? "Phân công công việc" : "Việc của tôi"}
      description={
        manager
          ? "Điều phối và theo dõi công việc trong phạm vi quản lý."
          : "Công việc được giao, tiến độ xử lý và lịch sử của bạn."
      }
      error={w.error}
      notice={w.notice}
    >
      <div className="ws-row work-toolbar">
        <button
          aria-pressed={!history}
          onClick={() => {
            setPhase("all");
            move({});
          }}
        >
          Đang mở ({rows.filter((r) => r.phase !== "history").length})
        </button>
        <button
          aria-pressed={history}
          onClick={() => {
            setPhase("all");
            move({ view: "history" });
          }}
        >
          Lịch sử ({rows.filter((r) => r.phase === "history").length})
        </button>
        {manager && (
          <button aria-pressed={board} onClick={() => setBoard(!board)}>
            {board ? "Xem danh sách" : "Xem theo tiến độ"}
          </button>
        )}
      </div>
      {!manager && (
        <label className="work-availability">
          <input
            type="checkbox"
            checked={account.available}
            onChange={(e) =>
              w.run(
                (s) => setAvailability(s, account.id, e.target.checked),
                "Đã cập nhật trạng thái nhận việc.",
              )
            }
          />{" "}
          Sẵn sàng nhận thêm việc
        </label>
      )}
      <div className="ws-card ws-row">
        <label>
          Tìm công việc
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nội dung, mã ticket, vị trí, nhân viên"
          />
        </label>
        <details className="work-filters">
          <summary>Bộ lọc bộ phận và tiến độ</summary>
          <div className="ws-row">
            <label>
              Bộ phận
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                <option value="">Tất cả bộ phận</option>
                {[...new Set(rows.map((r) => r.department))].map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </label>
            {!history && (
              <label>
                Tiến độ
                <select
                  value={phase}
                  onChange={(e) => setPhase(e.target.value)}
                >
                  <option value="all">Tất cả tiến độ</option>
                  {phases
                    .filter((p) => p.id !== "history")
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                </select>
              </label>
            )}
          </div>
        </details>
      </div>
      <p className="ws-helper">{visible.length} công việc phù hợp</p>
      {board ? (
        <div className="ws-board">
          {phases
            .filter((p) => (history ? p.id === "history" : p.id !== "history"))
            .map((p) => (
              <section className="ws-card" key={p.id}>
                <h2>{p.label}</h2>
                {visible.filter((r) => r.phase === p.id).map(card)}
                {!visible.some((r) => r.phase === p.id) && (
                  <p>Chưa có công việc.</p>
                )}
              </section>
            ))}
        </div>
      ) : (
        <div className="work-list">{visible.map(card)}</div>
      )}
      {!visible.length && (
        <p className="ws-empty">
          Không có công việc phù hợp. Công việc được phân công sẽ xuất hiện tại
          đây.
        </p>
      )}
    </WorkspaceFrame>
  );
}
