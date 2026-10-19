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
import { ChatLayout } from '@/components/layout/ChatLayout';
import { SettingsLayout } from '@/components/layout/SettingsLayout';
import { buildChatTour } from '@/components/tour/chatTourSteps';
import { TourCard } from '@/components/tour/TourCard';
import { CurrentUserProvider } from '@/context/CurrentUserContext';
import { UploadProvider } from '@/context/UploadContext';
import { useTranslation } from '@/i18n/useI18n';
import { queryClient } from '@/lib/query-client';
import { AuthPage } from '@/pages/auth';
import { ChannelPage } from '@/pages/channel';
import { ChatPage } from '@/pages/chat';
import { CredentialPage } from '@/pages/credential';
import { KnowledgePage } from '@/pages/knowledge';
import { LandingPage } from '@/pages/landing';
import { SchedulePage } from '@/pages/schedule';
import { AgentManagementPage } from '@/pages/workforce/agents';
import { AgentBuilderPage } from '@/pages/workforce/builder';
import { LeaderPage } from '@/pages/workforce/leader';

const router = createBrowserRouter([
	{
		element: <ChatLayout />,
		errorElement: <RouteError />,
		children: [{ path: '/chat/:agentId?/:sessionId?/:memberId?', element: <ChatPage /> }],
	},
	{
		element: <SettingsLayout />,
		errorElement: <RouteError />,
		children: [
			{
				// Content-level boundary: a crash in a page replaces only
				// the Outlet area, so SettingsLayout (the icon rail / nav) stays
				// usable. The parent route keeps its own errorElement as a
				// last-resort catch-all for SettingsLayout/SettingsSidebar crashes.
				errorElement: <RouteError />,
				children: [
					{ path: '/', element: <Navigate to="/workforce/leader" replace /> },
					{ path: '/workforce/leader', element: <LeaderPage /> },
					{ path: '/workforce/builder', element: <AgentBuilderPage /> },
					{ path: '/workforce/agents/:agentId?', element: <AgentManagementPage /> },
					{ path: '/settings', element: <Navigate to="/workforce/agents" replace /> },
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
	...['/login', '/register', '/auth'].map((path) => ({
		path,
		element: <Navigate to="/" replace />,
	})),
]);

function App() {
	const { t } = useTranslation();
	const [authStatus, setAuthStatus] = useState<'checking' | 'authenticated' | 'anonymous'>(
		'checking',
	);
	const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
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
		if (window.location.pathname === '/') return <LandingPage />;
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
					<CurrentUserProvider value={currentUser}>
						<UploadProvider>
							<RouterProvider router={router} />
						</UploadProvider>
					</CurrentUserProvider>
					<Toaster richColors position="top-right" />
				</Onborda>
			</OnbordaProvider>
		</QueryClientProvider>
	);
}

export default App;
