import {
	ArrowLeft,
	BookText,
	Bot,
	Cable,
	Calendars,
	Crown,
	Hammer,
	KeyRound,
	LibraryBig,
	PanelLeftClose,
	PanelLeftOpen,
	Users,
} from 'lucide-react';
import type { ComponentType } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import MCPSvg from '@/assets/images/mcp.svg?react';
import { AccountMenu } from '@/components/layout/AccountMenu';
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarRail,
	useSidebar,
} from '@/components/ui/sidebar';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

interface SettingsItem {
	/** i18n key of the label. */
	label: string;
	icon: ComponentType<{ className?: string }>;
	path: string;
	/** Stays lit on the pages beneath it (`/mcp/:hubId`). */
	prefix?: boolean;
}

/**
 * Everything that is configured rather than talked to: the agents themselves
 * first, then what runs them day to day, then what they are able to use.
 */
const GROUPS: { label?: string; items: SettingsItem[] }[] = [
	{
		label: 'shell.groupWorkforce',
		items: [
			{ label: 'shell.leader', icon: Crown, path: '/workforce/leader' },
			{ label: 'shell.builder', icon: Hammer, path: '/workforce/builder' },
			{ label: 'shell.agentStudio', icon: Users, path: '/workforce/agents', prefix: true },
			{ label: 'shell.agentMap', icon: Bot, path: '/agents', prefix: true },
		],
	},
	{
		label: 'shell.groupOperations',
		items: [
			{ label: 'common.schedule', icon: Calendars, path: '/schedule' },
			{ label: 'common.channel', icon: Cable, path: '/channel' },
		],
	},
	{
		label: 'shell.groupCapabilities',
		items: [
			{ label: 'common.credential', icon: KeyRound, path: '/credential' },
			{ label: 'common.mcp-hub', icon: MCPSvg, path: '/mcp', prefix: true },
			{ label: 'common.skill-hub', icon: BookText, path: '/skill', prefix: true },
			{ label: 'common.knowledge', icon: LibraryBig, path: '/knowledge', prefix: true },
		],
	},
];

/**
 * A Cue nav row: 40px, 15px text, 12px corners, 20px thin icons. Folded to
 * icons it stays a 40px square, the icon centred, the label left to the tooltip.
 */
const ITEM =
	'h-10 gap-3 rounded-xl px-3 text-[15px]/5 [&_svg]:size-[18px] group-data-[collapsible=icon]:size-10! group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0! group-data-[collapsible=icon]:[&>span]:sr-only';

/**
 * The settings shell's navigation: the way back to the chat on top, the
 * settings pages below, the account at the foot.
 */
export function SettingsSidebar() {
	const navigate = useNavigate();
	const location = useLocation();
	const { t } = useTranslation();
	const { isMobile, setOpenMobile, open, toggleSidebar } = useSidebar();

	const go = (path: string) => {
		navigate(path);
		setOpenMobile(false);
	};

	return (
		// Desktop folds down to an icon rail (labels move into tooltips); mobile
		// turns it into the off-canvas drawer the layout's menu button opens.
		<Sidebar
			collapsible={isMobile ? 'offcanvas' : 'icon'}
			className="cue-column border-r border-sidebar-border"
		>
			<SidebarHeader className="h-12 shrink-0 justify-center px-2 py-0">
				<SidebarMenu>
					<SidebarMenuItem>
						<SidebarMenuButton
							className={ITEM}
							tooltip={t('shell.backToChat')}
							onClick={() => go('/chat')}
						>
							<ArrowLeft />
							<span>{t('shell.backToChat')}</span>
						</SidebarMenuButton>
					</SidebarMenuItem>
				</SidebarMenu>
			</SidebarHeader>
			<SidebarContent>
				{GROUPS.map((group) => (
					<SidebarGroup key={group.label ?? group.items[0].path} className="px-2 py-1">
						{group.label && (
							<SidebarGroupLabel
								// Folded, the label fades out over the row above it;
								// it must not catch that row's clicks.
								className="h-7 px-3 text-[13px]/[18px] font-normal text-[var(--cue-text-secondary,var(--muted-foreground))] group-data-[collapsible=icon]:pointer-events-none"
							>
								{t(group.label)}
							</SidebarGroupLabel>
						)}
						<SidebarGroupContent>
							<SidebarMenu>
								{group.items.map((item) => (
									<SidebarMenuItem key={item.path}>
										<SidebarMenuButton
											className={ITEM}
											isActive={
												item.prefix
													? location.pathname.startsWith(item.path)
													: location.pathname === item.path
											}
											tooltip={t(item.label)}
											onClick={() => go(item.path)}
										>
											<item.icon />
											<span>{t(item.label)}</span>
										</SidebarMenuButton>
									</SidebarMenuItem>
								))}
							</SidebarMenu>
						</SidebarGroupContent>
					</SidebarGroup>
				))}
			</SidebarContent>
			<SidebarFooter className="border-t border-sidebar-border p-2">
				{!isMobile && (
					<SidebarMenu>
						<SidebarMenuItem>
							<SidebarMenuButton
								className={cn(
									ITEM,
									'text-[var(--cue-text-secondary,var(--muted-foreground))]',
								)}
								tooltip={t('shell.expandSidebar')}
								aria-expanded={open}
								onClick={toggleSidebar}
							>
								{open ? <PanelLeftClose /> : <PanelLeftOpen />}
								<span>
									{t(open ? 'shell.collapseSidebar' : 'shell.expandSidebar')}
								</span>
							</SidebarMenuButton>
						</SidebarMenuItem>
					</SidebarMenu>
				)}
				<AccountMenu />
			</SidebarFooter>
			<SidebarRail />
		</Sidebar>
	);
}
