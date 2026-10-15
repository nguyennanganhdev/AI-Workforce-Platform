import { useQueryClient } from '@tanstack/react-query';
import {
	Bot,
	BotMessageSquare,
	Cable,
	CalendarClock,
	Check,
	ChevronDown,
	type LucideIcon,
	MessageSquarePlus,
	Pencil,
	Plus,
	Search,
	Trash2,
	Users,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { ChatViewport } from './ChatViewport';
import { sessionApi, type AgentView, type SessionRecord, type SessionSourceKind } from '@/api';
import { GroupAvatar } from '@/components/chat/GroupAvatar';
import { NewChatMenu } from '@/components/chat/NewChatMenu';
import { SearchPalette } from '@/components/chat/SearchPalette';
import { sessionTime, sessionTitle } from '@/components/chat/session-row-utils';
import { ChatRow } from '@/components/chat/SessionRow';
import { AgentDialog } from '@/components/dialog/AgentDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { EditAgentDialog } from '@/components/dialog/EditAgentDialog';
import { GroupChatDialog } from '@/components/dialog/GroupChatDialog';
import { QuickAgentDialog } from '@/components/dialog/QuickAgentDialog';
import { RenameSessionDialog } from '@/components/dialog/RenameSessionDialog';
import { AccountMenu } from '@/components/layout/AccountMenu';
import { Brand } from '@/components/layout/Brand';
import { ChatTourController } from '@/components/tour/ChatTourController';
import { Button } from '@/components/ui/button';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
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
import { useGroupChats } from '@/hooks/useGroupChats';
import { useSessions } from '@/hooks/useSessions';
import { useSettled } from '@/hooks/useSettled';
import { useTranslation } from '@/i18n/useI18n.ts';
import { type GroupChat, removeGroupChat } from '@/lib/group-chats';

/**
 * The chat page's outer shell, laid out like Cue: every agent is one
 * conversation in the sidebar, and its chats (sessions) sit behind a small
 * switcher in the chat header.
 *
 * - **This component** owns *which* `(agent, session)` is being
 *   viewed. The URL is the single source of truth: every selection
 *   (agent row, session switcher, team member, new session) is a
 *   ``navigate(...)`` call. State is derived from ``useParams``,
 *   never duplicated in React state. Renders the agent list with its
 *   create / search / edit / delete actions and computes the
 *   ``effective`` ids to feed the chat viewport.
 * - **`ChatViewport`** owns *what* to render for that pair: messages,
 *   model selector, permission mode, workspace drawer, team sidebar.
 *
 * Driving everything off URL also gets us browser back / forward,
 * shareable links, and refresh-preserving state for free.
 *
 * @returns The chat page JSX.
 */
// Icon per session origin, shown only when a list mixes sources.
const SOURCE_ICON: Record<SessionSourceKind, LucideIcon> = {
	user: BotMessageSquare,
	schedule: CalendarClock,
	channel: Cable,
	team: Users,
};

/** localStorage keys holding the last (agent, session) the user viewed. */
const LAST_AGENT_KEY = 'chat_last_agent';
const LAST_SESSION_KEY = 'chat_last_session';

const newestFirst = (a: string, b: string) => new Date(b).getTime() - new Date(a).getTime();

const ChatPageInner = ({ onAgentsChanged }: { onAgentsChanged: () => void }) => {
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
	const queryClient = useQueryClient();
	const { agents, refetch: refetchAgents } = useAgents();
	const {
		sessions,
		loading: sessionsLoading,
		refetch: refetchSessions,
		create: createSession,
		update: updateSession,
		remove: removeSession,
	} = useSessions(urlAgentId ?? null);

	const { isMobile, setOpen, setOpenMobile } = useSidebar();
	/** The agent an edit / delete from a row's menu applies to. */
	const [targetAgent, setTargetAgent] = useState<AgentView | null>(null);
	const [editOpen, setEditOpen] = useState(false);
	const [renameOpen, setRenameOpen] = useState(false);
	const [renameSession, setRenameSession] = useState<SessionRecord | null>(null);
	const [deleteSessionOpen, setDeleteSessionOpen] = useState(false);
	const [sessionToDelete, setSessionToDelete] = useState<SessionRecord | null>(null);
	const [searchOpen, setSearchOpen] = useState(false);
	const [quickAgentOpen, setQuickAgentOpen] = useState(false);
	const [fullAgentOpen, setFullAgentOpen] = useState(false);
	const [groupOpen, setGroupOpen] = useState(false);
	const [groupToDelete, setGroupToDelete] = useState<GroupChat | null>(null);
	const groupChats = useGroupChats();

	const selectedAgent = agents.find((a) => a.id === urlAgentId) ?? null;
	const currentView = sessions.find((v) => v.session.id === urlSessionId) ?? null;
	// Show a per-origin icon only when sessions actually mix sources —
	// a uniform list needs no disambiguation.
	const showSourceIcons = new Set(sessions.map((v) => v.session.origin.type)).size > 1;

	// "Inner focus" — when the URL carries a third `:memberId` segment
	// the user is drilling into a team member's chat. The sidebar stays
	// anchored on the outer (leader) agent; only the chat viewport
	// follows this inner focus. When `urlMemberId` is undefined or
	// doesn't resolve to a known team member, the inner focus collapses
	// back to the outer (leader) session.
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
	// under *this* agent, falling back to the newest one.
	useEffect(() => {
		if (!urlAgentId || sessions.length === 0) return;
		const matches = urlSessionId && sessions.some((v) => v.session.id === urlSessionId);
		if (matches) return;
		const remembered =
			localStorage.getItem(LAST_AGENT_KEY) === urlAgentId
				? localStorage.getItem(LAST_SESSION_KEY)
				: null;
		const view =
			sessions.find((v) => v.session.id === remembered) ??
			[...sessions].sort((a, b) =>
				newestFirst(a.session.created_at, b.session.created_at),
			)[0];
		navigate(`/chat/${urlAgentId}/${view.session.id}`, { replace: true });
	}, [urlAgentId, urlSessionId, sessions, navigate]);

	/**
	 * Create a new session under the currently selected agent and
	 * pre-fill it with the model + fallback the currently open session
	 * is using (so "new chat" inherits whatever the user just had
	 * configured). Falls back to any other session under this agent
	 * when there is no current one. Navigates to the freshly created
	 * session.
	 */
	const handleCreateSession = async () => {
		if (!urlAgentId) return;
		const seedConfig = currentView?.session.config ?? sessions[0]?.session.config;
		const res = await createSession({
			agent_id: urlAgentId,
			...(seedConfig?.chat_model_config
				? { chat_model_config: seedConfig.chat_model_config }
				: {}),
			...(seedConfig?.fallback_chat_model_config
				? { fallback_chat_model_config: seedConfig.fallback_chat_model_config }
				: {}),
		});
		navigate(`/chat/${urlAgentId}/${res.session_id}`);
	};

	// An agent is a conversation: opening one that has never been talked
	// to starts its first chat right away, instead of showing an empty
	// list to pick from. Once per agent, so a failure does not loop.
	const autoStarted = useRef<Set<string>>(new Set());
	useEffect(() => {
		if (!urlAgentId || !selectedAgent || sessionsLoading || sessions.length > 0)
			return;
		if (autoStarted.current.has(urlAgentId)) return;
		autoStarted.current.add(urlAgentId);
		void handleCreateSession();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [urlAgentId, selectedAgent, sessionsLoading, sessions.length]);

	const handleAgentCreated = async (agentId: string) => {
		await refetchAgents();
		onAgentsChanged();
		navigate(`/chat/${agentId}`);
		setOpenMobile(false);
	};

	const handleDeleteSession = async (sessionId: string) => {
		await removeSession(sessionId);
		removeGroupChat(sessionId);
		// If we just removed the session the URL is pointing at, fall
		// back to the parent /chat/:agentId path; the redirect effect
		// will then pick the next available session.
		if (sessionId === urlSessionId && urlAgentId) {
			navigate(`/chat/${urlAgentId}`, { replace: true });
		}
	};

	const handleRenameConfirm = async (name: string) => {
		if (!renameSession) return;
		await updateSession(renameSession.id, { name });
	};

	// Show group conversations here; agents remain accessible through search.
	const agentById = new Map(agents.map((a) => [a.id, a]));
	const activeGroup = groupChats.find((g) => g.sessionId === urlSessionId) ?? null;
	const visibleGroups = groupChats
		.filter((group) => agentById.has(group.agentId))
		.sort((a, b) => newestFirst(a.createdAt, b.createdAt));
	/** Leader first, then the members; names from the live agent list. */
	const groupMembers = (group: GroupChat) =>
		[group.agentId, ...group.memberIds].map((id) => ({
			id,
			name: agentById.get(id)?.data.name ?? id,
		}));

	const handleGroupCreated = async (agentId: string, sessionId: string) => {
		// Members may have just been made invitable, and the leader's session
		// list has to know the new chat before the URL points at it — the
		// redirect above sends an unknown session back to the last one.
		await Promise.all([
			refetchAgents(),
			queryClient.invalidateQueries({ queryKey: ['sessions'] }),
		]);
		navigate(`/chat/${agentId}/${sessionId}`);
		setOpenMobile(false);
	};
	const sortedSessions = [...sessions].sort((a, b) =>
		newestFirst(a.session.created_at, b.session.created_at),
	);
	const agentName = selectedAgent?.data.name ?? '';

	// ⌘K / Ctrl+K opens the search palette from anywhere on the page.
	useEffect(() => {
		const onKeyDown = (event: KeyboardEvent) => {
			if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
				event.preventDefault();
				setSearchOpen(true);
			}
		};
		window.addEventListener('keydown', onKeyDown);
		return () => window.removeEventListener('keydown', onKeyDown);
	}, []);

	const openAgent = (agentId: string) => {
		if (agentId !== urlAgentId) navigate(`/chat/${agentId}`);
		setOpenMobile(false);
	};

	// The open agent's chats, in a small switcher beside its name in the
	// chat header: pick one, start a new one, rename or delete this one.
	const sessionSwitcher = urlAgentId ? (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<button
					id="tour-create-session"
					type="button"
					className="flex h-8 min-w-0 items-center gap-1 rounded-lg px-2 text-[13px]/[18px] text-[var(--cue-text-tertiary,var(--muted-foreground))] hover:bg-[var(--cue-bg-subtle,var(--accent))] hover:text-foreground aria-expanded:bg-[var(--cue-bg-subtle,var(--accent))]"
				>
					<span className="truncate">
						{sessionTitle(currentView?.session.config.name) || t('chat.newSession')}
					</span>
					<ChevronDown className="size-3.5 shrink-0" />
				</button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" className="max-h-96 w-72 overflow-y-auto">
				<DropdownMenuItem onClick={handleCreateSession}>
					<MessageSquarePlus />
					{t('chat.newSession')}
				</DropdownMenuItem>
				{sortedSessions.length > 0 && (
					<>
						<DropdownMenuSeparator />
						<DropdownMenuLabel className="text-[13px] font-normal text-muted-foreground">
							{t('chat.agents.sessions')}
						</DropdownMenuLabel>
						{sortedSessions.map((view) => {
							const SourceIcon =
								SOURCE_ICON[view.session.origin.type] ?? BotMessageSquare;
							const active = view.session.id === urlSessionId;
							return (
								<DropdownMenuItem
									key={view.session.id}
									onClick={() =>
										navigate(`/chat/${urlAgentId}/${view.session.id}`)
									}
								>
									{showSourceIcons ? (
										<SourceIcon />
									) : (
										<Check className={active ? 'opacity-100' : 'opacity-0'} />
									)}
									<span className="min-w-0 flex-1 truncate">
										{sessionTitle(view.session.config.name) ||
											sessionTime(view.session.created_at)}
									</span>
									<span className="shrink-0 text-xs text-muted-foreground tabular-nums">
										{sessionTime(view.session.created_at)}
									</span>
								</DropdownMenuItem>
							);
						})}
					</>
				)}
				{currentView && (
					<>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							onClick={() => {
								setRenameSession(currentView.session);
								setRenameOpen(true);
							}}
						>
							<Pencil />
							{t('chat.agents.renameSession')}
						</DropdownMenuItem>
						<DropdownMenuItem
							variant="destructive"
							onClick={() => {
								setSessionToDelete(currentView.session);
								setDeleteSessionOpen(true);
							}}
						>
							<Trash2 />
							{t('chat.agents.deleteSession')}
						</DropdownMenuItem>
					</>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	) : null;

	return (
		<div className="flex h-full w-full">
			{/*
			 * Desktop stays `collapsible="none"` so the agent list sits in
			 * normal flow as the chat shell's own navigation. Mobile switches to
			 * `offcanvas`, which makes shadcn's Sidebar render its Sheet overlay
			 * (the drawer we want) — instead of the desktop `fixed left-0`
			 * container.
			 */}
			<Sidebar
				collapsible={isMobile ? 'offcanvas' : 'none'}
				className="cue-column border-r border-sidebar-border"
			>
				{/* 48px header: the mark on the left, new agent + search on the right. */}
				<SidebarHeader className="h-12 shrink-0 flex-row items-center justify-between gap-2 py-0 pr-2 pl-4">
					<Brand />
					<div className="flex items-center gap-1">
						<NewChatMenu
							onCreateAgent={() => setQuickAgentOpen(true)}
							onCreateGroup={() => setGroupOpen(true)}
						/>
						<Button
							variant="ghost"
							size="icon"
							aria-label={t('chat.session.search')}
							title={`${t('chat.session.search')} (⌘K)`}
							onClick={() => setSearchOpen(true)}
						>
							<Search className="size-5" />
						</Button>
					</div>
				</SidebarHeader>
				{/* Group conversations, most recent first. */}
				<SidebarContent className="no-scrollbar gap-0 px-2 pb-2">
					{visibleGroups.map((group) => {
						const active = group.sessionId === urlSessionId;
						const members = groupMembers(group);
						return (
							<ChatRow
								key={`g:${group.sessionId}`}
								avatarId={group.agentId}
								avatar={<GroupAvatar members={members} />}
								title={group.name}
								time={sessionTime(group.createdAt)}
								active={active}
								status={active ? (currentView?.status ?? 'idle') : 'idle'}
								icon={<Users className="size-3.5 shrink-0" />}
								preview={members.map((m) => m.name).join(', ')}
								onSelect={() => {
									navigate(`/chat/${group.agentId}/${group.sessionId}`);
									setOpenMobile(false);
								}}
								actions={
									<Button
										variant="ghost"
										size="icon-sm"
										className="bg-[var(--cue-bg-subtle,var(--accent))] text-muted-foreground"
										aria-label={t('groupChat.delete')}
										title={t('groupChat.delete')}
										onClick={() => setGroupToDelete(group)}
									>
										<Trash2 />
									</Button>
								}
							/>
						);
					})}
					{/* One row per agent: its chat opens where it was left. */}
					<p className="mt-4 mb-1 px-3 text-[13px]/[18px] font-medium text-[var(--cue-text-tertiary,var(--muted-foreground))]">
						{t('chat.agents.label')}
					</p>
					{agents.map((agent) => (
						<ChatRow
							key={`a:${agent.id}`}
							avatarId={agent.id}
							avatarLabel={agent.data.name}
							title={agent.data.name}
							active={!activeGroup && agent.id === urlAgentId}
							status={!activeGroup && agent.id === urlAgentId ? (currentView?.status ?? 'idle') : 'idle'}
							preview={agent.data.invite_config?.invite_description?.trim() ?? ''}
							onSelect={() => {
								navigate(`/chat/${agent.id}`);
								setOpenMobile(false);
							}}
						/>
					))}
				</SidebarContent>
				{/* The way out of the chat shell: Settings, and the account. */}
				<SidebarFooter className="gap-0 border-t border-sidebar-border p-2">
					<AccountMenu showSettings showTour />
				</SidebarFooter>
			</Sidebar>
			<div className="flex flex-1 min-w-0">
				<ChatViewport
					agentId={effectiveAgentId}
					sessionId={effectiveSessionId}
					onSessionsChanged={refetchSessions}
					agentName={
						focusedMember?.agent.data.name ??
						(activeGroup ? activeGroup.name : agentName)
					}
					headerSlot={
						focusedMember ? undefined : activeGroup ? (
							// A group's header names it, then who leads and how many
							// are in it; its one chat needs no switcher.
							<span className="flex min-w-0 items-center gap-1.5 px-2 text-[13px]/[18px] text-[var(--cue-text-tertiary,var(--muted-foreground))]">
								<Users className="size-3.5 shrink-0" />
								<span className="truncate">
									{t('groupChat.headerNote', {
										leader: agentName,
										count: activeGroup.memberIds.length + 1,
									})}
								</span>
							</span>
						) : (
							sessionSwitcher
						)
					}
					onOpenAgentSettings={
						!focusedMember && selectedAgent?.editable
							? () => {
									setTargetAgent(selectedAgent);
									setEditOpen(true);
								}
							: undefined
					}
				/>
			</div>
			{targetAgent && (
				<>
					<EditAgentDialog
						open={editOpen}
						onOpenChange={setEditOpen}
						agent={targetAgent}
						onUpdated={refetchAgents}
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
			<DeleteDialog
				open={!!groupToDelete}
				onOpenChange={(open) => !open && setGroupToDelete(null)}
				title={t('common.deleteTitle', {
					entity: t('groupChat.entity'),
					name: groupToDelete?.name ?? '',
				})}
				description={t('common.deleteDescription')}
				confirmLabel={t('groupChat.delete')}
				onConfirm={async () => {
					if (!groupToDelete) return;
					const { sessionId, agentId } = groupToDelete;
					await sessionApi.delete(sessionId, agentId);
					removeGroupChat(sessionId);
					if (sessionId === urlSessionId) navigate(`/chat/${agentId}`, { replace: true });
					await refetchSessions();
				}}
			/>
			<GroupChatDialog
				open={groupOpen}
				onOpenChange={setGroupOpen}
				agents={agents}
				modelConfig={{
					chat: (currentView ?? sessions[0])?.session.config.chat_model_config,
					fallback: (currentView ?? sessions[0])?.session.config
						.fallback_chat_model_config,
				}}
				onCreateAgent={() => {
					setGroupOpen(false);
					setQuickAgentOpen(true);
				}}
				onCreated={handleGroupCreated}
			/>
			<SearchPalette
				open={searchOpen}
				onOpenChange={setSearchOpen}
				agents={agents}
				sessions={sessions}
				loading={sessionsLoading}
				currentAgent={selectedAgent}
				onSelectAgent={openAgent}
				onSelectSession={(id) => {
					navigate(`/chat/${urlAgentId}/${id}`);
					setOpenMobile(false);
				}}
			/>
			<QuickAgentDialog
				open={quickAgentOpen}
				onOpenChange={setQuickAgentOpen}
				onCreated={handleAgentCreated}
				onAdvanced={() => setFullAgentOpen(true)}
			/>
			<AgentDialog
				open={fullAgentOpen}
				onOpenChange={setFullAgentOpen}
				onCreated={async () => {
					await refetchAgents();
					onAgentsChanged();
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

export const ChatPage = () => {
	const navigate = useNavigate();
	const { t } = useTranslation();
	const { agents, loading, refetch } = useAgents();
	const [quickAgentOpen, setQuickAgentOpen] = useState(false);
	const [groupOpen, setGroupOpen] = useState(false);

	// "No agents" only means something once a fetch has actually come back.
	const settled = useSettled(loading);

	if (!settled) return null;

	// With no agent there is nobody to talk to: say so, and offer the two ways
	// to make one (a quick agent here, or a tested one in the Builder).
	if (agents.length === 0) {
		return (
			<>
				<div className="flex h-full flex-col">
					<header className="flex h-12 shrink-0 items-center justify-between px-4">
						<Brand />
						<NewChatMenu
							onCreateAgent={() => setQuickAgentOpen(true)}
							onCreateGroup={() => setGroupOpen(true)}
						/>
					</header>
					<Empty className="flex-1 border-none">
						<EmptyHeader>
							<EmptyMedia variant="icon">
								<Bot />
							</EmptyMedia>
							<EmptyTitle>Chưa có agent nào</EmptyTitle>
							<EmptyDescription>
								Tạo agent đầu tiên để bắt đầu trò chuyện, hoặc dựng và kiểm thử agent trong Builder.
							</EmptyDescription>
						</EmptyHeader>
						<EmptyContent className="flex-row justify-center gap-2">
							<Button onClick={() => setQuickAgentOpen(true)}>
								<Plus />
								{t('quickAgent.title')}
							</Button>
							<Button variant="outline" onClick={() => navigate('/workforce/builder')}>
								Mở Builder
							</Button>
						</EmptyContent>
					</Empty>
					<div className="border-t p-2">
						<AccountMenu showSettings />
					</div>
				</div>
				<QuickAgentDialog
					open={quickAgentOpen}
					onOpenChange={setQuickAgentOpen}
					onCreated={async (agentId) => {
						navigate(`/chat/${agentId}`);
						await refetch();
					}}
				/>
				<GroupChatDialog
					open={groupOpen}
					onOpenChange={setGroupOpen}
					agents={agents}
					onCreateAgent={() => {
						setGroupOpen(false);
						setQuickAgentOpen(true);
					}}
					onCreated={(agentId, sessionId) => {
						navigate(`/chat/${agentId}/${sessionId}`);
					}}
				/>
			</>
		);
	}

	return (
		<AudioProvider>
			<SidebarProvider defaultOpen className="h-full min-h-0">
				<ChatPageInner onAgentsChanged={() => void refetch()} />
			</SidebarProvider>
		</AudioProvider>
	);
};
