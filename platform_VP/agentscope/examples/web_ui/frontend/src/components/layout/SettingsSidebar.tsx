import { ArrowLeft, BookText, Bot, Cable, Calendars, KeyRound, LibraryBig } from 'lucide-react';
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
	useSidebar,
} from '@/components/ui/sidebar';
import { useTranslation } from '@/i18n/useI18n';

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
		items: [{ label: 'agents.title', icon: Bot, path: '/agents', prefix: true }],
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

/** A Cue nav row: 40px, 15px text, 12px corners, 20px thin icons. */
const ITEM = 'h-10 gap-3 rounded-xl px-3 text-[15px]/5 [&_svg]:size-[18px]';

/**
 * The settings shell's navigation: the way back to the chat on top, the
 * settings pages below, the account at the foot.
 */
export function SettingsSidebar() {
	const navigate = useNavigate();
	const location = useLocation();
	const { t } = useTranslation();
	const { isMobile, setOpenMobile } = useSidebar();

	const go = (path: string) => {
		navigate(path);
		setOpenMobile(false);
	};

	return (
		// Desktop keeps the panel in normal flow; mobile turns it into the
		// off-canvas drawer the layout's menu button opens.
		<Sidebar
			collapsible={isMobile ? 'offcanvas' : 'none'}
			className="cue-column border-r border-sidebar-border"
		>
			<SidebarHeader className="h-12 shrink-0 justify-center px-2 py-0">
				<SidebarMenu>
					<SidebarMenuItem>
						<SidebarMenuButton className={ITEM} onClick={() => go('/chat')}>
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
							<SidebarGroupLabel className="h-7 px-3 text-[13px]/[18px] font-normal text-[var(--cue-text-secondary,var(--muted-foreground))]">
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
				<AccountMenu />
			</SidebarFooter>
		</Sidebar>
	);
}
