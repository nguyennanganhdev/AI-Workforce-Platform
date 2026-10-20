import type { CSSProperties } from 'react';
import { Outlet } from 'react-router-dom';

import { SettingsSidebar } from '@/components/layout/SettingsSidebar';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { useCueTheme } from '@/hooks/useCueTheme';
import { useTranslation } from '@/i18n/useI18n';

/** Shared shell keeps chat and configuration pages beside the same navigation rail. */
export function SettingsLayout() {
	useCueTheme();
	const { t } = useTranslation();
	return (
		<SidebarProvider
			className="h-screen min-h-0 bg-canvas"
			// Always the icon rail on desktop: the pages need the width, the
			// labels live in the tooltips. Mobile keeps its drawer.
			open={false}
			style={
				{
					// Narrower than the chat's 320px: this is a list of seven short labels.
					'--sidebar-width': '16rem',
					// A 40px icon button inside an 8px gutter on each side.
					'--sidebar-width-icon': '3.5rem',
				} as CSSProperties
			}
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
