import { FileText, Mail, User, Users } from 'lucide-react';

import type { Actor } from './office-sim';
import { ClayAvatar, clayTone } from '@/components/ui/clay-avatar';
import { cn } from '@/lib/utils';

/**
 * The office's people. Each sits in a 3D overlay that is moved to the actor's
 * tile, so a person draws with their feet at the overlay's origin.
 */

const BODY: Record<Exclude<Actor['kind'], 'agent' | 'mail'>, string> = {
	leader: '#24262d',
	user: '#e5484d',
	resident: '#9aa0a6',
};

export function Person({
	actor,
	selected,
	onSelect,
	offLabel,
}: {
	actor: Actor;
	selected: boolean;
	onSelect: () => void;
	offLabel: string;
}) {
	const walking = actor.path.length > 0;

	if (actor.kind === 'mail') {
		return (
			<div
				className="of-mail absolute"
				style={{ left: 0, top: -46 }}
				aria-hidden="true"
			>
				<Mail className="size-4" />
			</div>
		);
	}

	const body = actor.kind === 'agent' ? clayTone(actor.id).background : BODY[actor.kind];
	const clickable = actor.kind === 'agent' || actor.kind === 'leader';
	const Tag = clickable ? 'button' : 'div';

	return (
		<Tag
			type={clickable ? 'button' : undefined}
			onClick={clickable ? onSelect : undefined}
			aria-label={clickable ? actor.name : undefined}
			className={cn(
				'of-person absolute flex flex-col items-center',
				clickable && 'cursor-pointer',
				actor.status === 'off' && 'of-off',
			)}
			style={{ left: 0, top: 0 }}
		>
			<span className="of-shadow" />
			<span className={cn('of-figure flex flex-col items-center', walking && 'of-walking')}>
				<span
					className={cn('of-head', selected && 'of-selected')}
					style={{ transform: `scaleX(${actor.facing})` }}
				>
					{actor.kind === 'agent' || actor.kind === 'leader' ? (
						<ClayAvatar
							id={actor.kind === 'leader' ? 'leader' : actor.id}
							label={actor.name}
							size={40}
							working={actor.status === 'working'}
							className="rounded-full!"
						/>
					) : (
						<span
							className="flex size-10 items-center justify-center rounded-full border-2 border-white text-white"
							style={{ background: BODY[actor.kind] }}
						>
							{actor.kind === 'user' ? (
								<User className="size-5" />
							) : (
								<Users className="size-5" />
							)}
						</span>
					)}
				</span>
				<span className="of-body" style={{ background: body }}>
					{actor.carrying && (
						<span className="of-carry">
							<FileText className="size-3" />
						</span>
					)}
				</span>
			</span>
			{actor.status === 'working' && (
				<span className="of-badge text-[#2f6fe0]">
					<span className="ag-eq">
						<i />
						<i />
						<i />
					</span>
				</span>
			)}
			{actor.status === 'off' && <span className="of-zz">Zz</span>}
			<span
				className={cn('of-name', actor.kind === 'leader' && 'of-name-leader')}
				title={actor.status === 'off' ? offLabel : undefined}
			>
				{actor.name}
			</span>
		</Tag>
	);
}

export function Bubble({ actor }: { actor: Actor }) {
	if (!actor.bubble) return null;
	return (
		<div className="of-bubble" style={{ left: 0, top: -84 }} key={actor.bubble.text}>
			{actor.bubble.text}
		</div>
	);
}
