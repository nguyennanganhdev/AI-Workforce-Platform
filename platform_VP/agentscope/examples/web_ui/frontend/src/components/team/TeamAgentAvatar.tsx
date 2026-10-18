import teamAgentMascot from '@/assets/images/team-agent-mascot.png';
import type { TeamRuntimeStatus } from '@/hooks/useTeamActivity';
import { cn } from '@/lib/utils';

import './TeamAgentAvatar.css';

interface TeamAgentAvatarProps {
	status?: TeamRuntimeStatus;
	role?: 'leader' | 'member';
	size?: 'sm' | 'md' | 'lg';
	className?: string;
}

export function TeamAgentAvatar({
	status = 'idle',
	role = 'member',
	size = 'md',
	className,
}: TeamAgentAvatarProps) {
	return (
		<span
			className={cn(
				'team-agent-avatar',
				`team-agent-avatar--${status}`,
				`team-agent-avatar--${size}`,
				role === 'leader' && 'team-agent-avatar--leader',
				className,
			)}
			aria-hidden="true"
		>
			<img
				className="team-agent-avatar__image"
				src={teamAgentMascot}
				alt=""
				draggable={false}
			/>
		</span>
	);
}
