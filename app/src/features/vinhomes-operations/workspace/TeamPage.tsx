import { useState } from "react";
import { createAgent, sendRoomMessage } from "./service";
import { stageLabels, type Agent } from "./model";
import { useWorkspace } from "./use-workspace";
import { WorkspaceFrame } from "./WorkspaceFrame";

export function TeamPage() {
  const w = useWorkspace();
  const [text, setText] = useState(""),
    [agentId, setAgentId] = useState(""),
    [ticketId, setTicketId] = useState("");
  const [name, setName] = useState(""),
    [specialty, setSpecialty] = useState<Agent["specialty"]>("technical");
  if (w.account?.role !== "manager")
    return <p role="alert">Không gian này dành cho ban quản lý.</p>;
  const actor = w.account.id,
    room = w.state.rooms.find((r) => r.scope === w.account!.scope)!;
  const agents = w.state.agents.filter((a) => room.agentIds.includes(a.id));
  const tickets = w.state.cases.filter((c) => c.scope === room.scope);
  return (
    <WorkspaceFrame
      title="Không gian ban quản lý"
      description="Trao đổi cùng đội agent và theo dõi ticket trong tòa nhà của bạn."
      error={w.error}
      notice={w.notice}
    >
      <div className="ws-team-grid">
        <section className="ws-card">
          <h2>{room.name}</h2>
          <p>
            Nhóm riêng · {agents.length} agent · Phạm vi {room.scope}
          </p>
          <div className="ws-transcript" role="log" aria-label="Tin nhắn nhóm">
            {room.messages.map((m) => (
              <article key={m.id}>
                <strong>{m.author}</strong>
                <time>
                  {new Date(m.at).toLocaleTimeString("vi-VN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
                <p>
                  {m.agentId && (
                    <span className="ws-status">
                      @{agents.find((a) => a.id === m.agentId)?.name}
                    </span>
                  )}{" "}
                  {m.text}
                </p>
                {m.ticketId && (
                  <a
                    href={`/operations/dispatch?ticket=${encodeURIComponent(m.ticketId)}`}
                  >
                    {m.ticketId}
                  </a>
                )}
                {m.context && (
                  <details>
                    <summary>Ngữ cảnh mẫu đính kèm</summary>
                    <code>{m.context}</code>
                  </details>
                )}
              </article>
            ))}
          </div>
          <form
            className="ws-stack"
            onSubmit={(e) => {
              e.preventDefault();
              if (
                w.run(
                  (s) =>
                    sendRoomMessage(
                      s,
                      actor,
                      room.id,
                      text,
                      agentId || undefined,
                      ticketId || undefined,
                    ),
                  "Đã gửi tin nhắn trong bản mẫu.",
                )
              )
                setText("");
            }}
          >
            <div className="ws-row">
              <label>
                @Nhắc agent
                <select
                  value={agentId}
                  onChange={(e) => setAgentId(e.target.value)}
                >
                  <option value="">Tin nhắn trong nhóm</option>
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      @{a.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Ticket liên quan
                <select
                  value={ticketId}
                  onChange={(e) => setTicketId(e.target.value)}
                >
                  <option value="">Không đính kèm</option>
                  {tickets.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} · {c.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Nội dung
              <textarea
                required
                maxLength={2000}
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Ví dụ: tổng hợp tiến độ xử lý ticket này…"
              />
            </label>
            <button disabled={!text.trim()}>Gửi tin nhắn</button>
          </form>
        </section>
        <aside className="ws-card">
          <h2>Agent trong nhóm</h2>
          <div className="ws-row">
            {agents.map((a) => (
              <button
                className="ws-secondary"
                key={a.id}
                onClick={() => setAgentId(a.id)}
              >
                @{a.name}
              </button>
            ))}
          </div>
          <form
            className="ws-stack"
            onSubmit={(e) => {
              e.preventDefault();
              if (
                w.run(
                  (s) => createAgent(s, actor, name, specialty),
                  "Đã tạo agent mẫu và thêm vào nhóm.",
                )
              )
                setName("");
            }}
          >
            <h3>Tạo agent</h3>
            <label>
              Tên agent
              <input
                required
                minLength={2}
                maxLength={50}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Chuyên môn
              <select
                value={specialty}
                onChange={(e) =>
                  setSpecialty(e.target.value as Agent["specialty"])
                }
              >
                <option value="technical">Kỹ thuật</option>
                <option value="security">An ninh</option>
                <option value="reception">Lễ tân</option>
                <option value="report">Báo cáo</option>
              </select>
            </label>
            <button>Thêm vào nhóm</button>
          </form>
          <p className="ws-demo-actions">
            Agent trả lời mẫu để duyệt UI. Việc tạo agent thật và chọn ngữ cảnh
            do backend thực hiện.
          </p>
          <a href="/operations/reports">Tạo báo cáo →</a>
        </aside>
      </div>
      <section>
        <h2>Bảng công việc · {tickets.length} ticket</h2>
        <div className="ws-board">
          {[
            { label: "Chờ / đã giao", match: ["queued", "assigned"] },
            {
              label: "Đang xử lý / chờ duyệt",
              match: [
                "on-site",
                "working",
                "awaiting-consent",
                "isolation-requested",
                "isolation-approved",
                "outage-notified",
                "isolated",
                "restored",
                "awaiting-confirmation",
                "controlled",
                "cancel-requested",
              ],
            },
            { label: "Đã đóng", match: ["completed", "cancelled"] },
          ].map((column) => (
            <div className="ws-card" key={column.label}>
              <h3>{column.label}</h3>
              {tickets
                .filter((c) => column.match.includes(c.stage))
                .map((c) => (
                  <a
                    className="ws-ticket"
                    key={c.id}
                    href={`/operations/dispatch?ticket=${c.id}`}
                  >
                    <span className="ws-status">{c.severity}</span>
                    <strong>{c.title}</strong>
                    <p>
                      {c.id} · {stageLabels[c.stage]}
                    </p>
                  </a>
                ))}
              {!tickets.some((c) => column.match.includes(c.stage)) && (
                <p>Chưa có ticket.</p>
              )}
            </div>
          ))}
        </div>
      </section>
    </WorkspaceFrame>
  );
}
