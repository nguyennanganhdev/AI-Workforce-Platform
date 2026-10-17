import { Crown, UsersRound } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import type { AgentView, TeamDetailResponse } from '@/api';
import { cleanName } from '@/components/chat/teamDialogText';
import { PanelEmpty } from '@/components/panel/PanelEmpty';
import { RoomActivity } from '@/components/panel/RoomActivity';
import { ClayAvatar } from '@/components/ui/clay-avatar';
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

/** One agent of the room: its portrait, its name and what it is here for. */
function AgentRow({
	agent,
	role,
	active,
	disabled,
	index,
	onClick,
}: {
	agent: AgentView;
	role: string;
	active: boolean;
	disabled: boolean;
	index: number;
	onClick: () => void;
}) {
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
				<ClayAvatar id={agent.id} label={agent.data.name} size={32} />
				<span className="flex min-w-0 flex-1 flex-col">
					<span className="truncate text-sm font-medium text-foreground">{cleanName(agent.data.name)}</span>
					<span className="truncate text-xs text-muted-foreground">{role}</span>
				</span>
			</button>
		</li>
	);
}

/**
 * Dock panel of a ticket's room: the Leader, the agents it invited (each
 * opens its own session) and what they said to each other.
 *
 * Renders without its own header or border — the surrounding `Panel`
 * chrome from `PanelDock` provides those.
 */
export function TeamPanel({ team, currentSessionId }: TeamPanelProps) {
	const { t } = useTranslation();
	const navigate = useNavigate();

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
					<li className="flex items-center">
						<button
							type="button"
							onClick={goToLeader}
							data-active={currentSessionId === leaderSessionId || undefined}
							className="flex h-12 w-full items-center gap-2.5 rounded-xl px-2 text-left transition-colors hover:bg-[var(--cue-bg-hover,var(--accent))] data-active:bg-[var(--cue-bg-subtle,var(--accent))]"
						>
							<ClayAvatar id={team.leader_agent.id} label="Leader" size={32} />
							<span className="flex min-w-0 flex-1 flex-col">
								<span className="truncate text-sm font-medium">Leader</span>
								<span className="truncate text-xs text-muted-foreground">{t('common.leader')}</span>
							</span>
							<Crown className="size-3.5 shrink-0 text-muted-foreground" />
						</button>
					</li>
				)}
				{team.members.map((member, index) => (
					<AgentRow
						key={member.agent.id}
						agent={member.agent}
						role={member.agent.data.invite_config?.invite_description?.trim() || t('panel.team.member')}
						active={member.session_id === currentSessionId}
						disabled={member.session_id === null}
						index={index}
						onClick={() => goToMember(member.agent.id)}
					/>
				))}
			</ul>
			{team.members.length === 0 && (
				<p className="-mt-2 px-3 text-xs text-muted-foreground">{t('panel.team.noMembers')}</p>
			)}

			<RoomActivity />
		</div>
	);
}
