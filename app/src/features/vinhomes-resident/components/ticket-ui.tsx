import { IconChevronRight } from '@tabler/icons-react';
import { cn } from '@/lib/utils';
import { formatVnd } from '@/features/vinhomes-operations/lib/field-flow';
import type { QuoteLine } from '@/features/vinhomes-operations/types/field-flow';
import type { PendingAction, QuoteView, ResidentTicketView, TicketTone } from '../types';

const TONE_CLASS: Record<TicketTone, string> = {
  neutral: 'bg-muted text-foreground',
  info: 'bg-sky-50 text-sky-800 dark:bg-sky-500/15 dark:text-sky-200',
  attention: 'bg-amber-50 text-amber-900 dark:bg-amber-500/15 dark:text-amber-200',
  success: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200',
  muted: 'bg-muted text-muted-foreground',
  danger: 'bg-rose-50 text-rose-800 dark:bg-rose-500/15 dark:text-rose-200',
};

const DOT_CLASS: Record<TicketTone, string> = {
  neutral: 'bg-muted-foreground/60',
  info: 'bg-sky-500',
  attention: 'bg-amber-500',
  success: 'bg-emerald-500',
  muted: 'bg-muted-foreground/40',
  danger: 'bg-rose-500',
};

export function StatusBadge({ ticket, className }: { ticket: Pick<ResidentTicketView, 'statusLabel' | 'tone'>; className?: string }) {
  return (
    <span className={cn('inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium', TONE_CLASS[ticket.tone], className)}>
      <span aria-hidden className={cn('size-1.5 rounded-full', DOT_CLASS[ticket.tone])} />
      {ticket.statusLabel}
    </span>
  );
}

export function StatusDot({ tone }: { tone: TicketTone }) {
  return <span aria-hidden className={cn('size-2 shrink-0 rounded-full', DOT_CLASS[tone])} />;
}

export function pendingActionLabel(action: PendingAction): string {
  switch (action.type) {
    case 'AGREE_QUOTE':
      return action.quote.noCharge ? 'Xác nhận bắt đầu sửa' : `Duyệt danh mục sửa chữa · ${formatVnd(action.quote.total)}`;
    case 'SIGN':
      return `Ký xác nhận kết quả · ${formatVnd(action.quote.total)}`;
    case 'CONFIRM_COMPLETION':
      return 'Xác nhận hoàn thành';
  }
}

/** Thẻ theo dõi yêu cầu, hiện trong chat và trong "Yêu cầu của tôi". */
export function TicketCard({
  ticket,
  onOpen,
  compact = false,
}: {
  ticket: ResidentTicketView;
  onOpen: () => void;
  compact?: boolean;
}) {
  const action = ticket.pendingAction;
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'group flex w-full flex-col gap-2 rounded-xl border bg-card p-3.5 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
        action && 'border-amber-300 dark:border-amber-500/40',
      )}
    >
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium tabular-nums text-muted-foreground">{ticket.code}</span>
        <StatusBadge ticket={ticket} className="ml-auto" />
      </div>
      <p className={cn('font-medium leading-snug text-foreground', compact ? 'line-clamp-1 text-sm' : 'line-clamp-2 text-[15px]')}>{ticket.title}</p>
      <p className="line-clamp-2 text-sm text-muted-foreground">{ticket.detail}</p>
      {action && (
        <span className="mt-0.5 flex items-center justify-between gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 dark:bg-amber-500/15 dark:text-amber-100">
          <span className="min-w-0 truncate">Việc cần bạn làm: {pendingActionLabel(action)}</span>
          <IconChevronRight className="size-4 shrink-0" />
        </span>
      )}
    </button>
  );
}

function Lines({ lines }: { lines: QuoteLine[] }) {
  return (
    <ul className="divide-y">
      {lines.map((l) => (
        <li key={l.id} className="flex items-start justify-between gap-3 py-2">
          <div className="min-w-0">
            <p className="text-sm text-foreground">{l.name}</p>
            <p className="text-xs text-muted-foreground">
              {l.quantity} {l.unit} × {formatVnd(l.unit_price)}
            </p>
            {l.is_additional && l.additional_reason && <p className="text-xs text-amber-800 dark:text-amber-200">Lý do: {l.additional_reason}</p>}
          </div>
          <p className="shrink-0 text-sm font-medium tabular-nums">{formatVnd(l.amount)}</p>
        </li>
      ))}
    </ul>
  );
}

/** Danh mục vật tư & chi phí; `split` tách phần đã thống nhất và phần phát sinh (bước ký). */
export function QuoteTable({ quote, split = false }: { quote: QuoteView; split?: boolean }) {
  if (quote.noCharge) return <p className="rounded-lg border p-3 text-sm">Không phát sinh chi phí.</p>;
  const showSplit = split && quote.additionalLines.length > 0;
  return (
    <div className="flex flex-col gap-1 rounded-lg border p-3">
      {showSplit ? (
        <>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Đã thống nhất trước khi sửa</p>
          <Lines lines={quote.agreedLines} />
          <p className="pt-2 text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-200">Phát sinh trong khi sửa</p>
          <Lines lines={quote.additionalLines} />
        </>
      ) : (
        <Lines lines={quote.lines} />
      )}
      {quote.laborCost > 0 && (
        <p className="flex justify-between border-t py-2 text-sm">
          <span>Tiền công</span>
          <span className="font-medium tabular-nums">{formatVnd(quote.laborCost)}</span>
        </p>
      )}
      <p className="flex items-baseline justify-between border-t pt-2">
        <span className="text-sm font-semibold">Tổng cộng</span>
        <span className="text-lg font-semibold tabular-nums">{formatVnd(quote.total)}</span>
      </p>
      {quote.warrantyMonths > 0 && <p className="text-xs text-muted-foreground">Bảo hành {quote.warrantyMonths} tháng</p>}
    </div>
  );
}
