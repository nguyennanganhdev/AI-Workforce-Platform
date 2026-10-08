import { useRef, useState } from "react";
import type { ReportSelection } from "./ReportsPage";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Download, BarChart3 } from 'lucide-react';
import { OpsSelect } from '../connected/ui';

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
  const [kind, setKind] = useState<ReportSelection['kind']>('frequency');
  const [from, setFrom] = useState(() => new Date(Date.now()-30*86400000).toLocaleDateString('en-CA', {timeZone:'Asia/Ho_Chi_Minh'}));
  const [to, setTo] = useState(() => new Date().toLocaleDateString('en-CA', {timeZone:'Asia/Ho_Chi_Minh'}));
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
  return <div className="flex flex-col gap-5">
    {error && <div role="alert" className="live-error">{error}<Button variant="outline" onClick={() => void queryReport({name:kind === 'frequency' ? 'Tần suất sự cố' : 'Giá trị hóa đơn đã phát hành',kind,from,to})}>Thử lại</Button></div>}
    {!buildings.length && <p className="ws-empty">Chưa có tòa nhà trong danh mục. Cần cấu hình dữ liệu tòa nhà trước khi tạo báo cáo.</p>}
    <form className="ops-page-panel" onSubmit={e => {e.preventDefault(); void queryReport({name:kind === 'frequency' ? 'Tần suất sự cố' : 'Giá trị hóa đơn đã phát hành',kind,from,to});}}>
      <div className="ops-panel-heading">Tạo báo cáo</div><div className="ops-form-grid">
      <label>Tòa nhà<OpsSelect label="Tòa nhà" value={building} onValueChange={setBuilding} options={buildings.map(b=>({value:b.id,label:b.name}))} disabled={busy} /></label>
      <label>Loại báo cáo<OpsSelect label="Loại báo cáo" value={kind} onValueChange={v=>setKind(v as ReportSelection['kind'])} options={[{value:'frequency',label:'Tần suất sự cố'},{value:'revenue',label:'Giá trị hóa đơn đã phát hành'}]} disabled={busy} /></label>
      {kind === 'revenue' && <label>Loại dịch vụ<OpsSelect label="Loại dịch vụ" value={category} onValueChange={setCategory} options={categories.map(c=>({value:c.id,label:c.name}))} disabled={busy} /></label>}
      <label>Từ ngày<Input type="date" required value={from} max={to} onChange={e=>setFrom(e.target.value)} disabled={busy} /></label>
      <label>Đến ngày<Input type="date" required value={to} min={from} onChange={e=>setTo(e.target.value)} disabled={busy} /></label>
      </div><div className="ops-panel-footer"><p>Giá trị hóa đơn đã phát hành chưa phải tiền đã thu.</p><Button type="submit" disabled={busy || !buildings.length}>{busy ? 'Đang tải…' : 'Xem báo cáo'}</Button></div>
    </form>
    {busy && !result && <Skeleton className="h-52" />}
    {!result && !busy && <div className="ops-page-panel ops-empty"><BarChart3 size={24} /><p>Chọn tòa nhà và khoảng thời gian để xem báo cáo.</p></div>}
    {result && <article className="ops-page-panel"><div className="ops-panel-heading"><h2>{result.selection.name}</h2><Button variant="outline" disabled={busy} onClick={() => void download()}><Download size={16} />Tải DOCX</Button></div><div className="p-5">
      <p>{result.selection.from} → {result.selection.to}</p>
      <div className="ws-table-scroll"><table className="ws-table"><thead><tr><th>Tháng</th>
        {result.selection.kind === "frequency" ? <><th>Loại sự cố</th><th>Số sự cố</th></> : <><th>Số hóa đơn</th><th>Trước thuế</th><th>Thuế</th><th>Tổng giá trị</th></>}
      </tr></thead><tbody>{result.rows.map((row, i) => <tr key={`${row.month}-${i}`}><td>{row.month}</td>
        {result.selection.kind === "frequency" ? <><td>{row.incident_type}</td><td>{row.incident_count}</td></> : <><td>{row.invoice_count}</td><td>{row.net_amount}</td><td>{row.tax_amount}</td><td>{row.billed_amount} {row.currency}</td></>}
      </tr>)}</tbody></table></div>
      {!result.rows.length && <p>Không có dữ liệu trong kỳ đã chọn.</p>}
      </div></article>}
  </div>;
}
