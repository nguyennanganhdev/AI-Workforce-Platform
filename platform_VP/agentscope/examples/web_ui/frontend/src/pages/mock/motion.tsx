import { type ReactNode, useLayoutEffect, useRef, useState } from 'react';

import { cn } from '@/lib/utils';

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Fades a transcript entry up into place when it arrives during playback.
 * Decided once, on mount, so a re-render never replays it.
 */
export function Enter({ animate, children }: { animate: boolean; children: ReactNode }) {
	const [on] = useState(animate);
	return <div className={on ? 'cue-enter' : undefined}>{children}</div>;
}

/**
 * An agent tile that, on mount, flies in from wherever that agent last
 * appeared in the transcript — the chip the Leader just added it with, or its
 * own sticker on the step it acted in. Sources mark themselves with
 * `data-fly-from={agent}`; the last one in the document wins, which is the
 * newest.
 *
 * The flight is a fixed-position copy on `<body>`, so a scrolling rail or the
 * header's bounds cannot clip it. The real tile stays hidden until the copy
 * lands, then gives a small bounce.
 */
export function FlyIn({
	agent,
	children,
	className,
}: {
	agent: string;
	children: ReactNode;
	className?: string;
}) {
	const ref = useRef<HTMLSpanElement>(null);

	useLayoutEffect(() => {
		const el = ref.current;
		if (!el || reducedMotion()) return;
		const to = el.getBoundingClientRect();
		const sources = document.querySelectorAll<HTMLElement>(`[data-fly-from="${agent}"]`);
		const source = sources[sources.length - 1];
		if (!to.width || !source) return;
		const from = source.getBoundingClientRect();
		if (!from.width) return;

		const dx = from.left + from.width / 2 - (to.left + to.width / 2);
		const dy = from.top + from.height / 2 - (to.top + to.height / 2);
		const scale = source.offsetWidth / el.offsetWidth || 1;

		const ghost = el.cloneNode(true) as HTMLElement;
		Object.assign(ghost.style, {
			position: 'fixed',
			left: `${to.left}px`,
			top: `${to.top}px`,
			width: `${to.width}px`,
			height: `${to.height}px`,
			margin: '0',
			zIndex: '60',
			pointerEvents: 'none',
		});
		document.body.appendChild(ghost);
		el.style.opacity = '0';

		// An arc rather than a straight line: up and over, slightly larger at
		// the top, so it reads as being lifted out of the transcript.
		const flight = ghost.animate(
			[
				{ transform: `translate(${dx}px, ${dy}px) scale(${scale})`, opacity: 0.6 },
				{
					transform: `translate(${dx * 0.45}px, ${dy * 0.45 - 36}px) scale(1.25)`,
					opacity: 1,
					offset: 0.55,
				},
				{ transform: 'translate(0, 0) scale(1)', opacity: 1 },
			],
			{ duration: 700, delay: 250, easing: 'cubic-bezier(.3,.7,.2,1)', fill: 'both' },
		);
		const land = () => {
			ghost.remove();
			el.style.opacity = '';
			el.animate(
				[{ transform: 'scale(1.18)' }, { transform: 'scale(0.96)' }, { transform: 'none' }],
				{ duration: 320, easing: 'ease-out' },
			);
		};
		flight.onfinish = land;
		return () => {
			flight.onfinish = null;
			flight.cancel();
			ghost.remove();
			el.style.opacity = '';
		};
	}, [agent]);

	return (
		<span ref={ref} className={cn('inline-flex shrink-0', className)}>
			{children}
		</span>
	);
}
