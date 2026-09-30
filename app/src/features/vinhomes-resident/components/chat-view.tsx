import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate } from '@tanstack/react-router';
import { IconMapPin, IconPlus, IconSparkles } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useResidentGateway, type ConversationSummary } from '../hooks/use-resident-gateway';
import { formatTime } from '../lib/format';
import { myApartmentLocation } from '../lib/reception-agent';
import type { ConversationMessage } from '../types';
import { Composer } from './composer';
import { useOpenTicket } from './resident-layout';
import { TicketCard } from './ticket-ui';

export function AgentAvatar({ className }: { className?: string }) {
  return (
    <span className={cn('flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground', className)}>
      <IconSparkles className="size-4" />
    </span>
  );
}

function MessageRow({ message }: { message: ConversationMessage }) {
  const gw = useResidentGateway();
  const openTicket = useOpenTicket();
  const navigate = useNavigate();
  const ticket = message.ticketCaseId ? gw.getTicket(message.ticketCaseId) : null;

  if (message.role === 'resident') {
    return (
      <li className="flex flex-col items-end gap-1">
        {message.photos && message.photos.length > 0 && (
          <div className="flex max-w-[85%] flex-wrap justify-end gap-1.5">
            {message.photos.map((p) => (
              <img key={p.id} src={p.url} alt={p.name} className="size-24 rounded-xl border object-cover" />
            ))}
          </div>
        )}
        {message.text && (
          <p className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-[15px] whitespace-pre-line text-primary-foreground">
            {message.text}
          </p>
        )}
        <span className="px-1 text-[11px] tabular-nums text-muted-foreground">{formatTime(message.createdAt)}</span>
      </li>
    );
  }

  return (
    <li className="flex gap-2.5">
      <AgentAvatar />
      <div className="flex min-w-0 max-w-[85%] flex-col gap-2">
        <p className="rounded-2xl rounded-tl-md bg-muted px-3.5 py-2 text-[15px] whitespace-pre-line">{message.text}</p>
        {ticket && <TicketCard ticket={ticket} compact onOpen={() => openTicket(ticket.caseId)} />}
        {message.suggestNewConversation && (
          <Button variant="outline" size="sm" className="self-start" onClick={() => navigate({ to: '/resident' })}>
            <IconPlus data-icon="inline-start" /> Cuộc trò chuyện mới
          </Button>
        )}
        <span className="px-1 text-[11px] tabular-nums text-muted-foreground">{formatTime(message.createdAt)}</span>
      </div>
    </li>
  );
}

function DraftReview({ conversation }: { conversation: ConversationSummary }) {
  const gw = useResidentGateway();
  const [error, setError] = useState<string | null>(null);
  const draft = conversation.draft;
  if (draft?.step !== 'review') return null;
  const act = (fn: () => void) => {
    setError(null);
    try {
      fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chưa gửi được, bạn thử lại nhé.');
    }
  };
  return (
    <section className="ml-10 flex flex-col gap-3 rounded-xl border bg-card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Kiểm tra trước khi gửi</p>
      <dl className="flex flex-col gap-2 text-sm">
        <div>
          <dt className="text-muted-foreground">Sự cố</dt>
          <dd className="whitespace-pre-line">{draft.description}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Vị trí</dt>
          <dd>{draft.location}</dd>
        </div>
      </dl>
      {draft.photos.length > 0 && (
        <div className="flex gap-1.5">
          {draft.photos.map((p) => (
            <img key={p.id} src={p.url} alt={p.name} className="size-16 rounded-lg border object-cover" />
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Yêu cầu sẽ gửi tới Ban quản lý tòa {gw.profile.towerCode} kèm tên và số điện thoại của bạn để nhân viên liên hệ.
      </p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button variant="outline" size="lg" className="flex-1" onClick={() => act(() => gw.cancelDraft(conversation.id))}>
          Hủy
        </Button>
        <Button size="lg" className="flex-1" onClick={() => act(() => gw.submitDraft(conversation.id))}>
          Gửi yêu cầu
        </Button>
      </div>
    </section>
  );
}

function suggestionsFor(conversation: ConversationSummary, apartment: string): string[] {
  if (conversation.ticket) return conversation.ticket.isOpen ? ['Tiến độ thế nào rồi?'] : [];
  if (conversation.draft?.step === 'location') return [`Tại căn hộ của tôi (${apartment})`];
  if (conversation.draft) return [];
  return ['Báo sự cố', 'Xem tiến độ yêu cầu', 'Giờ yên tĩnh là mấy giờ?'];
}

export function ChatView({ conversationId }: { conversationId: string }) {
  const gw = useResidentGateway();
  const openTicket = useOpenTicket();
  const conversation = gw.getConversation(conversationId);
  const messages = gw.getMessages(conversationId);
  const end = useRef<HTMLDivElement>(null);

  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll to the newest message whenever the thread or draft card grows.
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, conversation?.draft?.step]);

  const unread = conversation?.unread ?? 0;
  const { markRead } = gw;
  useEffect(() => {
    if (unread > 0) markRead(conversationId);
  }, [unread, conversationId, markRead]);

  if (!conversation) return <Navigate to="/resident" replace />;
  const ticket = conversation.ticket;

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 flex-col gap-2 border-b px-4 py-3">
        <div className="mx-auto flex w-full max-w-3xl items-center gap-2">
          <h1 className="min-w-0 flex-1 truncate text-sm font-semibold">{conversation.title}</h1>
          {conversation.draft && !ticket && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <IconMapPin className="size-3.5" />
              {conversation.draft.step === 'description' ? 'Bước 1/3 · Mô tả' : conversation.draft.step === 'location' ? 'Bước 2/3 · Vị trí' : 'Bước 3/3 · Gửi'}
            </span>
          )}
        </div>
        {ticket && (
          <div className="mx-auto w-full max-w-3xl">
            <TicketCard ticket={ticket} compact onOpen={() => openTicket(ticket.caseId)} />
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <ol className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-5">
          {messages.map((m) => (
            <MessageRow key={m.id} message={m} />
          ))}
        </ol>
        <div className="mx-auto w-full max-w-3xl px-4 pb-4">
          <DraftReview conversation={conversation} />
        </div>
        <div ref={end} />
      </div>

      <div className="shrink-0 px-4 pt-2 pb-[max(env(safe-area-inset-bottom),0.75rem)]">
        <div className="mx-auto w-full max-w-3xl">
          <Composer
            placeholder={
              ticket
                ? 'Nhắn thêm về yêu cầu này…'
                : conversation.draft?.step === 'location'
                  ? `VD: ${myApartmentLocation(gw.profile)}, bếp`
                  : 'Mô tả sự cố hoặc đặt câu hỏi…'
            }
            suggestions={suggestionsFor(conversation, gw.profile.apartmentLabel)}
            onSend={(text, photos) => {
              gw.sendMessage(conversationId, text, photos);
            }}
          />
        </div>
      </div>
    </div>
  );
}
