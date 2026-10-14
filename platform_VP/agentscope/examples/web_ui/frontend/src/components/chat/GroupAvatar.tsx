import { ClayAvatar } from '@/components/ui/clay-avatar';
import { cn } from '@/lib/utils';

/**
 * A group's mark: its first two members, overlapped on the diagonal, in the
 * space one agent's avatar takes. A third member and up shows as a count
 * badge, so the tile stays the same size however big the group gets.
 */
export function GroupAvatar({
	members,
	size = 36,
	className,
}: {
	members: { id: string; name: string }[];
	size?: number;
	className?: string;
}) {
	// 28px and up draws the stickers rather than initials (see ClayAvatar).
	const tile = Math.round(size * 0.78);
	const [first, second] = members;
	const rest = members.length - 2;
	return (
		<span
			aria-hidden="true"
			className={cn('relative block shrink-0', className)}
			style={{ width: size, height: size }}
		>
			{second && (
				<ClayAvatar
					id={second.id}
					label={second.name}
					size={tile}
					className="absolute right-0 bottom-0"
				/>
			)}
			{first && (
				<ClayAvatar
					id={first.id}
					label={first.name}
					size={tile}
					className="absolute top-0 left-0 ring-2 ring-white"
				/>
			)}
			{rest > 0 && (
				<span className="absolute -right-1 -bottom-1 flex h-4 min-w-4 items-center justify-center rounded-full border-2 border-white bg-[var(--cue-text,#1a1a1a)] px-1 text-[9px] font-semibold text-white">
					+{rest}
				</span>
			)}
		</span>
	);
}
