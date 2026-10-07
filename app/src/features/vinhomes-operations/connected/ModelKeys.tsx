import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminConfirm } from "./admin/AdminUI";
import { adminRequest } from "./admin/queries";
import { AgentBadge } from "./agent-display";
import { OpsSelect } from "./ui";

/** A model an agent of the unit may run on: allowed by the administrator, or the unit's own (`own`). */
export type UnitModel = { id: string; name: string; provider: string; check_status: "unchecked" | "ok" | "error"; own: boolean; credential_hint?: string | null };
const PROVIDERS = [{ value: "openai", label: "OpenAI" }, { value: "deepseek", label: "DeepSeek" }, { value: "groq", label: "Groq" }, { value: "google", label: "Google" }];
const providerName = (code: string) => PROVIDERS.find(p => p.value === code)?.label || code;
const base = (roomId: string) => `/rooms/${encodeURIComponent(roomId)}/models`;
export const unitModelsKey = (roomId: string) => ["unit-models", roomId] as const;
export function useUnitModels(roomId: string) {
  return useQuery({ queryKey: unitModelsKey(roomId), enabled: !!roomId, queryFn: () => adminRequest<{ items: UnitModel[]; canManage: boolean }>(base(roomId)) });
}

/** A new key for a model whose key was typed in the app. The server keeps it only once the provider answers with it. */
export function ModelKeyDialog({ title, path, onClose, onDone }: { title: string; path: string; onClose: () => void; onDone: () => void | Promise<void> }) {
  const [key, setKey] = useState("");
  const replace = useMutation({ mutationFn: () => adminRequest(path, { method: "PUT", body: { api_key: key.trim() } }), onSuccess: async () => { await onDone(); onClose(); } });
  return <Dialog open onOpenChange={open => { if (!open && !replace.isPending) onClose(); }}><DialogContent className="ops-ui"><DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>Máy chủ thử khóa mới với nhà cung cấp trước khi lưu. Nếu khóa mới không dùng được, khóa cũ được giữ.</DialogDescription></DialogHeader>
    <DialogBody><label htmlFor="model-new-key">Khóa API mới</label><Input id="model-new-key" type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} />{replace.error && <p role="alert" className="agent-error">{replace.error.message}</p>}</DialogBody>
    <DialogFooter><Button variant="outline" disabled={replace.isPending} onClick={onClose}>Hủy</Button><Button disabled={key.trim().length < 8 || replace.isPending} onClick={() => replace.mutate()}>{replace.isPending ? "Đang thử khóa…" : "Thay khóa"}</Button></DialogFooter></DialogContent></Dialog>;
}

/** The unit adds a model with its own key: only this unit's agents can run on it. It is checked right after it is saved. */
export function NewUnitModel({ roomId, onClose }: { roomId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", provider: "openai", api_key: "" });
  const add = useMutation({
    mutationFn: async () => {
      const { id } = await adminRequest<{ id: string }>(base(roomId), { method: "POST", body: { name: form.name.trim(), provider: form.provider, api_key: form.api_key.trim() } });
      return adminRequest<{ ok: boolean; message: string }>(`${base(roomId)}/${id}/check`, { method: "POST" });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: unitModelsKey(roomId) }),
  });
  return <Dialog open onOpenChange={open => { if (!open && !add.isPending) onClose(); }}><DialogContent className="ops-ui"><DialogHeader><DialogTitle>Thêm model của đơn vị</DialogTitle><DialogDescription>Khóa API được mã hóa trên máy chủ, không hiển thị lại. Chỉ agent của đơn vị này dùng được model này, và chi phí tính vào khóa của đơn vị.</DialogDescription></DialogHeader>
    <DialogBody><label htmlFor="unit-model-name">Tên model</label><Input id="unit-model-name" placeholder="Tên model do nhà cung cấp cấp" value={form.name} maxLength={120} disabled={add.isSuccess} onChange={e => setForm({ ...form, name: e.target.value })} />
      <label>Nhà cung cấp</label><OpsSelect className="w-full" label="Nhà cung cấp" value={form.provider} disabled={add.isSuccess} options={PROVIDERS} onValueChange={provider => setForm({ ...form, provider })} />
      <label htmlFor="unit-model-key">Khóa API</label><Input id="unit-model-key" type="password" autoComplete="off" value={form.api_key} disabled={add.isSuccess} onChange={e => setForm({ ...form, api_key: e.target.value })} />
      {add.data && <p role="status" className={add.data.ok ? "agent-hint" : "agent-error"}>{add.data.ok ? "Đã thêm và kiểm tra model. Chọn model này trong trang soạn agent." : "Đã lưu nhưng model chưa trả lời. Kiểm tra tên model và khóa, rồi bấm Kiểm tra hoặc Thay khóa."}</p>}
      {add.error && <p role="alert" className="agent-error">{add.error.message}</p>}</DialogBody>
    <DialogFooter>{add.isSuccess ? <Button onClick={onClose}>Xong</Button> : <><Button variant="outline" disabled={add.isPending} onClick={onClose}>Hủy</Button><Button disabled={!form.name.trim() || form.api_key.trim().length < 8 || add.isPending} onClick={() => add.mutate()}>{add.isPending ? "Đang thêm và kiểm tra…" : "Thêm model"}</Button></>}</DialogFooter></DialogContent></Dialog>;
}

/** Library tab: the models this unit's agents may choose, and the unit's own keys. */
export function UnitModels({ roomId, adding, onAddingChange }: { roomId: string; adding: boolean; onAddingChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const models = useUnitModels(roomId);
  const [replacing, setReplacing] = useState<UnitModel>();
  const [removing, setRemoving] = useState<UnitModel>();
  const refresh = () => queryClient.invalidateQueries({ queryKey: unitModelsKey(roomId) });
  const action = useMutation({
    mutationFn: ({ id, remove }: { id: string; remove?: boolean }) => remove ? adminRequest<{ ok: boolean; message?: string }>(`${base(roomId)}/${id}`, { method: "DELETE" }) : adminRequest<{ ok: boolean; message: string }>(`${base(roomId)}/${id}/check`, { method: "POST" }),
    onSuccess: async () => { setRemoving(undefined); await refresh(); },
  });
  if (models.isPending) return <Skeleton className="h-24" />;
  if (models.error) return <div role="alert" className="agent-error">{models.error.message}<Button variant="outline" onClick={() => void models.refetch()}>Thử lại</Button></div>;
  const manage = models.data.canManage;
  return <>
    <table className="agent-table"><thead><tr><th>Tên</th><th>Nhà cung cấp</th><th>Thuộc về</th><th>Trạng thái</th>{manage && <th><span className="sr-only">Thao tác</span></th>}</tr></thead><tbody>
      {models.data.items.map(m => <tr key={m.id}><td>{m.name}</td><td>{providerName(m.provider)}</td><td><span className="agent-owner-tag">{m.own ? `Khóa của đơn vị ${m.credential_hint || ""}` : "Quản trị viên cấp"}</span></td>
        <td><AgentBadge label={m.check_status === "ok" ? "Đã kiểm tra" : m.check_status === "error" ? "Không trả lời" : "Chưa kiểm tra"} tone={m.check_status === "ok" ? "ok" : m.check_status === "error" ? "danger" : "wait"} /></td>
        {manage && <td>{m.own && <><Button variant="ghost" size="sm" disabled={action.isPending} onClick={() => action.mutate({ id: m.id })}>Kiểm tra</Button><Button variant="ghost" size="sm" disabled={action.isPending} onClick={() => setReplacing(m)}>Thay khóa</Button><Button variant="ghost" size="sm" disabled={action.isPending} onClick={() => setRemoving(m)}>Xóa</Button></>}</td>}</tr>)}
    </tbody></table>
    {!models.data.items.length && <div className="agent-empty">Chưa có model. Quản trị viên cho phép model dùng chung, hoặc đơn vị thêm khóa riêng.</div>}
    {action.error && <p role="alert" className="agent-error">{action.error.message}</p>}
    {action.data && "message" in action.data && action.data.message && <p role="status" className="agent-hint">{action.data.message}</p>}
    {adding && <NewUnitModel roomId={roomId} onClose={() => onAddingChange(false)} />}
    {replacing && <ModelKeyDialog title={`Thay khóa của ${replacing.name}`} path={`${base(roomId)}/${replacing.id}/credential`} onClose={() => setReplacing(undefined)} onDone={refresh} />}
    {removing && <AdminConfirm title={`Xóa ${removing.name}?`} consequence="Chỉ xóa được model không còn agent nào dùng. Khóa đã lưu bị xóa theo." confirm="Xóa model" busy={action.isPending} onCancel={() => setRemoving(undefined)} onConfirm={() => action.mutate({ id: removing.id, remove: true })} />}
  </>;
}
