import { useEffect, useState, type ReactNode } from 'react';
import { IconAlertTriangle, IconCheck, IconClock, IconLock, IconX } from '@tabler/icons-react';
import { STEP_LABELS, formatDuration, type StageTone } from '../../lib/field-flow';
import type { FlowKind } from '../../types/field-flow';

/** Re-render every `intervalMs` so countdowns stay fresh. */
export function useNow(intervalMs = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

const TONE_CLASSES: Record<StageTone, string> = {
  red: 'bg-rose-50 text-rose-700 border-rose-200',
  amber: 'bg-amber-50 text-amber-800 border-amber-200',
  blue: 'bg-blue-50 text-blue-700 border-blue-200',
  green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  slate: 'bg-slate-100 text-slate-600 border-slate-200',
  violet: 'bg-violet-50 text-violet-700 border-violet-200',
};

export function StatusPill({ tone, children }: { tone: StageTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full border ${TONE_CLASSES[tone]}`}>
      {children}
    </span>
  );
}

const SEVERITY_META: Record<string, { label: string; cls: string }> = {
  P1: { label: 'Khẩn cấp', cls: 'bg-rose-600 text-white' },
  P2: { label: 'Cao', cls: 'bg-orange-500 text-white' },
  P3: { label: 'Bình thường', cls: 'bg-slate-200 text-slate-700' },
  P4: { label: 'Thấp', cls: 'bg-slate-100 text-slate-500' },
};

export function SeverityBadge({ severity }: { severity?: string }) {
  const meta = SEVERITY_META[severity || 'P3'] || SEVERITY_META.P3;
  return <span className={`text-xs font-bold px-2 py-0.5 rounded ${meta.cls}`}>{meta.label}</span>;
}

export function SlaCountdown({ dueAt, now }: { dueAt?: string | null; now: number }) {
  if (!dueAt) return null;
  const ms = new Date(dueAt).getTime() - now;
  const overdue = ms <= 0;
  const urgent = !overdue && ms < 30 * 60 * 1000;
  return (
    <span className={`inline-flex items-center gap-1 text-sm font-medium ${overdue || urgent ? 'text-rose-600' : 'text-slate-500'}`}>
      <IconClock className="w-4 h-4" />
      {overdue ? `Quá hạn ${formatDuration(-ms)}` : `Còn ${formatDuration(ms)}`}
    </span>
  );
}

export function AutoCompleteCountdown({ autoCompleteAt, now }: { autoCompleteAt?: string | null; now: number }) {
  if (!autoCompleteAt) return null;
  const ms = new Date(autoCompleteAt).getTime() - now;
  return (
    <span className="inline-flex items-center gap-1 text-sm text-violet-700">
      <IconClock className="w-4 h-4" />
      {ms > 0 ? `Tự động hoàn thành sau ${formatDuration(ms)}` : 'Đang tự động hoàn thành…'}
    </span>
  );
}

export function StepProgress({ current, kind = 'REPAIR' }: { current: number; kind?: FlowKind }) {
  return (
    <ol className="flex items-center gap-1" aria-label="Tiến trình công việc">
      {STEP_LABELS[kind].map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={label} className="flex-1 flex flex-col items-center gap-1.5 min-w-0">
            <div className="w-full flex items-center">
              <div className={`h-1.5 flex-1 rounded-full ${done || active ? 'bg-blue-600' : 'bg-slate-200'}`} />
            </div>
            <span className={`text-xs truncate max-w-full ${active ? 'text-blue-700 font-semibold' : done ? 'text-slate-600' : 'text-slate-400'}`}>
              {done ? '✓ ' : ''}{label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** Sticky footer holding the one primary action (and at most one secondary). */
export function BottomActionBar({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div
      className="sticky bottom-0 z-20 -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 mt-4 border-t border-slate-200 bg-white/95 backdrop-blur px-3 sm:px-5 pt-3"
      style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)' }}
    >
      <div className="max-w-2xl mx-auto space-y-2">
        {hint}
        <div className="flex gap-2">{children}</div>
      </div>
    </div>
  );
}

type BtnVariant = 'primary' | 'secondary' | 'danger' | 'success';
const BTN_CLASSES: Record<BtnVariant, string> = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-slate-300',
  success: 'bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-slate-300',
  danger: 'bg-white text-rose-600 border border-rose-200 hover:bg-rose-50',
  secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50',
};

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
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`${grow ? 'flex-1' : 'shrink-0'} min-h-12 px-4 rounded-xl text-base font-semibold inline-flex items-center justify-center gap-2 transition-colors disabled:cursor-not-allowed ${BTN_CLASSES[variant]}`}
    >
      {children}
    </button>
  );
}

/** Lists what is still missing, shown right above a locked primary button. */
export function ChecklistGate({ blockers }: { blockers: string[] }) {
  if (blockers.length === 0) return null;
  return (
    <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
      <p className="text-sm font-semibold text-amber-800 flex items-center gap-1.5">
        <IconLock className="w-4 h-4" /> Còn thiếu trước khi tiếp tục:
      </p>
      <ul className="mt-1 space-y-0.5">
        {blockers.map((b) => (
          <li key={b} className="text-sm text-amber-800">• {b}</li>
        ))}
      </ul>
    </div>
  );
}

export function Section({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-800">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Banner({ kind, children, onClose }: { kind: 'error' | 'success'; children: ReactNode; onClose?: () => void }) {
  const cls = kind === 'error' ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800';
  const Icon = kind === 'error' ? IconAlertTriangle : IconCheck;
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm ${cls}`}>
      <Icon className="w-5 h-5 shrink-0" />
      <div className="flex-1">{children}</div>
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Đóng" className="p-1 -m-1">
          <IconX className="w-4 h-4" />
        </button>
      )}
    </div>
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
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <button type="button" aria-label="Đóng" className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative w-full sm:max-w-md bg-white rounded-t-2xl sm:rounded-2xl p-4 space-y-4"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 16px)' }}
      >
        <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
        {reasons && (
          <div className="flex flex-wrap gap-2">
            {(Object.keys(reasons) as T[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setReason(key)}
                className={`min-h-11 px-4 rounded-full border text-sm font-medium ${
                  reason === key ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-slate-300 text-slate-700'
                }`}
              >
                {reasons[key]}
              </button>
            ))}
          </div>
        )}
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder={needsNote ? 'Ghi chú (bắt buộc)' : 'Ghi chú thêm (không bắt buộc)'}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-base"
        />
        <div className="flex gap-2">
          <ActionButton variant="secondary" onClick={onClose}>Hủy</ActionButton>
          <ActionButton disabled={!canConfirm} onClick={() => onConfirm(reason, note)}>{confirmLabel}</ActionButton>
        </div>
      </div>
    </div>
  );
}
