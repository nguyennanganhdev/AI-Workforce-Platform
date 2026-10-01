import { useRef, useState } from "react";
import { ReportForm, type ReportSelection } from "./ReportsPage";
import { WorkspaceFrame } from "./WorkspaceFrame";

type CatalogItem = { id: string; name: string };
type ReportRow = {
  month: string; incident_type?: string; incident_count?: number;
  invoice_count?: number; net_amount?: string; tax_amount?: string;
  billed_amount?: string; currency?: string;
};

export function LiveReportsPage({ buildings, categories }: { buildings: CatalogItem[]; categories: CatalogItem[] }) {
  const [building, setBuilding] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const [result, setResult] = useState<{selection: ReportSelection; query: string; endpoint: string; rows: ReportRow[]} | null>(null);
  async function queryReport(selection: ReportSelection) {
    if (locked.current) return;
    if (!building || (selection.kind === "revenue" && !category)) {
      setError(!building ? "Chọn tòa nhà cần báo cáo." : "Chọn loại dịch vụ cho báo cáo hóa đơn."); return;
    }
    const start = new Date(`${selection.from}T00:00:00Z`);
    const end = new Date(`${selection.to}T00:00:00Z`);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || start > end) {
      setError("Khoảng ngày báo cáo không hợp lệ."); return;
    }
    locked.current = true; setBusy(true); setError(""); setResult(null);
    // The form's final day is inclusive; the API uses a half-open date interval.
    end.setUTCDate(end.getUTCDate() + 1);
    const query = new URLSearchParams({buildingId: building, fromDate: selection.from, toDate: end.toISOString().slice(0,10)});
    if (selection.kind === "revenue") query.set("categoryId", category);
    const endpoint = selection.kind === "revenue" ? "issued-revenue" : "incident-frequency";
    try {
      const response = await fetch(`/api/business/reports/${endpoint}?${query}`, {credentials: "include"});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Không tải được báo cáo.");
      setResult({selection, query: query.toString(), endpoint, rows: data.items});
    } catch (e) { setError(e instanceof Error ? e.message : "Lỗi kết nối."); }
    finally { locked.current = false; setBusy(false); }
  }
  async function download() {
    if (!result || locked.current) return;
    locked.current = true; setBusy(true); setError("");
    try {
      const response = await fetch(`/api/business/reports/${result.endpoint}.docx?${result.query}`, {credentials: "include"});
      if (!response.ok) throw new Error("Không xuất được DOCX. Kiểm tra phiên đăng nhập và quyền truy cập.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = `${result.endpoint}.docx`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e instanceof Error ? e.message : "Lỗi tải file."); }
    finally { locked.current = false; setBusy(false); }
  }
  return <WorkspaceFrame title="Báo cáo vận hành" description="Tổng hợp theo tòa nhà và khoảng thời gian được chọn."
    connectedAccount={{role: "manager", scope: "được cấp trên hệ thống"}} error={error}>
    {!buildings.length && <p className="ws-empty">Chưa có tòa nhà trong danh mục. Cần cấu hình dữ liệu tòa nhà trước khi tạo báo cáo.</p>}
    <ReportForm busy={busy} onSubmit={queryReport}>
      <label>Tòa nhà<select required value={building} onChange={e => setBuilding(e.target.value)}>
        <option value="">Chọn tòa nhà</option>{buildings.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
      </select></label>
      <label>Loại dịch vụ (báo cáo hóa đơn)<select value={category} onChange={e => setCategory(e.target.value)}>
        <option value="">Chọn loại dịch vụ</option>{categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label>
    </ReportForm>
    {result && <article className="ws-card"><h2>{result.selection.name}</h2>
      <p>{result.selection.from} → {result.selection.to}</p>
      <div className="ws-table-scroll"><table className="ws-table"><thead><tr><th>Tháng</th>
        {result.selection.kind === "frequency" ? <><th>Loại sự cố</th><th>Số sự cố</th></> : <><th>Số hóa đơn</th><th>Trước thuế</th><th>Thuế</th><th>Tổng giá trị</th></>}
      </tr></thead><tbody>{result.rows.map((row, i) => <tr key={`${row.month}-${i}`}><td>{row.month}</td>
        {result.selection.kind === "frequency" ? <><td>{row.incident_type}</td><td>{row.incident_count}</td></> : <><td>{row.invoice_count}</td><td>{row.net_amount}</td><td>{row.tax_amount}</td><td>{row.billed_amount} {row.currency}</td></>}
      </tr>)}</tbody></table></div>
      {!result.rows.length && <p>Không có dữ liệu trong kỳ đã chọn.</p>}
      <button disabled={busy} onClick={() => void download()}>Tải DOCX</button>
    </article>}
  </WorkspaceFrame>;
}
