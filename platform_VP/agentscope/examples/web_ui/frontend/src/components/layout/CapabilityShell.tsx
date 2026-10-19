import { AlertCircle, LogOut } from 'lucide-react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { authApi } from '@/api/auth';
import { Button } from '@/components/ui/button';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { usePlatformAccess } from '@/context/platform-access';
import { homeFor, mayVisit } from '@/features/workforce/shell/access';
import { AdminPage } from '@/pages/admin';

async function logoutFromShell() {
	try { await authApi.logout(); } finally { window.location.assign('/'); }
}

export function AccessBlocked({ unavailable = false, refresh, home }: { unavailable?: boolean; refresh?: () => void; home?: string }) {
	const navigate = useNavigate();
	return (
		<main className="flex min-h-0 flex-1 items-center justify-center p-6">
			<div className="max-w-md space-y-4 text-center" role="alert">
				<AlertCircle className="mx-auto size-8 text-muted-foreground" aria-hidden="true" />
				<h1 className="text-xl font-semibold">{unavailable ? 'Chưa xác minh được quyền truy cập' : 'Bạn chưa được cấp quyền cho trang này'}</h1>
				<p className="text-sm leading-6 text-muted-foreground">
					{unavailable ? 'Vui lòng thử lại. Các tác vụ sẽ khả dụng sau khi hệ thống xác minh được không gian và quyền hiện tại của bạn.'
						: 'Chọn một trang được cấp quyền hoặc chuyển sang không gian phù hợp.'}
				</p>
				<div className="flex flex-wrap justify-center gap-3">
					{home && <Button className="min-h-11" onClick={() => navigate(home, { replace: true })}>Về trang bắt đầu</Button>}
					{refresh && <Button className="min-h-11" variant="outline" onClick={refresh}>Thử lại</Button>}
					<Button className="min-h-11" variant="ghost" onClick={logoutFromShell}><LogOut aria-hidden="true" />Đăng xuất</Button>
				</div>
			</div>
		</main>
	);
}

/** All authenticated routes pass here, including direct URLs and legacy aliases. */
export function CapabilityShell() {
	const access = usePlatformAccess();
	const user = useCurrentUser();
	const location = useLocation();
	if (!access) return user?.role === 'VIN_USER' || ['/admin', '/account'].some((path) => location.pathname === path || location.pathname.startsWith(`${path}/`))
		? <AccessBlocked unavailable /> : <Outlet />;
	if (access.pending) return <div role="status" className="flex h-screen items-center justify-center bg-canvas p-6 text-sm">Đang xác minh không gian làm việc…</div>;
	if (!access.workspace || !access.view) return <div className="flex h-screen bg-canvas"><AccessBlocked unavailable refresh={access.refresh} /></div>;
	const workspace = access.workspace;
	const home = homeFor(workspace);
	const aliases = ['/', '/settings', '/setup', '/login', '/register', '/auth'];
	if (home && aliases.includes(location.pathname)) return <Navigate to={home} replace />;
	if (location.pathname.startsWith('/agents') && mayVisit(workspace, '/workforce/agents')) return <Navigate to="/workforce/agents?view=graph" replace />;
	const allowed = mayVisit(workspace, location.pathname);

	return (
		<div className="flex h-dvh min-h-0 flex-col bg-canvas">
			<a href="#workspace-content" className="sr-only rounded-md bg-background p-3 focus:not-sr-only focus:absolute focus:z-50">Đến nội dung</a>
			<div id="workspace-content" tabIndex={-1} className="relative flex min-h-0 flex-1 flex-col overflow-auto [&_[data-slot=sidebar-container]]:absolute [&_[data-slot=sidebar-container]]:h-full">
				{allowed ? <Outlet key={`${workspace.id}:${access.view.authorization_revision}`} /> : <AccessBlocked home={home ?? undefined} />}
			</div>
		</div>
	);
}

export function RoutedAdminPage() {
	const user = useCurrentUser();
	return user ? <AdminPage user={user} onLogout={logoutFromShell} /> : <AccessBlocked unavailable />;
}
