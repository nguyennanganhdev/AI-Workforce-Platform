import {
	Activity,
	AlertCircle,
	ArrowRight,
	Bot,
	Check,
	Clock3,
	Crown,
	LoaderCircle,
	MessageSquareMore,
	Radio,
	Settings2,
	UsersRound,
	Wrench,
} from 'lucide-react';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import type { AgentView, TeamDetailResponse, TeamMemberInfo } from '@/api';
import { AddTeamMemberDialog } from '@/components/dialog/AddTeamMemberDialog';
import { PanelEmpty } from '@/components/panel/PanelEmpty';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	useTeamActivity,
	type TeamActivityItem,
	type TeamActivityParticipant,
	type TeamMemberRuntime,
	type TeamRuntimeStatus,
} from '@/hooks/useTeamActivity';
import { useTranslation } from '@/i18n/useI18n';
import { filterTeamThreads, groupTeamThreads, readableToolName, type TeamThread } from '@/lib/teamThreads';
import { cn } from '@/lib/utils';

interface TeamPanelProps {
	team: TeamDetailResponse | null;
	currentSessionId: string | null;
	agentId: string | null;
	canManage: boolean;
	onMembersChanged: () => Promise<void>;
}

const STATUS_STYLE: Record<TeamRuntimeStatus, string> = {
	loading: 'bg-muted-foreground/45',
	idle: 'bg-muted-foreground/45',
	active: 'bg-blue-500',
	communicating: 'bg-cyan-500',
	waiting: 'bg-amber-500',
	completed: 'bg-emerald-500',
	error: 'bg-destructive',
};

/** Vietnamese-only strings for the coordination log (not in the i18n files). */
const THREAD_TEXT = {
	all: 'Tất cả',
	filterLabel: 'Lọc theo agent',
	sendMessage: 'Gửi tin',
	sendFailed: 'Gửi tin thất bại',
	lookupsBy: 'Tra cứu của',
	otherLookups: 'Tra cứu khác',
	toolRunning: 'Đang chạy',
	toolDone: 'Xong',
	toolFailed: 'Lỗi',
	messages: 'tin',
	showMore: 'Bấm để xem đầy đủ',
	showLess: 'Bấm để thu gọn',
	noMatches: 'Không có trao đổi nào liên quan đến agent này.',
	description: 'Mỗi thẻ là một luồng trao đổi giữa các agent, kèm các tra cứu đã chạy. Không hiển thị suy luận riêng tư.',
} as const;

const ACTIVITY_KIND_LABEL: Record<string, string> = {
	assign: 'Giao việc',
	handoff: 'Bàn giao công việc',
	question: 'Hỏi thông tin',
	answer: 'Trả lời',
	result: 'Gửi kết quả',
	progress: 'Cập nhật tiến độ',
	requires_user_input: 'Hỏi khách hàng',
	user_input_proposal: 'Đề xuất câu hỏi',
	conflict: 'Báo xung đột',
	error: 'Báo lỗi',
};

const timeFormatter = new Intl.DateTimeFormat(undefined, {
	hour: '2-digit',
	minute: '2-digit',
	second: '2-digit',
});

const formatTime = (value: string): string => {
	const date = new Date(value);
	return Number.isNaN(date.getTime()) ? '' : timeFormatter.format(date);
};

const statusLabel = (status: TeamRuntimeStatus): string => {
	const labels: Record<TeamRuntimeStatus, string> = {
		loading: 'Đang kết nối',
		idle: 'Chưa hoạt động',
		active: 'Đang xử lý',
		communicating: 'Đang giao tiếp',
		waiting: 'Đang chờ',
		completed: 'Đã xong lượt',
		error: 'Gặp lỗi',
	};
	return labels[status];
};

const activityIcon = (item: TeamActivityItem): ReactNode => {
	if (item.state === 'error') return <AlertCircle className="size-3.5 text-destructive" />;
	if (item.state === 'running') {
		return <LoaderCircle className="size-3.5 text-blue-500 motion-safe:animate-spin" />;
	}
	if (item.type === 'communication') {
		return <MessageSquareMore className="size-3.5 text-cyan-600 dark:text-cyan-400" />;
	}
	return <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />;
};

const messageLabel = (item: TeamActivityItem): string => {
	if (item.state === 'error') return THREAD_TEXT.sendFailed;
	return ACTIVITY_KIND_LABEL[item.kind ?? ''] ?? THREAD_TEXT.sendMessage;
};

const toolStateLabel = (state: TeamActivityItem['state']): string =>
	state === 'running' ? THREAD_TEXT.toolRunning : state === 'error' ? THREAD_TEXT.toolFailed : THREAD_TEXT.toolDone;

/** A name with its agent portrait; pseudo-recipients (customer, whole team) get an icon. */
function Party({ name, agentId }: { name: string; agentId: string | undefined }) {
	return (
		<span className="inline-flex min-w-0 items-center gap-1">
			{agentId ? (
				<ClayAvatar id={agentId} label={name} size={18} />
			) : (
				<span className="flex size-[18px] shrink-0 items-center justify-center rounded-full bg-muted">
					<UsersRound className="size-3 text-muted-foreground" />
				</span>
			)}
			<span className="min-w-0 break-words">{name}</span>
		</span>
	);
}

function ToolRow({ tool, showTime }: { tool: TeamActivityItem; showTime?: boolean }) {
	return (
		<li className="flex items-start gap-1.5 text-[10px] leading-4">
			<span className="mt-0.5 shrink-0">
				{tool.state === 'running' ? (
					<LoaderCircle className="size-3 text-blue-500 motion-safe:animate-spin" />
				) : tool.state === 'error' ? (
					<AlertCircle className="size-3 text-destructive" />
				) : (
					<Wrench className="size-3 text-muted-foreground" />
				)}
			</span>
			<span className="min-w-0 flex-1 break-words">
				<span className="font-medium text-foreground/80">{readableToolName(tool.toolName)}</span>
				{tool.argsSummary ? <span className="text-muted-foreground"> · {tool.argsSummary}</span> : null}
			</span>
			<span className="shrink-0 text-muted-foreground">
				{toolStateLabel(tool.state)}
				{showTime ? ` · ${formatTime(tool.createdAt)}` : null}
			</span>
		</li>
	);
}

interface ThreadCardProps {
	thread: TeamThread;
	avatarId: (name: string | null) => string | undefined;
	expanded: ReadonlySet<string>;
	onToggle: (id: string) => void;
}

/** One conversation: "sender → recipient", then its messages and the lookups made for them. */
function ThreadCard({ thread, avatarId, expanded, onToggle }: ThreadCardProps) {
	return (
		<li className="rounded-xl border px-2.5 py-2">
			<div className="flex items-start gap-2">
				<div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] font-medium">
					<Party name={thread.sourceName} agentId={avatarId(thread.sourceName)} />
					{thread.targetName ? (
						<>
							<ArrowRight className="size-3 shrink-0 text-muted-foreground" />
							<Party name={thread.targetName} agentId={avatarId(thread.targetName)} />
						</>
					) : null}
				</div>
				<span className="inline-flex shrink-0 items-center gap-1 text-[10px] text-muted-foreground">
					{thread.state === 'running' ? (
						<LoaderCircle className="size-3 text-blue-500 motion-safe:animate-spin" />
					) : thread.state === 'error' ? (
						<AlertCircle className="size-3 text-destructive" />
					) : null}
					{thread.messages.length} {THREAD_TEXT.messages} ·{' '}
					<time dateTime={thread.lastAt}>{formatTime(thread.lastAt)}</time>
				</span>
			</div>
			<ol className="ml-2 mt-2 space-y-2.5 border-l pl-2.5">
				{thread.messages.map(({ item, tools }) => {
					const isOpen = expanded.has(item.id);
					return (
						<li key={item.id}>
							<div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] text-muted-foreground">
								<span className="shrink-0">{activityIcon(item)}</span>
								<span
									className={cn(
										'rounded-full bg-muted px-1.5 py-px font-medium text-foreground/80',
										item.state === 'error' && 'text-destructive',
									)}
								>
									{messageLabel(item)}
								</span>
								<span className="min-w-0 break-words">
									{item.sourceName}
									{item.targetName ? ` → ${item.targetName}` : ''}
								</span>
								<time className="ml-auto shrink-0" dateTime={item.createdAt}>
									{formatTime(item.createdAt)}
								</time>
							</div>
							{item.detail ? (
								<button
									type="button"
									aria-expanded={isOpen}
									title={isOpen ? THREAD_TEXT.showLess : THREAD_TEXT.showMore}
									onClick={() => onToggle(item.id)}
									className="mt-1 block w-full rounded-md text-left text-[11px] leading-4 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
								>
									<span className={cn('block break-words', isOpen ? 'whitespace-pre-wrap' : 'line-clamp-3')}>
										{item.detail}
									</span>
								</button>
							) : null}
							{tools.length > 0 ? (
								<div className="mt-1.5 rounded-lg bg-muted/40 px-2 py-1.5">
									<p className="mb-1 break-words text-[10px] text-muted-foreground">
										{THREAD_TEXT.lookupsBy} {item.targetName}
									</p>
									<ul className="space-y-1">
										{tools.map((tool) => (
											<ToolRow key={tool.id} tool={tool} />
										))}
									</ul>
								</div>
							) : null}
						</li>
					);
				})}
			</ol>
		</li>
	);
}

/**
 * Team observability panel. It intentionally exposes only observable
 * runtime events such as status, tools and TeamSay traffic. Private model
 * reasoning is reduced to the neutral state "Đang phân tích yêu cầu".
 */
export function TeamPanel({ team, currentSessionId, agentId, canManage, onMembersChanged }: TeamPanelProps) {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const participants = useMemo<TeamActivityParticipant[]>(() => {
		if (!team) return [];
		const rows: TeamActivityParticipant[] = [];
		if (team.leader_agent) {
			rows.push({
				agentId: team.leader_agent.id,
				sessionId: team.team.session_id,
				name: team.leader_agent.data.name,
				role: 'leader',
			});
		}
		for (const member of team.members) {
			rows.push({
				agentId: member.agent.id,
				sessionId: member.session_id,
				name: member.agent.data.name,
				role: 'member',
			});
		}
		return rows;
	}, [team]);
	const { runtimeBySession, activities } = useTeamActivity(participants);
	const [agentFilter, setAgentFilter] = useState<string | null>(null);
	const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());
	const threadView = useMemo(() => groupTeamThreads(activities), [activities]);
	const filterNames = useMemo(
		() => participants.map((participant) => participant.name).filter((name) => threadView.agents.includes(name)),
		[participants, threadView],
	);
	const activeFilter = agentFilter && filterNames.includes(agentFilter) ? agentFilter : null;
	const visibleThreads = useMemo(() => filterTeamThreads(threadView, activeFilter), [threadView, activeFilter]);
	const avatarIdByName = useMemo(
		() => new Map(participants.map((participant) => [participant.name, participant.agentId])),
		[participants],
	);
	const avatarId = useCallback(
		(name: string | null) => (name ? avatarIdByName.get(name) : undefined),
		[avatarIdByName],
	);
	const toggleExpanded = useCallback((id: string) => {
		setExpanded((current) => {
			const next = new Set(current);
			if (next.has(id)) next.delete(id);
			else next.add(id);
			return next;
		});
	}, []);
	const addMember = canManage && agentId && currentSessionId ? (
		<AddTeamMemberDialog key={currentSessionId} agentId={agentId} sessionId={currentSessionId}
			present={team?.members.map(({ agent }) => agent.id) ?? []}
			disabled={runtimeBySession[currentSessionId]?.status === 'active'}
			onAdded={onMembersChanged} />
	) : null;

	if (!team) {
		return (
			<div className="flex min-h-0 flex-1 flex-col">
				<div className="flex items-center justify-between px-2">
					<span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{t('panel.team.agents')}</span>
					{addMember}
				</div>
				<PanelEmpty
					icon={UsersRound}
					title={t('panel.team.emptyTitle')}
					description={t('panel.team.emptyDescription')}
				/>
			</div>
		);
	}

	const leaderAgentId = team.leader_agent?.id ?? null;
	const leaderSessionId = team.team.session_id;
	const activeCount = participants.filter((participant) => {
		if (!participant.sessionId) return false;
		const status = runtimeBySession[participant.sessionId]?.status;
		return status === 'active' || status === 'communicating';
	}).length;
	const communicatingCount = participants.filter(
		(participant) =>
			participant.sessionId &&
			runtimeBySession[participant.sessionId]?.status === 'communicating',
	).length;
	const hasLiveConnection = participants.some(
		(participant) => participant.sessionId && runtimeBySession[participant.sessionId]?.connected,
	);

	const goToLeader = () => {
		if (!leaderAgentId) return;
		navigate(`/chat/${leaderAgentId}/${leaderSessionId}`);
	};

	const goToMember = (memberAgentId: string) => {
		if (!leaderAgentId) return;
		navigate(`/chat/${leaderAgentId}/${leaderSessionId}/${memberAgentId}`);
	};

	const renderRow = (
		key: string,
		icon: ReactNode,
		label: string,
		sessionId: string | null,
		disabled: boolean,
		onClick: () => void,
		editable: boolean,
	) => {
		const runtime: TeamMemberRuntime = sessionId
			? (runtimeBySession[sessionId] ?? {
					status: 'loading',
					detail: 'Đang kết nối',
					activeTool: null,
					updatedAt: null,
					connected: false,
				})
			: {
					status: 'idle',
					detail: 'Chưa có phiên làm việc',
					activeTool: null,
					updatedAt: null,
					connected: false,
				};
		const isActive = currentSessionId === sessionId;
		return (
			<li key={key} className="flex items-center">
				<Button
					variant="ghost"
					disabled={disabled}
					onClick={onClick}
					className={cn(
						'h-auto min-w-0 flex-1 items-start justify-start gap-2 rounded-xl px-2 py-2 text-left font-normal',
						isActive && 'bg-accent text-accent-foreground',
					)}
				>
					<span className="mt-0.5 shrink-0"><ClayAvatar id={key} label={label} size={32} /></span>
					<span className="min-w-0 flex-1">
						<span className="flex items-center gap-2">
							{icon}<span className="min-w-0 flex-1 truncate text-xs font-medium">{label}</span>
							<span className="inline-flex shrink-0 items-center gap-1 text-[10px] text-muted-foreground">
								<span
									className={cn(
										'size-1.5 rounded-full',
										STATUS_STYLE[runtime.status],
										(runtime.status === 'active' || runtime.status === 'communicating') &&
											'motion-safe:animate-pulse',
									)}
								/>
								{statusLabel(runtime.status)}
							</span>
						</span>
						<span className="mt-0.5 block truncate text-[11px] text-muted-foreground">
							{runtime.detail}
						</span>
					</span>
				</Button>
				{editable && <Button variant="ghost" size="icon-sm" aria-label={`${t('agentManagement.configure')}: ${label}`} onClick={() => navigate(`/workforce/agents/${key}?edit=1`)}><Settings2 className="size-3.5" /></Button>}
			</li>
		);
	};

	const renderLeader = (leader: AgentView) =>
		renderRow(
			leader.id,
			<Crown className="size-3.5 text-amber-600 dark:text-amber-400" />,
			leader.data.name,
			leaderSessionId,
			false,
			goToLeader,
			leader.editable,
		);

	const renderMember = (member: TeamMemberInfo) =>
		renderRow(
			member.agent.id,
			<Bot className="size-3.5" />,
			member.agent.data.name,
			member.session_id,
			member.session_id === null,
			() => goToMember(member.agent.id),
			member.agent.editable,
		);

	return (
		<div
			className="flex min-h-0 flex-1 flex-col overflow-y-auto text-sm"
			aria-label="Hoạt động của team"
		>
			<header className="shrink-0 border-b px-2 pb-3 pt-1">
				<div className="flex items-start justify-between gap-3">
					<div className="min-w-0">
						<p className="truncate text-sm font-semibold">{team.team.data.name}</p>
						{team.team.data.description ? (
							<p className="mt-0.5 line-clamp-2 text-[11px] leading-4 text-muted-foreground">
								{team.team.data.description}
							</p>
						) : null}
					</div>
					<span className="inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[10px] text-muted-foreground">
						<Radio
							className={cn('size-3', hasLiveConnection && 'text-emerald-500')}
						/>
						{hasLiveConnection ? 'Đang theo dõi' : 'Đang kết nối'}
					</span>
				</div>
				<div
					className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground"
					aria-live="polite"
				>
					<span className="inline-flex items-center gap-1.5">
						<Activity className="size-3.5" />
						{activeCount} agent đang chạy
					</span>
					<span className="inline-flex items-center gap-1.5">
						<MessageSquareMore className="size-3.5" />
						{communicatingCount} đang giao tiếp
					</span>
				</div>
			</header>

			<section className="shrink-0 border-b py-3">
				<div className="mb-1 flex items-center justify-between px-2">
					<span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
						Agent trong team
					</span>
					<div className="flex items-center gap-1">
						<span className="text-[10px] text-muted-foreground">{participants.length} agent</span>
						{addMember}
					</div>
				</div>
				{team.team.data.manual_membership && <p className="px-2 pb-2 text-[11px] text-muted-foreground">{t('panel.team.manualMembership')}</p>}
				<ul className="flex flex-col">
					{team.leader_agent && renderLeader(team.leader_agent)}
					{team.members.map(renderMember)}
				</ul>
				{team.members.length === 0 ? (
					<p className="px-2 py-1 text-xs text-muted-foreground">{t('panel.team.noMembers')}</p>
				) : null}
			</section>

			<section className="flex min-h-0 flex-1 flex-col py-3">
				<div className="flex items-center justify-between px-2 pb-2">
					<span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
						Nhật ký phối hợp
					</span>
					<Clock3 className="size-3.5 text-muted-foreground" />
				</div>
				<p className="px-2 pb-2 text-[10px] leading-4 text-muted-foreground">
					{THREAD_TEXT.description}
				</p>
				{filterNames.length > 1 ? (
					<div className="flex flex-wrap gap-1 px-2 pb-2" role="group" aria-label={THREAD_TEXT.filterLabel}>
						{[null, ...filterNames].map((name) => (
							<button
								key={name ?? '__all__'}
								type="button"
								aria-pressed={activeFilter === name}
								onClick={() => setAgentFilter(name)}
								className={cn(
									'rounded-full border px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground',
									activeFilter === name && 'border-transparent bg-accent font-medium text-accent-foreground',
								)}
							>
								{name ?? THREAD_TEXT.all}
							</button>
						))}
					</div>
				) : null}
				{activities.length === 0 ? (
					<div className="mx-2 flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed px-4 py-6 text-center">
						<Radio className="mb-2 size-5 text-muted-foreground" />
						<p className="text-xs font-medium">Chưa có hoạt động</p>
						<p className="mt-1 text-[11px] leading-4 text-muted-foreground">
							Tool và luồng gọi giữa các agent sẽ xuất hiện tại đây.
						</p>
					</div>
				) : visibleThreads.threads.length === 0 && visibleThreads.otherTools.length === 0 ? (
					<p className="px-2 py-2 text-[11px] text-muted-foreground">{THREAD_TEXT.noMatches}</p>
				) : (
					<div className="flex flex-col gap-3 px-2">
						{visibleThreads.threads.length > 0 ? (
							<ol className="flex flex-col gap-2">
								{visibleThreads.threads.map((thread) => (
									<ThreadCard
										key={thread.id}
										thread={thread}
										avatarId={avatarId}
										expanded={expanded}
										onToggle={toggleExpanded}
									/>
								))}
							</ol>
						) : null}
						{visibleThreads.otherTools.length > 0 ? (
							<div>
								<p className="pb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
									{THREAD_TEXT.otherLookups}
								</p>
								<ul className="flex flex-col gap-2">
									{visibleThreads.otherTools.map((group) => (
										<li key={group.agentName} className="rounded-xl border px-2.5 py-2">
											<div className="mb-1.5 text-[11px] font-medium">
												<Party name={group.agentName} agentId={avatarId(group.agentName)} />
											</div>
											<ul className="space-y-1">
												{group.tools.map((tool) => (
													<ToolRow key={tool.id} tool={tool} showTime />
												))}
											</ul>
										</li>
									))}
								</ul>
							</div>
						) : null}
					</div>
				)}
			</section>
		</div>
	);
}
