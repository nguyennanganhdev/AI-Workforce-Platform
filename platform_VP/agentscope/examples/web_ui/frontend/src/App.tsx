import { QueryClientProvider } from '@tanstack/react-query';
import { Onborda, OnbordaProvider } from 'onborda';
import { useEffect, useMemo, useState } from 'react';
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { Toaster } from 'sonner';

import { MCPHubPage } from './pages/mcp';
import { SkillHubPage } from './pages/skill';
import { authApi } from '@/api';
import type { AuthUser } from '@/api';
import { AUTH_EXPIRED_EVENT } from '@/api/client';
import { RouteError } from '@/components/error/RouteError';
import { AppLayout } from '@/components/layout/AppLayout';
import { buildChatTour } from '@/components/tour/chatTourSteps';
import { TourCard } from '@/components/tour/TourCard';
import { UploadProvider } from '@/context/UploadContext';
import { useTranslation } from '@/i18n/useI18n';
import { queryClient } from '@/lib/query-client';
import { AuthPage } from '@/pages/auth';
import { ChannelPage } from '@/pages/channel';
import { ChatPage } from '@/pages/chat';
import { CredentialPage } from '@/pages/credential';
import { KnowledgePage } from '@/pages/knowledge';
import { SchedulePage } from '@/pages/schedule';

const router = createBrowserRouter([
	{
		element: <AppLayout />,
		errorElement: <RouteError />,
		children: [
			{
				// Content-level boundary: a crash in a page replaces only
				// the Outlet area, so AppLayout (the icon rail / nav) stays
				// usable. The parent route keeps its own errorElement as a
				// last-resort catch-all for AppLayout/AppSidebar crashes.
				errorElement: <RouteError />,
				children: [
					{ path: '/', element: <Navigate to="/chat" replace /> },
					{
						path: '/chat/:agentId?/:sessionId?/:memberId?',
						element: <ChatPage />,
					},
					{ path: '/schedule', element: <SchedulePage /> },
					{ path: '/channel', element: <ChannelPage /> },
					{ path: '/credential', element: <CredentialPage /> },
					{ path: '/mcp', element: <MCPHubPage /> },
					{ path: '/mcp/:hubId', element: <MCPHubPage /> },
					{ path: '/skill', element: <SkillHubPage /> },
					{ path: '/skill/:hubId', element: <SkillHubPage /> },
					{ path: '/knowledge', element: <KnowledgePage /> },
					{ path: '/knowledge/:kbId', element: <KnowledgePage /> },
				],
			},
		],
	},
	{ path: '/setup', element: <Navigate to="/" replace />, errorElement: <RouteError /> },
]);

function App() {
	const { t } = useTranslation();
	const [authStatus, setAuthStatus] = useState<'checking' | 'authenticated' | 'anonymous'>(
		'checking',
	);
	const [, setCurrentUser] = useState<AuthUser | null>(null);
	const tours = useMemo(() => [buildChatTour(t)], [t]);

	useEffect(() => {
		let active = true;
		authApi.restoreSession().then((user) => {
			if (!active) return;
			setCurrentUser(user);
			setAuthStatus(user ? 'authenticated' : 'anonymous');
		});
		const handleExpired = () => {
			setCurrentUser(null);
			setAuthStatus('anonymous');
			queryClient.clear();
		};
		window.addEventListener(AUTH_EXPIRED_EVENT, handleExpired);
		return () => {
			active = false;
			window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpired);
		};
	}, []);

	if (authStatus === 'checking') {
		return (
			<div className="flex min-h-screen items-center justify-center bg-canvas text-sm text-muted-foreground">
				{t('common.loading')}
			</div>
		);
	}

	if (authStatus === 'anonymous') {
		return (
			<>
				<AuthPage
					onAuthenticated={(user) => {
						setCurrentUser(user);
						setAuthStatus('authenticated');
					}}
				/>
				<Toaster richColors position="top-right" />
			</>
		);
	}

	return (
		<QueryClientProvider client={queryClient}>
			<OnbordaProvider>
				<Onborda
					steps={tours}
					cardComponent={TourCard}
					shadowOpacity="0.6"
					cardTransition={{ type: 'spring', duration: 0.4 }}
				>
					<UploadProvider>
						<RouterProvider router={router} />
					</UploadProvider>
					<Toaster richColors position="top-right" />
				</Onborda>
			</OnbordaProvider>
		</QueryClientProvider>
	);
}

export default App;
