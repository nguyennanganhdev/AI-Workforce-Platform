import { useEffect, useState, type ReactNode } from 'react';
import { IconX } from '@tabler/icons-react';
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldLabel } from '@/components/ui/field';
import { Textarea } from '@/components/ui/textarea';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';
import { formatDuration, type StageTone } from '../../lib/field-flow';

/** Re-render every `intervalMs` so countdowns stay fresh. */
export function useNow(intervalMs = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

/**
 * Status is plain text: the wording already says what state the job is in.
 * `tone` is kept on the API so callers do not change, but it no longer colours anything.
 */
export function StatusPill({ children }: { tone?: StageTone; children: ReactNode }) {
  return <span className="shrink-0 text-sm text-slate-700">{children}</span>;
}

const SEVERITY_LABELS: Record<string, string> = {
  P1: 'Khẩn cấp',
  P2: 'Cao',
  P3: 'Bình thường',
  P4: 'Thấp',
};

export function severityLabel(severity?: string) {
  return SEVERITY_LABELS[severity || 'P3'] || SEVERITY_LABELS.P3;
}

/** Urgency is carried by weight, not colour. */
export function SeverityBadge({ severity }: { severity?: string }) {
  const urgent = severity === 'P1' || severity === 'P2';
  return <span className={cn('text-sm', urgent ? 'font-semibold text-foreground' : 'text-slate-600')}>{severityLabel(severity)}</span>;
}

export function slaText(dueAt: string | null | undefined, now: number) {
  if (!dueAt) return null;
  const ms = new Date(dueAt).getTime() - now;
  return { text: ms <= 0 ? `Quá hạn ${formatDuration(-ms)}` : `Còn ${formatDuration(ms)}`, pressing: ms < 30 * 60 * 1000 };
}

export function SlaCountdown({ dueAt, now }: { dueAt?: string | null; now: number }) {
  const sla = slaText(dueAt, now);
  if (!sla) return null;
  return <span className={cn('text-sm tabular-nums', sla.pressing ? 'font-semibold text-foreground' : 'text-slate-600')}>{sla.text}</span>;
}

export function autoCompleteText(autoCompleteAt: string | null | undefined, now: number) {
  if (!autoCompleteAt) return null;
  const ms = new Date(autoCompleteAt).getTime() - now;
  return ms > 0 ? `Tự hoàn thành sau ${formatDuration(ms)}` : 'Đang tự động hoàn thành…';
}

export function AutoCompleteCountdown({ autoCompleteAt, now }: { autoCompleteAt?: string | null; now: number }) {
  const text = autoCompleteText(autoCompleteAt, now);
  return text ? <span className="text-sm tabular-nums text-slate-600">{text}</span> : null;
}

/**
 * Sticky action bar that sits flush with the content column: no negative margins, so its left
 * and right edges always line up with the cards above, whatever width the content column has.
 */
export function BottomActionBar({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div
      className="sticky bottom-0 z-20 mt-2 flex flex-col gap-2 rounded-lg border bg-card/95 p-3 shadow-[0_-4px_16px_rgb(15_23_42/0.06)] backdrop-blur lg:flex-row lg:items-center lg:justify-between lg:gap-6 lg:px-4"
      style={{ marginBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      {hint && <div className="min-w-0 lg:flex-1">{hint}</div>}
      <div className="flex gap-2 lg:ml-auto lg:shrink-0">{children}</div>
    </div>
  );
}

type BtnVariant = 'primary' | 'secondary' | 'danger' | 'success';

/** One accent. `success`/`danger` stay as aliases so the flow code reads naturally. */
export function ActionButton({
  variant = 'primary',
  grow = true,
  disabled,
  onClick,
  children,
}: {
  variant?: BtnVariant;
  grow?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      variant={variant === 'primary' || variant === 'success' ? 'default' : 'outline'}
      size="lg"
      disabled={disabled}
      onClick={onClick}
      className={cn('h-11 px-4 text-[15px]', grow ? 'flex-1 lg:min-w-40 lg:flex-none' : 'shrink-0')}
    >
      {children}
    </Button>
  );
}

/** Lists what is still missing, shown right above a locked primary button. */
export function ChecklistGate({ blockers }: { blockers: string[] }) {
  if (blockers.length === 0) return null;
  return (
    <Alert className="bg-muted/40">
      <AlertTitle>Còn thiếu trước khi tiếp tục</AlertTitle>
      <AlertDescription>
        <ul className="list-disc pl-5">
          {blockers.map((b) => <li key={b}>{b}</li>)}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

export function Section({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="px-4 md:px-5">
        <CardTitle className="text-[15px] font-semibold">{title}</CardTitle>
        {right && <CardAction className="text-sm text-muted-foreground">{right}</CardAction>}
      </CardHeader>
      <CardContent className="flex flex-col gap-3 px-4 md:px-5">{children}</CardContent>
    </Card>
  );
}

export function Banner({ kind, children, onClose }: { kind: 'error' | 'success'; children: ReactNode; onClose?: () => void }) {
  return (
    <Alert variant={kind === 'error' ? 'destructive' : 'default'} role={kind === 'error' ? 'alert' : 'status'}>
      <AlertDescription className="text-foreground">{children}</AlertDescription>
      {onClose && (
        <AlertAction>
          <Button variant="ghost" size="icon-sm" aria-label="Đóng" onClick={onClose}>
            <IconX />
          </Button>
        </AlertAction>
      )}
    </Alert>
  );
}

/** Bottom sheet with quick-pick reason chips (+ free text when needed). */
export function ReasonSheet<T extends string>({
  title,
  reasons,
  confirmLabel,
  requireNoteFor,
  noteRequired = false,
  onConfirm,
  onClose,
}: {
  title: string;
  reasons: Partial<Record<T, string>> | null;
  confirmLabel: string;
  requireNoteFor?: T;
  noteRequired?: boolean;
  onConfirm: (reason: T | null, note: string) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState<T | null>(null);
  const [note, setNote] = useState('');
  const needsNote = noteRequired || (reason !== null && reason === requireNoteFor);
  const canConfirm = (reasons === null || reason !== null) && (!needsNote || note.trim().length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button type="button" aria-label="Đóng" className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative flex w-full flex-col gap-4 rounded-t-xl bg-card p-4 sm:max-w-md sm:rounded-xl sm:p-5"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 16px)' }}
      >
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        {reasons && (
          <ToggleGroup
            aria-label="Lý do"
            variant="outline"
            spacing={2}
            value={reason ? [reason] : []}
            onValueChange={(next) => setReason((next[0] as T | undefined) ?? null)}
            className="flex-wrap"
          >
            {(Object.keys(reasons) as T[]).map((key) => (
              <ToggleGroupItem
                key={key}
                value={key}
                size="lg"
                className="h-11 px-4 font-normal data-pressed:border-primary data-pressed:bg-primary data-pressed:text-primary-foreground"
              >
                {reasons[key]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        )}
        <Field>
          <FieldLabel htmlFor="reason-note">{needsNote ? 'Ghi chú (bắt buộc)' : 'Ghi chú thêm (không bắt buộc)'}</FieldLabel>
          <Textarea id="reason-note" value={note} onChange={(e) => setNote(e.target.value)} rows={3} className="text-base md:text-base" />
        </Field>
        <div className="flex gap-2">
          <ActionButton variant="secondary" onClick={onClose}>Hủy</ActionButton>
          <ActionButton disabled={!canConfirm} onClick={() => onConfirm(reason, note)}>{confirmLabel}</ActionButton>
        </div>
      </div>
    </div>
  );
}
