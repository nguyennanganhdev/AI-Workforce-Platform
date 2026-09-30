import { useNavigate } from '@tanstack/react-router';
import { IconBolt, IconDroplet, IconListCheck, IconShieldCheck } from '@tabler/icons-react';
import { useResidentGateway } from '../hooks/use-resident-gateway';
import { AgentAvatar } from './chat-view';
import { Composer } from './composer';
import { useOpenTicket } from './resident-layout';
import { TicketCard } from './ticket-ui';

const STARTERS = [
  { icon: IconDroplet, label: 'Báo rò rỉ nước', text: 'Báo sự cố rò rỉ nước' },
  { icon: IconBolt, label: 'Báo sự cố điện', text: 'Báo sự cố điện' },
  { icon: IconShieldCheck, label: 'Phản ánh tiếng ồn, an ninh', text: 'Phản ánh tiếng ồn' },
  { icon: IconListCheck, label: 'Xem tiến độ yêu cầu', text: 'Xem tiến độ yêu cầu' },
];

/** Màn hình cuộc trò chuyện mới: tin nhắn đầu tiên tạo cửa sổ chat. */
export function NewChat() {
  const gw = useResidentGateway();
  const navigate = useNavigate();
  const openTicket = useOpenTicket();
  const waiting = gw.tickets.filter((t) => t.pendingAction);

  const start = (text: string, photos: Parameters<typeof gw.sendMessage>[2] = []) => {
    const id = gw.sendMessage(null, text, photos);
    navigate({ to: '/resident/c/$conversationId', params: { conversationId: id } });
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-4 py-8">
        <div className="flex flex-col items-start gap-3">
          <AgentAvatar className="size-10" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Chào {gw.profile.name}, mình có thể giúp gì?</h1>
            <p className="text-sm text-muted-foreground">
              Căn hộ {gw.profile.apartmentLabel} · {gw.profile.projectName}. Mỗi cuộc trò chuyện theo dõi một yêu cầu.
            </p>
          </div>
        </div>

        {waiting.length > 0 && (
          <section className="flex flex-col gap-2">
            <h2 className="text-sm font-medium">Đang chờ bạn</h2>
            {waiting.map((t) => (
              <TicketCard key={t.caseId} ticket={t} compact onOpen={() => openTicket(t.caseId)} />
            ))}
          </section>
        )}

        <div className="grid grid-cols-2 gap-2">
          {STARTERS.map(({ icon: Icon, label, text }) => (
            <button
              key={label}
              type="button"
              onClick={() => start(text)}
              className="flex flex-col items-start gap-2 rounded-xl border bg-card p-3 text-left text-sm hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <Icon className="size-5 text-muted-foreground" />
              {label}
            </button>
          ))}
        </div>

        <Composer placeholder="Mô tả sự cố hoặc đặt câu hỏi…" onSend={(text, photos) => start(text, photos)} />
      </div>
    </div>
  );
}
