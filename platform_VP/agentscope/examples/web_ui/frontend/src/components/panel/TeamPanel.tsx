import {
	Activity,
	AlertCircle,
	ArrowRight,
	Bot,
	Check,
	ChevronRight,
	Clock3,
	Crown,
	LoaderCircle,
	MessageSquareMore,
	Radio,
	Trash2,
	UsersRound,
	Wrench,
} from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import type { AgentView, TeamDetailResponse, TeamMemberInfo } from '@/api';
import { sessionApi } from '@/api';
import { AddTeamMemberDialog } from '@/components/dialog/AddTeamMemberDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { PanelEmpty } from '@/components/panel/PanelEmpty';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
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

/** Keep the exchange readable; longer messages expand without leaving the log. */
function ActivityEntry({ item }: { item: TeamActivityItem }) {
	const label = item.state === 'error'
		? 'Thất bại'
		: item.state === 'running' ? 'Đang chạy' : 'Hoàn tất';
	const longDetail = (item.detail?.length ?? 0) > 180 || (item.detail?.split('\n').length ?? 0) > 3;
	return (
		<li className="relative flex gap-2.5 py-3 first:pt-1">
			<span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted">
				{activityIcon(item)}
			</span>
			<div className="min-w-0 flex-1">
				<div className="flex items-start gap-2 text-[11px]">
					<div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-0.5 font-medium">
						<span className="break-words [overflow-wrap:anywhere]">{item.sourceName}</span>
						{item.targetName && <>
							<ArrowRight className="size-3 shrink-0 text-muted-foreground" />
							<span className="break-words [overflow-wrap:anywhere]">{item.targetName}</span>
						</>}
					</div>
					<time dateTime={item.createdAt} className="shrink-0 text-[10px] tabular-nums text-muted-foreground">{formatTime(item.createdAt)}</time>
				</div>
				<p className={cn('mt-1 text-[10px] text-muted-foreground', item.state === 'error' && 'text-destructive')}>
					{item.type === 'communication'
						? item.state === 'error' ? 'Gửi tin thất bại' : ACTIVITY_KIND_LABEL[item.kind ?? ''] ?? 'Gửi tin'
						: <><span className="break-all font-medium">{item.toolName}</span> · {label}</>}
				</p>
				{item.detail && (longDetail ? (
					<Collapsible className="group/message mt-1.5">
						<p className="line-clamp-3 whitespace-pre-wrap break-words text-xs leading-5 group-data-[state=open]/message:hidden [overflow-wrap:anywhere]">{item.detail}</p>
						<CollapsibleContent className="whitespace-pre-wrap break-words text-xs leading-5 [overflow-wrap:anywhere]">{item.detail}</CollapsibleContent>
						<CollapsibleTrigger className="mt-1 rounded text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
							<span className="group-data-[state=open]/message:hidden">Xem thêm</span>
							<span className="hidden group-data-[state=open]/message:inline">Thu gọn</span>
						</CollapsibleTrigger>
					</Collapsible>
				) : <p className="mt-1.5 whitespace-pre-wrap break-words text-xs leading-5 [overflow-wrap:anywhere]">{item.detail}</p>)}
			</div>
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
	const [memberToRemove, setMemberToRemove] = useState<TeamMemberInfo | null>(null);
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

	const communications = activities.filter((item) => item.type === 'communication');
	const tools = activities.filter((item) => item.type === 'tool');
	const runningTools = tools.filter((item) => item.state === 'running').length;
	const failedTools = tools.filter((item) => item.state === 'error').length;

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
		member?: TeamMemberInfo,
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
				{canManage && member && <Button variant="ghost" size="icon-sm"
					className="text-muted-foreground hover:text-destructive"
					aria-label={`Gỡ ${label} khỏi phòng`} title="Gỡ khỏi phòng"
					disabled={runtime.status === 'active' || runtime.status === 'communicating'
						|| runtimeBySession[leaderSessionId]?.status === 'active'}
					onClick={() => setMemberToRemove(member)}><Trash2 className="size-3.5" /></Button>}
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
		);

	const renderMember = (member: TeamMemberInfo) =>
		renderRow(
			member.agent.id,
			<Bot className="size-3.5" />,
			member.agent.data.name,
			member.session_id,
			member.session_id === null,
			() => goToMember(member.agent.id),
			member,
		);

	return (
		<div
			className="flex min-h-0 flex-1 flex-col overflow-y-auto text-sm"
			aria-label="Hoạt động của team"
		>
			{canManage && leaderAgentId && memberToRemove && team.members.some(
				(member) => member.session_id === memberToRemove.session_id && member.agent.id === memberToRemove.agent.id,
			) && <DeleteDialog open onOpenChange={(open) => { if (!open) setMemberToRemove(null); }}
				title={`Gỡ ${memberToRemove.agent.data.name} khỏi phòng?`}
				description="Agent và lịch sử làm việc vẫn được giữ lại. Bạn có thể thêm agent vào phòng lại sau."
				confirmLabel="Gỡ khỏi phòng"
				onConfirm={async () => {
					await sessionApi.removeTeamMember(leaderSessionId, leaderAgentId, memberToRemove.agent.id);
					setMemberToRemove(null);
					await onMembersChanged();
				}} />}
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

			<section className="flex min-h-0 flex-1 flex-col gap-2 px-2 py-3">
				<div className="flex items-center justify-between pb-1">
					<h2 className="text-xs font-semibold">Nhật ký phối hợp</h2>
					<Clock3 className="size-3.5 text-muted-foreground" />
				</div>
				{communications.length > 0 ? (
					<ol className="divide-y divide-border/50">
						{communications.map((item) => <ActivityEntry key={item.id} item={item} />)}
					</ol>
				) : (
					<p className="py-4 text-center text-xs leading-5 text-muted-foreground">
						{tools.length > 0 ? 'Chưa có trao đổi giữa các agent.' : 'Chưa có hoạt động phối hợp.'}
					</p>
				)}
				{tools.length > 0 && (
					<Collapsible key={team.team.id} defaultOpen={false} className="rounded-xl border border-border/60 bg-muted/20">
						<CollapsibleTrigger asChild>
							<button type="button" className="group/tools flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
								<Wrench className="size-3.5 shrink-0" />
								<span className="min-w-0 flex-1">
									<span className="block font-medium">Hoạt động công cụ <span className="ml-1 tabular-nums">({tools.length})</span></span>
									{(runningTools > 0 || failedTools > 0) && (
										<span role="status" className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-[10px]">
											{runningTools > 0 && <span className="inline-flex items-center gap-1"><LoaderCircle className="size-3 motion-safe:animate-spin" />{runningTools} đang chạy</span>}
											{failedTools > 0 && <span className="inline-flex items-center gap-1 text-destructive"><AlertCircle className="size-3" />{failedTools} thất bại</span>}
										</span>
									)}
								</span>
								<ChevronRight className="size-3.5 shrink-0 transition-transform motion-reduce:transition-none group-data-[state=open]/tools:rotate-90" />
							</button>
						</CollapsibleTrigger>
						<CollapsibleContent>
							<ol className="max-h-80 overflow-y-auto overscroll-contain border-t border-border/60 px-3 divide-y divide-border/50">
								{tools.map((item) => <ActivityEntry key={item.id} item={item} />)}
							</ol>
						</CollapsibleContent>
					</Collapsible>
				)}
			</section>
		</div>
	);
}
