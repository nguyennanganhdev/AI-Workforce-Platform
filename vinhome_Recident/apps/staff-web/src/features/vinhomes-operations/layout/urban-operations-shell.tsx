import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { Link, useLocation } from '@tanstack/react-router';
import { Bell, Building2, ChartColumn, History, Inbox, LayoutGrid, Search, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { UrbanNavigation, type UrbanNavItem } from './urban-navigation';
import { ConnectedOperationsShell as LegacyShell, type ShellNotice } from './connected-operations-shell';
import '../connected/foundation.css';

const titles: Record<string, string> = { '': 'Tổng quan', kanban: 'Yêu cầu', reports: 'Báo cáo', accounts: 'Tài khoản', units: 'Đơn vị quản lý', audit: 'Nhật ký' };
const icon = (Component: typeof Bell) => <Component size={16} strokeWidth={1.75} />;
export function UrbanOperationsShell({ name, email, management, administrator = false, field = false, alerts = [], notices = [], flush = false, banner, children, unit, buildingCount, searchItems = [] }: {
  name?: string; email?: string; management: boolean; administrator?: boolean; field?: boolean;
  alerts?: { id: string; title: string; location_json: { towerCode?: string } }[]; notices?: ShellNotice[];
  flush?: boolean; banner?: ShellNotice[]; children: ReactNode; unit?: string; buildingCount?: number;
  searchItems?: { id: string; title: string; location?: string; to: string }[];
}) {
  const path = useLocation().pathname.split('/')[2] || (administrator ? '' : 'kanban');
  const [modern, setModern] = useState(() => { try { return new URLSearchParams(location.search).get('ui') !== 'legacy' && localStorage.getItem('operations.ui') !== 'legacy'; } catch { return true; } });
  const [open, setOpen] = useState(() => window.innerWidth >= 1280);
  const [command, setCommand] = useState(false);
  const [query, setQuery] = useState('');
  const [read, setRead] = useState<string[]>([]);
  const role = administrator ? 'Quản trị viên' : 'Ban quản lý';
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setCommand(v => !v); } };
    document.addEventListener('keydown', key); return () => document.removeEventListener('keydown', key);
  }, []);
  const noticeCount = notices.reduce((total, notice) => total + (notice.count ?? 1), 0);
  const countFor = (page: string) => notices.filter(notice => notice.to.includes(`/operations/${page}`)).reduce((total, notice) => total + (notice.count ?? 1), 0);
  useEffect(() => { document.title = `${noticeCount ? `(${noticeCount}) ` : ''}${titles[path] || 'Vận hành'} | Vận hành đô thị`; }, [path, noticeCount]);
  const setVersion = (version: boolean) => { setModern(version); try { localStorage.setItem('operations.ui', version ? 'modern' : 'legacy'); } catch { /* The layout remains usable without storage. */ } };
  if (field || !modern) return <><LegacyShell name={name} management={management} administrator={administrator} field={field} alerts={alerts} notices={notices} flush={flush} banner={banner}>{!field && <Button className="m-3" onClick={() => setVersion(true)}>Dùng giao diện mới</Button>}{children}</LegacyShell></>;
  const work: UrbanNavItem[] = [
    ...(administrator ? [{ page: '' as const, label: 'Tổng quan', icon: icon(LayoutGrid) }] : []),
    { page: 'kanban', label: 'Yêu cầu', icon: icon(Inbox), count: countFor('kanban') },
    { page: 'reports', label: 'Báo cáo', icon: icon(ChartColumn) },
  ];
  const setup: UrbanNavItem[] = administrator ? [
    { page: 'accounts', label: 'Tài khoản', icon: icon(Users), count: countFor('accounts') },
    { page: 'units', label: 'Đơn vị quản lý', icon: icon(Building2) }, { page: 'audit', label: 'Nhật ký', icon: icon(History) },
  ] : [];
  const needle = query.trim().toLocaleLowerCase('vi');
  const navResults = [...work, ...setup].filter(item => item.label.toLocaleLowerCase('vi').includes(needle));
  const ticketResults = needle ? searchItems.filter(item => `${item.title} ${item.location || ''}`.toLocaleLowerCase('vi').includes(needle)).slice(0, 12) : [];
  const unread = notices.filter(n => !read.includes(n.id));
  return <SidebarProvider open={open} onOpenChange={setOpen} lang="vi" translate="no" className="operations-app connected-shell ops-ui notranslate flex h-[100dvh] min-h-0 w-full overflow-hidden" style={{ '--sidebar-width': '208px', '--sidebar-width-icon': '56px' } as CSSProperties}>
    <UrbanNavigation name={name || 'Đang tải tài khoản…'} email={email} role={role} administrator={administrator} page={path} work={work} setup={setup} unit={unit} buildingCount={buildingCount} onLegacy={() => setVersion(false)} />
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden"><header className="ops-topbar"><SidebarTrigger aria-label="Mở hoặc thu gọn điều hướng" /><h1>{titles[path] || 'Vận hành'}</h1><div id="ops-page-controls" className="ops-page-controls" /><span className="ops-topbar-spacer" />
      <button className="ops-search-trigger" onClick={() => setCommand(true)} aria-label="Tìm nhanh"><Search size={16} /><span>Tìm nhanh</span><kbd>Ctrl K</kbd></button>
      <DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="ops-bell" aria-label={`Thông báo, ${noticeCount} việc chờ xử lý`} />}><Bell size={18} />{noticeCount > 0 && <span className="ops-bell-count">{noticeCount}</span>}</DropdownMenuTrigger>
        <DropdownMenuContent className="ops-ui ops-notices" align="end"><div className="ops-notices-header"><strong>Cần bạn xử lý</strong><Button size="sm" variant="ghost" onClick={() => setRead(notices.map(n => n.id))}>Đánh dấu đã đọc tất cả</Button></div>{notices.length ? notices.map(n => <Link key={n.id} to={n.to} className="ops-notice"><Inbox size={16} /><span className="flex-1"><strong>{n.title}</strong><small>{n.note}</small></span>{unread.some(item => item.id === n.id) && <span className="ops-notice-unread" />}</Link>) : <p className="ops-empty">Không còn việc nào chờ bạn.</p>}</DropdownMenuContent>
      </DropdownMenu>
    </header><main className={flush ? 'min-h-0 flex-1 overflow-hidden' : 'min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 lg:p-6'}>{children}</main></div>
    <Dialog open={command} onOpenChange={setCommand}><DialogContent className="ops-ui"><DialogHeader><DialogTitle>Tìm nhanh</DialogTitle></DialogHeader><Input autoFocus value={query} onChange={e => setQuery(e.target.value)} placeholder="Tìm yêu cầu, căn hộ hoặc trang…" aria-label="Nội dung tìm kiếm" /><div className="ops-command-list">{ticketResults.map(item => <Link key={item.id} to={item.to} onClick={() => setCommand(false)} className="ops-command-link">{item.title}{item.location && <small>{item.location}</small>}</Link>)}{navResults.map(item => <Link key={item.page} to={item.page ? `/operations/${item.page}` : '/operations'} onClick={() => setCommand(false)} className="ops-command-link">{item.label}</Link>)}{!ticketResults.length && !navResults.length && <p className="ops-empty">Không tìm thấy kết quả. Thử tên hoặc căn hộ khác.</p>}</div></DialogContent></Dialog>
  </SidebarProvider>;
}
