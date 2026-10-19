import { ClayPortrait, portraitFor } from '@/components/ui/clay-portrait';
import { cn } from '@/lib/utils';

/**
 * The mark an agent carries.
 *
 * One implementation, so the same agent is the same colour on every screen —
 * a mark whose colour is not stable across screens identifies nothing.
 *
 * Three colours rather than a generated gradient: three recurring colours are
 * few enough to become familiar, while a space of thousands is noise that
 * happens to be colourful. The portrait does the identifying; the colour makes a
 * row findable again once you have seen it.
 */

/**
 * The three clay tones. Written out rather than derived, because a clay
 * surface's highlight and shadow are mixed for its own hue.
 */
export const CLAY_TONES = [
	{
		background: '#aec4ff',
		color: '#273f84',
		border: '#dde7ff',
		/** The same hue, pale, for a large surface that has to stay readable under text. */
		wash: '#e7edff',
		shadow: 'inset 3px 3px 4px #e3ecff, inset -3px -3px 5px #748ddd55, 0 3px 0 #dde4f6',
	},
	{
		background: '#9ce3d5',
		color: '#245d58',
		border: '#d5fff4',
		wash: '#e3f5ef',
		shadow: 'inset 3px 3px 5px #e0fff8, inset -3px -3px 5px #51af9f66, 0 3px 0 #d4ece7',
	},
	{
		background: '#ffc0a7',
		color: '#824c3a',
		border: '#ffe2d4',
		wash: '#fff0ea',
		shadow: 'inset 3px 3px 5px #ffe9d9, inset -3px -3px 5px #d9876e55, 0 3px 0 #f0ddd4',
	},
] as const;

export type ClayTone = (typeof CLAY_TONES)[number];

/**
 * Which of the three a given subject gets. A sum of char codes: it only has
 * to be stable across reloads and screens, and spread evenly enough that
 * three adjacent rows are not all blue.
 */
export function clayTone(id: string): ClayTone {
	return CLAY_TONES[clayToneIndex(id)];
}

function clayToneIndex(id: string): number {
	let sum = 0;
	for (let index = 0; index < id.length; index += 1) {
		sum += id.charCodeAt(index);
	}
	return sum % CLAY_TONES.length;
}

/**
 * One agent tile, `size` pixels square, always the agent's portrait: an agent
 * is shown by its character at every size, never by initials.
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
	/** What the portrait's role is read from. Falls back to `id`. */
	label?: string;
	size: number;
	working?: boolean;
}) {
	const name = label ?? id;
	return (
		<span
			aria-hidden="true"
			data-agent={id}
			data-working={working || undefined}
			className={cn(
				'flex shrink-0 items-center justify-center overflow-hidden',
				working && 'agent-avatar-working',
				className,
			)}
			style={{
				width: size,
				height: size,
				background: '#ffffff',
				border: '1px solid var(--cue-border, #e8e8e8)',
				// 12px at the 36px sidebar size, scaling with the tile.
				borderRadius: Math.max(5, Math.round(size / 3)),
			}}
		>
			<ClayPortrait size={size} which={portraitFor(name)} working={working} />
		</span>
	);
}
