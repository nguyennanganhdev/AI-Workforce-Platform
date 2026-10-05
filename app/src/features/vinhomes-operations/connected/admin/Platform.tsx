import { useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IconRefresh } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { auditQueryOptions, exportAuditMutationOptions, createUnitMutationOptions, unitOptionsQueryOptions, modelsQueryOptions, unitsQueryOptions, type AuditEvent, type RoleModel } from "@/lib/admin/queries";

const select = "h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground";

function Page({ title, lead, action, children }: { title: string; lead: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-5xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{title}</h1>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">{lead}</p>
        </div>
        {action}
      </header>
      {children}
    </div>
  );
}

/** The management units of this organisation: what each covers and who works in it. */
export function UnitsPage() {
  const units = useQuery(unitsQueryOptions());
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const options = useQuery({ ...unitOptionsQueryOptions(), enabled: creating });
  const create = useMutation(createUnitMutationOptions(queryClient));
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [buildings, setBuildings] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const toggle = (id: string, selected: string[], set: (value: string[]) => void) =>
    set(selected.includes(id) ? selected.filter((value) => value !== id) : [...selected, id]);
  return (
    <Page title="Đơn vị quản lý" lead="Mỗi đơn vị phụ trách một số tòa nhà và có nhóm Ban quản lý riêng: phiên điều phối, agent và kết nối ngoài của nhóm đó."
      action={<Button onClick={() => { create.reset(); setCreating(true); }}>Tạo đơn vị</Button>}>
      {creating && <form className="mt-6 space-y-4 rounded-lg border border-border bg-card p-4" onSubmit={(event) => {
        event.preventDefault();
        create.mutate({ name: name.trim(), code, building_ids: buildings, category_ids: categories }, {
          onSuccess: () => { setCreating(false); setName(""); setCode(""); setBuildings([]); setCategories([]); },
        });
      }}>
        <h2 className="font-semibold">Tạo đơn vị quản lý</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1 text-sm">Tên đơn vị<Input aria-label="Tên đơn vị" required minLength={2} maxLength={160} value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="space-y-1 text-sm">Mã đơn vị<Input aria-label="Mã đơn vị" required minLength={2} maxLength={60} pattern="[a-z0-9][a-z0-9-]+" placeholder="bql-pavilion" value={code} onChange={(e) => setCode(e.target.value)} /><span className="text-xs text-muted-foreground">Chữ thường, số và dấu gạch ngang.</span></label>
        </div>
        {options.isPending ? <Skeleton className="h-24" /> : <div className="grid gap-4 sm:grid-cols-2">
          <fieldset className="space-y-2"><legend className="mb-2 text-sm font-medium">Tòa nhà phụ trách</legend>
            <div className="max-h-56 space-y-2 overflow-auto">{options.data?.buildings.map((b) => <label key={b.id} className="flex gap-2 text-sm"><input type="checkbox" checked={buildings.includes(b.id)} onChange={() => toggle(b.id, buildings, setBuildings)} />{b.name}</label>)}</div>
          </fieldset>
          <fieldset className="space-y-2"><legend className="mb-2 text-sm font-medium">Dịch vụ phụ trách</legend>
            {options.data?.categories.map((c) => <label key={c.id} className="flex gap-2 text-sm"><input type="checkbox" checked={categories.includes(c.id)} onChange={() => toggle(c.id, categories, setCategories)} />{c.name}</label>)}
          </fieldset>
        </div>}
        {(create.error || options.error) && <p role="alert" className="text-sm text-destructive">{create.error?.message || options.error?.message}</p>}
        <p className="text-xs text-muted-foreground">Nhóm Ban quản lý và Supervisor được tạo cùng đơn vị. Sau đó cấp tài khoản Ban quản lý cho đơn vị ở trang Tài khoản.</p>
        <div className="flex gap-2"><Button type="submit" disabled={create.isPending || !buildings.length || !categories.length}>{create.isPending ? "Đang tạo…" : "Tạo đơn vị và nhóm"}</Button>
          <Button type="button" variant="outline" disabled={create.isPending} onClick={() => setCreating(false)}>Hủy</Button></div>
      </form>}
      {units.error && <p role="alert" className="mt-4 text-sm text-destructive">{units.error.message}</p>}
      {units.isPending ? <Skeleton className="mt-6 h-40" /> : (
        <div className="mt-6 space-y-3">
          {units.data?.map((u) => (
            <section key={u.id} aria-label={u.name} className="rounded-lg border border-border bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-base font-semibold text-foreground">{u.name}</h2>
                <Badge variant={u.status === "active" ? "secondary" : "destructive"}>{u.status === "active" ? "Đang hoạt động" : "Ngừng"}</Badge>
              </div>
              <dl className="mt-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[10rem_1fr]">
                <dt className="text-muted-foreground">Tòa nhà phụ trách</dt>
                <dd className="text-foreground">{u.buildings.length ? u.buildings.join(", ") : "Chưa được giao tòa nào"}</dd>
                <dt className="text-muted-foreground">Nhóm Ban quản lý</dt>
                <dd className="space-y-1 text-foreground">
                  {u.groups.length ? u.groups.map((g) => (
                    <p key={g.id}>{g.name}<span className="text-muted-foreground"> · {g.members} thành viên · {g.agents} agent đang phát hành · {g.connections} kết nối ngoài</span></p>
                  )) : "Chưa có nhóm"}
                </dd>
                <dt className="text-muted-foreground">Nhân viên hiện trường</dt>
                <dd className="text-foreground">{u.staff}</dd>
                <dt className="text-muted-foreground">Yêu cầu đang mở</dt>
                <dd className="text-foreground">{u.open_tickets}</dd>
              </dl>
            </section>
          ))}
          {!units.error && !units.data?.length && <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">Chưa có đơn vị quản lý nào.</p>}
        </div>
      )}
    </Page>
  );
}

const ROLE: Record<RoleModel["role"], [string, string]> = {
  reception: ["Lễ tân", "Trả lời cư dân và lập yêu cầu"],
  supervisor: ["Supervisor", "Điều phối phiên và lập phương án"],
  specialist: ["Agent chuyên môn", "Agent của Ban quản lý trong phiên và trong nhóm"],
  factory: ["Factory", "Soạn chỉ dẫn cho agent mới"],
  embedding: ["Tìm kiếm tri thức", "Embedding của kho tri thức"],
};
const PROVIDER: Record<string, string> = { openai: "OpenAI", google: "Google Gemini", deepseek: "DeepSeek", groq: "Groq", anthropic: "Anthropic Claude", custom: "Máy chủ riêng" };

function modelStanding(m: RoleModel): { label: string; tone: "secondary" | "destructive" | "outline" } {
  if (!m.configured) return { label: "Chưa cấu hình", tone: "outline" };
  // What is known is that the service answers, not that its model key is accepted.
  if (m.running === false) return { label: "Dịch vụ không trả lời", tone: "destructive" };
  return { label: m.running ? "Dịch vụ đang chạy" : "Đang dùng", tone: "secondary" };
}

/** Which model each role runs on, as the running services report it. */
export function ModelsPage() {
  const models = useQuery({ ...modelsQueryOptions(), refetchInterval: 30_000 });
  return (
    <Page title="Model" lead="Mỗi vai trò dùng một model riêng, có thể của nhà cung cấp khác nhau. Bảng này đọc từ chính các dịch vụ đang chạy."
      action={<Button variant="outline" disabled={models.isFetching} onClick={() => void models.refetch()}><IconRefresh />Kiểm tra lại</Button>}>
      {models.error && <p role="alert" className="mt-4 text-sm text-destructive">{models.error.message}</p>}
      {models.isPending ? <Skeleton className="mt-6 h-40" /> : (
        <ul className="mt-6 divide-y divide-border rounded-lg border border-border bg-card">
          {models.data?.map((m) => (
            <li key={m.role} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
              <span className="min-w-48 flex-1">
                <span className="block text-sm font-medium text-foreground">{ROLE[m.role][0]}</span>
                <span className="block text-xs text-muted-foreground">{ROLE[m.role][1]}</span>
              </span>
              <span className="min-w-40 text-sm text-foreground">
                {m.model || "—"}
                {m.provider && <span className="block text-xs text-muted-foreground">{PROVIDER[m.provider] || m.provider}</span>}
              </span>
              <Badge variant={modelStanding(m).tone}>{modelStanding(m).label}</Badge>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 max-w-prose text-xs text-muted-foreground">
        Đổi model, nhà cung cấp hoặc khóa của một vai trò trong file cấu hình của bản triển khai rồi khởi động lại dịch vụ đó. Khóa không hiển thị ở đây, và bảng này chưa gọi thử model: khóa sai chỉ lộ ra khi một lượt trả lời thất bại.
        Đổi model embedding thì phải nhập lại kho tri thức.
      </p>
    </Page>
  );
}

const KIND: Record<string, string> = { agent: "Agent", connection: "Kết nối ngoài", team: "Phiên điều phối", room: "Nhóm", reception: "Lễ tân",
  reception_supervisor: "Lễ tân và Supervisor", account: "Tài khoản", ticket: "Yêu cầu", routine: "Lịch chạy agent", audit: "Nhật ký" };
const EVENT: Record<string, string> = {
  "agent.tool_called": "Agent gọi công cụ", "agent.configured": "Lưu cấu hình agent", "agent.evaluated": "Chạy đánh giá agent", "agent.tried": "Hỏi thử bản nháp agent",
  "agent.review_submitted": "Gửi bản agent chờ phát hành", "agent.review_decided": "Quyết định phát hành agent",
  "agent.release_revoked": "Thu hồi agent", "agent.factory_constructed": "Factory soạn chỉ dẫn agent",
  "room.agent_created": "Tạo agent", "room.agent_answered": "Agent trả lời trong nhóm",
  "team.created": "Mở phiên điều phối", "team.closure_approved": "Duyệt đóng phiên", "team.control_requested": "Điều khiển phiên", "team.agent_asked": "Hỏi agent trong phiên",
  "connection.created": "Thêm kết nối ngoài", "connection.tools_allowed": "Chọn công cụ được phép", "connection.removed": "Xóa kết nối ngoài",
  "audit.exported": "Xuất nhật ký ra tệp",
  "routine.created": "Đặt lịch chạy agent", "routine.changed": "Sửa lịch chạy", "routine.switched": "Bật hoặc tắt lịch chạy", "routine.removed": "Xóa lịch chạy",
  "reception.delegation_issued": "Lễ tân nhận quyền thay cư dân", "reception_supervisor.input_received": "Supervisor nhận yêu cầu",
  "reception_supervisor.result_received": "Supervisor trả kết quả",
};
const at = (iso: string) => new Date(iso).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });

function EventRow({ event }: { event: AuditEvent }) {
  const detail = Object.keys(event.payload || {}).length ? JSON.stringify(event.payload, null, 1) : "";
  return (
    <li className="px-4 py-2.5">
      <details>
        <summary className="flex cursor-pointer flex-wrap items-baseline gap-x-3 gap-y-0.5 text-sm">
          <span className="w-36 shrink-0 text-xs tabular-nums text-muted-foreground">{at(event.created_at)}</span>
          <span className="font-medium text-foreground">{EVENT[event.event_type] || event.event_type}</span>
          <span className="text-muted-foreground">{event.actor || (event.initiator_kind === "system" ? "Hệ thống" : "Không rõ")}</span>
        </summary>
        <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-2 text-xs text-muted-foreground">
          {`${event.event_type} · ${event.target_type} ${event.target_id}${detail ? `\n${detail}` : ""}`}
        </pre>
      </details>
    </li>
  );
}

/** The audit trail: who did what, newest first. */
/** A local day as the date input writes it. */
const day = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

export function AuditPage() {
  const [kind, setKind] = useState("");
  const [from, setFrom] = useState(() => { const now = new Date(); return day(new Date(now.getFullYear(), now.getMonth(), 1)); });
  const [to, setTo] = useState(() => day(new Date()));
  const exported = useMutation(exportAuditMutationOptions());
  const trail = useInfiniteQuery(auditQueryOptions(kind));
  const events = trail.data?.pages.flatMap((p) => p.items) || [];
  const kinds = trail.data?.pages[0]?.kinds || [];
  return (
    <Page title="Nhật ký" lead="Mọi thao tác quản trị, mọi lần agent gọi công cụ và mọi quyết định trong phiên đều được ghi lại. Nhật ký chỉ đọc."
      action={<select aria-label="Loại sự kiện" value={kind} className={select} onChange={(e) => setKind(e.target.value)}>
        <option value="">Mọi loại</option>
        {kinds.map((k) => <option key={k} value={k}>{KIND[k] || k}</option>)}
      </select>}>
      <form className="mt-4 flex flex-wrap items-end gap-3" aria-label="Xuất nhật ký" onSubmit={(e) => { e.preventDefault(); exported.mutate({ from, to, kind }); }}>
        <div className="space-y-1"><label htmlFor="audit-from" className="block text-xs text-muted-foreground">Từ ngày</label>
          <Input id="audit-from" type="date" className="w-40" value={from} max={to} onChange={(e) => setFrom(e.target.value)} /></div>
        <div className="space-y-1"><label htmlFor="audit-to" className="block text-xs text-muted-foreground">Đến hết ngày</label>
          <Input id="audit-to" type="date" className="w-40" value={to} min={from} onChange={(e) => setTo(e.target.value)} /></div>
        <Button type="submit" size="sm" variant="outline" disabled={!from || !to || exported.isPending}>{exported.isPending ? "Đang xuất…" : "Xuất tệp CSV"}</Button>
        <p className="basis-full text-xs text-muted-foreground">Tệp gồm các sự kiện{kind ? ` loại ${KIND[kind] || kind}` : ""} trong khoảng ngày đã chọn, theo giờ Việt Nam. Mỗi lần xuất được ghi vào nhật ký.</p>
      </form>
      {(trail.error || exported.error) && <p role="alert" className="mt-4 text-sm text-destructive">{(trail.error || exported.error)!.message}</p>}
      {trail.isPending ? <Skeleton className="mt-6 h-40" /> : (
        <>
          <ul className="mt-6 divide-y divide-border rounded-lg border border-border bg-card">
            {events.map((e) => <EventRow key={e.id} event={e} />)}
            {!events.length && <li className="px-4 py-10 text-center text-sm text-muted-foreground">Chưa có sự kiện nào.</li>}
          </ul>
          {trail.hasNextPage && <Button variant="outline" size="sm" className="mt-3" disabled={trail.isFetchingNextPage} onClick={() => void trail.fetchNextPage()}>
            {trail.isFetchingNextPage ? "Đang tải…" : "Xem các sự kiện cũ hơn"}</Button>}
        </>
      )}
    </Page>
  );
}
