import { ClayPortrait, portraitFor } from '@/components/ui/clay-portrait';
import type { TeamRuntimeStatus } from '@/hooks/useTeamActivity';
import { cn } from '@/lib/utils';

import './TeamAgentAvatar.css';

const AVATAR_SIZE = { sm: 24, md: 28, lg: 40 } as const;

interface TeamAgentAvatarProps {
	status?: TeamRuntimeStatus;
	name?: string;
	role?: 'leader' | 'member';
	size?: 'sm' | 'md' | 'lg';
	className?: string;
}

export function TeamAgentAvatar({
	status = 'idle',
	name,
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
			<ClayPortrait
				which={role === 'leader' ? 'leader' : portraitFor(name ?? '')}
				size={AVATAR_SIZE[size]}
				working={status === 'active' || status === 'communicating'}
			/>
		</span>
	);
}
