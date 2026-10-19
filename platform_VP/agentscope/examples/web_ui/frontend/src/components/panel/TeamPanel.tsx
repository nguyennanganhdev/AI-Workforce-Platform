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
import { useMemo, type ReactNode } from 'react';
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
					Hiển thị trạng thái, tool và nội dung TeamSay. Không hiển thị suy luận riêng tư.
				</p>
				{activities.length === 0 ? (
					<div className="mx-2 flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed px-4 py-6 text-center">
						<Radio className="mb-2 size-5 text-muted-foreground" />
						<p className="text-xs font-medium">Chưa có hoạt động</p>
						<p className="mt-1 text-[11px] leading-4 text-muted-foreground">
							Tool và luồng gọi giữa các agent sẽ xuất hiện tại đây.
						</p>
					</div>
				) : (
					<ol className="divide-y px-2">
						{activities.map((item) => (
							<li key={item.id} className="py-2.5 first:pt-1">
								<div className="flex items-start gap-2">
									<span className="mt-0.5 shrink-0">{activityIcon(item)}</span>
									<div className="min-w-0 flex-1">
										<div className="flex items-center gap-1.5 text-[11px]">
											<span className="truncate font-medium">{item.sourceName}</span>
											{item.targetName ? (
												<>
													<ArrowRight className="size-3 shrink-0 text-muted-foreground" />
													<span className="truncate font-medium">{item.targetName}</span>
												</>
											) : null}
							<time
								className="ml-auto shrink-0 text-[10px] text-muted-foreground"
								dateTime={item.createdAt}
							>
												{formatTime(item.createdAt)}
											</time>
										</div>
										<div className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground">
											{item.type === 'tool' ? <Wrench className="size-3" /> : null}
											<span>
												{item.state === 'error'
													? item.type === 'communication'
														? 'Gửi tin thất bại'
														: `Tool ${item.toolName} thất bại`
													: item.type === 'communication'
													? ACTIVITY_KIND_LABEL[item.kind ?? ''] ?? 'Gửi tin'
													: `Gọi tool ${item.toolName}`}
											</span>
										</div>
										{item.detail ? (
											<p
												className="mt-1 line-clamp-2 text-[11px] leading-4 text-muted-foreground"
												title={item.detail}
											>
												{item.detail}
											</p>
										) : null}
									</div>
								</div>
							</li>
						))}
					</ol>
				)}
			</section>
		</div>
	);
}
