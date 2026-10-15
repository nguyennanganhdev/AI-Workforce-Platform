import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Cable, Check, Copy, Download, Eye, EyeOff, KeyRound, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { businessHeaders } from "@/lib/business-headers";
import { AdminBadge, AdminPage, AdminState, absoluteTime } from "./AdminUI";
import { adminRequest } from "./queries";
import "./platform-connection.css";

type Secret = "customer_key" | "provider_key" | "signing_secret";
type Route = { route_id: string; revision: number; status: string; confirmed_at: string };
type CheckResult = { ok: boolean; checked_at: string; url: string; checks: { key: string; ok: boolean; code: string }[]; signing: string };
export type Connection = {
  version: number; source: "admin" | "environment"; enabled: boolean; url: string; signing_key_id: string;
  encryption_ready: boolean; secrets_configured: Record<Secret, boolean>; updated_at: string | null;
  worker_seen_at: string | null; worker_version: number | null; last_check: CheckResult | null;
  counts: { active_workflows: number; pending_commands: number; failed_commands: number; pending_events: number; rejected_events: number };
  units: { code: string; name: string; route: Route | null }[];
  mcp: { url: string; transport: string; configured: boolean; grant_path: string; ttl_seconds: number; tools: string[] };
};
const path = "/admin/platform-connection";
const queryKey = ["admin", "platform-connection"];
const labels: Record<Secret, string> = { customer_key: "Customer key", provider_key: "Provider key", signing_secret: "Signing secret" };
const explanations: Record<Secret, string> = {
  customer_key: "Domain gửi ticket, đọc phản hồi và xác nhận tuyến.",
  provider_key: "Domain gửi tiến độ staff và đọc biên nhận sự kiện.",
  signing_secret: "Ký HMAC cho các sự kiện tiến độ gửi Platform.",
};
type Draft = { url: string; signing_key_id: string } & Record<Secret, string>;
const empty: Draft = { url: "", signing_key_id: "", customer_key: "", provider_key: "", signing_secret: "" };

function SecretField({ name, value, configured, disabled, onChange, error }: { name: Secret; value: string; configured: boolean; disabled: boolean; onChange: (value: string) => void; error?: string }) {
  const [visible, setVisible] = useState(false);
  return <div className="platform-field"><div className="platform-field-label"><label htmlFor={name}>{labels[name]}</label>{configured && <span><Check size={13} aria-hidden="true" /> Đã lưu</span>}</div>
    <div className="platform-secret"><Input id={name} type={visible ? "text" : "password"} value={value} autoComplete="new-password" spellCheck={false} disabled={disabled} maxLength={4096}
      placeholder={configured ? "Để trống để giữ khóa hiện tại" : "Nhập khóa Platform cấp"} aria-invalid={!!error} aria-describedby={`${name}-hint${error ? ` ${name}-error` : ""}`} onChange={e => onChange(e.target.value)} />
      <Button type="button" variant="ghost" aria-label={`${visible ? "Ẩn" : "Hiện"} ${labels[name]}`} aria-pressed={visible} onClick={() => setVisible(!visible)} disabled={disabled}>{visible ? <EyeOff size={16} /> : <Eye size={16} />}</Button></div>
    <small id={`${name}-hint`}>{explanations[name]}</small>{error && <small className="platform-field-error" id={`${name}-error`}>{error}</small>}</div>;
}

function RouteRow({ unit, version, disabled, onConfirm }: { unit: Connection["units"][number]; version: number; disabled: boolean; onConfirm: (body: { version: number; management_ref: string; route_id: string; revision: number }) => Promise<void> }) {
  const [id, setId] = useState(unit.route?.route_id || "");
  const [revision, setRevision] = useState(String(unit.route?.revision || 1));
  const [submitting, setSubmitting] = useState(false);
  return <form className="platform-route" onSubmit={async e => { e.preventDefault(); setSubmitting(true); try { await onConfirm({ version, management_ref: unit.code, route_id: id.trim(), revision: Number(revision) }); } finally { setSubmitting(false); } }}>
    <div className="platform-route-unit"><strong>{unit.name}</strong><code>{unit.code}</code>{unit.route && <AdminBadge tone="ok">Đã xác nhận · v{unit.route.revision}</AdminBadge>}</div>
    <div className="platform-field"><label htmlFor={`route-${unit.code}`}>Mã tuyến Platform</label><Input id={`route-${unit.code}`} value={id} onChange={e => setId(e.target.value)} required maxLength={200} disabled={disabled || submitting} placeholder="Route ID do Platform cấp" /></div>
    <div className="platform-field"><label htmlFor={`revision-${unit.code}`}>Revision</label><Input id={`revision-${unit.code}`} type="number" min={1} step={1} required value={revision} onChange={e => setRevision(e.target.value)} disabled={disabled || submitting} /></div>
    <Button type="submit" variant="outline" disabled={disabled || submitting || !id.trim() || Number(revision) < 1 || (unit.route?.route_id === id && unit.route?.revision === Number(revision))}>{submitting ? "Đang xác nhận…" : unit.route?.route_id === id && unit.route?.revision === Number(revision) ? "Đã xác nhận" : "Xác nhận tuyến"}</Button>
  </form>;
}

export function PlatformConnectionPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey, queryFn: () => adminRequest<Connection>(path), refetchInterval: 10_000 });
  const data = query.data;
  const [tab, setTab] = useState<"connection" | "routes" | "mcp">("connection");
  const [draft, setDraft] = useState<Draft>(empty);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null);
  const [checked, setChecked] = useState<CheckResult | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => { if (data) { setDraft({ ...empty, url: data.url, signing_key_id: data.signing_key_id }); setChecked(null); } }, [data?.version]); // Keep unsaved fields while status refreshes.
  const dirty = !!data && (draft.url !== data.url || draft.signing_key_id !== data.signing_key_id || Object.keys(labels).some(k => !!draft[k as Secret]));
  const body = (enabled = data?.enabled || false) => ({ version: data?.version || 0, enabled, url: draft.url.trim(), signing_key_id: draft.signing_key_id.trim(),
    ...Object.fromEntries(Object.keys(labels).filter(k => draft[k as Secret]).map(k => [k, draft[k as Secret]])) });
  const change = (key: keyof Draft, value: string) => { setDraft(v => ({ ...v, [key]: value })); setChecked(null); setNotice(null); setErrors(v => ({ ...v, [key]: "" })); };
  const run = async (key: string, action: () => Promise<void>) => { setBusy(key); setNotice(null); setErrors({}); try { await action(); } catch (e) { setErrors((e as {fieldErrors?: Record<string, string>})?.fieldErrors || {}); setNotice({ text: e instanceof Error ? e.message : "Không thực hiện được thao tác.", error: true }); } finally { setBusy(null); } };
  const accept = (value: Connection) => { client.setQueryData(queryKey, value); setDraft({ ...empty, url: value.url, signing_key_id: value.signing_key_id }); setChecked(null); };
  const save = (e: FormEvent) => { e.preventDefault(); void run("save", async () => { accept(await adminRequest<Connection>(path, { method: "PUT", body: body() })); setNotice({ text: "Đã lưu. API áp dụng ngay; worker tự đồng bộ cấu hình." }); }); };
  const check = () => void run("check", async () => { const result = await adminRequest<CheckResult>(`${path}/check`, { method: "POST", body: body(false) }); setChecked(result); setNotice({ text: result.ok ? "Customer key và Provider key được chấp nhận." : "Kiểm tra chưa đạt. Xem kết quả từng khóa bên dưới.", error: !result.ok }); });
  const toggle = () => void run("toggle", async () => { const enabled = !data?.enabled; accept(await adminRequest<Connection>(path, { method: "PUT", body: body(enabled) })); setNotice({ text: enabled ? "Đã bật bàn giao ticket và đồng bộ tiến độ sang Platform." : "Đã tắt kết nối Platform. Cấu hình được giữ để dùng lại." }); });
  const exportMcp = () => void run("export", async () => {
    const response = await fetch(`/api/business${path}/mcp-export`, { method: "POST", credentials: "include", headers: businessHeaders() });
    if (!response.ok) throw new Error("Không xuất được bộ kết nối MCP. Kiểm tra quyền và trạng thái MCP.");
    const url = URL.createObjectURL(await response.blob()); const a = document.createElement("a"); a.href = url; a.download = "vinhomes-platform-connection.zip"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice({ text: "Đã tải bộ kết nối có token riêng tư. Chỉ bàn giao cho người vận hành Platform." });
  });
  if (!data) return <AdminPage title="Kết nối Platform"><AdminState loading={query.isPending} error={query.error} onRetry={() => void query.refetch()} /></AdminPage>;
  const activeRoutes = data.units.filter(u => u.route?.status === "active").length;
  const result = checked || data.last_check;
  const workerCurrent = !!data.worker_seen_at && Date.now() - new Date(data.worker_seen_at).getTime() < 60_000 && data.worker_version === data.version;
  return <div className="ops-platform"><AdminPage title="Kết nối Platform" meta="Điều phối yêu cầu cư dân" action={<Button variant="ghost" disabled={!!busy} onClick={() => void query.refetch()} aria-label="Làm mới trạng thái kết nối"><RefreshCw size={16} /> Làm mới</Button>}>
    <section className="ops-admin-panel platform-summary" aria-label="Trạng thái kết nối"><span className="platform-icon"><Cable size={22} aria-hidden="true" /></span><div><h2>Domain Vinhome ↔ Platform</h2><p>Reception bàn giao ticket; Platform giao việc và nhận tiến độ từ staff.</p></div><AdminBadge tone={data.enabled ? "ok" : "neutral"}>{data.enabled ? "Đang bật" : "Đang tắt"}</AdminBadge></section>
    <div className="platform-tabs" role="tablist" aria-label="Cấu hình Platform">{([{ key: "connection", label: "Cấu hình kết nối" }, { key: "routes", label: "Tuyến đơn vị" }, { key: "mcp", label: "Bàn giao MCP" }] as const).map((t, index, tabs) => <button key={t.key} type="button" role="tab" id={`tab-${t.key}`} tabIndex={tab === t.key ? 0 : -1} aria-selected={tab === t.key} aria-controls={`panel-${t.key}`} onClick={() => { setTab(t.key); setNotice(null); }} onKeyDown={e => {
      const next = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : e.key === "ArrowRight" ? (index + 1) % tabs.length : e.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : -1;
      if (next >= 0) { e.preventDefault(); setTab(tabs[next].key); document.getElementById(`tab-${tabs[next].key}`)?.focus(); }
    }}>{t.label}</button>)}</div>
    {notice && <div className="platform-feedback" data-error={!!notice.error} role={notice.error ? "alert" : "status"}>{notice.text}</div>}
    {query.error && <div className="platform-feedback" data-error role="alert">Không làm mới được trạng thái. Dữ liệu đang hiển thị là lần tải trước.</div>}
    {tab === "connection" && <div role="tabpanel" id="panel-connection" aria-labelledby="tab-connection" className="platform-layout">
      <section className="ops-admin-panel"><header className="ops-admin-panel-title"><h2>Máy chủ và thông tin xác thực</h2><KeyRound size={16} aria-hidden="true" /></header>
        <form onSubmit={save} className="platform-form"><p>Nhập thông tin Platform cấp cho Domain. Khóa đã lưu được mã hóa và không trả lại trình duyệt.</p>
          {!data.encryption_ready && <div className="platform-feedback" data-error role="alert">Máy chủ chưa có khóa mã hóa cấu hình. Liên hệ người vận hành để thiết lập một lần.</div>}
          <div className="platform-field"><label htmlFor="platform-url">URL Platform</label><Input id="platform-url" type="url" placeholder="https://platform.example.com" value={draft.url} maxLength={500} disabled={!!busy} onChange={e => change("url", e.target.value)} aria-invalid={!!errors.url} aria-describedby={`platform-url-hint${errors.url ? " platform-url-error" : ""}`} /><small id="platform-url-hint">URL gốc mà máy chủ Domain truy cập được. Không thêm /workforce/v1. Địa chỉ localhost của máy bạn không phải địa chỉ Platform cho VPS.</small>{errors.url && <small id="platform-url-error" className="platform-field-error">{errors.url}</small>}</div>
          <div className="platform-fields">{(["customer_key", "provider_key"] as const).map(name => <SecretField key={name} name={name} value={draft[name]} configured={data.secrets_configured[name]} disabled={!!busy} error={errors[name]} onChange={v => change(name, v)} />)}
            <div className="platform-field"><label htmlFor="signing-key-id">Signing key ID</label><Input id="signing-key-id" value={draft.signing_key_id} maxLength={160} disabled={!!busy} onChange={e => change("signing_key_id", e.target.value)} autoComplete="off" /><small>Mã khóa ký do Platform cấp.</small></div>
            <SecretField name="signing_secret" value={draft.signing_secret} configured={data.secrets_configured.signing_secret} disabled={!!busy} error={errors.signing_secret} onChange={v => change("signing_secret", v)} />
          </div>
          <div className="platform-actions"><Button type="submit" disabled={!!busy || !data.encryption_ready || (!dirty && data.source === "admin")}>{busy === "save" ? "Đang lưu…" : "Lưu cấu hình"}</Button><Button type="button" variant="outline" disabled={!!busy || !draft.url.trim()} onClick={check}>{busy === "check" ? "Đang kiểm tra…" : "Kiểm tra kết nối"}</Button>{dirty && <span>Thay đổi chưa lưu</span>}</div>
          {result && <section className="platform-check" aria-label="Kết quả kiểm tra"><strong>{result.ok ? "Xác thực API đạt" : "Xác thực API chưa đạt"}</strong><small>{result.url} · {absoluteTime(result.checked_at)}</small>{result.checks.map(c => <div key={c.key}><span>{labels[c.key as Secret] || c.key}</span><AdminBadge tone={c.ok ? "ok" : "danger"}>{c.ok ? "Được chấp nhận" : c.code === "UNREACHABLE" ? "Không kết nối được" : c.code === "AUTH_REFUSED" ? "Khóa bị từ chối" : "Sai endpoint hoặc contract"}</AdminBadge></div>)}<p>Kiểm tra chỉ đọc API, không gọi Agent. Chữ ký HMAC và luồng nghiệp vụ cần nghiệm thu bằng sự kiện thực tế.</p></section>}
        </form></section>
      <aside><section className="ops-admin-panel"><header className="ops-admin-panel-title"><h2>Áp dụng cấu hình</h2></header><div className="platform-form"><dl className="platform-facts"><div><dt>Nguồn cấu hình</dt><dd>{data.source === "admin" ? "Quản trị Domain" : "Env máy chủ"}</dd></div><div><dt>Worker</dt><dd>{data.source === "environment" ? "Chưa có cấu hình UI" : workerCurrent ? "Đã đồng bộ" : "Chờ đồng bộ"}</dd></div><div><dt>Tuyến đã xác nhận</dt><dd>{activeRoutes}/{data.units.length}</dd></div></dl>
        <p>Lưu cấu hình → xác nhận tuyến do Platform cấp → bật kết nối. Chỉ đơn vị có tuyến xác nhận được bàn giao ticket mới.</p>
        <Button variant={data.enabled ? "outline" : "default"} disabled={!!busy || dirty || !data.encryption_ready || (!data.enabled && !activeRoutes) || (data.enabled && data.counts.active_workflows > 0)} onClick={toggle}>{busy === "toggle" ? "Đang áp dụng…" : data.enabled ? "Tắt kết nối" : "Bật kết nối"}</Button>
        {data.counts.active_workflows > 0 && <small>Hoàn tất workflow đang mở trước khi tắt hoặc đổi máy chủ.</small>}</div></section>
        <section className="ops-admin-panel"><header className="ops-admin-panel-title"><h2>Tồn đọng đồng bộ</h2></header><dl className="platform-facts platform-form">{([
          ["Workflow đang mở", data.counts.active_workflows], ["Lệnh chờ gửi", data.counts.pending_commands], ["Lệnh lỗi", data.counts.failed_commands], ["Sự kiện chờ xử lý", data.counts.pending_events], ["Sự kiện bị từ chối", data.counts.rejected_events],
        ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section></aside>
    </div>}
    {tab === "routes" && <section role="tabpanel" id="panel-routes" aria-labelledby="tab-routes" className="ops-admin-panel"><header className="ops-admin-panel-title"><h2>Đơn vị được bàn giao yêu cầu</h2></header><div className="platform-form"><p>Người vận hành Platform cấp Route ID và revision cho từng mã đơn vị. Xác nhận tại đây trước khi bật bàn giao.</p>{(dirty || !data.version) && <div className="platform-feedback">Lưu cấu hình kết nối trước khi xác nhận tuyến.</div>}
      {data.units.map(unit => <RouteRow key={`${unit.code}-${unit.route?.revision || 0}-${unit.route?.route_id || ""}`} unit={unit} version={data.version} disabled={!!busy || dirty || !data.version} onConfirm={b => run("route", async () => { accept(await adminRequest<Connection>(`${path}/routes/confirm`, { method: "POST", body: b })); setNotice({ text: `Đã xác nhận tuyến cho ${unit.name}.` }); })} />)}
      {!data.units.length && <AdminState empty="Chưa có đơn vị quản lý hoạt động. Tạo đơn vị trước khi cấu hình tuyến." />}</div></section>}
    {tab === "mcp" && <section role="tabpanel" id="panel-mcp" aria-labelledby="tab-mcp" className="ops-admin-panel"><header className="ops-admin-panel-title"><h2>Platform gọi vào Domain</h2><AdminBadge tone={data.mcp.configured ? "ok" : "wait"}>{data.mcp.configured ? "MCP đã bật" : "MCP chưa bật"}</AdminBadge></header><div className="platform-form"><p>Bàn giao endpoint và token khởi tạo cho người vận hành Platform. Backend Platform cần đổi grant riêng cho mỗi ticket trước khi thực thi công cụ.</p>
      <div className="platform-endpoint"><code>{data.mcp.url}</code><Button variant="outline" aria-label="Sao chép địa chỉ MCP" onClick={() => void run("copy", async () => { await navigator.clipboard.writeText(data.mcp.url); setNotice({ text: "Đã sao chép địa chỉ MCP." }); })}><Copy size={16} /></Button></div>
      <dl className="platform-facts"><div><dt>Giao thức</dt><dd>Streamable HTTP</dd></div><div><dt>Endpoint cấp grant</dt><dd><code>{data.mcp.grant_path}</code></dd></div><div><dt>Thời hạn grant mặc định</dt><dd>60 phút</dd></div></dl>
      <div className="platform-tools">{data.mcp.tools.map(tool => <code key={tool}>{tool}</code>)}</div>
      <div className="platform-security"><ShieldCheck size={20} aria-hidden="true" /><p>Bộ tải xuống chứa token bí mật. Giữ ngoài Git và chỉ gửi qua kênh riêng cho người vận hành Platform. Mọi lần xuất được ghi nhật ký.</p></div>
      <Button disabled={!!busy || !data.mcp.configured} onClick={exportMcp}><Download size={16} />{busy === "export" ? "Đang xuất…" : "Tải bộ kết nối MCP"}</Button></div></section>}
  </AdminPage></div>;
}
