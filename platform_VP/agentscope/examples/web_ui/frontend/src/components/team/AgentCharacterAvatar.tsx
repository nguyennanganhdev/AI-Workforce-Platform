import { Crown } from 'lucide-react';

import { cn } from '@/lib/utils';

interface AgentCharacterAvatarProps {
	role?: 'leader' | 'member' | 'courier';
	active?: boolean;
	className?: string;
}

/** A lightweight mascot shared by the session list and the office scene. */
export function AgentCharacterAvatar({
	role = 'member',
	active = false,
	className,
}: AgentCharacterAvatarProps) {
	return (
		<span
			className={cn(
				'agent-character-avatar',
				`agent-character-avatar--${role}`,
				active && 'is-active',
				className,
			)}
			aria-hidden="true"
		>
			<span className="agent-character-avatar__shadow" />
			<span className="agent-character-avatar__body">
				<span className="agent-character-avatar__collar" />
			</span>
			<span className="agent-character-avatar__head">
				<span className="agent-character-avatar__hair" />
				<span className="agent-character-avatar__face">
					<span />
					<span />
				</span>
			</span>
			{role === 'leader' ? <Crown className="agent-character-avatar__crown" /> : null}
			{active ? <span className="agent-character-avatar__signal" /> : null}
		</span>
	);
}
