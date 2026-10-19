import { ClayPortrait, portraitFor } from '@/components/ui/clay-portrait';
import { cn } from '@/lib/utils';

/** Up to two letters, which is what fits in these tiles. */
export function clayInitials(label: string): string {
	const words = label
		.trim()
		.split(/[\s._-]+/)
		.filter(Boolean);
	if (words.length === 0) return '?';
	if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
	return (words[0][0] + words[1][0]).toUpperCase();
}

/**
 * Use initials below 28px, where portrait details are hard to distinguish.
 */
const PORTRAIT_FLOOR = 28;

/**
 * One agent tile, `size` pixels square: the agent's portrait, or its initials
 * on Cue's mascot grey below {@link PORTRAIT_FLOOR}.
 *
 * The radius tracks the size so a small mark keeps the same SHAPE as a large
 * one (36px in the sidebar, 20px in the chat header, 52px on a profile).
 */
export function ClayAvatar({
	className,
	id,
	label,
	size,
	working = false,
}: {
	className?: string;
	/** Identifies the agent; also the fallback label. */
	id: string;
	/** What the initials and the role are read from. Falls back to `id`. */
	label?: string;
	size: number;
	working?: boolean;
}) {
	const name = label ?? id;
	const drawPortrait = size >= PORTRAIT_FLOOR;
	return (
		<span
			aria-hidden="true"
			data-agent={id}
			data-working={working || undefined}
			className={cn(
				'flex shrink-0 items-center justify-center overflow-hidden font-bold',
				working && 'agent-avatar-working',
				className,
			)}
			style={{
				width: size,
				height: size,
				// Cue: a monochrome grey mascot tile; a sticker brings its own ground.
				background: drawPortrait ? '#ffffff' : 'var(--cue-mascot, #8a8a8a)',
				color: '#ffffff',
				border: '1px solid var(--cue-border, #e8e8e8)',
				// 12px at the 36px sidebar size, scaling with the tile.
				borderRadius: Math.max(5, Math.round(size / 3)),
				// Scaled to the tile, so two letters fit at every size.
				fontSize: Math.max(8, Math.round(size * 0.34)),
				letterSpacing: '0.01em',
			}}
		>
			{drawPortrait ? (
				<ClayPortrait size={size} which={portraitFor(name)} working={working} />
			) : (
				clayInitials(name)
			)}
		</span>
	);
}
