import type { CSSProperties } from 'react';
import { Outlet } from 'react-router-dom';

import { SettingsSidebar } from '@/components/layout/SettingsSidebar';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { useCueTheme } from '@/hooks/useCueTheme';
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
	useCueTheme();
	const { t } = useTranslation();

	return (
		<SidebarProvider
			className="h-screen min-h-0 bg-canvas"
			// Narrower than the chat's 320px: this is a list of seven short labels.
			style={{ '--sidebar-width': '16rem' } as CSSProperties}
		>
			<SettingsSidebar />
			<div className="flex min-w-0 flex-1 flex-col">
				{/* Mobile only: the one way to reach the drawer. */}
				<div className="flex h-12 shrink-0 items-center gap-2 px-2 md:hidden">
					<SidebarTrigger />
					<span className="text-[17px]/6 font-medium">{t('common.settings')}</span>
				</div>
				<div className="min-h-0 flex-1">
					<Outlet />
				</div>
			</div>
		</SidebarProvider>
	);
}
