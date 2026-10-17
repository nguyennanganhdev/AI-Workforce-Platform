import { QueryClientProvider } from '@tanstack/react-query';
import { Onborda, OnbordaProvider } from 'onborda';
import { useEffect, useMemo, useState } from 'react';
import type { ComponentType } from 'react';
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { Toaster } from 'sonner';

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
import { LandingPage } from '@/pages/landing/LandingPage';

/**
 * Load a page's code only when its route is visited. The chat viewport pulls
 * in markdown, mermaid and code highlighting; keeping every page in the entry
 * chunk made the first load download all of it (3 MB entry chunk).
 */
function page<T extends Record<string, unknown>>(load: () => Promise<T>, name: keyof T) {
	return async () => ({ Component: (await load())[name] as ComponentType });
}

const router = createBrowserRouter([
	// Two shells. The chat gets the whole window; everything that is
	// configured rather than talked to lives behind its own navigation.
	{
		element: <ChatLayout />,
		errorElement: <RouteError />,
		children: [
			{
				// Content-level boundary: a crash in a page replaces only
				// the Outlet area, so the shell around it stays usable. The
				// parent route keeps its own errorElement as a last-resort
				// catch-all for a crash in the layout itself.
				errorElement: <RouteError />,
				children: [
					{
						path: '/chat/:agentId?/:sessionId?/:memberId?',
						lazy: page(() => import('@/pages/chat'), 'ChatPage'),
					},
				],
			},
		],
	},
	{
		element: <SettingsLayout />,
		errorElement: <RouteError />,
		children: [
			{
				errorElement: <RouteError />,
				children: [
					// Tickets and agents first: the Leader is the management board's
					// front door; settings keep their own paths so old links still work.
					{ path: '/', element: <Navigate to="/workforce/leader" replace /> },
					{
						path: '/workforce/leader',
						lazy: page(() => import('@/pages/workforce/leader'), 'LeaderPage'),
					},
					{
						path: '/workforce/builder',
						lazy: page(() => import('@/pages/workforce/builder'), 'AgentBuilderPage'),
					},
					{
						path: '/workforce/agents',
						lazy: page(
							() => import('@/pages/workforce/agents/compatible'),
							'AgentManagementPage',
						),
					},
					{
						path: '/workforce/agents/:agentId',
						lazy: page(
							() => import('@/pages/workforce/agents/compatible'),
							'AgentDetailPage',
						),
					},
					{ path: '/settings', element: <Navigate to="/workforce/agents" replace /> },
					// The agent map is a tab of agent management now.
					{
						path: '/agents/*',
						element: <Navigate to="/workforce/agents?view=graph" replace />,
					},
					{
						path: '/schedule',
						lazy: page(() => import('@/pages/schedule'), 'SchedulePage'),
					},
					{
						path: '/channel',
						lazy: page(() => import('@/pages/channel'), 'ChannelPage'),
					},
					{
						path: '/credential',
						lazy: page(() => import('@/pages/credential'), 'CredentialPage'),
					},
					{ path: '/mcp', lazy: page(() => import('./pages/mcp'), 'MCPHubPage') },
					{ path: '/mcp/:hubId', lazy: page(() => import('./pages/mcp'), 'MCPHubPage') },
					{ path: '/skill', lazy: page(() => import('./pages/skill'), 'SkillHubPage') },
					{
						path: '/skill/:hubId',
						lazy: page(() => import('./pages/skill'), 'SkillHubPage'),
					},
					{
						path: '/knowledge',
						lazy: page(() => import('@/pages/knowledge'), 'KnowledgePage'),
					},
					{
						path: '/knowledge/:kbId',
						lazy: page(() => import('@/pages/knowledge'), 'KnowledgePage'),
					},
				],
			},
		],
	},
	{ path: '/setup', element: <Navigate to="/" replace />, errorElement: <RouteError /> },
]);

function PlatformApp() {
	const { t } = useTranslation();
	const [authStatus, setAuthStatus] = useState<'checking' | 'authenticated' | 'anonymous'>(
		'checking',
	);
	const [showAuth, setShowAuth] = useState(false);
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
		return (
			<>
				{showAuth ? (
					<AuthPage
						onBack={() => setShowAuth(false)}
						onAuthenticated={(user) => {
							setCurrentUser(user);
							setAuthStatus('authenticated');
						}}
					/>
				) : (
					<LandingPage onGetStarted={() => setShowAuth(true)} />
				)}
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

export default PlatformApp;
