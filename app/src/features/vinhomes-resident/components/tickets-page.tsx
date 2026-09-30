import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useResidentGateway } from '../hooks/use-resident-gateway';
import { useOpenTicket } from './resident-layout';
import { TicketCard } from './ticket-ui';

type Filter = 'open' | 'done';

/** "Yêu cầu của tôi": mọi yêu cầu cư dân đã gửi, kể cả khi đã hoàn tất. */
export function TicketsPage() {
  const gw = useResidentGateway();
  const openTicket = useOpenTicket();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>('open');
  const list = gw.tickets.filter((t) => (filter === 'open' ? t.isOpen : !t.isOpen));
  const openCount = gw.tickets.filter((t) => t.isOpen).length;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 py-5">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold">Yêu cầu của tôi</h1>
            <p className="text-sm text-muted-foreground">Trạng thái cập nhật ngay khi nhân viên thao tác.</p>
          </div>
        </div>
        <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
          <TabsList>
            <TabsTrigger value="open">Đang xử lý ({openCount})</TabsTrigger>
            <TabsTrigger value="done">Đã xong ({gw.tickets.length - openCount})</TabsTrigger>
          </TabsList>
        </Tabs>
        {list.length === 0 ? (
          <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed p-5">
            <p className="text-sm text-muted-foreground">
              {filter === 'open' ? 'Bạn không có yêu cầu nào đang xử lý.' : 'Chưa có yêu cầu nào hoàn tất.'}
            </p>
            <Button variant="outline" onClick={() => navigate({ to: '/resident' })}>
              Báo sự cố mới
            </Button>
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {list.map((t) => {
              const conversationId = gw.conversationForCase(t.caseId);
              return (
                <li key={t.caseId} className="flex flex-col gap-1">
                  <TicketCard ticket={t} onOpen={() => openTicket(t.caseId)} />
                  {conversationId && (
                    <Button
                      variant="link"
                      size="sm"
                      className="self-start px-1"
                      onClick={() => navigate({ to: '/resident/c/$conversationId', params: { conversationId } })}
                    >
                      Mở cuộc trò chuyện
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
