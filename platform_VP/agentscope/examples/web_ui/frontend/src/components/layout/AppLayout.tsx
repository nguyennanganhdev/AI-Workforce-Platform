import { Outlet } from 'react-router-dom';

import { AppSidebar } from '@/components/layout/AppSidebar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { useCueTheme } from '@/hooks/useCueTheme';

export function AppLayout() {
	// The sign-in page renders outside this layout and is left as it was.
	useCueTheme();

	return (
		<div className="h-screen flex">
			<SidebarProvider>
				<AppSidebar />
				<SidebarInset className="flex-1 overflow-hidden bg-canvas">
					<Outlet />
				</SidebarInset>
			</SidebarProvider>
		</div>
	);
}
