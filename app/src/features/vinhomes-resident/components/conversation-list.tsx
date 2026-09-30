import { Link, useRouterState } from '@tanstack/react-router';
import { cn } from '@/lib/utils';
import { useResidentGateway } from '../hooks/use-resident-gateway';
import { formatShort } from '../lib/format';
import { StatusDot } from './ticket-ui';

export function ConversationList({ onNavigate }: { onNavigate?: () => void }) {
  const gw = useResidentGateway();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  if (gw.conversations.length === 0) {
    return <p className="px-3 py-2 text-sm text-muted-foreground">Chưa có cuộc trò chuyện nào.</p>;
  }

  return (
    <ul className="flex flex-col gap-0.5">
      {gw.conversations.map((c) => {
        const active = pathname === `/resident/c/${c.id}`;
        const subtitle = c.ticket
          ? `${c.ticket.code} · ${c.ticket.statusLabel}`
          : c.draft
            ? 'Đang soạn yêu cầu'
            : c.lastMessage?.text ?? 'Chưa có tin nhắn';
        return (
          <li key={c.id}>
            <Link
              to="/resident/c/$conversationId"
              params={{ conversationId: c.id }}
              onClick={onNavigate}
              aria-current={active ? 'page' : undefined}
              className={cn('flex flex-col gap-0.5 rounded-lg px-3 py-2 hover:bg-muted', active && 'bg-muted')}
            >
              <span className="flex items-center gap-2">
                <span className={cn('min-w-0 flex-1 truncate text-sm', c.unread > 0 ? 'font-semibold' : 'font-medium')}>{c.title}</span>
                <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">{formatShort(c.updatedAt)}</span>
              </span>
              <span className="flex items-center gap-1.5">
                {c.ticket && <StatusDot tone={c.ticket.tone} />}
                <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{subtitle}</span>
                {c.unread > 0 && (
                  <span className="flex h-4.5 min-w-4.5 shrink-0 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
                    {c.unread}
                  </span>
                )}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
