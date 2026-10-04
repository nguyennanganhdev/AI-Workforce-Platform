import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { IconPlus, IconSearch } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { accountsQueryOptions, createAccountMutationOptions, updateAccountMutationOptions, type Account } from "@/lib/admin/queries";
import { queryClient } from "@/query-client";

const ROLES: Record<string, string> = { customer: "Cư dân", staff: "Nhân viên", management: "Ban quản lý" };
const STATUS: Record<string, string> = { active: "Đang hoạt động", pending: "Chờ duyệt", suspended: "Đã khóa" };
const select = "h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground";
type Units = { id: string; name: string }[];
const roleOf = (a: Account) => (a.administrator ? "Quản trị viên" : ROLES[a.role] || a.role);

/** Who may sign in, as what, and in which management unit. */
export function AccountsPage() {
  const data = useQuery(accountsQueryOptions());
  const [text, setText] = useState("");
  const [role, setRole] = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState("");
  const accounts = data.data?.accounts || [];
  const units = data.data?.units || [];
  const needle = text.trim().toLowerCase();
  const shown = accounts.filter((a) => (!needle || a.name.toLowerCase().includes(needle) || a.email.toLowerCase().includes(needle))
    && (!role || (role === "admin" ? a.administrator : !a.administrator && a.role === role)));
  const waiting = accounts.filter((a) => a.status === "pending").length;
  const open = accounts.find((a) => a.id === selected);
  return (
    <div className="mx-auto w-full max-w-5xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Tài khoản</h1>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            Ban quản lý làm việc trong đơn vị được chọn; không chọn đơn vị thì có quyền trên toàn khu. Nhân viên chỉ thấy việc được giao.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}><IconPlus />Tạo tài khoản</Button>
      </header>
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1">
          <IconSearch className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input aria-label="Tìm tài khoản" placeholder="Tìm theo tên hoặc email" value={text} className="pl-8" onChange={(e) => setText(e.target.value)} />
        </div>
        <select aria-label="Vai trò" value={role} className="h-9 w-44 rounded-md border border-input bg-background px-2 text-sm text-foreground" onChange={(e) => setRole(e.target.value)}>
          <option value="">Mọi vai trò</option>
          {Object.entries(ROLES).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          <option value="admin">Quản trị viên</option>
        </select>
      </div>
      {data.error && <p role="alert" className="mt-4 text-sm text-destructive">{data.error.message}</p>}
      {data.isPending ? <Skeleton className="mt-4 h-40" /> : (
        <>
          <p className="mt-4 text-xs text-muted-foreground">{shown.length} tài khoản{waiting ? ` · ${waiting} chờ duyệt` : ""}</p>
          <ul className="mt-2 divide-y divide-border rounded-lg border border-border bg-card">
            {shown.map((a) => (
              <li key={a.id}>
                <button type="button" disabled={a.administrator} onClick={() => setSelected(a.id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left enabled:hover:bg-muted disabled:cursor-default">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium text-foreground">{a.name.trim().charAt(0).toUpperCase()}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">{a.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">{a.email}</span>
                  </span>
                  <span className="hidden text-right text-xs text-muted-foreground sm:block">
                    {roleOf(a)}{a.role === "management" && !a.administrator ? ` · ${units.find((u) => u.id === a.management_unit_id)?.name || "Toàn khu"}` : ""}
                  </span>
                  <Badge variant={a.status === "active" ? "secondary" : a.status === "pending" ? "default" : "destructive"}>{STATUS[a.status] || a.status}</Badge>
                </button>
              </li>
            ))}
            {!shown.length && <li className="px-4 py-10 text-center text-sm text-muted-foreground">Không có tài khoản phù hợp.</li>}
          </ul>
        </>
      )}
      {creating && <NewAccount units={units} onClose={() => setCreating(false)} />}
      {open && <AccountEditor key={open.id} account={open} units={units} onClose={() => setSelected("")} />}
    </div>
  );
}

function UnitField({ id, value, units, onChange }: { id: string; value: string; units: Units; onChange: (unit: string) => void }) {
  return (
    <div className="space-y-1.5"><label htmlFor={id} className="text-sm font-medium">Đơn vị quản lý</label>
      <select id={id} className={select} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Toàn khu</option>
        {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
      </select></div>
  );
}

function NewAccount({ units, onClose }: { units: Units; onClose: () => void }) {
  const create = useMutation(createAccountMutationOptions(queryClient));
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "customer", unit: "" });
  const ready = form.name.trim().length >= 2 && /\S+@\S+\.\S+/.test(form.email) && form.password.length >= 12;
  return (
    <Dialog open onOpenChange={(o) => { if (!o && !create.isPending) onClose(); }}><DialogContent>
      <DialogHeader><DialogTitle>Tạo tài khoản</DialogTitle>
        <DialogDescription>Người dùng đăng nhập bằng email và mật khẩu ban đầu này. Cư dân còn phải xác minh căn hộ trước khi gửi phản ánh.</DialogDescription></DialogHeader>
      <DialogBody className="space-y-4">
        <div className="space-y-1.5"><label htmlFor="account-name" className="text-sm font-medium">Họ và tên</label>
          <Input id="account-name" value={form.name} maxLength={100} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div className="space-y-1.5"><label htmlFor="account-email" className="text-sm font-medium">Email</label>
          <Input id="account-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div className="space-y-1.5"><label htmlFor="account-password" className="text-sm font-medium">Mật khẩu ban đầu</label>
          <Input id="account-password" type="password" autoComplete="new-password" value={form.password} maxLength={128} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <p className="text-xs text-muted-foreground">Ít nhất 12 ký tự.</p></div>
        <div className="space-y-1.5"><label htmlFor="account-role" className="text-sm font-medium">Vai trò</label>
          <select id="account-role" className={select} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {Object.entries(ROLES).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select></div>
        {form.role === "management" && <UnitField id="account-unit" value={form.unit} units={units} onChange={(unit) => setForm({ ...form, unit })} />}
        {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
      </DialogBody>
      <DialogFooter>
        <Button size="sm" variant="outline" disabled={create.isPending} onClick={onClose}>Hủy</Button>
        <Button size="sm" disabled={!ready || create.isPending} onClick={async () => {
          try { await create.mutateAsync({ name: form.name.trim(), email: form.email.trim(), password: form.password, role: form.role,
            ...(form.role === "management" && form.unit ? { management_unit_id: form.unit } : {}) }); onClose(); } catch { /* visible mutation error */ }
        }}>{create.isPending ? "Đang tạo…" : "Tạo tài khoản"}</Button>
      </DialogFooter>
    </DialogContent></Dialog>
  );
}

function AccountEditor({ account, units, onClose }: { account: Account; units: Units; onClose: () => void }) {
  const update = useMutation(updateAccountMutationOptions(queryClient));
  const [role, setRole] = useState(account.role);
  const [unit, setUnit] = useState(account.management_unit_id || "");
  const scoped = role === "management" && unit ? { management_unit_id: unit } : {};
  async function save(status: "active" | "suspended") {
    try { await update.mutateAsync({ id: account.id, role, status, ...(status === "active" ? scoped : {}) }); onClose(); } catch { /* visible mutation error */ }
  }
  return (
    <Dialog open onOpenChange={(o) => { if (!o && !update.isPending) onClose(); }}><DialogContent>
      <DialogHeader><DialogTitle>{account.name}</DialogTitle>
        <DialogDescription>{account.email} · {STATUS[account.status] || account.status}</DialogDescription></DialogHeader>
      <DialogBody className="space-y-4">
        <div className="space-y-1.5"><label htmlFor="edit-role" className="text-sm font-medium">Vai trò</label>
          <select id="edit-role" className={select} value={role} disabled={update.isPending} onChange={(e) => setRole(e.target.value)}>
            {Object.entries(ROLES).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select></div>
        {role === "management" && <UnitField id="edit-unit" value={unit} units={units} onChange={setUnit} />}
        {role === "management" && <p className="text-xs text-muted-foreground">Đổi đơn vị thì tài khoản rời nhóm của đơn vị cũ và vào nhóm của đơn vị mới.</p>}
        {update.error && <p role="alert" className="text-sm text-destructive">{update.error.message}</p>}
      </DialogBody>
      <DialogFooter>
        {account.status !== "suspended" && <Button size="sm" variant="ghost" className="mr-auto text-destructive" disabled={update.isPending} onClick={() => void save("suspended")}>Khóa truy cập</Button>}
        <Button size="sm" variant="outline" disabled={update.isPending} onClick={onClose}>Đóng</Button>
        <Button size="sm" disabled={update.isPending} onClick={() => void save("active")}>
          {update.isPending ? "Đang lưu…" : account.status === "pending" ? "Duyệt tài khoản" : account.status === "suspended" ? "Mở lại và lưu" : "Lưu"}</Button>
      </DialogFooter>
    </DialogContent></Dialog>
  );
}
