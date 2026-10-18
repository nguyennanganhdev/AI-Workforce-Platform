import {
	BotMessageSquare,
	Cable,
	CalendarClock,
	Ellipsis,
	Pencil,
	Plus,
	Settings2,
	Trash2,
	Users,
} from 'lucide-react';
import { useEffect, useState, type CSSProperties } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { ChatViewport } from './ChatViewport';
import type { SessionRecord } from '@/api';
import { sessionTime, useSessionPreview } from '@/components/chat/session-row-utils';
import { ChatRow } from '@/components/chat/SessionRow';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { EditAgentDialog } from '@/components/dialog/EditAgentDialog';
import { RenameSessionDialog } from '@/components/dialog/RenameSessionDialog';
import { AccountMenu } from '@/components/layout/AccountMenu';
import { Brand } from '@/components/layout/Brand';
import { AgentSelect } from '@/components/select/AgentSelect';
import { ChatTourController } from '@/components/tour/ChatTourController';
import { Button } from '@/components/ui/button';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarHeader,
	SidebarProvider,
	useSidebar,
} from '@/components/ui/sidebar';
import { AudioProvider } from '@/context/AudioContext';
import { useAgents } from '@/hooks/useAgents';
import { useSessions } from '@/hooks/useSessions';
import { useTranslation } from '@/i18n/useI18n.ts';

/**
 * The chat page's outer shell. Responsibilities split cleanly:
 *
 * - **This component** owns *which* `(agent, session)` is being
 *   viewed. The URL is the single source of truth: every selection
 *   (agent dropdown, session row, team member, new session) is a
 *   ``navigate(...)`` call. State is derived from ``useParams``,
 *   never duplicated in React state. Renders the main left sidebar
 *   (agent picker + session list + create/rename/delete actions) and
 *   computes the ``effective`` ids to feed the chat viewport.
 * - **`ChatViewport`** owns *what* to render for that pair: messages,
 *   model selector, permission mode, workspace drawer, team sidebar.
 *
 * Splitting along this seam means switching between the leader's
 * session and a focused team member is just a prop change for the
 * viewport — the leader's session list stays anchored in this outer
 * sidebar. Driving everything off URL also gets us browser back /
 * forward, shareable links, and refresh-preserving state for free.
 *
 * @returns The chat page JSX.
 */
/** localStorage keys holding the last (agent, session) the user viewed. */
const LAST_AGENT_KEY = 'chat_last_agent';
const LAST_SESSION_KEY = 'chat_last_session';

const SOURCE_ICON = {
	user: BotMessageSquare,
	schedule: CalendarClock,
	channel: Cable,
	team: Users,
};

const ChatPageInner = () => {
	const navigate = useNavigate();
	const {
		agentId: urlAgentId,
		sessionId: urlSessionId,
		memberId: urlMemberId,
	} = useParams<{
		agentId?: string;
		sessionId?: string;
		memberId?: string;
	}>();
	const { t } = useTranslation();
	const sessionPreview = useSessionPreview();
	const { agents, refetch: refetchAgents, remove: removeAgent } = useAgents();
	const {
		sessions,
		refetch: refetchSessions,
		create: createSession,
		update: updateSession,
		remove: removeSession,
	} = useSessions(urlAgentId ?? null);

	const { isMobile, setOpen, setOpenMobile } = useSidebar();
	const [editOpen, setEditOpen] = useState(false);
	const [deleteOpen, setDeleteOpen] = useState(false);
	const [renameOpen, setRenameOpen] = useState(false);
	const [renameSession, setRenameSession] = useState<SessionRecord | null>(null);
	const [deleteSessionOpen, setDeleteSessionOpen] = useState(false);
	const [sessionToDelete, setSessionToDelete] = useState<SessionRecord | null>(null);

	const selectedAgent = agents.find((a) => a.id === urlAgentId) ?? null;
	const currentView = sessions.find((v) => v.session.id === urlSessionId) ?? null;
	const showSourceIcons = new Set(sessions.map((view) => view.session.origin.type)).size > 1;

	// "Inner focus" — when the URL carries a third `:memberId` segment
	// the user is drilling into a team member's chat. The main sidebar
	// stays anchored on the outer (leader) session; only the chat
	// viewport follows this inner focus. When `urlMemberId` is
	// undefined or doesn't resolve to a known team member, the inner
	// focus collapses back to the outer (leader) session.
	const focusedMember = urlMemberId
		? (currentView?.team?.members.find((m) => m.agent.id === urlMemberId) ?? null)
		: null;
	const effectiveAgentId =
		focusedMember && focusedMember.session_id ? focusedMember.agent.id : (urlAgentId ?? null);
	const effectiveSessionId =
		focusedMember && focusedMember.session_id
			? focusedMember.session_id
			: currentView
				? (urlSessionId ?? null)
				: null;

	// Remember where the user was, so coming back to a bare `/chat` —
	// from another page, or from a new tab — reopens it instead of
	// making them pick the same pair again.
	useEffect(() => {
		if (!urlAgentId || !urlSessionId) return;
		localStorage.setItem(LAST_AGENT_KEY, urlAgentId);
		localStorage.setItem(LAST_SESSION_KEY, urlSessionId);
	}, [urlAgentId, urlSessionId]);

	// Redirect: URL is missing an agent → reopen the last one viewed,
	// falling back to the first, and rewrite the URL in-place (replace
	// so we don't pollute history).
	useEffect(() => {
		if (urlAgentId || agents.length === 0) return;
		const remembered = localStorage.getItem(LAST_AGENT_KEY);
		const agent = agents.find((a) => a.id === remembered) ?? agents[0];
		navigate(`/chat/${agent.id}`, { replace: true });
	}, [agents, urlAgentId, navigate]);

	// Redirect: URL has an agent but no session, or its sessionId no
	// longer exists for this agent → reopen the last session viewed
	// under *this* agent, falling back to the first available one.
	useEffect(() => {
		if (!urlAgentId || sessions.length === 0) return;
		const matches = urlSessionId && sessions.some((v) => v.session.id === urlSessionId);
		if (matches) return;
		const remembered =
			localStorage.getItem(LAST_AGENT_KEY) === urlAgentId
				? localStorage.getItem(LAST_SESSION_KEY)
				: null;
		const view = sessions.find((v) => v.session.id === remembered) ?? sessions[0];
		navigate(`/chat/${urlAgentId}/${view.session.id}`, { replace: true });
	}, [urlAgentId, urlSessionId, sessions, navigate]);

	/**
	 * Create a new session under the currently selected agent and
	 * pre-fill it with the model + fallback the currently open session
	 * is using (so "new chat" inherits whatever the user just had
	 * configured). Falls back to any other session under this agent
	 * when there is no current one — keeps the model choice sticky
	 * across "delete last → create new" instead of dropping back to
	 * whatever ChatViewport's auto-pick happens to land on. Navigates
	 * to the freshly created session.
	 */
	const handleCreateSession = async () => {
		if (!urlAgentId) return;
		const seedConfig = currentView?.session.config ?? sessions[0]?.session.config;
		const res = await createSession({
			agent_id: urlAgentId,
			...(seedConfig?.chat_model_config
				? { chat_model_config: seedConfig.chat_model_config }
				: {}),
			...(seedConfig?.sub_agent_chat_model_config
				? { sub_agent_chat_model_config: seedConfig.sub_agent_chat_model_config }
				: {}),
			...(seedConfig?.fallback_chat_model_config
				? { fallback_chat_model_config: seedConfig.fallback_chat_model_config }
				: {}),
		});
		navigate(`/chat/${urlAgentId}/${res.session_id}`);
	};

	const handleAgentDeleted = async () => {
		navigate('/chat', { replace: true });
		await refetchAgents();
	};

	const handleDeleteSession = async (sessionId: string) => {
		await removeSession(sessionId);
		// If we just removed the session the URL is pointing at, fall
		// back to the parent /chat/:agentId path; the redirect effect
		// will then pick the next available session.
		if (sessionId === urlSessionId && urlAgentId) {
			navigate(`/chat/${urlAgentId}`, { replace: true });
		}
	};

	const requestDeleteSession = (session: SessionRecord) => {
		setSessionToDelete(session);
		setDeleteSessionOpen(true);
	};

	const handleRenameConfirm = async (name: string) => {
		if (!renameSession) return;
		await updateSession(renameSession.id, { name });
	};

	return (
		<div className="flex h-full w-full min-h-0">
			<Sidebar
				collapsible={isMobile ? 'offcanvas' : 'none'}
				className="cue-column w-80 shrink-0 border-r border-sidebar-border bg-sidebar"
			>
				<SidebarHeader className="gap-3 px-3 py-4">
					<Brand />
					<div className="flex items-center gap-1">
						<AgentSelect
							className="min-w-0 flex-1"
							agents={agents}
							value={urlAgentId ?? null}
							onChange={(id) => navigate(`/chat/${id}`)}
							variant="ghost"
							size="default"
						/>
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									aria-label={t('agent-menu.settings')}
									disabled={!selectedAgent?.editable}
								>
									<Ellipsis />
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent className="w-auto">
								<DropdownMenuItem onClick={() => setEditOpen(true)}>
									<Settings2 />
									{t('agent-menu.settings')}
								</DropdownMenuItem>
								<DropdownMenuItem
									onClick={() => navigate(`/workforce/agents/${urlAgentId}`)}
								>
									<Settings2 />
									{t('shell.agentStudio')}
								</DropdownMenuItem>
								<DropdownMenuItem
									onClick={() => setDeleteOpen(true)}
									variant="destructive"
								>
									<Trash2 />
									{t('agent-menu.delete')}
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					</div>
					<Button
						id="tour-create-session"
						variant="outline"
						disabled={!urlAgentId}
						onClick={handleCreateSession}
					>
						<Plus />
						{t('chat.newSession')}
					</Button>
				</SidebarHeader>
				<SidebarContent className="no-scrollbar px-2">
					{sessions.length === 0 && (
						<p className="px-3 py-6 text-center text-sm text-muted-foreground">
							{t('chat.session.emptyTitle')}
						</p>
					)}
					{sessions.map((view) => {
						const SourceIcon = SOURCE_ICON[view.session.origin.type];
						return (
							<ChatRow
								key={view.session.id}
								avatarId={urlAgentId ?? ''}
								avatarLabel={selectedAgent?.data.name}
								title={view.session.config.name || view.session.id}
								time={sessionTime(view.session.updated_at)}
								preview={sessionPreview(view, selectedAgent?.data.name ?? '')}
								status={view.status}
								icon={showSourceIcons && <SourceIcon className="size-3 shrink-0" />}
								active={urlSessionId === view.session.id}
								onSelect={() => {
									navigate(`/chat/${urlAgentId}/${view.session.id}`);
									setOpenMobile(false);
								}}
								actions={
									<DropdownMenu>
										<DropdownMenuTrigger asChild>
											<Button
												variant="ghost"
												size="icon-sm"
												aria-label={t('chat.session.label')}
											>
												<Ellipsis />
											</Button>
										</DropdownMenuTrigger>
										<DropdownMenuContent
											className="w-auto"
											side="right"
											align="start"
										>
											<DropdownMenuItem
												onClick={() => {
													setRenameSession(view.session);
													setRenameOpen(true);
												}}
											>
												<Pencil />
												{t('session-menu.rename')}
											</DropdownMenuItem>
											<DropdownMenuItem
												variant="destructive"
												onClick={() => requestDeleteSession(view.session)}
											>
												<Trash2 />
												{t('session-menu.delete')}
											</DropdownMenuItem>
										</DropdownMenuContent>
									</DropdownMenu>
								}
							/>
						);
					})}
				</SidebarContent>
				<SidebarFooter className="border-t border-sidebar-border px-2 py-2">
					<AccountMenu showSettings showTour />
				</SidebarFooter>
			</Sidebar>
			<div className="flex min-w-0 flex-1">
				<ChatViewport
					key={`${effectiveAgentId}:${effectiveSessionId}`}
					agentId={effectiveAgentId}
					sessionId={effectiveSessionId}
					readOnly={focusedMember !== null}
					onSessionsChanged={refetchSessions}
				/>
			</div>
			{selectedAgent && (
				<>
					<EditAgentDialog
						open={editOpen}
						onOpenChange={setEditOpen}
						agent={selectedAgent}
						onUpdated={refetchAgents}
					/>
					<DeleteDialog
						open={deleteOpen}
						onOpenChange={setDeleteOpen}
						title={t('common.deleteTitle', {
							entity: t('dialog-agent-delete.entity'),
							name: selectedAgent.data.name,
						})}
						description={t('common.deleteDescription')}
						confirmLabel={t('dialog-agent-delete.confirm')}
						onConfirm={async () => {
							await removeAgent(selectedAgent.id);
							await handleAgentDeleted();
						}}
					/>
				</>
			)}
			<RenameSessionDialog
				open={renameOpen}
				onOpenChange={setRenameOpen}
				currentName={renameSession?.config.name ?? renameSession?.id ?? ''}
				onConfirm={handleRenameConfirm}
			/>
			<DeleteDialog
				open={deleteSessionOpen}
				onOpenChange={setDeleteSessionOpen}
				title={t('common.deleteTitle', {
					entity: t('dialog-session-delete.entity'),
					name: (() => {
						const raw = sessionToDelete?.config.name || sessionToDelete?.id || '';
						return raw.length > 30 ? `${raw.slice(0, 30)}…` : raw;
					})(),
				})}
				description={t('common.deleteDescription')}
				confirmLabel={t('dialog-session-delete.confirm')}
				onConfirm={async () => {
					if (sessionToDelete) {
						await handleDeleteSession(sessionToDelete.id);
					}
				}}
			/>
			<ChatTourController
				sessionsCount={sessions.length}
				onEnsureSidebarOpen={() => {
					setOpen(true);
					setOpenMobile(true);
				}}
			/>
		</div>
	);
};

export const ChatPage = () => (
	<AudioProvider>
		<SidebarProvider
			className="h-full min-h-0"
			defaultOpen
			style={{ '--sidebar-width': '20rem' } as CSSProperties}
		>
			<ChatPageInner />
		</SidebarProvider>
	</AudioProvider>
);
