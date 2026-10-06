import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { OpsSelect, StatusBadge } from "../ui";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";
import { queryClient } from "@/query-client";
import { roomKeys } from "@/lib/rooms/queries";
import { requestKeys, type RequestCatalog, type RequestDetail } from "./request-data";

/** Manual execution stays inside the same request and uses the existing transactional workflow. */
export function RequestWork({ detail, catalog, hasPlan }: { detail: RequestDetail; catalog?: RequestCatalog; hasPlan: boolean }) {
  const [note, setNote] = useState(""), [staff, setStaff] = useState("");
  const ticket = detail.ticket;
  const available = useQuery({ queryKey: ["operations-available-staff", ticket.management_unit_id, ticket.category_id],
    enabled: !!ticket.management_unit_id && !!ticket.category_id && detail.workOrders.some(order => order.status === "queued"),
    queryFn: async (): Promise<{ items: { id: string }[] }> => (await client(`/api/business/staff/available?managementUnitId=${encodeURIComponent(ticket.management_unit_id)}&categoryId=${encodeURIComponent(ticket.category_id)}`,
      { headers: businessHeaders(), fallback: "Không tải được người thực hiện đang rảnh." })).json() });
  const change = useMutation({ mutationFn: async ({ path, body }: { path: string; body: unknown }) =>
    (await client(`/api/business${path}`, { method: "POST", headers: businessHeaders(), body, fallback: "Không ghi được thao tác xử lý. Hãy thử lại." })).json(),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: requestKeys.all }); void queryClient.invalidateQueries({ queryKey: roomKeys.all }); } });
  const send = (path: string, body: unknown) => change.mutate({ path, body });
  const options = (available.data?.items || []).flatMap(person => { const actual = catalog?.staff?.find(item => item.id === person.id); return actual?.name ? [{ value: person.id, label: actual.name }] : []; });
  const unfinished = !["closed", "cancelled"].includes(ticket.status);
  return <section className="ops-work-panel" aria-label="Thực hiện yêu cầu">
    <h3>Thực hiện yêu cầu</h3>
    {unfinished && <label>Ghi chú xử lý<Textarea className="resize-none" value={note} maxLength={2000} rows={2} onChange={event => setNote(event.target.value)} /></label>}
    {!hasPlan && unfinished && ["open", "triaging"].includes(ticket.status) && <div className="ops-work-actions">
      {ticket.status === "open" && <Button variant="outline" disabled={change.isPending} onClick={() => send(`/tickets/${ticket.id}/routing/ack`, {})}>Tiếp nhận</Button>}
      <Button disabled={change.isPending || !ticket.category_id} onClick={() => send(`/tickets/${ticket.id}/work-orders`, { category_id: ticket.category_id, required_specialty_id: ticket.category_id, description: note.trim() || ticket.description, ticket_version: ticket.version })}>Tạo phiếu thi công</Button>
    </div>}
    {detail.workOrders.map(order => <article className="ops-work-order" key={order.id}>
      <StatusBadge tone={order.status === "completed" ? "wait" : "ok"}>{({ queued: "Chờ phân công", offered: "Chờ người thực hiện nhận việc", accepted: "Đã nhận việc", en_route: "Đang di chuyển", arrived: "Đã đến hiện trường", in_progress: "Đang thi công", awaiting_approval: "Chờ cư dân đồng ý", completed: "Chờ nghiệm thu", cancelled: "Đã dừng" } as Record<string, string>)[order.status] || "Đang xử lý"}</StatusBadge>
      {order.description && <p>{order.description}</p>}
      {order.status === "queued" && <div className="ops-work-actions"><OpsSelect label="Người thực hiện" value={staff} onValueChange={setStaff} options={options} placeholder="Chọn người đang rảnh" />
        <Button disabled={change.isPending || !staff} onClick={() => send(`/work-orders/${order.id}/assignments`, { staff_id: staff, work_order_version: order.version, offer_expires_at: new Date(Date.now() + 30 * 60000).toISOString() })}>Phân công</Button>
        {!available.isPending && !options.length && <p>Chưa tìm được thợ rảnh.</p>}
      </div>}
      {order.status === "completed" && !["closed", "resolved"].includes(ticket.status) && <div className="ops-work-actions">
        <Button disabled={change.isPending} onClick={() => send(`/work-orders/${order.id}/qc`, { outcome: "pass", criteria: [{ name: "Kết quả hiện trường", passed: true }], note: note || "Đã kiểm tra kết quả hiện trường." })}>Nghiệm thu đạt</Button>
        <Button variant="outline" disabled={change.isPending || !note.trim()} onClick={() => change.mutate({ path: `/work-orders/${order.id}/qc`, body: { outcome: "fail", criteria: [{ name: "Kết quả hiện trường", passed: false }], redo_required: true, note } }, { onSuccess: (qc: { id: string }) => send(`/work-orders/${order.id}/redo`, { qc_result_id: qc.id, work_order_version: order.version, instruction: note }) })}>Yêu cầu làm lại</Button>
      </div>}
    </article>)}
    {(change.error || available.error) && <p role="alert">{(change.error || available.error)?.message}</p>}
  </section>;
}
