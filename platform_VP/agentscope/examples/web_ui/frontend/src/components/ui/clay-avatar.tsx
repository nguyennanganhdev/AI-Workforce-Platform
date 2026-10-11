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
 * happens to be colourful. The initials do the identifying; the colour makes a
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
 * Below this, a sticker is a smudge: the robot and its role badge collapse
 * into a few coloured pixels, while two letters stay legible. 28 is where the
 * badge's icon can still be told apart.
 */
const PORTRAIT_FLOOR = 28;

/**
 * One clay tile, `size` pixels square.
 *
 * The radius tracks the size so a small mark keeps the same SHAPE as a large
 * one. The clay itself is only drawn once there is room for it — three
 * stacked shadows inside an 18px square read as a smudge.
 */
export function ClayAvatar({
	className,
	id,
	label,
	size,
}: {
	className?: string;
	/** Decides the colour, including that of a plain robot when the name names no role. */
	id: string;
	/** What the initials and the role are read from. Falls back to `id`. */
	label?: string;
	size: number;
}) {
	const tone = clayTone(id);
	const name = label ?? id;
	const roomForClay = size >= 22;
	const drawPortrait = size >= PORTRAIT_FLOOR;
	return (
		<span
			aria-hidden="true"
			className={cn(
				'flex shrink-0 items-center justify-center overflow-hidden font-bold',
				className,
			)}
			style={{
				width: size,
				height: size,
				// A sticker brings its own ground.
				background: drawPortrait ? undefined : tone.background,
				color: tone.color,
				border: `1px solid ${tone.border}`,
				borderRadius: Math.max(5, Math.round(size * 0.37)),
				boxShadow: roomForClay ? tone.shadow : undefined,
				// Scaled to the tile, so two letters fit at every size.
				fontSize: Math.max(8, Math.round(size * 0.34)),
				letterSpacing: '0.01em',
			}}
		>
			{drawPortrait ? (
				<ClayPortrait size={size} which={portraitFor(name)} variant={clayToneIndex(id)} />
			) : (
				clayInitials(name)
			)}
		</span>
	);
}
