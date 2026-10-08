import { useId, useState, type ReactNode } from "react";
import { IconCamera, IconCheck, IconChevronLeft, IconLoader2, IconMapPin } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { OnsiteConsent, QuoteForm, type QuoteInput } from "../RepairQuote";
import { AFTER, REJECTIONS, STEPS, ended, stateOf, stateText, stepOf, type FieldOrder, type FieldPhoto, type FieldPlan, type FieldTicket } from "./model";

export type FieldActions = {
  accept: (order: FieldOrder, minutes: number) => void;
  reject: (order: FieldOrder, reason: string) => void;
  /** Moves the order on: en_route, arrived, in_progress or completed. */
  advance: (order: FieldOrder, status: string, note: string) => void;
  quote: (order: FieldOrder, note: string, quote: QuoteInput) => void;
  consent: (order: FieldOrder, approved: boolean) => void;
  photo: (order: FieldOrder, file: File, phase: "before" | "after", note: string) => void;
};

const ETA = [15, 30, 60, 120];
const minutes = (value: number) => value < 60 ? `${value} phút` : `${value / 60} giờ`;
const primary = "min-h-12 h-auto w-full whitespace-normal px-3 py-3 text-base";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section aria-label={title} className="flex flex-col gap-3 rounded-xl border border-border bg-background p-4"><h2 className="text-sm font-semibold text-foreground">{title}</h2>{children}</section>;
}

function Photos({ photos }: { photos: FieldPhoto[] }) {
  return <>{photos.map((photo) => (
    <a key={photo.id} href={photo.src} target="_blank" rel="noreferrer" aria-label={`Xem ảnh ${photo.name}`} className="block size-20 shrink-0 overflow-hidden rounded-lg border border-border bg-muted focus-visible:ring-2 focus-visible:ring-ring">
      <img src={photo.src} alt={photo.name} loading="lazy" className="size-full object-cover" />
    </a>
  ))}</>;
}

/** The photos of one moment of the work, with the camera to add another while the work goes on. */
function Shots({ title, photos, disabled, onAdd }: { title: string; photos: FieldPhoto[]; disabled: boolean; onAdd?: (file: File) => void }) {
  return (
    <div>
      <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
        {title}{photos.length > 0 && <IconCheck className="size-4 text-primary" stroke={2} aria-label="đã có ảnh" />}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Photos photos={photos} />
        {onAdd && (
          <label className={cn("flex size-20 shrink-0 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-input text-xs text-muted-foreground focus-within:border-ring", disabled && "pointer-events-none opacity-50")}>
            <IconCamera aria-hidden="true" className="size-5" stroke={1.5} />Thêm ảnh
            {/* The camera, not the library: the photo is of the place as it is now. */}
            <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" aria-label={`Thêm ${title.toLocaleLowerCase("vi")}`} disabled={disabled}
              onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) onAdd(file); }} />
          </label>
        )}
      </div>
    </div>
  );
}

/** One order as its stepper and the single thing to do now. */
function FieldStep({ order, ticket, photos, busy, request, actions, planned, currentWork }: {
  order: FieldOrder; ticket: FieldTicket; photos: FieldPhoto[]; busy: boolean; request: <T>(path: string) => Promise<T>; actions: FieldActions;
  planned: boolean; currentWork?: { title: string; onOpen: () => void };
}) {
  const state = stateOf(order);
  const noteId = useId();
  const [note, setNote] = useState("");
  const [eta, setEta] = useState(30);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [approved, setApproved] = useState(false);
  const [quoting, setQuoting] = useState(false);
  const needsRevision = !!order.repair_approval_status && order.repair_approval_status !== "approved";
  const before = photos.filter((p) => p.purpose === "before"), after = photos.filter((p) => p.purpose === "after");
  const ready = before.length > 0 && after.length > 0;
  const step = stepOf(state, ready);
  const text = stateText(state);
  const sent = state === "completed" ? AFTER[ticket.status] : undefined;
  const refusal = reason === "OTHER" ? note.trim() : REJECTIONS.find(([code]) => code === reason)?.[1] || "";
  return (
    <section aria-label="Việc cần làm" aria-busy={busy} className="flex min-w-0 flex-col gap-4 rounded-xl border border-border bg-background p-4">
      {order.description && order.description !== ticket.description && <p className="text-sm leading-relaxed text-foreground">{order.description}</p>}
      <ol aria-label="Các bước xử lý" className="flex">
        {STEPS.map((name, index) => (
          <li key={name} aria-current={index === step ? "step" : undefined} className="flex min-w-0 flex-1 flex-col items-center gap-1.5 text-center">
            <span className="flex w-full items-center">
              <i className={cn("h-0.5 flex-1", index === 0 ? "bg-transparent" : index <= step ? "bg-primary" : "bg-border")} />
              <span className={cn("flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-medium tabular-nums",
                index < step ? "bg-primary text-primary-foreground" : index === step ? "border-2 border-primary text-primary" : "border border-border text-muted-foreground")}>
                {index < step ? <IconCheck className="size-3.5" stroke={2.5} /> : index + 1}
              </span>
              <i className={cn("h-0.5 flex-1", index === STEPS.length - 1 ? "bg-transparent" : index < step ? "bg-primary" : "bg-border")} />
            </span>
            <span className={cn("px-1 text-xs", index === step ? "font-semibold text-primary" : "text-muted-foreground")}>{name}</span>
          </li>
        ))}
      </ol>
      <div>
        <h2 className="text-lg font-semibold text-foreground">{sent?.[0] || text.label}</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{sent?.[1] || (state === "arrived" && planned ? needsRevision ? "Phương án phát sinh chưa được cư dân đồng ý. Điều chỉnh và gửi lại trước khi bắt đầu xử lý." : "Phương án đã được duyệt. Kiểm tra hiện trường rồi bắt đầu xử lý theo nội dung bên dưới." : text.guide)}</p>
      </div>
      {busy && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><IconLoader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />Đang lưu, vui lòng chờ…</p>}
      {currentWork && ["offered", "accepted"].includes(state) && <div className="rounded-lg border border-border bg-muted/50 p-3 text-sm leading-relaxed">
        <p>Việc này nằm trong hàng đợi. Bạn đang làm: <strong>{currentWork.title}</strong>.</p>
        <Button variant="outline" className="mt-2 min-h-[44px] h-auto w-full whitespace-normal py-2" disabled={busy} onClick={currentWork.onOpen}>Tiếp tục việc đang làm</Button>
      </div>}

      {state === "offered" && !rejecting && (
        <>
          <fieldset>
            <legend className="text-sm font-medium text-foreground">Bạn sẽ đến sau</legend>
            <div className="mt-2 grid grid-cols-4 gap-2">
              {ETA.map((value) => (
                <button key={value} type="button" aria-pressed={eta === value} onClick={() => setEta(value)}
                  className={cn("h-[44px] rounded-lg border text-sm font-medium", eta === value ? "border-primary bg-primary/10 text-primary" : "border-border text-foreground")}>{minutes(value)}</button>
              ))}
            </div>
          </fieldset>
          <Button className={primary} disabled={busy} onClick={() => actions.accept(order, eta)}>Nhận việc</Button>
          <Button variant="ghost" className="h-[44px] w-full text-muted-foreground" disabled={busy} onClick={() => setRejecting(true)}>Từ chối việc này</Button>
        </>
      )}
      {state === "offered" && rejecting && (
        <>
          <fieldset>
            <legend className="text-sm font-medium text-foreground">Lý do từ chối</legend>
            <div className="mt-2 flex flex-col gap-2">
              {REJECTIONS.map(([code, label]) => (
                <label key={code} className={cn("flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm text-foreground", reason === code ? "border-primary bg-primary/5" : "border-border")}>
                  <input type="radio" name={`reject-${order.id}`} value={code} checked={reason === code} onChange={() => setReason(code)} />{label}
                </label>
              ))}
            </div>
          </fieldset>
          {reason === "OTHER" && <Textarea aria-label="Lý do khác" rows={2} maxLength={500} placeholder="Ghi rõ lý do để Ban quản lý giao người khác" value={note} onChange={(e) => setNote(e.target.value)} />}
          <Button variant="destructive" className={primary} disabled={busy || !refusal} onClick={() => actions.reject(order, refusal)}>Xác nhận từ chối</Button>
          <Button variant="ghost" className="h-[44px] w-full" disabled={busy} onClick={() => setRejecting(false)}>Quay lại</Button>
        </>
      )}

      {(state === "accepted" || state === "en_route") && (
        <Button className={primary} disabled={busy || (state === "accepted" && !!currentWork)} onClick={() => actions.advance(order, state === "accepted" ? "en_route" : "arrived", "")}>{text.next}</Button>
      )}

      {state === "arrived" && planned && <>
        <Button className={primary} disabled={busy || needsRevision || quoting} onClick={() => actions.advance(order, "in_progress", "")}>Bắt đầu xử lý</Button>
        {!needsRevision && <Button variant="outline" className="min-h-[44px] h-auto w-full whitespace-normal py-2" disabled={busy} aria-expanded={quoting} onClick={() => setQuoting((value) => !value)}>{quoting ? "Đóng phương án phát sinh" : "Có phát sinh, lập phương án mới"}</Button>}
        {needsRevision && <p role="status" className="text-sm leading-relaxed text-muted-foreground">Cư dân chưa đồng ý phương án phát sinh. Bạn cần gửi lại phương án và chờ cư dân duyệt.</p>}
      </>}
      {state === "arrived" && (!planned || needsRevision || quoting) && (
        <>
          <label className="text-sm font-medium text-foreground" htmlFor={noteId}>Hiện trạng và cách xử lý
            <Textarea id={noteId} className="mt-1.5 text-base" rows={3} maxLength={2000} placeholder="Ví dụ: dây cấp dưới chậu bị nứt, cần thay dây mới." value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <QuoteForm disabled={busy || note.trim().length < 8} onSubmit={(quote) => actions.quote(order, note.trim(), quote)} />
          {note.trim().length < 8 && <p className="text-xs text-muted-foreground">Ghi hiện trạng (ít nhất 8 ký tự) trước khi gửi phương án.</p>}
        </>
      )}

      {state === "awaiting_approval" && (
        <>
          <OnsiteConsent orderId={order.id} disabled={busy} request={request} onApprovedChange={setApproved} onDecide={(approved) => actions.consent(order, approved)} />
          <Button className={primary} disabled={busy || !approved} onClick={() => actions.advance(order, "in_progress", "")}>{text.next}</Button>
        </>
      )}

      {state === "in_progress" && (
        <>
          <Shots title="Ảnh trước khi xử lý" photos={before} disabled={busy} onAdd={(file) => actions.photo(order, file, "before", note.trim())} />
          <Shots title="Ảnh sau khi xử lý" photos={after} disabled={busy} onAdd={(file) => actions.photo(order, file, "after", note.trim())} />
          <label className="text-sm font-medium text-foreground" htmlFor={noteId}>Ghi chú kết quả <span className="font-normal text-muted-foreground">(không bắt buộc)</span>
            <Textarea id={noteId} className="mt-1.5 text-base" rows={2} maxLength={2000} placeholder="Việc đã làm, lưu ý cho cư dân hoặc Ban quản lý" value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <Button className={primary} disabled={busy || !ready} onClick={() => actions.advance(order, "completed", note.trim())}>{text.next}</Button>
          {!ready && <p role="status" className="text-sm leading-relaxed text-muted-foreground">Cần ít nhất 1 ảnh trước và 1 ảnh sau khi xử lý của việc này để gửi kết quả.</p>}
        </>
      )}

      {ended(state) && (before.length > 0 || after.length > 0) && (
        <>
          {before.length > 0 && <Shots title="Ảnh trước khi xử lý" photos={before} disabled />}
          {after.length > 0 && <Shots title="Ảnh sau khi xử lý" photos={after} disabled />}
        </>
      )}
    </section>
  );
}

/**
 * One job on site, top to bottom: where to go, the step to do now, what the resident reported, and
 * the plan that was agreed. Nothing of the request's internal codes or of management's session.
 */
export function FieldJob({ ticket, place, orders, plan, photos, conversation, busy, request, actions, onBack, currentWork }: {
  ticket: FieldTicket; place: string; orders: FieldOrder[]; plan?: FieldPlan; photos: FieldPhoto[];
  conversation: { id: string; sender_kind: string; text: string }[]; busy: boolean;
  request: <T>(path: string) => Promise<T>; actions: FieldActions; onBack: () => void;
  currentWork?: { orderId: string; title: string; onOpen: () => void };
}) {
  const reported = photos.filter((p) => !["before", "after"].includes(p.purpose));
  const said = conversation.filter((m) => m.sender_kind === "user");
  const open = orders.some((o) => !ended(stateOf(o)));
  return (
    <article className="flex min-w-0 flex-col gap-4 [overflow-wrap:anywhere]">
      <button type="button" disabled={busy} onClick={onBack} className="-ml-2 flex h-[44px] w-fit items-center gap-0.5 rounded-md px-2 text-sm text-muted-foreground disabled:opacity-50">
        <IconChevronLeft aria-hidden="true" className="size-4" stroke={1.75} />Việc của tôi
      </button>
      <header className="flex flex-col gap-2">
        {open && ["critical", "high"].includes(ticket.priority) && <Badge variant="destructive" className="w-fit">{ticket.priority === "critical" ? "Khẩn cấp" : "Ưu tiên cao"}</Badge>}
        <h1 className="text-xl font-semibold leading-snug text-foreground">{ticket.title}</h1>
        <p className="flex items-start gap-1.5 text-sm text-muted-foreground"><IconMapPin aria-hidden="true" className="mt-0.5 size-4 shrink-0" stroke={1.75} />{place}</p>
      </header>

      {!orders.length && <p role="status" className="rounded-xl border border-border bg-background p-4 text-sm leading-relaxed text-muted-foreground">Việc này không còn được giao cho bạn. Quay lại danh sách để xem công việc hiện tại.</p>}
      {orders.map((order) => <FieldStep key={order.id} order={order} ticket={ticket} photos={photos.filter((p) => p.work_order_id === order.id)} busy={busy} request={request} actions={actions}
        planned={!!plan} currentWork={currentWork?.orderId !== order.id ? currentWork : undefined} />)}

      <Section title="Cư dân phản ánh">
        <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">{ticket.description || ticket.title}</p>
        {reported.length > 0 && <div className="flex flex-wrap gap-2"><Photos photos={reported} /></div>}
        {said.length > 1 && (
          <details>
            <summary className="min-h-[44px] cursor-pointer py-3 text-sm text-muted-foreground">Cư dân đã nói thêm ({said.length} tin nhắn)</summary>
            <ul className="mt-2 flex flex-col gap-2 border-l-2 border-border pl-3 text-sm text-foreground">{said.map((m) => <li key={m.id}>{m.text}</li>)}</ul>
          </details>
        )}
      </Section>

      {plan && (
        <Section title="Phương án đã được duyệt">
          <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm leading-relaxed text-foreground">{plan.proposal.steps.map((step) => <li key={step}>{step}</li>)}</ol>
          <dl className="flex flex-col gap-2 border-t border-border pt-3 text-sm">
            <div><dt className="text-xs text-muted-foreground">Thời gian dự kiến</dt><dd className="text-foreground">{plan.proposal.expected_duration}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Điều kiện</dt><dd className="text-foreground">{plan.proposal.conditions}</dd></div>
          </dl>
        </Section>
      )}
    </article>
  );
}
