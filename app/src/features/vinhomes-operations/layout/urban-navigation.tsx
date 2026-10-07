import { Link } from '@tanstack/react-router';
import { ChevronsUpDown, KeyRound, LogOut, PanelsTopLeft } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { ChangePasswordDialog } from './change-password';
import { Sidebar, SidebarHeader, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarMenuBadge, useSidebar } from '@/components/ui/sidebar';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export type UrbanNavItem = { page: '' | 'team' | 'ask' | 'agents' | 'reports' | 'accounts' | 'units' | 'connections' | 'models' | 'audit'; label: string; icon: ReactNode; count?: number };
export function UrbanNavigation({ name, email, role, administrator, page, work, setup, unit, buildingCount, onLegacy }: {
  name: string; email?: string; role: string; administrator: boolean; page: string; work: UrbanNavItem[]; setup: UrbanNavItem[]; unit?: string; buildingCount?: number; onLegacy: () => void;
}) {
  const { setOpenMobile } = useSidebar();
  const [changing, setChanging] = useState(false);
  const group = (label: string, items: UrbanNavItem[]) => <SidebarGroup>{label && <SidebarGroupLabel>{label}</SidebarGroupLabel>}<SidebarMenu>{items.map(item => <SidebarMenuItem key={item.page}>
    <SidebarMenuButton isActive={page === item.page} tooltip={item.label} render={<Link to={item.page ? `/operations/${item.page}` : '/operations'} />} onClick={() => setOpenMobile(false)}>
      {item.icon}<span>{item.label}</span>
    </SidebarMenuButton>{!!item.count && <SidebarMenuBadge>{item.count}</SidebarMenuBadge>}
  </SidebarMenuItem>)}</SidebarMenu></SidebarGroup>;
  const initials = name.split(' ').filter(Boolean).slice(-2).map(word => word[0]).join('').toLocaleUpperCase('vi');
  return <Sidebar collapsible="icon" className="urban-navigation">
    <SidebarHeader><div className="ops-unit-brand"><span className="ops-brand-mark">{administrator ? 'V' : (unit || 'BQL')[0]}</span><div className="ops-unit-copy"><strong>{administrator ? 'Vận hành đô thị' : unit || 'Ban quản lý'}</strong><small>{administrator ? 'Toàn hệ thống' : buildingCount ? `${buildingCount} tòa nhà` : 'Không gian vận hành'}</small></div><ChevronsUpDown className="ops-unit-chevron" size={16} aria-hidden="true" /></div></SidebarHeader>
    <SidebarContent>{group('', work)}{setup.length > 0 && group('Quản trị', setup)}</SidebarContent>
    <SidebarFooter><DropdownMenu><DropdownMenuTrigger className="ops-user" aria-label="Tài khoản và tùy chọn giao diện"><span className="ops-user-avatar">{initials}</span><span className="ops-user-copy"><strong>{name}</strong><small>{email || role}</small></span></DropdownMenuTrigger><DropdownMenuContent className="ops-ui" side="top" align="start">
      <DropdownMenuItem onClick={() => setChanging(true)}><KeyRound size={16} />Đổi mật khẩu</DropdownMenuItem>
      <DropdownMenuItem onClick={onLegacy}><PanelsTopLeft size={16} />Giao diện trước</DropdownMenuItem>
      <DropdownMenuItem onClick={() => { void fetch('/api/business/auth/logout', { method: 'POST', credentials: 'include' }).finally(() => location.assign('/operations/login')); }}><LogOut size={16} />Đăng xuất</DropdownMenuItem>
    </DropdownMenuContent></DropdownMenu>{changing && <ChangePasswordDialog onClose={() => setChanging(false)} />}</SidebarFooter>
  </Sidebar>;
}
