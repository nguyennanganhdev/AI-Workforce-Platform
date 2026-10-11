import type { CSSProperties } from 'react';
import { Outlet } from 'react-router-dom';

import { SettingsSidebar } from '@/components/layout/SettingsSidebar';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { useClayTheme } from '@/hooks/useClayTheme';
import { useTranslation } from '@/i18n/useI18n';

/**
 * The settings shell: everything that is configured rather than talked to —
 * schedules, channels, credentials, MCP, skills, knowledge — behind its own
 * navigation, with one way back to the chat.
 *
 * Split from {@link ChatLayout} so the chat is not one tab among seven: a
 * conversation gets the whole window, and configuration is somewhere you go
 * on purpose and come back from.
 */
export function SettingsLayout() {
	useClayTheme();
	const { t } = useTranslation();

	return (
		<SidebarProvider
			className="h-screen min-h-0 bg-canvas"
			// Narrower than the stock 16rem: this is a list of six short labels.
			style={{ '--sidebar-width': '13rem' } as CSSProperties}
		>
			{/* The gutter the slab floats in. Empty on mobile, where the
			    sidebar renders as a drawer instead. */}
			<div className="md:py-2 md:pl-2">
				<SettingsSidebar />
			</div>
			<div className="flex min-w-0 flex-1 flex-col">
				{/* Mobile only: the one way to reach the drawer. */}
				<div className="flex h-[52px] shrink-0 items-center gap-2 px-2 md:hidden">
					<SidebarTrigger />
					<span className="text-[16px]/[24px] font-semibold">
						{t('common.settings')}
					</span>
				</div>
				<div className="min-h-0 flex-1">
					<Outlet />
				</div>
			</div>
		</SidebarProvider>
	);
}
