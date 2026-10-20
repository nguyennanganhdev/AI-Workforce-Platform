import type { TeamDetailResponse } from '@/api';
import { ClayAvatar, clayTone } from '@/components/ui/clay-avatar';
import { useTranslation } from '@/i18n/useI18n';

/** A room keeps its coordinator in front, with the other participants behind it. */
export function TeamSessionAvatar({
	team,
	agentId,
	agentName,
	working = false,
}: {
	team: TeamDetailResponse;
	agentId: string;
	agentName?: string;
	working?: boolean;
}) {
	const { t } = useTranslation();
	const leader = team.leader_agent ?? { id: agentId, data: { name: agentName ?? agentId } };
	const agents = [leader, ...team.members.map(({ agent }) => agent)]
		.filter((agent, index, all) => all.findIndex((other) => other.id === agent.id) === index);
	if (agents.length === 1) {
		return <ClayAvatar id={leader.id} label={leader.data.name} size={36} />;
	}
	const label = `${t('common.team')}: ${agents.map((agent) => agent.data.name).join(', ')}`;

	return (
		<span className="relative block h-9 w-11" role="img" aria-label={label} title={label}>
			{agents.slice(0, 3).map((agent, index) => (
				<span
					key={agent.id}
					className={`absolute top-0 rounded-xl border-2 bg-sidebar shadow-sm ${working ? 'motion-safe:animate-[agent-working-breathe_2.4s_ease-in-out_infinite]' : ''}`}
					style={{
						left: index * 7,
						top: index * 3,
						zIndex: 3 - index,
						borderColor: clayTone(agent.id).background,
						animationDelay: `${index * -0.4}s`,
					}}
				>
					<ClayAvatar id={agent.id} label={agent.data.name} size={30 - index * 4} working={working && index === 0} />
				</span>
			))}
			<span aria-hidden="true" className="absolute -right-1 -bottom-1 z-10 rounded-full border-2 border-sidebar bg-foreground px-1 text-[9px]/3 font-semibold text-background">
				+{agents.length - 1}
			</span>
		</span>
	);
}
