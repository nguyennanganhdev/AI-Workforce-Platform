import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { IconArrowLeft, IconExternalLink } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { askSessionAgentMutationOptions, closeSessionMutationOptions, decidePlanMutationOptions } from "@/lib/rooms/mutations";
import { ticketSessionQueryOptions, type RoomMessage, type RoomSession, type SessionPlan } from "@/lib/rooms/queries";
import { queryClient } from "@/query-client";
import { SessionControls } from "../SessionControls";
import { mentionStatus, pauseText, planStatus, sessionFeed, sessionState } from "./model";
import { Composer, Note, Said, Transcript } from "./parts";

/** The plan the Supervisor proposed. Management approves it or sends it back with a reason. */
function PlanCard({ plan }: { plan: SessionPlan }) {
  const decide = useMutation(decidePlanMutationOptions(queryClient));
  const [note, setNote] = useState("");
  const pending = plan.status === "management_pending";
  const send = (decision: "approve" | "reject") =>
    decide.mutate({ planId: plan.id, decision, version: plan.version, note: note.trim() || "Đồng ý phương án." }, { onSuccess: () => setNote("") });
  const facts = [
    ["Người thực hiện", plan.proposal.performer_role],
    ["Thời gian dự kiến", plan.proposal.expected_duration],
    ["Điều kiện", plan.proposal.conditions],
    ["Chi phí dự kiến", plan.proposal.cost ? `${plan.proposal.cost.amount.toLocaleString("vi-VN")} ${plan.proposal.cost.currency}` : "Chưa có"],
  ];
  return (
    <section aria-label="Phương án xử lý" className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">Phương án xử lý</h3>
        <Badge variant={pending ? "default" : "secondary"}>{planStatus[plan.status] || plan.status}</Badge>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-foreground">{plan.title}</p>
      <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm leading-relaxed text-foreground">
        {plan.proposal.steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
      <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {facts.map(([label, value]) => (
          <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="text-foreground">{value}</dd></div>
        ))}
      </dl>
      {plan.management_note && !pending && <p className="mt-3 text-sm text-muted-foreground">Ghi chú của Ban quản lý: {plan.management_note}</p>}
      {pending && (
        <div className="mt-4 space-y-2 border-t border-border pt-3">
          <label htmlFor={`plan-note-${plan.id}`} className="text-xs text-muted-foreground">Ghi chú cho Supervisor và cư dân (bắt buộc khi từ chối)</label>
          <Textarea id={`plan-note-${plan.id}`} rows={2} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={decide.isPending} onClick={() => send("approve")}>Duyệt phương án</Button>
            <Button size="sm" variant="outline" disabled={decide.isPending || !note.trim()} onClick={() => send("reject")}>Từ chối</Button>
          </div>
          {decide.error && <p role="alert" className="text-sm text-destructive">{decide.error.message}</p>}
        </div>
      )}
    </section>
  );
}

export function SessionThread({ session, messages, agents, userId, onBack }: {
  session: RoomSession; messages: RoomMessage[]; agents: { id: string; name: string; published: boolean; status: string }[]; userId: string; onBack: () => void;
}) {
  const detail = useQuery(ticketSessionQueryOptions(session.ticket_id));
  const ask = useMutation(askSessionAgentMutationOptions(queryClient));
  const close = useMutation(closeSessionMutationOptions(queryClient));
  const request = useRef<{ signature: string; id: string } | null>(null);
  const state = sessionState(session);
  const feed = sessionFeed(session.id, messages, detail.data, agents, userId);
  // Names repeat when an agent was revoked and made again; only the one at work can be asked.
  const members = agents.filter((a) => a.published && a.status === "active" && detail.data?.room?.members.includes(a.name));
  const finished = state.group === "done";
  const waiting = feed.some((item) => item.type === "asked" && ["queued", "running"].includes(item.status));
  async function send(text: string, agentId: string) {
    const signature = JSON.stringify([session.id, text, agentId]);
    if (request.current?.signature !== signature) request.current = { signature, id: crypto.randomUUID() };
    try {
      await ask.mutateAsync({ ticketId: session.ticket_id, text, agentId: agentId || (members.length > 1 ? members[0].id : undefined), requestId: request.current.id });
      request.current = null;
      return true;
    } catch { return false; }
  }
  return (
    <>
      <header className="flex flex-wrap items-start gap-3 border-b border-border px-4 py-3 md:px-6">
        <Button size="icon" variant="ghost" className="md:hidden" aria-label="Về danh sách phiên" onClick={onBack}><IconArrowLeft /></Button>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-base font-semibold text-foreground">{session.ticket_title}</h2>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant={state.group === "attention" ? "default" : "secondary"}>{state.label}</Badge>
            {!!detail.data?.room?.members.length && <span>Agent tham gia: {detail.data.room.members.join(", ")}</span>}
          </p>
        </div>
        <Button size="sm" variant="outline" render={<a href={`/operations/kanban?ticket=${encodeURIComponent(session.ticket_id)}`} />}>
          <IconExternalLink />Mở công việc
        </Button>
        {!finished && <div className="basis-full [&>div]:mt-0"><SessionControls teamId={session.id} /></div>}
      </header>
      <Transcript label="Diễn biến phiên" count={feed.length}>
        {detail.isPending && <Skeleton className="h-24" />}
        {detail.error && <p role="alert" className="text-sm text-destructive">{detail.error.message}</p>}
        {feed.map((item) =>
          item.type === "note" ? <Note key={item.id} at={item.at}>{item.text}</Note>
          : item.type === "plan" ? <PlanCard key={item.id} plan={detail.data!.room!.plan!} />
          : item.type === "resident" ? <Said key={item.id} who="Cư dân" at={item.at}>{item.text}</Said>
          : item.type === "supervisor" ? <Said key={item.id} who="Supervisor hỏi cư dân" at={item.at} agent tone="accent">{item.text}</Said>
          : item.type === "agent" ? <Said key={item.id} who={item.author} at={item.at} agent>{item.text}</Said>
          : <Said key={item.id} who={item.author} at={item.at} mine footer={`Hỏi @${item.agent} · ${mentionStatus[item.status] || "Đã gửi"}`}>{item.text}</Said>)}
        {session.runtime?.phase === "paused" && !finished && (
          <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">{pauseText(session.runtime.pauseReason)}</p>
        )}
        {detail.data?.awaitingManagementApproval && (
          <section aria-label="Duyệt đóng phiên" className="rounded-lg border border-primary/20 bg-primary/5 p-4">
            <h3 className="text-sm font-semibold text-foreground">Cư dân đã xác nhận hoàn tất</h3>
            <p className="mt-1 text-sm text-muted-foreground">Công việc đã nghiệm thu và cư dân đã xác nhận. Duyệt để đóng phiên điều phối.</p>
            <Button size="sm" className="mt-3" disabled={close.isPending}
              onClick={() => close.mutate({ ticketId: session.ticket_id, version: detail.data!.session!.state_version })}>Duyệt đóng phiên</Button>
            {close.error && <p role="alert" className="mt-2 text-sm text-destructive">{close.error.message}</p>}
          </section>
        )}
        {finished && <Note>{state.label === "Đã đóng" ? "Phiên đã đóng" : state.label}</Note>}
      </Transcript>
      {!finished && (
        <Composer agents={members} disabled={!members.length || waiting} error={ask.error?.message} onSend={send}
          placeholder={members.length ? `Hỏi ${members.length === 1 ? `@${members[0].name}` : "agent"} về yêu cầu này…` : "Phiên chưa có agent để hỏi"}
          hint={waiting ? "Đang chờ agent trả lời câu hỏi trước." : "Agent trả lời trong phiên, dựa trên yêu cầu và phần đã trao đổi."} />
      )}
    </>
  );
}
