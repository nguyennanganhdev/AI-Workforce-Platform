import { Link } from '@tanstack/react-router';
import { IconBuildingCommunity, IconLogout } from '@tabler/icons-react';
import { Sidebar, SidebarHeader, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarMenuBadge, SidebarTrigger, useSidebar } from '@/components/ui/sidebar';
import type { ReactNode } from 'react';

export type NavigationPage = 'kanban' | 'reports' | 'accounts' | 'units' | 'audit' | 'my-tasks';
type Item = { page: NavigationPage; label: string; icon: ReactNode; count?: number };
export function ConnectedNavigation({ name, role, page, work, setup }: { name: string; role: string; page: string; work: Item[]; setup: Item[] }) {
  const { setOpenMobile } = useSidebar();
  const group = (title: string, items: Item[]) => items.length > 0 && <SidebarGroup>
    <SidebarGroupLabel>{title}</SidebarGroupLabel>
    <SidebarMenu>{items.map(item => <SidebarMenuItem key={item.page}>
      <SidebarMenuButton isActive={page === item.page} render={<Link to={`/operations/${item.page}`} />} onClick={() => setOpenMobile(false)} className="min-h-10 text-sm">
        {item.icon}<span>{item.label}</span>
      </SidebarMenuButton>
      {!!item.count && <SidebarMenuBadge>{item.count}</SidebarMenuBadge>}
    </SidebarMenuItem>)}</SidebarMenu>
  </SidebarGroup>;
  return <Sidebar collapsible="offcanvas" className="connected-navigation">
    <SidebarHeader className="flex-row items-center gap-2 px-4 py-4">
      <IconBuildingCommunity className="size-5 text-primary" stroke={1.5} />
      <span className="flex-1 text-base font-semibold tracking-tight">Vinhomes</span>
      <SidebarTrigger aria-label="Ẩn thanh điều hướng" />
    </SidebarHeader>
    <SidebarContent>{group('Không gian làm việc', work)}{group('Quản trị', setup)}</SidebarContent>
    <SidebarFooter className="border-t border-border p-3">
      <div className="flex min-w-0 items-center gap-3 px-2 py-2">
        <span aria-hidden="true" className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium">{name.charAt(0)}</span>
        <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium" title={name}>{name}</p><p className="text-xs text-muted-foreground">{role}</p></div>
      </div>
      <SidebarMenuButton onClick={() => { void fetch('/api/business/auth/logout', {method:'POST', credentials:'include'}).finally(() => location.assign('/operations/login')); }}>
        <IconLogout className="size-4" /><span>Đăng xuất</span>
      </SidebarMenuButton>
    </SidebarFooter>
  </Sidebar>;
}
