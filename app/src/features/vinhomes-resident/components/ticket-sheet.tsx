import { useEffect, useId, useRef, useState } from 'react';
import { IconAlertCircle, IconCircleCheck, IconPhone } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';
import { SignaturePad, type SignaturePadHandle } from '@/features/vinhomes-operations/components/technician/signature-pad';
import { useResidentGateway } from '../hooks/use-resident-gateway';
import { formatRemaining, formatTime } from '../lib/format';
import type { PendingAction, ResidentTicketView } from '../types';
import { QuoteTable, StatusBadge } from './ticket-ui';

type Run = (fn: () => void, success: string) => boolean;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function Photos({ urls, label }: { urls: string[]; label: string }) {
  if (urls.length === 0) return null;
  return (
    <div className="flex gap-2 overflow-x-auto">
      {urls.map((url, i) => (
        <a key={url} href={url} target="_blank" rel="noreferrer" className="shrink-0">
          <img src={url} alt={`${label} ${i + 1}`} className="size-20 rounded-lg border object-cover" />
        </a>
      ))}
    </div>
  );
}

function ReasonForm({
  label,
  placeholder,
  submitLabel,
  minLength,
  onSubmit,
  onCancel,
}: {
  label: string;
  placeholder: string;
  submitLabel: string;
  minLength: number;
  onSubmit: (note: string) => void;
  onCancel: () => void;
}) {
  const [note, setNote] = useState('');
  const [tried, setTried] = useState(false);
  const id = useId();
  const invalid = note.trim().length < minLength;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
      <Textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder={placeholder} aria-invalid={tried && invalid} />
      {tried && invalid && <p className="text-xs text-destructive">Vui lòng nhập ít nhất {minLength} ký tự.</p>}
      <div className="flex gap-2">
        <Button variant="outline" size="lg" className="flex-1" onClick={onCancel}>
          Quay lại
        </Button>
        <Button size="lg" className="flex-1" onClick={() => (invalid ? setTried(true) : onSubmit(note.trim()))}>
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}

function ActionPanel({ action, ticket, run }: { action: PendingAction; ticket: ResidentTicketView; run: Run }) {
  const gw = useResidentGateway();
  const [mode, setMode] = useState<'main' | 'reason'>('main');
  const [hasInk, setHasInk] = useState(false);
  const pad = useRef<SignaturePadHandle>(null);

  if (action.type === 'AGREE_QUOTE') {
    return (
      <div className="flex flex-col gap-3">
        {action.channel === 'DEVICE' && (
          <p className="text-sm text-muted-foreground">Nhân viên cũng đang đưa máy để bạn xem. Bạn có thể đồng ý ở đó hoặc ngay tại đây.</p>
        )}
        <QuoteTable quote={action.quote} />
        <Button size="lg" className="h-11" onClick={() => run(() => gw.agreeQuote(action), 'Đã ghi nhận bạn đồng ý. Nhân viên bắt đầu sửa.')}>
          Tôi đồng ý, bắt đầu sửa
        </Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="lg"
            className="flex-1"
            onClick={() => run(() => gw.requestQuoteChanges(action), 'Đã báo nhân viên điều chỉnh lại danh mục. Bạn trao đổi trực tiếp với nhân viên nhé.')}
          >
            Cần điều chỉnh
          </Button>
          <Button
            variant="ghost"
            size="lg"
            className="flex-1 text-destructive"
            onClick={() => window.confirm('Bạn chắc chắn không muốn sửa nữa?') && run(() => gw.cancelJob(action), 'Đã ghi nhận bạn không sửa nữa.')}
          >
            Không sửa nữa
          </Button>
        </div>
      </div>
    );
  }

  if (action.type === 'SIGN') {
    if (mode === 'reason') {
      return (
        <ReasonForm
          label="Bạn chưa đồng ý điểm nào trong phần phát sinh? Ban quản lý sẽ liên hệ giải quyết."
          placeholder="VD: Tôi không được báo trước về vật tư phát sinh"
          submitLabel="Gửi ý kiến cho Ban quản lý"
          minLength={8}
          onCancel={() => setMode('main')}
          onSubmit={(note) => run(() => gw.dispute(action, note), 'Đã gửi ý kiến của bạn cho Ban quản lý.')}
        />
      );
    }
    return (
      <div className="flex flex-col gap-3">
        {ticket.resolution && <Photos urls={ticket.resolution.photos} label="Ảnh sau khi sửa" />}
        <QuoteTable quote={action.quote} split />
        <p className="text-sm">Ký tên để xác nhận khối lượng công việc và chi phí:</p>
        <SignaturePad ref={pad} onChange={setHasInk} />
        <Button
          size="lg"
          className="h-11"
          disabled={!hasInk}
          onClick={() => {
            const url = pad.current?.toDataUrl();
            if (url) run(() => gw.sign(action, url), 'Đã ghi nhận chữ ký của bạn.');
          }}
        >
          Ký xác nhận
        </Button>
        {action.quote.additionalLines.length > 0 && (
          <Button variant="ghost" size="lg" className="text-destructive" onClick={() => setMode('reason')}>
            Tôi không đồng ý phần phát sinh
          </Button>
        )}
      </div>
    );
  }

  const remaining = formatRemaining(action.autoCompleteAt);
  if (mode === 'reason') {
    return (
      <ReasonForm
        label="Điều gì chưa được xử lý? Mình sẽ tạo lượt xử lý lại."
        placeholder="VD: Mở vòi vẫn còn rò ở khớp nối"
        submitLabel="Gửi yêu cầu xử lý lại"
        minLength={8}
        onCancel={() => setMode('main')}
        onSubmit={(note) => run(() => gw.reportIssue(action, note), 'Đã tạo lượt xử lý lại.')}
      />
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {ticket.resolution?.note && <p className="rounded-lg bg-muted/60 p-3 text-sm">{ticket.resolution.note}</p>}
      {ticket.resolution && <Photos urls={ticket.resolution.photos} label="Ảnh sau khi xử lý" />}
      {remaining && <p className="text-sm text-muted-foreground">Tự động hoàn tất sau {remaining} nếu bạn không phản hồi.</p>}
      <Button size="lg" className="h-11" onClick={() => run(() => gw.confirmCompletion(action), 'Cảm ơn bạn đã xác nhận. Yêu cầu đã hoàn tất.')}>
        Xác nhận hoàn thành
      </Button>
      <Button variant="outline" size="lg" onClick={() => setMode('reason')}>
        Chưa đạt, cần xử lý lại
      </Button>
    </div>
  );
}

function TicketDetail({ ticket }: { ticket: ResidentTicketView }) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const action = ticket.pendingAction;
  const actionKey = action ? `${action.type}-${action.version}` : null;

  // A new step for the resident replaces the confirmation of the previous one.
  useEffect(() => {
    if (actionKey) setNotice(null);
  }, [actionKey]);

  const run: Run = (fn, success) => {
    setError(null);
    try {
      fn();
      setNotice(success);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chưa thực hiện được, bạn thử lại nhé.');
      return false;
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 pb-6">
      {error && (
        <p role="alert" className="flex gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
          <IconAlertCircle className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}
      {notice && !error && (
        <p role="status" className="flex gap-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200">
          <IconCircleCheck className="mt-0.5 size-4 shrink-0" />
          {notice}
        </p>
      )}

      {action && (
        <section className="flex flex-col gap-3 rounded-xl border border-amber-300 bg-amber-50/40 p-3.5 dark:border-amber-500/40 dark:bg-amber-500/5">
          <h3 className="text-sm font-semibold">Việc cần bạn làm</h3>
          {/* key: reset the panel when the step changes under it (e.g. staff edited the list). */}
          <ActionPanel key={actionKey} action={action} ticket={ticket} run={run} />
        </section>
      )}

      {ticket.assignee && (
        <Section title="Người phụ trách">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-medium">{ticket.assignee.name}</p>
              {ticket.teamLabel && <p className="text-xs text-muted-foreground">{ticket.teamLabel}</p>}
            </div>
            {ticket.assignee.phone && (
              <Button variant="outline" size="sm" nativeButton={false} render={<a href={`tel:${ticket.assignee.phone.replace(/\s/g, '')}`} />}>
                <IconPhone data-icon="inline-start" /> {ticket.assignee.phone}
              </Button>
            )}
          </div>
        </Section>
      )}

      {ticket.resolution && action?.type !== 'CONFIRM_COMPLETION' && action?.type !== 'SIGN' && (
        <Section title="Kết quả xử lý">
          {ticket.resolution.note && <p className="text-sm">{ticket.resolution.note}</p>}
          <Photos urls={ticket.resolution.photos} label="Ảnh sau khi xử lý" />
        </Section>
      )}

      <Section title="Nội dung bạn gửi">
        <p className="whitespace-pre-line text-sm">{ticket.description}</p>
        {ticket.location && <p className="text-sm text-muted-foreground">Vị trí: {ticket.location}</p>}
        <Photos urls={ticket.photos} label="Ảnh bạn gửi" />
      </Section>

      <Section title="Tiến trình">
        <ol className="flex flex-col">
          {[...ticket.events].reverse().map((e, i) => (
            <li key={e.id} className="relative flex gap-3 pb-4 last:pb-0">
              <span className="relative flex w-3 justify-center">
                <span className={i === 0 ? 'mt-1.5 size-2.5 rounded-full bg-foreground' : 'mt-1.5 size-2 rounded-full bg-muted-foreground/40'} />
                {i < ticket.events.length - 1 && <span className="absolute top-4 bottom-0 w-px bg-border" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">{e.label}</p>
                {e.note && <p className="text-sm text-muted-foreground">{e.note}</p>}
                <p className="text-xs tabular-nums text-muted-foreground">{formatTime(e.at)}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}

export function TicketSheet({ caseId, onClose }: { caseId: string | null; onClose: () => void }) {
  const gw = useResidentGateway();
  const ticket = caseId ? gw.getTicket(caseId) : null;
  return (
    <Sheet open={!!ticket} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="data-[side=right]:w-full data-[side=right]:sm:max-w-md">
        {ticket && (
          <>
            <SheetHeader className="gap-2 pr-12">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium tabular-nums text-muted-foreground">{ticket.code}</span>
                <StatusBadge ticket={ticket} />
              </div>
              <SheetTitle className="text-base leading-snug">{ticket.title}</SheetTitle>
              <SheetDescription>{ticket.detail}</SheetDescription>
            </SheetHeader>
            <TicketDetail key={ticket.caseId} ticket={ticket} />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
