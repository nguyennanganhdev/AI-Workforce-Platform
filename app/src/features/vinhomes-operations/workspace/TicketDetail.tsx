import { useEffect, useState } from "react";
import { caseAction, type CaseAction } from "./service";
import { stageLabels } from "./model";
import { useWorkspace } from "./use-workspace";
import { WorkspaceFrame } from "./WorkspaceFrame";
async function photoData(file: File): Promise<string> {
  if (
    !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
    file.size > 10 * 1024 * 1024
  )
    throw new Error("Chọn ảnh JPG, PNG hoặc WebP, tối đa 10 MB.");
  const bitmap = await createImageBitmap(file);
  try {
    const ratio = Math.min(1, 1000 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * ratio));
    canvas.height = Math.max(1, Math.round(bitmap.height * ratio));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Trình duyệt không hỗ trợ xử lý ảnh.");
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.75);
  } finally {
    bitmap.close();
  }
}

export function TicketDetail({
  ticketId,
  onBack,
}: {
  ticketId: string;
  onBack: () => void;
}) {
  const w = useWorkspace();
  const [worker, setWorker] = useState(""),
    [reason, setReason] = useState(""),
    [uploading, setUploading] = useState(false);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);
  const account = w.account;
  if (
    !account ||
    !["manager", "technical", "security", "sanitation"].includes(account.role)
  )
    return <p role="alert">Bạn không có quyền xem công việc này.</p>;
  const manager = account.role === "manager";
  const c = w.state.cases.find(
    (t) =>
      t.id === ticketId &&
      t.scope === account.scope &&
      (manager || t.workerId === account.id),
  );
  const closed = c && ["completed", "cancelled"].includes(c.stage);
  const urgent = c?.domain === "security" && ["P0", "P1"].includes(c.severity);
  const act = (action: CaseAction, value = "") => {
    if (c) w.run((s) => caseAction(s, account.id, c.id, action, value));
  };
  const action = (id: CaseAction, label: string, disabled = false) => (
    <button
      key={id}
      type="button"
      disabled={disabled || uploading}
      onClick={() => act(id)}
    >
      {label}
    </button>
  );
  return (
    <WorkspaceFrame
      title={manager ? "Chi tiết công việc" : "Xử lý công việc"}
      description="Theo dõi cùng một hồ sơ xuyên suốt quá trình xử lý."
      error={w.error}
      notice={w.notice}
    >
      <button className="ws-back" onClick={onBack}>
        ← {manager ? "Phân công công việc" : "Việc của tôi"}
      </button>
      {!c && (
        <p role="alert" className="ws-empty">
          Không tìm thấy công việc hoặc bạn không được cấp quyền xem.
        </p>
      )}
      {c && (
        <section className="ws-card" key={c.id}>
          <div className="ws-row between">
            <h2>{c.title}</h2>
            <span className="ws-status" data-status={c.severity}>
              {c.severity}
            </span>
          </div>
          <p>
            {c.id} · {c.scope} · {c.apartment}
          </p>
          <p>
            Cư dân: {c.resident} · <a href={`tel:${c.phone}`}>{c.phone}</a>
          </p>
          <p>
            Nhân viên:{" "}
            {w.state.accounts.find((a) => a.id === c.workerId)?.name ||
              "Chưa phân công"}
          </p>
          <span className="ws-status" data-status={c.stage}>
            {stageLabels[c.stage]}
          </span>
          {c.domain === "security" && (
            <div className="ws-notice">
              <p>
                Camera khu vực:{" "}
                {c.camera === "online"
                  ? "Có dữ liệu camera (mẫu)"
                  : c.camera === "offline"
                    ? "Camera mất kết nối"
                    : "Chưa xác định"}
                . Chưa kết nối luồng camera trực tiếp.
              </p>
              {urgent && (
                <p>
                  Cảnh báo người trực:{" "}
                  <strong>
                    {c.alertAcknowledged
                      ? "Đã xác nhận tiếp nhận"
                      : "Đang chờ xác nhận"}
                  </strong>{" "}
                  · Đã chuyển cấp {c.escalation} lần. Xác minh hiện trường, kiểm
                  soát sự cố và bổ sung bằng chứng trước khi BQL đóng ticket.
                </p>
              )}
            </div>
          )}
          {!closed && (
            <>
              {manager && ["queued", "assigned"].includes(c.stage) && (
                <form
                  className="ws-card"
                  onSubmit={(e) => {
                    e.preventDefault();
                    act("assign", worker);
                  }}
                >
                  <label>
                    Phân công nhân viên
                    <select
                      required
                      value={worker}
                      onChange={(e) => setWorker(e.target.value)}
                    >
                      <option value="">Chọn nhân viên</option>
                      {w.state.accounts
                        .filter(
                          (a) =>
                            a.status === "active" &&
                            a.scope === c.scope &&
                            a.role ===
                              (c.domain === "security"
                                ? "security"
                                : "technical"),
                        )
                        .map((a) => {
                          const busy =
                            !a.available ||
                            w.state.cases.some(
                              (t) =>
                                t.workerId === a.id &&
                                t.id !== c.id &&
                                !["completed", "cancelled"].includes(t.stage),
                            );
                          return (
                            <option key={a.id} value={a.id}>
                              {a.name} ·{" "}
                              {busy ? "Bận · đưa vào hàng chờ" : "Sẵn sàng"}
                            </option>
                          );
                        })}
                    </select>
                  </label>
                  <button className="ws-primary">Xác nhận phân công</button>
                </form>
              )}
              <div className="ws-row">
                {c.stage === "assigned" &&
                  action("arrive", "Đã đến hiện trường")}
                {urgent &&
                  !c.alertAcknowledged &&
                  action("acknowledge", "Người trực xác nhận cảnh báo")}
                {((c.stage === "queued" && Date.parse(c.dueAt) <= now) ||
                  (urgent && !c.alertAcknowledged && c.stage !== "queued")) &&
                  action("escalate", "Báo trưởng ca / người tiếp theo")}
                {c.stage === "on-site" &&
                  c.domain !== "security" &&
                  !c.consent &&
                  action("ask-consent", "Đề nghị cư dân đồng ý sửa chữa")}
                {c.stage === "on-site" && c.domain === "water" && (
                  <label>
                    Đánh giá sự cố nước
                    <select
                      aria-label="Đánh giá sự cố nước"
                      value={c.majorWater ? "major" : "minor"}
                      onChange={(e) => act("classify-water", e.target.value)}
                    >
                      <option value="major">Cần khóa nước khu vực</option>
                      <option value="minor">
                        Sửa cục bộ, không khóa khu vực
                      </option>
                    </select>
                  </label>
                )}
                {c.stage === "on-site" &&
                  c.domain === "water" &&
                  c.majorWater &&
                  c.consent &&
                  action("request-isolation", "Đề nghị BQL duyệt khóa nước")}
                {c.stage === "isolation-requested" &&
                  manager &&
                  action("approve-isolation", "BQL duyệt khóa nước")}
                {c.stage === "isolation-approved" &&
                  manager &&
                  action("notify-outage", "Tạo thông báo cắt nước mẫu")}
                {c.stage === "outage-notified" &&
                  action("isolate", "Xác nhận đã khóa van")}
                {["on-site", "isolated"].includes(c.stage) &&
                  action(
                    "start",
                    "Bắt đầu xử lý",
                    (c.domain !== "security" && !c.consent) ||
                      (c.majorWater &&
                        c.domain === "water" &&
                        c.stage !== "isolated") ||
                      (!!urgent && !c.alertAcknowledged),
                  )}
                {c.stage === "working" &&
                  c.domain === "water" &&
                  c.majorWater &&
                  action(
                    "restore",
                    "Mở nước và thông báo khôi phục",
                    !c.evidence.length,
                  )}
                {["working", "restored"].includes(c.stage) &&
                  action(
                    "submit",
                    urgent
                      ? "Báo đã kiểm soát sự cố"
                      : "Gửi kết quả cho cư dân",
                    !c.evidence.length ||
                      (c.domain === "water" &&
                        c.majorWater &&
                        c.stage !== "restored"),
                  )}
                {c.stage === "controlled" &&
                  manager &&
                  action("manager-close", "BQL xác nhận hoàn tất")}
                {c.stage === "cancel-requested" &&
                  manager &&
                  action("approve-cancel", "BQL duyệt hủy điều động")}
              </div>
              {["awaiting-consent", "awaiting-confirmation"].includes(
                c.stage,
              ) && (
                <div className="ws-demo-actions">
                  <strong>Sự kiện cư dân · chỉ để kiểm thử UI</strong>
                  <p>
                    Backend sẽ đưa phản hồi thật của cư dân vào ticket. Nút dưới
                    đây chỉ mô phỏng sự kiện.
                  </p>
                  {c.stage === "awaiting-consent"
                    ? action("resident-consent", "Mô phỏng cư dân đồng ý")
                    : action(
                        "resident-confirm",
                        "Mô phỏng cư dân xác nhận hoàn tất",
                      )}
                </div>
              )}
              {["on-site", "working", "restored", "controlled"].includes(
                c.stage,
              ) && (
                <label>
                  Bằng chứng hiện trường ({c.evidence.length}/3)
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={uploading || c.evidence.length >= 3}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (!file) return;
                      const ticket = c.id;
                      setUploading(true);
                      try {
                        const photo = await photoData(file);
                        w.run((s) =>
                          caseAction(s, account.id, ticket, "evidence", photo),
                        );
                      } catch (err) {
                        w.setError(
                          err instanceof Error
                            ? err.message
                            : "Không đọc được ảnh.",
                        );
                      } finally {
                        setUploading(false);
                      }
                    }}
                  />
                  {uploading && <span role="status">Đang xử lý ảnh…</span>}
                </label>
              )}
              {(["queued", "assigned", "on-site"].includes(c.stage) ||
                (c.domain === "security" &&
                  !urgent &&
                  ["working", "awaiting-confirmation"].includes(c.stage))) && (
                <details>
                  <summary>Đánh giá lại / đề nghị hủy</summary>
                  <label>
                    Lý do (ít nhất 8 ký tự)
                    <textarea
                      maxLength={1000}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </label>
                  <div className="ws-row">
                    {c.domain === "security" && !urgent && (
                      <button
                        onClick={() => act("raise-emergency", reason)}
                        disabled={reason.trim().length < 8}
                      >
                        Nâng lên P0, cảnh báo người trực
                      </button>
                    )}
                    {!urgent &&
                      ["queued", "assigned", "on-site"].includes(c.stage) && (
                        <button
                          onClick={() => act("request-cancel", reason)}
                          disabled={reason.trim().length < 8}
                        >
                          Đề nghị hủy điều động
                        </button>
                      )}
                  </div>
                </details>
              )}
            </>
          )}
          <div className="ws-photo-grid">
            {c.evidence.map((src, i) => (
              <a href={src} target="_blank" rel="noreferrer" key={i}>
                <img src={src} alt={`Bằng chứng hiện trường ${i + 1}`} />
              </a>
            ))}
          </div>
          <h3>Tiến trình xử lý</h3>
          <ol className="ws-timeline">
            {c.events.map((e) => (
              <li key={e.id}>
                <small>
                  {new Date(e.at).toLocaleString("vi-VN")} · {e.actor}
                </small>
                <p>{e.label}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </WorkspaceFrame>
  );
}
