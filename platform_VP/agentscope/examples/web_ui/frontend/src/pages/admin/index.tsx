import { LogOut, ShieldCheck, Users } from 'lucide-react';
import { type ComponentType, type CSSProperties, useState } from 'react';

import { UsersPanel } from './UsersPanel';
import { VinAdministration } from './VinAdministration';
import type { AuthUser } from '@/api/auth';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuBadge,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarProvider,
	SidebarTrigger,
	useSidebar,
} from '@/components/ui/sidebar';
import { Skeleton } from '@/components/ui/skeleton';
import { usePlatformAccess } from '@/context/platform-access';
import { useCueTheme } from '@/hooks/useCueTheme';

type Section = 'users' | 'vin';

/** One admin page: a title, what it is for, its actions, then its content. */
function Page({ title, hint, action, children }: { title: string; hint: string; action?: React.ReactNode; children: React.ReactNode }) {
	return (
		<main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
			<div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3 pb-3">
				<div className="min-w-0">
					<h1 className="text-[17px]/6 font-semibold">{title}</h1>
					<p className="mt-0.5 text-[13px]/[18px] text-muted-foreground">{hint}</p>
				</div>
				{action}
			</div>
			<Separator />
			<div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">{children}</div>
		</main>
	);
}

/** A Cue nav row, as in the settings sidebar. */
const ITEM =
	'h-10 gap-3 rounded-xl px-3 text-[15px]/5 [&_svg]:size-[18px] group-data-[collapsible=icon]:size-10! group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0! group-data-[collapsible=icon]:[&>span]:sr-only';

function AdminSidebar({
	user,
	title,
	items,
	section,
	onSection,
	onLogout,
}: {
	user: AuthUser;
	title: string;
	items: { key: Section; label: string; icon: ComponentType; count?: number }[];
	section: Section;
	onSection: (section: Section) => void;
	onLogout: () => void;
}) {
	const { isMobile, setOpenMobile } = useSidebar();
	return (
		<Sidebar collapsible={isMobile ? 'offcanvas' : 'icon'} className="cue-column border-r border-sidebar-border">
			<SidebarHeader className="h-12 shrink-0 justify-center px-4 py-0 group-data-[collapsible=icon]:px-2">
				<p className="truncate text-[15px]/5 font-semibold group-data-[collapsible=icon]:sr-only">{title}</p>
			</SidebarHeader>
			<SidebarContent>
				<SidebarGroup className="px-2 py-1">
					<SidebarGroupContent>
						<SidebarMenu>
							{items.map((item) => (
								<SidebarMenuItem key={item.key}>
									<SidebarMenuButton
										className={ITEM}
										isActive={section === item.key}
										tooltip={item.label}
										onClick={() => {
											onSection(item.key);
											setOpenMobile(false);
										}}
									>
										<item.icon />
										<span>{item.label}</span>
									</SidebarMenuButton>
									{item.count ? <SidebarMenuBadge>{item.count}</SidebarMenuBadge> : null}
								</SidebarMenuItem>
							))}
						</SidebarMenu>
					</SidebarGroupContent>
				</SidebarGroup>
			</SidebarContent>
			<SidebarFooter className="border-t border-sidebar-border p-2">
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<button
							type="button"
							title={user.username}
							className="flex h-12 w-full items-center gap-3 rounded-xl px-2 hover:bg-[var(--cue-bg-hover,var(--accent))] group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
						>
							<span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--cue-avatar-user,#e5484d)] text-[15px] font-medium text-white">
								{user.username.charAt(0).toUpperCase()}
							</span>
							<span className="min-w-0 flex-1 truncate text-left text-[15px]/5 group-data-[collapsible=icon]:hidden">
								{user.username}
							</span>
						</button>
					</DropdownMenuTrigger>
					<DropdownMenuContent side="right" align="end" className="w-auto min-w-48">
						<DropdownMenuLabel className="font-normal text-muted-foreground">{user.username}</DropdownMenuLabel>
						<DropdownMenuSeparator />
						<DropdownMenuItem variant="destructive" onClick={onLogout}>
							<LogOut /> Đăng xuất
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</SidebarFooter>
		</Sidebar>
	);
}

export function AdminPage({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
	useCueTheme();
	const access = usePlatformAccess();
	const manageAccounts = access?.view?.capabilities['accounts.manage'] === true;
	const manageVin = access?.view?.capabilities['quota.manage'] === true || access?.view?.capabilities['catalog.manage'] === true;
	const [section, setSection] = useState<Section>('users');

	const items: { key: Section; label: string; icon: ComponentType; count?: number }[] = [
		...(manageAccounts ? [{ key: 'users' as const, label: 'Người dùng', icon: Users }] : []),
		...(manageVin ? [{ key: 'vin' as const, label: 'Hạn mức & thư viện', icon: ShieldCheck }] : []),
	];
	const current = items.some((item) => item.key === section) ? section : items[0]?.key;

	const content = !access?.view ? (
		<main className="flex-1 space-y-4 p-4">
			<Skeleton className="h-10 w-72" />
			<Skeleton className="h-64 w-full" />
		</main>
	) : current === 'users' ? (
		<Page title="Người dùng" hint="Tài khoản khách hàng tự đăng ký. Khoá thì người dùng bị đăng xuất ngay; xoá thì mất toàn bộ dữ liệu của họ.">
			<UsersPanel />
		</Page>
	) : current === 'vin' ? (
		<Page title="Hạn mức & thư viện" hint="Hạn mức token, quyền dùng AI, catalog tài nguyên dùng chung và các gói mẫu.">
			<VinAdministration />
		</Page>
	) : (
		<main className="flex-1 p-4 text-sm text-muted-foreground">Tài khoản này không có quyền quản trị.</main>
	);

	return (
		<SidebarProvider
			className={access ? 'h-full min-h-0 bg-canvas' : 'h-screen min-h-0 bg-canvas'}
			open={false}
			style={{ '--sidebar-width': '16rem', '--sidebar-width-icon': '3.5rem' } as CSSProperties}
		>
			<AdminSidebar
				user={user}
				title="Quản trị platform"
				items={items}
				section={current ?? 'users'}
				onSection={setSection}
				onLogout={onLogout}
			/>
			<div className="flex min-w-0 flex-1 flex-col">
				{/* Mobile only: the one way to reach the drawer. */}
				<div className="flex h-12 shrink-0 items-center gap-2 px-2 md:hidden">
					<SidebarTrigger />
					<span className="text-[17px]/6 font-medium">Quản trị</span>
				</div>
				<div className="flex min-h-0 flex-1">{content}</div>
			</div>
		</SidebarProvider>
	);
}
