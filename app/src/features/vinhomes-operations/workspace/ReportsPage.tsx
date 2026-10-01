import { useState } from "react";
import { createReport, finishReport, reportRows } from "./service";
import { type ReportJob } from "./model";
import { createDocx } from "./docx";
import { useWorkspace } from "./use-workspace";
import { WorkspaceFrame } from "./WorkspaceFrame";

export function ReportsPage() {
  const w = useWorkspace();
  const [name, setName] = useState("Báo cáo vận hành"),
    [kind, setKind] = useState<ReportJob["kind"]>("frequency");
  const [from, setFrom] = useState(() =>
    new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10),
  );
  const [to, setTo] = useState(() => new Date().toISOString().slice(0, 10));
  if (w.account?.role !== "manager")
    return (
      <p role="alert">
        Chỉ ban quản lý được tạo báo cáo trong phạm vi được cấp.
      </p>
    );
  const actor = w.account.id,
    jobs = w.state.reports.filter((r) => r.scope === w.account!.scope);
  const currency = (n: number) => n.toLocaleString("vi-VN") + " ₫";
  function download(job: ReportJob) {
    try {
      const rows = reportRows(w.state, job);
      const lines = [
        job.name,
        "BÁO CÁO MẪU – dữ liệu thử nghiệm FE, không phải báo cáo tài chính chính thức",
        `Phạm vi: ${job.scope} | Từ ${job.from} đến ${job.to}`,
        job.kind === "revenue"
          ? "Doanh thu mẫu từ các ticket kỹ thuật hoàn tất. Backend cần thay bằng hóa đơn hợp lệ."
          : "Tần suất sự cố theo ngày tạo ticket trong tòa nhà.",
        ...rows.map(
          (c) =>
            `${c.id} | ${c.title} | ${c.domain} | ${c.createdAt.slice(0, 10)}${job.kind === "revenue" ? " | " + currency(c.amount) : ""}`,
        ),
        `Tổng số ticket: ${rows.length}`,
        ...(job.kind === "revenue"
          ? [
              `Tổng tiền mẫu: ${currency(rows.reduce((n, c) => n + c.amount, 0))}`,
            ]
          : ["electric", "water", "security"].map(
              (domain) =>
                `${domain}: ${rows.filter((c) => c.domain === domain).length}`,
            )),
      ];
      const blob = new Blob([createDocx(lines) as BlobPart], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      const url = URL.createObjectURL(blob),
        a = document.createElement("a");
      a.href = url;
      a.download = `bao-cao-mau-${job.scope}-${job.kind}-${job.from}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      w.setError("Không tạo được file. Vui lòng thử tải lại.");
    }
  }
  return (
    <WorkspaceFrame
      title="Báo cáo vận hành"
      description="Chọn loại báo cáo và thời gian. Kết quả luôn giới hạn trong tòa nhà được cấp."
      error={w.error}
      notice={w.notice}
    >
      <form
        className="ws-card"
        onSubmit={(e) => {
          e.preventDefault();
          w.run(
            (s) => createReport(s, actor, { name, kind, from, to }),
            "Đã đưa báo cáo mẫu vào hàng chờ.",
          );
        }}
      >
        <div className="ws-grid">
          <label>
            Tên báo cáo
            <input
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Loại báo cáo
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as ReportJob["kind"])}
            >
              <option value="frequency">Tần suất sự cố</option>
              <option value="revenue">Doanh thu kỹ thuật</option>
            </select>
          </label>
          <label>
            Từ ngày
            <input
              type="date"
              required
              value={from}
              max={to}
              onChange={(e) => setFrom(e.target.value)}
            />
          </label>
          <label>
            Đến ngày
            <input
              type="date"
              required
              value={to}
              min={from}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
        </div>
        <p className="ws-helper">
          Doanh thu hiện dùng số tiền mẫu trên ticket kỹ thuật đã hoàn tất; chưa
          kết nối hóa đơn hoặc thanh toán.
        </p>
        <button className="ws-primary">Tạo báo cáo mẫu</button>
      </form>
      {!jobs.length && (
        <p className="ws-empty">
          Chưa có báo cáo. Tạo báo cáo đầu tiên để xem trước và tải DOCX.
        </p>
      )}
      {jobs.map((r) => {
        const rows = reportRows(w.state, r);
        return (
          <article className="ws-card" key={r.id}>
            <div className="ws-row between">
              <h2>{r.name}</h2>
              <span className="ws-status" data-status={r.status}>
                {r.status === "queued"
                  ? "Đang chờ tạo"
                  : r.status === "ready"
                    ? "Sẵn sàng"
                    : "Tạo thất bại"}
              </span>
            </div>
            <p>
              {r.kind === "revenue" ? "Doanh thu kỹ thuật" : "Tần suất sự cố"} ·{" "}
              {r.scope} · {r.from} → {r.to}
            </p>
            {r.status !== "ready" && (
              <div className="ws-demo-actions">
                <p>
                  {r.error || "Mô phỏng tiến trình tạo báo cáo của backend."}
                </p>
                <div className="ws-row">
                  <button
                    onClick={() => w.run((s) => finishReport(s, actor, r.id))}
                  >
                    {r.status === "failed"
                      ? "Thử tạo lại bản mẫu"
                      : "Hoàn tất bản mẫu"}
                  </button>
                  {r.status === "queued" && (
                    <button
                      onClick={() =>
                        w.run((s) => finishReport(s, actor, r.id, true))
                      }
                    >
                      Mô phỏng lỗi
                    </button>
                  )}
                </div>
              </div>
            )}
            {r.status === "ready" && (
              <>
                <div className="ws-metrics">
                  <div>
                    <small>Số ticket</small>
                    <strong>{rows.length}</strong>
                  </div>
                  {r.kind === "revenue" ? (
                    <div>
                      <small>Tổng tiền mẫu</small>
                      <strong>
                        {currency(rows.reduce((n, c) => n + c.amount, 0))}
                      </strong>
                    </div>
                  ) : (
                    <div>
                      <small>Điện / Nước / An ninh</small>
                      <strong>
                        {["electric", "water", "security"]
                          .map((d) => rows.filter((c) => c.domain === d).length)
                          .join(" / ")}
                      </strong>
                    </div>
                  )}
                </div>
                <div className="ws-table-scroll">
                  <table className="ws-table">
                    <thead>
                      <tr>
                        <th>Ticket</th>
                        <th>Nội dung</th>
                        <th>Ngày tạo</th>
                        {r.kind === "revenue" && <th>Số tiền mẫu</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((c) => (
                        <tr key={c.id}>
                          <td>{c.id}</td>
                          <td>{c.title}</td>
                          <td>{c.createdAt.slice(0, 10)}</td>
                          {r.kind === "revenue" && (
                            <td>{currency(c.amount)}</td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!rows.length && (
                  <p>Không có dữ liệu trong khoảng thời gian này.</p>
                )}
                <button className="ws-primary" onClick={() => download(r)}>
                  Tải DOCX mẫu
                </button>
              </>
            )}
          </article>
        );
      })}
    </WorkspaceFrame>
  );
}
