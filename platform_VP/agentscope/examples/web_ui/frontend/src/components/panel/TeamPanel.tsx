import {
	AlertCircle,
	ArrowRight,
	Check,
	Crown,
	LoaderCircle,
	MessageSquareMore,
	UsersRound,
	Wrench,
} from 'lucide-react';
import { useMemo, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import type { AgentView, TeamDetailResponse } from '@/api';
import { cleanName } from '@/components/chat/teamDialogText';
import { PanelEmpty } from '@/components/panel/PanelEmpty';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	useTeamActivity,
	type TeamActivityItem,
	type TeamActivityParticipant,
	type TeamMemberRuntime,
	type TeamRuntimeStatus,
} from '@/hooks/useTeamActivity';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

interface TeamPanelProps {
	/**
	 * Resolved team detail (leader + members), or `null` when the open
	 * session is not part of a team.
	 */
	team: TeamDetailResponse | null;
	/**
	 * The session currently shown in the chat area — drives which row is
	 * highlighted as active.
	 */
	currentSessionId: string | null;
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

const STATUS_LABEL: Record<TeamRuntimeStatus, string> = {
	loading: 'Đang kết nối',
	idle: 'Chưa hoạt động',
	active: 'Đang xử lý',
	communicating: 'Đang giao tiếp',
	waiting: 'Đang chờ',
	completed: 'Đã xong lượt',
	error: 'Gặp lỗi',
};

const ACTIVITY_KIND_LABEL: Record<string, string> = {
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

const NO_SESSION: TeamMemberRuntime = {
	status: 'idle',
	detail: 'Chưa có phiên làm việc',
	activeTool: null,
	updatedAt: null,
	connected: false,
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

const activityLabel = (item: TeamActivityItem): string => {
	if (item.state === 'error') {
		return item.type === 'communication' ? 'TeamSay thất bại' : `Tool ${item.toolName} thất bại`;
	}
	return item.type === 'communication'
		? (ACTIVITY_KIND_LABEL[item.kind ?? ''] ?? 'Gửi TeamSay')
		: `Gọi tool ${item.toolName}`;
};

/** One agent of the team: its portrait, its name, and what it is doing now. */
function AgentRow({
	agent,
	label,
	runtime,
	active,
	disabled,
	index,
	trailing,
	onClick,
}: {
	agent: AgentView;
	label: string;
	runtime: TeamMemberRuntime;
	active: boolean;
	disabled: boolean;
	index: number;
	trailing?: ReactNode;
	onClick: () => void;
}) {
	const busy = runtime.status === 'active' || runtime.status === 'communicating';
	return (
		<li
			className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1 motion-safe:fill-mode-both"
			style={{ animationDelay: `${index * 40}ms` }}
		>
			<button
				type="button"
				disabled={disabled}
				onClick={onClick}
				data-active={active || undefined}
				className={cn(
					'flex h-12 w-full items-center gap-2.5 rounded-xl px-2 text-left transition-colors',
					'enabled:hover:bg-[var(--cue-bg-hover,var(--accent))] data-active:bg-[var(--cue-bg-subtle,var(--accent))]',
					'disabled:cursor-default',
				)}
			>
				<span className="relative shrink-0">
					<ClayAvatar id={agent.id} label={agent.data.name} size={32} />
					<span
						className={cn(
							'absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full border-2 border-background',
							STATUS_STYLE[runtime.status],
							busy && 'motion-safe:animate-pulse',
						)}
					/>
				</span>
				<span className="flex min-w-0 flex-1 flex-col">
					<span className="truncate text-sm font-medium text-foreground">{label}</span>
					<span className="truncate text-xs text-muted-foreground" title={runtime.detail}>
						{STATUS_LABEL[runtime.status]} · {runtime.detail}
					</span>
				</span>
				{trailing}
			</button>
		</li>
	);
}

/**
 * Dock panel of a team: the Leader, the agents it invited (each opens its own
 * session), what each is doing now and the TeamSay / tool traffic between
 * them, read from the members' session histories.
 *
 * Renders without its own header or border — the surrounding `Panel`
 * chrome from `PanelDock` provides those.
 */
export function TeamPanel({ team, currentSessionId }: TeamPanelProps) {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const participants = useMemo<TeamActivityParticipant[]>(() => {
		if (!team) return [];
		return [
			...(team.leader_agent
				? [{ agentId: team.leader_agent.id, sessionId: team.team.session_id, name: team.leader_agent.data.name, role: 'leader' as const }]
				: []),
			...team.members.map((member) => ({
				agentId: member.agent.id,
				sessionId: member.session_id,
				name: member.agent.data.name,
				role: 'member' as const,
			})),
		];
	}, [team]);
	const { runtimeBySession, activities } = useTeamActivity(participants);

	if (!team) {
		return (
			<PanelEmpty
				icon={UsersRound}
				title={t('panel.team.emptyTitle')}
				description={t('panel.team.emptyDescription')}
			/>
		);
	}

	const leaderAgentId = team.leader_agent?.id ?? null;
	const leaderSessionId = team.team.session_id;
	const runtimeOf = (sessionId: string | null) =>
		sessionId ? (runtimeBySession[sessionId] ?? { ...NO_SESSION, status: 'loading' as const, detail: 'Đang kết nối' }) : NO_SESSION;

	const goToLeader = () => {
		if (!leaderAgentId) return;
		navigate(`/chat/${leaderAgentId}/${leaderSessionId}`);
	};

	const goToMember = (memberAgentId: string) => {
		if (!leaderAgentId) return;
		navigate(`/chat/${leaderAgentId}/${leaderSessionId}/${memberAgentId}`);
	};

	return (
		<div className="flex min-h-0 flex-1 flex-col gap-y-4 overflow-y-auto text-sm">
			<ul className="flex flex-col gap-0.5 px-1">
				{team.leader_agent && (
					<AgentRow
						agent={team.leader_agent}
						label="Leader"
						runtime={runtimeOf(leaderSessionId)}
						active={currentSessionId === leaderSessionId}
						disabled={false}
						index={0}
						trailing={<Crown className="size-3.5 shrink-0 text-muted-foreground" />}
						onClick={goToLeader}
					/>
				)}
				{team.members.map((member, index) => (
					<AgentRow
						key={member.agent.id}
						agent={member.agent}
						label={cleanName(member.agent.data.name)}
						runtime={runtimeOf(member.session_id)}
						active={member.session_id === currentSessionId}
						disabled={member.session_id === null}
						index={index + 1}
						onClick={() => goToMember(member.agent.id)}
					/>
				))}
			</ul>
			{team.members.length === 0 && (
				<p className="-mt-2 px-3 text-xs text-muted-foreground">{t('panel.team.noMembers')}</p>
			)}

			<section className="flex min-h-0 flex-col px-1">
				<p className="px-2 pb-1 text-xs font-medium text-muted-foreground">Nhật ký phối hợp</p>
				{activities.length === 0 ? (
					<p className="px-2 text-xs text-muted-foreground">
						Tool và TeamSay giữa các agent sẽ xuất hiện tại đây.
					</p>
				) : (
					<ol className="divide-y divide-border/60 px-2">
						{activities.map((item) => (
							<li key={item.id} className="flex items-start gap-2 py-2">
								<span className="mt-0.5 shrink-0">{activityIcon(item)}</span>
								<div className="min-w-0 flex-1">
									<div className="flex items-center gap-1.5 text-xs">
										<span className="truncate font-medium">{cleanName(item.sourceName)}</span>
										{item.targetName ? (
											<>
												<ArrowRight className="size-3 shrink-0 text-muted-foreground" />
												<span className="truncate font-medium">{cleanName(item.targetName)}</span>
											</>
										) : null}
										<time className="ml-auto shrink-0 text-[11px] text-muted-foreground" dateTime={item.createdAt}>
											{formatTime(item.createdAt)}
										</time>
									</div>
									<div className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
										{item.type === 'tool' ? <Wrench className="size-3" /> : null}
										<span>{activityLabel(item)}</span>
									</div>
									{item.detail ? (
										<p className="mt-1 line-clamp-2 text-xs text-muted-foreground" title={item.detail}>
											{item.detail}
										</p>
									) : null}
								</div>
							</li>
						))}
					</ol>
				)}
			</section>
		</div>
	);
}
