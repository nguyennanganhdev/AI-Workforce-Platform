import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { IconPlugConnected, IconPlus } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { connectionsQueryOptions, type Connection, type Connections } from "@/lib/connections/queries";
import { allowConnectionToolsMutationOptions, checkConnectionMutationOptions, createConnectionMutationOptions,
  removeConnectionMutationOptions } from "@/lib/connections/mutations";
import { queryClient } from "@/query-client";

const host = (url: string) => { try { return new URL(url).host; } catch { return url; } };
const select = "h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground";

function standing(c: Connection): { label: string; live: boolean } {
  if (c.last_error) return { label: "Lỗi kết nối", live: false };
  return c.tools.length ? { label: `${c.tools.length} công cụ được phép`, live: true } : { label: "Chưa chọn công cụ", live: false };
}

/** The administrator's side of external tools: which servers exist, for which group, and which of their tools agents may be given. */
export function ConnectionsPage() {
  const connections = useQuery(connectionsQueryOptions());
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState("");
  const items = connections.data?.items || [];
  const open = items.find((c) => c.id === selected);
  return (
    <div className="mx-auto w-full max-w-5xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Kết nối ngoài</h1>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            Máy chủ MCP mà agent của Ban quản lý được dùng. Bạn thêm kết nối và chọn công cụ được phép; Ban quản lý cấp các công cụ đó cho agent của mình.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}><IconPlus />Thêm kết nối</Button>
      </header>
      {connections.error && <p role="alert" className="mt-4 text-sm text-destructive">{connections.error.message}</p>}
      {connections.isPending ? <Skeleton className="mt-6 h-32" /> : items.length ? (
        <div className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(17rem,1fr))] gap-3">
          {items.map((c) => (
            <button key={c.id} type="button" onClick={() => setSelected(c.id)}
              className="flex flex-col items-stretch gap-3 rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/40 focus-visible:border-ring focus-visible:outline-none">
              <span className="flex items-center gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground"><IconPlugConnected className="size-5" stroke={1.75} /></span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-foreground">{c.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">{host(c.url)}</span>
                </span>
              </span>
              <span className="text-sm text-muted-foreground">{c.workspace ? `Dành cho ${c.workspace}` : "Dành cho mọi nhóm"}</span>
              <span><Badge variant={standing(c).live ? "default" : "secondary"}>{standing(c).label}</Badge></span>
            </button>
          ))}
        </div>
      ) : !connections.error && (
        <p className="mt-6 rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          Chưa có kết nối nào. Agent của Ban quản lý hiện chỉ dùng công cụ sẵn có của hệ thống: báo cáo, an ninh, kỹ thuật.
        </p>
      )}
      {creating && <NewConnection workspaces={connections.data?.workspaces || []} onClose={(id) => { setCreating(false); if (id) setSelected(id); }} />}
      {open && <ConnectionEditor key={open.id} connection={open} onClose={() => setSelected("")} />}
    </div>
  );
}

function NewConnection({ workspaces, onClose }: { workspaces: Connections["workspaces"]; onClose: (id?: string) => void }) {
  const create = useMutation(createConnectionMutationOptions(queryClient));
  const [form, setForm] = useState({ title: "", url: "", token: "", workspace: "" });
  const ready = form.title.trim().length >= 2 && form.url.trim().length >= 8;
  return (
    <Dialog open onOpenChange={(o) => { if (!o && !create.isPending) onClose(); }}><DialogContent>
      <DialogHeader><DialogTitle>Thêm kết nối</DialogTitle>
        <DialogDescription>Kết nối tới một máy chủ MCP qua địa chỉ https. Khóa truy cập được mã hóa khi lưu và không hiện lại.</DialogDescription></DialogHeader>
      <DialogBody className="space-y-4">
        <div className="space-y-1.5"><label htmlFor="connection-title" className="text-sm font-medium">Tên kết nối</label>
          <Input id="connection-title" value={form.title} maxLength={80} placeholder="Ví dụ: Sổ tay vận hành" onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
        <div className="space-y-1.5"><label htmlFor="connection-url" className="text-sm font-medium">Địa chỉ máy chủ MCP</label>
          <Input id="connection-url" type="url" value={form.url} maxLength={500} placeholder="https://…/mcp" onChange={(e) => setForm({ ...form, url: e.target.value })} /></div>
        <div className="space-y-1.5"><label htmlFor="connection-token" className="text-sm font-medium">Khóa truy cập</label>
          <Input id="connection-token" type="password" autoComplete="off" value={form.token} maxLength={4000} onChange={(e) => setForm({ ...form, token: e.target.value })} />
          <p className="text-xs text-muted-foreground">Dùng chung cho mọi agent của nhóm được chọn. Để trống nếu máy chủ không cần khóa.</p></div>
        <div className="space-y-1.5"><label htmlFor="connection-workspace" className="text-sm font-medium">Nhóm được dùng</label>
          <select id="connection-workspace" className={select} value={form.workspace} onChange={(e) => setForm({ ...form, workspace: e.target.value })}>
            <option value="">Mọi nhóm</option>
            {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select></div>
        {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
      </DialogBody>
      <DialogFooter>
        <Button size="sm" variant="outline" disabled={create.isPending} onClick={() => onClose()}>Hủy</Button>
        <Button size="sm" disabled={!ready || create.isPending} onClick={async () => {
          try { onClose((await create.mutateAsync({ title: form.title.trim(), url: form.url.trim(),
            ...(form.token.trim() ? { token: form.token.trim() } : {}), ...(form.workspace ? { workspace_id: form.workspace } : {}) })).id);
          } catch { /* visible mutation error */ }
        }}>{create.isPending ? "Đang thêm…" : "Thêm kết nối"}</Button>
      </DialogFooter>
    </DialogContent></Dialog>
  );
}

function ConnectionEditor({ connection, onClose }: { connection: Connection; onClose: () => void }) {
  const check = useMutation(checkConnectionMutationOptions(queryClient));
  const allow = useMutation(allowConnectionToolsMutationOptions(queryClient));
  const remove = useMutation(removeConnectionMutationOptions(queryClient));
  const saved = connection.tools.map((t) => t.name);
  const [names, setNames] = useState(saved);
  const [confirming, setConfirming] = useState(false);
  // Opening a connection asks the server what it offers now: the list is never shown from memory.
  useEffect(() => { check.mutate(connection.id); }, [connection.id]);
  const busy = check.isPending || allow.isPending || remove.isPending;
  const offered = check.data?.tools || [];
  const dirty = names.length !== saved.length || names.some((n) => !saved.includes(n));
  const error = check.error || allow.error || remove.error;
  return (
    <Dialog open onOpenChange={(o) => { if (!o && !busy) onClose(); }}><DialogContent className="max-w-2xl">
      <DialogHeader><DialogTitle>{connection.title}</DialogTitle>
        <DialogDescription>{host(connection.url)} · {connection.workspace ? `dành cho ${connection.workspace}` : "dành cho mọi nhóm"} · {connection.has_token ? "có khóa truy cập" : "không dùng khóa"}</DialogDescription></DialogHeader>
      <DialogBody className="space-y-4">
        {check.isPending ? <Skeleton className="h-24" /> : check.data && !check.data.ok ? (
          <div role="alert" className="rounded-lg border border-destructive/40 p-3 text-sm">
            <p className="font-medium text-destructive">Không kết nối được tới máy chủ.</p>
            <p className="mt-1 text-muted-foreground">{check.data.error}</p>
          </div>
        ) : check.data && (
          <fieldset disabled={busy}>
            <legend className="text-sm font-medium">Công cụ được phép</legend>
            <p className="mb-3 text-xs text-muted-foreground">
              Chỉ chọn công cụ đọc dữ liệu. Agent gọi công cụ được chọn mà không cần người duyệt, và nội dung câu hỏi của agent được gửi tới máy chủ này.
            </p>
            {offered.length ? offered.map((t) => {
              const closed = t.destructive ? "Máy chủ đánh dấu công cụ này là phá hủy dữ liệu." : !t.usable ? "Tên công cụ không gọi được từ agent." : "";
              return (
                <label key={t.name} className="mb-2.5 flex items-start gap-2 text-sm">
                  <input type="checkbox" className="mt-1" disabled={!!closed} checked={names.includes(t.name)}
                    onChange={(e) => setNames(e.target.checked ? [...names, t.name] : names.filter((n) => n !== t.name))} />
                  <span className="min-w-0"><span className="font-medium text-foreground">{t.tool}</span>
                    <span className="line-clamp-2 text-xs text-muted-foreground" title={t.description}>{closed || t.description || "Máy chủ không mô tả công cụ này."}</span></span>
                </label>
              );
            }) : <p className="text-sm text-muted-foreground">Máy chủ không có công cụ nào.</p>}
          </fieldset>
        )}
        {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
        {allow.isSuccess && !dirty && <p role="status" className="text-xs text-muted-foreground">Đã lưu. Ban quản lý thấy các công cụ này trong mục Phạm vi và công cụ của agent.</p>}
      </DialogBody>
      <DialogFooter>
        {confirming ? <>
          <p className="mr-auto text-xs text-muted-foreground">Xóa kết nối và khóa truy cập của nó?</p>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => setConfirming(false)}>Giữ lại</Button>
          <Button size="sm" variant="destructive" disabled={busy} onClick={async () => {
            try { await remove.mutateAsync(connection.id); onClose(); } catch { setConfirming(false); }
          }}>{remove.isPending ? "Đang xóa…" : "Xóa kết nối"}</Button>
        </> : <>
          <Button size="sm" variant="ghost" className="mr-auto text-destructive" disabled={busy} onClick={() => setConfirming(true)}>Xóa kết nối</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => check.mutate(connection.id)}>Kiểm tra lại</Button>
          <Button size="sm" disabled={busy || !dirty || !check.data?.ok} onClick={() => allow.mutate({ id: connection.id, names })}>{allow.isPending ? "Đang lưu…" : "Lưu công cụ được phép"}</Button>
        </>}
      </DialogFooter>
    </DialogContent></Dialog>
  );
}
