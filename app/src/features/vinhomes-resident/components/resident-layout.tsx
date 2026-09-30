import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate, useRouterState } from '@tanstack/react-router';
import { IconExternalLink, IconHome, IconLayoutList, IconLogout, IconMenu2, IconPlus } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { useResidentGateway } from '../hooks/use-resident-gateway';
import { ConversationList } from './conversation-list';
import { TicketSheet } from './ticket-sheet';

const TicketSheetContext = createContext<(caseId: string) => void>(() => {});

/** Opens the ticket detail sheet from anywhere in the resident app. */
export function useOpenTicket() {
  return useContext(TicketSheetContext);
}

function Sidebar({ onNavigate, onSignOut }: { onNavigate?: () => void; onSignOut: () => void }) {
  const gw = useResidentGateway();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const waiting = gw.tickets.filter((t) => t.pendingAction).length;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2.5 px-4 pt-4 pb-3">
        <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <IconHome className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-tight">Trợ lý cư dân</p>
          <p className="truncate text-xs text-muted-foreground">{gw.profile.projectName}</p>
        </div>
      </div>
      <div className="flex flex-col gap-1 px-3">
        <Button
          variant="outline"
          size="lg"
          className="justify-start"
          onClick={() => {
            onNavigate?.();
            navigate({ to: '/resident' });
          }}
        >
          <IconPlus data-icon="inline-start" /> Cuộc trò chuyện mới
        </Button>
        <Link
          to="/resident/tickets"
          onClick={onNavigate}
          className={cn(
            'flex h-10 items-center gap-2 rounded-lg px-2.5 text-sm hover:bg-muted',
            pathname === '/resident/tickets' && 'bg-muted font-medium',
          )}
        >
          <IconLayoutList className="size-4 text-muted-foreground" />
          Yêu cầu của tôi
          {waiting > 0 && (
            <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-500/20 dark:text-amber-100">
              {waiting} chờ bạn
            </span>
          )}
        </Link>
      </div>
      <p className="px-5 pt-4 pb-1.5 text-xs font-medium text-muted-foreground">Cuộc trò chuyện</p>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        <ConversationList onNavigate={onNavigate} />
      </div>
      <div className="flex flex-col gap-2 border-t px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-full bg-muted text-xs font-semibold">
            {gw.profile.name
              .split(' ')
              .map((w) => w[0])
              .join('')
              .slice(0, 2)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{gw.profile.name}</p>
            <p className="truncate text-xs text-muted-foreground">Căn hộ {gw.profile.apartmentLabel}</p>
          </div>
          <Button variant="ghost" size="icon-lg" aria-label="Đăng xuất" title="Đăng xuất" onClick={onSignOut}>
            <IconLogout />
          </Button>
        </div>
        <a
          href="/vinhomes/login"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          Đăng nhập nhân viên ở tab mới <IconExternalLink className="size-3" />
        </a>
      </div>
    </div>
  );
}

export function ResidentLayout({ children, onSignOut }: { children: ReactNode; onSignOut: () => void }) {
  const gw = useResidentGateway();
  const [menuOpen, setMenuOpen] = useState(false);
  const [ticketId, setTicketId] = useState<string | null>(null);

  useEffect(() => {
    const originalTitle = document.title;
    const originalLang = document.documentElement.lang;
    document.documentElement.lang = 'vi';
    return () => {
      document.title = originalTitle;
      document.documentElement.lang = originalLang;
    };
  }, []);
  useEffect(() => {
    document.title = gw.totalUnread > 0 ? `(${gw.totalUnread}) Trợ lý cư dân` : 'Trợ lý cư dân';
  }, [gw.totalUnread]);

  return (
    <TicketSheetContext.Provider value={setTicketId}>
      <div className="flex h-dvh overflow-hidden bg-background text-foreground">
        <aside className="hidden w-72 shrink-0 border-r bg-muted/30 md:block">
          <Sidebar onSignOut={onSignOut} />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center gap-1 border-b px-2 md:hidden">
            <Button variant="ghost" size="icon-lg" aria-label="Mở danh sách cuộc trò chuyện" onClick={() => setMenuOpen(true)} className="relative">
              <IconMenu2 />
              {gw.totalUnread > 0 && <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-rose-500" />}
            </Button>
            <p className="min-w-0 flex-1 truncate text-sm font-semibold">Trợ lý cư dân</p>
            <Button variant="ghost" size="icon-lg" aria-label="Cuộc trò chuyện mới" nativeButton={false} render={<Link to="/resident" />}>
              <IconPlus />
            </Button>
          </header>
          <main className="min-h-0 flex-1">{children}</main>
        </div>
      </div>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-[85%] max-w-80 gap-0 p-0" showCloseButton={false}>
          <SheetTitle className="sr-only">Điều hướng</SheetTitle>
          <Sidebar onNavigate={() => setMenuOpen(false)} onSignOut={onSignOut} />
        </SheetContent>
      </Sheet>
      <TicketSheet caseId={ticketId} onClose={() => setTicketId(null)} />
    </TicketSheetContext.Provider>
  );
}
