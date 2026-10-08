import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bot, Check, ChevronDown, Clock, Copy, Ellipsis, MessageSquare, Pencil, Phone, Plug, ShieldCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { askSessionAgentMutationOptions, closeSessionMutationOptions, decidePlanMutationOptions, ROOM_FILE_ACCEPT, roomFilesRefusal } from "@/lib/rooms/mutations";
import { roomFileUrl, ticketSessionQueryOptions, type RoomMessage, type RoomSession, type SessionPlan } from "@/lib/rooms/queries";
import { businessHeaders } from "@/lib/coordination/queries";
import { client } from "@/lib/client";
import { queryClient } from "@/query-client";
import { SessionControls } from "../SessionControls";
import { ActivityLog, OpsSelect, StatusBadge } from "../ui";
import { askedLine, dueText, lifecycleStep, LIFECYCLE, pauseText, plain, planStatus, sessionFeed, sessionState } from "./model";
import { Composer, Said, Transcript } from "./parts";
import { requestDetailQueryOptions, requestKeys, requestPlace, requestPresentationQueryOptions, requestSessionSourcesQueryOptions, requestSessionCallsQueryOptions, type RequestCatalog, type RequestPresentation, type RequestTicket } from "./request-data";
import { RequestWork } from "./RequestWork";

function PlanCard({ plan, schedule, onEdit }: { plan: SessionPlan; schedule?: RequestPresentation["schedule"]; onEdit: () => void }) {
  const pending = plan.status === "management_pending";
  const [expanded, expand] = useState(false);
  return <section aria-label="Phương án xử lý" className="ops-plan-card">
    <header><h3>Phương án xử lý</h3><StatusBadge tone={pending || plan.status === "resident_pending" ? "wait" : plan.status === "rejected" ? "danger" : "ok"}>{planStatus[plan.status] || "Đang xử lý"}</StatusBadge></header>
    <div className="ops-plan-body"><p>{plain(plan.title)}</p><ol>{(expanded ? plan.proposal.steps : plan.proposal.steps.slice(0, 4)).map((step, index) => <li key={index}>{plain(step)}</li>)}</ol>
      {plan.proposal.steps.length > 4 && <button type="button" className="ops-text-action" aria-expanded={expanded} onClick={() => expand(!expanded)}>{expanded ? "Thu gọn" : `Xem thêm ${plan.proposal.steps.length - 4} bước`}</button>}
      {plan.proposal.conditions && <p className="ops-plan-conditions">{plain(plan.proposal.conditions)}</p>}
      {plan.management_note && !pending && <p className="ops-plan-conditions">Ghi chú của Ban quản lý: {plain(plan.management_note)}</p>}
    </div>
    <footer>
      {(schedule?.performer_name || pending) && <div><span>Người thực hiện</span>{pending ? <button type="button" onClick={onEdit}>{schedule?.performer_name || "Chọn người thực hiện"}<ChevronDown size={14} /></button> : <strong>{schedule?.performer_name}</strong>}</div>}
      {(schedule?.appointment_at || pending) && <div><span>Giờ hẹn</span>{pending ? <button type="button" onClick={onEdit}>{schedule?.appointment_at ? new Date(schedule.appointment_at).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }) : "Chọn giờ hẹn"}<ChevronDown size={14} /></button> : <strong>{schedule?.appointment_at && new Date(schedule.appointment_at).toLocaleString("vi-VN")}</strong>}</div>}
      {plan.proposal.cost && <div><span>Chi phí</span><strong>{plan.proposal.cost.amount.toLocaleString("vi-VN")} {plan.proposal.cost.currency}</strong></div>}
    </footer>
    {(plan.proposal.performer_role || plan.proposal.expected_duration) && <div className="ops-plan-extra">{plan.proposal.performer_role && <span>Chuyên môn: {plan.proposal.performer_role}</span>}{plan.proposal.expected_duration && <span>Thời gian dự kiến: {plan.proposal.expected_duration}</span>}</div>}
  </section>;
}
function SessionRail({ presentation, place, onAgent, sources }: { presentation?: RequestPresentation; place: string; onAgent: (name: string) => void; sources?: ReactNode }) {
  const [historyOpen, showHistory] = useState(false), [photosOpen, showPhotos] = useState(false);
  return <div className="ops-session-rail-content">
    {presentation?.resident && <section><h3>Cư dân</h3><div className="ops-resident-person"><span className="ops-person-avatar">{presentation.resident.name.split(" ").map(word => word[0]).slice(-2).join("")}</span><div><strong>{presentation.resident.name}</strong>{place && <p>{place}</p>}</div>{presentation.resident.phone && <a className="ops-icon-button" aria-label={`Gọi ${presentation.resident.name}`} href={`tel:${presentation.resident.phone}`}><Phone size={16} /></a>}</div>{presentation.resident.availability_note && <p className="ops-resident-constraint">{presentation.resident.availability_note}</p>}</section>}
    {!!presentation?.participants?.length && <section><h3>Đang tham gia phiên</h3><ul className="ops-session-participants">{presentation.participants.filter(person => !person.left_at).map(person => <li key={person.id}><button type="button" onClick={() => onAgent(person.name)}><span className="ops-agent-avatar"><Bot size={16} /></span><span><strong>{person.name}</strong><small>{person.kind === "supervisor" ? "Điều phối từ" : "Tham gia lúc"} {new Date(person.joined_at).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</small></span>{person.active && <span className="ops-participant-active">đang hỗ trợ</span>}</button></li>)}</ul></section>}
    {sources}
    {!!presentation?.photos?.length && <section className="ops-rail-collapse"><button type="button" aria-expanded={photosOpen} onClick={() => showPhotos(!photosOpen)}>Ảnh cư dân gửi ({presentation.photos.length})<ChevronDown size={16} /></button>{photosOpen && <ul className="ops-rail-photos">{presentation.photos.map(photo => <li key={photo.id}><a href={`/api/business/files/${encodeURIComponent(photo.id)}/content?inline=true`} target="_blank" rel="noreferrer"><img src={`/api/business/files/${encodeURIComponent(photo.id)}/content?inline=true`} alt={photo.name} loading="lazy" /></a></li>)}</ul>}</section>}
    {!!presentation?.apartment_history?.length && <section className="ops-rail-collapse"><button type="button" aria-expanded={historyOpen} onClick={() => showHistory(!historyOpen)}>Lịch sử căn hộ ({presentation.apartment_history.length})<ChevronDown size={16} /></button>{historyOpen && <ul>{presentation.apartment_history.map(item => <li key={item.id}>{item.title}</li>)}</ul>}</section>}
  </div>;
}

export function SessionThread({ roomId, session, messages, agents, userId, onBack, ticket, catalog, hasSession = true }: {
  roomId: string; session: RoomSession; messages: RoomMessage[]; agents: { id: string; name: string; published: boolean; status: string }[];
  userId: string; onBack?: () => void; ticket?: RequestTicket; catalog?: RequestCatalog; hasSession?: boolean;
}) {
  const detail = useQuery(ticketSessionQueryOptions(session.ticket_id));
  const requestDetail = useQuery(requestDetailQueryOptions(session.ticket_id));
  const presentation = useQuery(requestPresentationQueryOptions(session.ticket_id));
  const sources = useQuery(requestSessionSourcesQueryOptions(session.ticket_id, userId, hasSession));
  const calls = useQuery(requestSessionCallsQueryOptions(session.ticket_id, userId, hasSession));
  const [sourcesOpen, showSources] = useState(false);
  const sourceChange = useMutation({ mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
    await client(`/api/business/tickets/${encodeURIComponent(session.ticket_id)}/session/sources`, { method: "PUT", headers: businessHeaders(), body: { server_id: id, enabled }, fallback: "Không thay đổi được nguồn ngoài." });
  }, onSuccess: () => { void sources.refetch(); } });
  const callDecision = useMutation({ mutationFn: async ({ id, decision }: { id: string; decision: "approve" | "cancel" }) => {
    await client(`/api/business/tickets/${encodeURIComponent(session.ticket_id)}/session/external-calls/${encodeURIComponent(id)}/decision`, { method: "POST", headers: businessHeaders(), body: { decision }, fallback: "Không xác nhận được thao tác ghi. Hãy kiểm tra nguồn ngoài và thử lại." });
  }, onSuccess: () => { void calls.refetch(); void detail.refetch(); } });
  const ask = useMutation(askSessionAgentMutationOptions(queryClient));
  const decide = useMutation(decidePlanMutationOptions(queryClient));
  const close = useMutation(closeSessionMutationOptions(queryClient));
  const request = useRef<{ signature: string; id: string } | null>(null);
  const state = sessionState(session), step = lifecycleStep(session), plan = detail.data?.room?.plan;
  const [railOpen, setRailOpen] = useState(false), [controlOpen, setControlOpen] = useState(false);
  const [rejecting, setRejecting] = useState(false), [note, setNote] = useState(""), [editing, setEditing] = useState(false);
  const [confirmApprove, setConfirmApprove] = useState(false), [notice, setNotice] = useState(""), [asking, setAsking] = useState(false);
  const [summary, setSummary] = useState(""), [steps, setSteps] = useState(""), [performer, setPerformer] = useState(""), [appointment, setAppointment] = useState("");
  const feed = sessionFeed(session.id, messages, detail.data, agents, userId);
  for (const event of presentation.data?.events || []) {
    const kind = event.kind === "joined" ? "agent_joined_session" : event.kind === "left" ? "agent_left_session" : "supervisor_accepted";
    if (messages.some(message => message.body.sessionId === session.id && message.body.kind === kind && (event.kind === "accepted" || message.body.text?.includes(event.agent || "")))) continue;
    feed.push({ type: "note", id: event.id, at: event.at, text: event.kind === "accepted" ? "Supervisor nhận điều phối yêu cầu" : event.kind === "left" ? `${event.agent} rời phiên` : `Supervisor thêm ${event.agent} vào phiên${event.reason ? ` vì ${event.reason}` : ""}` });
  }
  feed.sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  const members = agents.filter(agent => agent.published && agent.status === "active" && detail.data?.room?.members.includes(agent.name));
  const finished = state.group === "done", pending = plan?.status === "management_pending";
  const waiting = feed.some(item => item.type === "asked" && ["queued", "running"].includes(item.status));
  const location = requestPlace(requestDetail.data?.ticket || ticket, catalog), due = dueText((requestDetail.data?.ticket || ticket)?.resolution_due_at);
  const save = useMutation({ mutationFn: async () => {
    if (!plan) return;
    return client(`/api/business/plans/${encodeURIComponent(plan.id)}/presentation`, { method: "PATCH", headers: businessHeaders(),
      body: { version: plan.version, summary: summary.trim(), steps: steps.split("\n").map(line => line.trim()).filter(Boolean), performer_staff_id: performer || null,
        appointment_at: appointment ? new Date(appointment).toISOString() : null }, fallback: "Không lưu được phương án. Hãy kiểm tra thông tin và thử lại." });
  }, onSuccess: () => { setEditing(false); setNotice("Đã lưu thay đổi phương án"); void detail.refetch(); void presentation.refetch(); void queryClient.invalidateQueries({ queryKey: requestKeys.all }); } });
  function startEdit() {
    if (!plan) return;
    setSummary(plan.title); setSteps(plan.proposal.steps.join("\n")); setPerformer(presentation.data?.schedule?.performer_staff_id || "");
    const iso = presentation.data?.schedule?.appointment_at;
    setAppointment(iso ? new Date(Date.parse(iso) - new Date(iso).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ""); setEditing(true);
  }
  function decision(action: "approve" | "reject") {
    if (!plan) return;
    decide.mutate({ planId: plan.id, decision: action, version: plan.version, note: action === "reject" ? note.trim() : "Đồng ý phương án." },
      { onSuccess: () => { setRejecting(false); setConfirmApprove(false); setNote(""); setNotice(action === "approve" ? "Đã duyệt và gửi cư dân" : "Đã từ chối phương án"); } });
  }
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "a" && pending && !editing && !(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLTextAreaElement)) { event.preventDefault(); setConfirmApprove(true); }
    }; window.addEventListener("keydown", shortcut); return () => window.removeEventListener("keydown", shortcut);
  }, [pending, editing]);
  async function send(text: string, agentId: string, files: File[]) {
    const signature = JSON.stringify([session.id, text, agentId, files.map(file => [file.name, file.size, file.lastModified])]);
    if (request.current?.signature !== signature) request.current = { signature, id: crypto.randomUUID() };
    try { await ask.mutateAsync({ ticketId: session.ticket_id, roomId, text, agentId: agentId || (members.length > 1 ? members[0].id : undefined), requestId: request.current.id, files }); request.current = null; return true; } catch { return false; }
  }
  const sourcePanel = hasSession && <section className="ops-session-sources"><h3>Nguồn ngoài (MCP)</h3><p>Chỉ dùng cho câu hỏi của bạn trong yêu cầu này. Thao tác ghi luôn chờ bạn cho phép.</p>{sources.isPending ? <Skeleton className="h-16" /> : sources.error ? <p role="alert">{sources.error.message}<Button variant="ghost" onClick={() => void sources.refetch()}>Thử lại</Button></p> : sources.data?.items.length ? sources.data.items.map(source => <div className="ops-session-source" key={source.id}><Plug size={16} /><div><strong>{source.title}</strong><small>{source.tools.some(tool => tool.effect !== "read") ? "Đọc, thao tác ghi cần bạn duyệt" : "Chỉ đọc"}</small>{source.status !== "active" && <StatusBadge tone="wait">{source.status === "suspended" ? "Tạm ngưng" : "Chờ duyệt"}</StatusBadge>}{source.suspension_reason && <small>{source.suspension_reason}</small>}</div><Switch aria-label={`Dùng ${source.title} cho câu hỏi của bạn trong yêu cầu này`} checked={source.enabled} disabled={finished || source.status !== "active" || sourceChange.isPending} onCheckedChange={enabled => sourceChange.mutate({ id: source.id, enabled })} /></div>) : <p>Đơn vị chưa có nguồn ngoài.</p>}{sourceChange.error && <p role="alert">{sourceChange.error.message}</p>}</section>;
  const rail = <SessionRail sources={sourcePanel} presentation={presentation.data} place={location} onAgent={name => { const agent = agents.find(item => item.name === name); if (agent) window.location.href = `/operations/agents?agent=${encodeURIComponent(agent.id)}`; }} />;
  return <div className="ops-session-page">
    <main className="ops-session-main">
      <header className="ops-session-heading">
        {onBack && <button className="ops-session-back" type="button" onClick={onBack}><ArrowLeft size={16} />Yêu cầu</button>}
        <div className="ops-session-title"><div><h2>{session.ticket_title}</h2>{location && <p>{location}</p>}</div>{due && <span className={`ops-session-deadline tone-${due.tone}`}><Clock size={16} />{due.label}</span>}
          <DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label="Tùy chọn yêu cầu" />}><Ellipsis size={16} /></DropdownMenuTrigger><DropdownMenuContent className="ops-ui" align="end">
            {hasSession && !finished && <DropdownMenuItem onClick={() => setControlOpen(true)}>Điều khiển phiên</DropdownMenuItem>}
            <DropdownMenuItem onClick={() => { void navigator.clipboard.writeText(session.ticket_code).then(() => setNotice("Đã sao chép mã yêu cầu")); }}><Copy size={16} />Sao chép mã yêu cầu</DropdownMenuItem>
          </DropdownMenuContent></DropdownMenu>
        </div>
        <p className="ops-mobile-step">Bước {step + 1}/6, {LIFECYCLE[step]}</p>
        <ol className="ops-lifecycle" aria-label="Tiến trình yêu cầu">{LIFECYCLE.map((label, index) => <li key={label} data-state={index < step ? "done" : index === step ? "current" : "next"} aria-current={index === step ? "step" : undefined}><span>{index < step ? <Check size={14} /> : index + 1}</span>{label}</li>)}</ol>
        <Button className="ops-mobile-details" variant="outline" onClick={() => setRailOpen(true)}>Chi tiết</Button>
      </header>
      {notice && <div role="status" className="ops-session-notice">{notice}<button type="button" aria-label="Đóng thông báo" onClick={() => setNotice("")}><X size={14} /></button></div>}
      <Transcript label="Diễn biến phiên" count={feed.length + (calls.data?.items.length || 0)}>
        {detail.isPending && <Skeleton className="h-24" />}
        {detail.error && <div role="alert"><p>{detail.error.message}</p><Button variant="outline" onClick={() => void detail.refetch()}>Thử lại</Button></div>}
        {feed.map(item => item.type === "note" ? <ActivityLog key={item.id} agent="" time={item.at}>{item.text}</ActivityLog>
          : item.type === "plan" && plan ? <PlanCard key={item.id} plan={plan} schedule={presentation.data?.schedule} onEdit={startEdit} />
          : item.type === "resident" ? <Said key={item.id} who={presentation.data?.resident?.name || "Cư dân"} at={item.at}>{item.text}</Said>
          : item.type === "supervisor" ? <Said key={item.id} who="Supervisor" at={item.at} agent>{item.text}</Said>
          : item.type === "agent" ? <Said key={item.id} who={item.author} at={item.at} agent>{item.text}</Said>
          : item.type === "asked" ? <Said key={item.id} who={item.author} at={item.at} mine footer={askedLine(item.agent, item.status)} files={item.files.map(file => ({ id: file.id, name: file.name, bytes: file.size_bytes, href: roomFileUrl(roomId, file.id), image: file.mime_type.startsWith("image/") ? roomFileUrl(roomId, file.id, true) : undefined }))}>{item.text}</Said> : null)}
        {!feed.some(item => item.type === "plan") && plan && <PlanCard plan={plan} schedule={presentation.data?.schedule} onEdit={startEdit} />}
        {session.runtime?.phase === "paused" && !finished && <p role="status" className="ops-session-pause">{pauseText(session.runtime.pauseReason)}</p>}
        {detail.data?.awaitingManagementApproval && <section className="ops-plan-card ops-closure-card"><h3>Cư dân đã xác nhận hoàn tất</h3><p>Công việc đã nghiệm thu và cư dân đã xác nhận. Duyệt để đóng yêu cầu.</p></section>}
        {requestDetail.data?.ticket && (!hasSession || requestDetail.data.workOrders.length > 0 || session.runtime?.phase === "paused") && <RequestWork detail={requestDetail.data} catalog={catalog} hasPlan={!!plan} />}
        {requestDetail.error && !hasSession && <div role="alert"><p>{requestDetail.error.message}</p><Button variant="outline" onClick={() => void requestDetail.refetch()}>Thử lại</Button></div>}
        {!hasSession && !detail.isPending && !detail.error && !feed.length && <p>Yêu cầu đã được tiếp nhận. Bạn có thể phân công và theo dõi thi công tại đây.</p>}
        {calls.data?.items.map(call => <section key={call.id} className="ops-session-external-call" aria-label={call.status === "pending" ? "Thao tác ghi chờ xác nhận" : "Kết quả thao tác ghi"}><header><Plug size={16} /><strong>{call.connection_title}</strong><StatusBadge tone={call.status === "pending" ? "wait" : call.status === "succeeded" ? "ok" : ["failed", "uncertain"].includes(call.status) ? "danger" : "neutral"}>{({ pending: "Thao tác ghi chờ bạn cho phép", succeeded: "Đã thực hiện", cancelled: "Đã hủy", failed: "Thao tác không thành công", uncertain: "Chưa xác định được kết quả", executing: "Đang thực hiện", expired: "Xác nhận đã hết hạn" } as Record<string, string>)[call.status] || call.status}</StatusBadge></header><p><strong>Thao tác:</strong> {call.description || "Thao tác ghi vào nguồn ngoài"}</p><p>Agent đề nghị ghi chính xác nội dung sau:</p><pre>{JSON.stringify(call.arguments, null, 2)}</pre>{call.status === "pending" && <footer><Button variant="outline" disabled={callDecision.isPending} onClick={() => callDecision.mutate({ id: call.id, decision: "cancel" })}>Hủy</Button><Button disabled={callDecision.isPending || finished} onClick={() => callDecision.mutate({ id: call.id, decision: "approve" })}>Cho phép</Button></footer>}{call.result?.text && <p>{call.result.text}</p>}{call.result?.error && <p>{call.result.error}</p>}{call.status === "uncertain" && <p>Kiểm tra kết quả ở nguồn ngoài trước khi yêu cầu thao tác mới.</p>}</section>)}
        {(calls.error || callDecision.error) && <div role="alert"><p>{calls.error?.message || callDecision.error?.message}</p><Button variant="outline" onClick={() => void calls.refetch()}>Kiểm tra lại</Button></div>}
      </Transcript>
      {!finished && <div className="ops-session-bottom">
        {(decide.error || close.error) && <p role="alert">{(decide.error || close.error)?.message}</p>}
        {rejecting && <div className="ops-decision-note"><label htmlFor="ops-rejection-note">Lý do từ chối</label><Textarea className="resize-none" id="ops-rejection-note" autoFocus rows={2} value={note} maxLength={2000} onChange={event => setNote(event.target.value)} /><div><Button variant="ghost" onClick={() => setRejecting(false)}>Hủy</Button><Button disabled={decide.isPending || !note.trim()} onClick={() => decision("reject")}>Từ chối phương án</Button></div></div>}
        {hasSession && !finished && <Button variant="ghost" className="ops-session-source-picker" onClick={() => showSources(true)}><Plug size={16} />{sources.data?.items.filter(source => source.enabled).length || 0} nguồn ngoài</Button>}
        {asking && <Composer agents={members} disabled={!members.length || waiting} error={ask.error?.message} onSend={send} attach={{ accept: ROOM_FILE_ACCEPT, refusal: roomFilesRefusal, withText: true }} placeholder="Hỏi agent về yêu cầu này…" />}
        {pending ? <div className="ops-decision-bar"><Button variant="ghost" onClick={() => setAsking(!asking)}><MessageSquare size={16} />Hỏi agent</Button><div><Button variant="outline" className="ops-reject-button" disabled={decide.isPending} onClick={() => setRejecting(true)}>Từ chối</Button><Button variant="outline" onClick={startEdit}><Pencil size={16} /><span>Sửa phương án</span></Button><Button className="ops-approve-button" disabled={decide.isPending} onClick={() => decision("approve")}><Check size={16} />Duyệt và gửi cư dân</Button></div></div>
        : detail.data?.awaitingManagementApproval ? <div className="ops-decision-bar"><span><ShieldCheck size={16} />Cư dân đã xác nhận</span><Button disabled={close.isPending} onClick={() => close.mutate({ ticketId: session.ticket_id, version: detail.data!.session!.state_version }, { onSuccess: () => setNotice("Đã duyệt đóng yêu cầu") })}>Duyệt đóng yêu cầu</Button></div>
        : hasSession && <Composer agents={members} disabled={!members.length || waiting} error={ask.error?.message} onSend={send} attach={{ accept: ROOM_FILE_ACCEPT, refusal: roomFilesRefusal, withText: true }} placeholder={members.length ? "Hỏi agent về yêu cầu này…" : "Phiên chưa có agent để hỏi"} hint={waiting ? "Đang chờ agent trả lời câu hỏi trước." : undefined} />}
      </div>}
    </main>
    <aside className="ops-session-rail" aria-label="Chi tiết yêu cầu">{presentation.isPending ? <Skeleton className="m-4 h-40" /> : rail}{presentation.error && <div className="ops-rail-error" role="alert"><p>{presentation.error.message}</p><Button variant="outline" onClick={() => void presentation.refetch()}>Thử lại</Button></div>}</aside>
    <Sheet open={sourcesOpen} onOpenChange={showSources}><SheetContent className="ops-ui ops-session-source-sheet"><SheetHeader><SheetTitle>Nguồn ngoài cho câu hỏi của bạn</SheetTitle><SheetDescription>Quyền này chỉ áp dụng cho bạn trong yêu cầu hiện tại.</SheetDescription></SheetHeader>{sourcePanel}</SheetContent></Sheet>
    <Sheet open={railOpen} onOpenChange={setRailOpen}><SheetContent side="bottom" className="ops-ui ops-session-mobile-rail"><SheetHeader><SheetTitle>Chi tiết yêu cầu</SheetTitle></SheetHeader>{rail}</SheetContent></Sheet>
    <Sheet open={editing} onOpenChange={setEditing}><SheetContent className="ops-ui ops-plan-edit" showCloseButton><SheetHeader><SheetTitle>Sửa phương án</SheetTitle><SheetDescription>Lưu thay đổi trước khi duyệt và gửi cư dân.</SheetDescription></SheetHeader><div className="ops-plan-edit-body"><label>Phương án xử lý<Textarea rows={3} className="resize-none" value={summary} maxLength={300} onChange={event => setSummary(event.target.value)} /></label><label>Các bước thực hiện<Textarea rows={5} className="resize-none" value={steps} onChange={event => setSteps(event.target.value)} /></label><label>Người thực hiện<OpsSelect value={performer} onValueChange={setPerformer} options={(catalog?.staff || []).filter(person => !!person.name).map(person => ({ value: person.id, label: person.name! }))} label="Người thực hiện" placeholder="Chọn người thực hiện" /></label><label>Giờ hẹn<Input type="datetime-local" value={appointment} onChange={event => setAppointment(event.target.value)} /></label>{save.error && <p role="alert">{save.error.message}</p>}</div><footer><Button variant="outline" onClick={() => setEditing(false)}>Hủy</Button><Button disabled={save.isPending || !summary.trim() || !steps.trim()} onClick={() => save.mutate()}>Lưu thay đổi</Button></footer></SheetContent></Sheet>
    <Dialog open={confirmApprove} onOpenChange={setConfirmApprove}><DialogContent className="ops-ui"><DialogTitle>Duyệt và gửi cư dân?</DialogTitle><DialogDescription>Phương án này sẽ được gửi để cư dân đồng ý trước khi thi công.</DialogDescription><DialogFooter><Button variant="outline" onClick={() => setConfirmApprove(false)}>Hủy</Button><Button disabled={decide.isPending} onClick={() => decision("approve")}>Duyệt và gửi cư dân</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={controlOpen} onOpenChange={setControlOpen}><DialogContent className="ops-ui"><DialogTitle>Điều khiển phiên</DialogTitle><DialogDescription>Tạm dừng, chạy tiếp hoặc dừng điều phối yêu cầu.</DialogDescription><SessionControls teamId={session.id} /></DialogContent></Dialog>
  </div>;
}
