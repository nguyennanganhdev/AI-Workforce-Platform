import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { Slot } from 'radix-ui';

import { cn } from '@/lib/utils';

function BubbleGroup({ className, ...props }: React.ComponentProps<'div'>) {
	return (
		<div
			data-slot="bubble-group"
			className={cn('flex min-w-0 flex-col gap-2', className)}
			{...props}
		/>
	);
}

const bubbleVariants = cva(
	// `agent` shares `ghost`'s exemption from the 80% cap: a reply has to be able
	// to span the column so a code block or a table inside it is not squeezed.
	'group/bubble relative flex w-fit max-w-[80%] min-w-0 flex-col gap-1 group-data-[align=end]/message:self-end data-[align=end]:self-end data-[variant=ghost]:max-w-full data-[variant=agent]:max-w-full',
	{
		variants: {
			variant: {
				default:
					'*:data-[slot=bubble-content]:bg-primary *:data-[slot=bubble-content]:text-primary-foreground [&>[data-slot=bubble-content]:is(button,a):hover]:bg-primary/80',
				secondary:
					'*:data-[slot=bubble-content]:bg-secondary *:data-[slot=bubble-content]:text-secondary-foreground [&>[data-slot=bubble-content]:is(button,a):hover]:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_5%)]',
				muted: '*:data-[slot=bubble-content]:bg-muted [&>[data-slot=bubble-content]:is(button,a):hover]:bg-[color-mix(in_oklch,var(--muted),var(--foreground)_5%)]',
				tinted: '*:data-[slot=bubble-content]:bg-[oklch(from_var(--primary)_0.93_calc(c*0.4)_h)] *:data-[slot=bubble-content]:text-foreground dark:*:data-[slot=bubble-content]:bg-[oklch(from_var(--primary)_0.3_calc(c*0.4)_h)] [&>[data-slot=bubble-content]:is(button,a):hover]:bg-[oklch(from_var(--primary)_0.88_calc(c*0.5)_h)] dark:[&>[data-slot=bubble-content]:is(button,a):hover]:bg-[oklch(from_var(--primary)_0.35_calc(c*0.5)_h)]',
				outline:
					'*:data-[slot=bubble-content]:border-border *:data-[slot=bubble-content]:bg-background [&>[data-slot=bubble-content]:is(button,a):hover]:bg-muted [&>[data-slot=bubble-content]:is(button,a):hover]:text-foreground dark:[&>[data-slot=bubble-content]:is(button,a):hover]:bg-input/30',
				ghost: 'border-none *:data-[slot=bubble-content]:rounded-none *:data-[slot=bubble-content]:bg-transparent *:data-[slot=bubble-content]:p-0 [&>[data-slot=bubble-content]:is(button,a):hover]:bg-muted [&>[data-slot=bubble-content]:is(button,a):hover]:text-foreground dark:[&>[data-slot=bubble-content]:is(button,a):hover]:bg-muted/50',
				destructive:
					'*:data-[slot=bubble-content]:bg-destructive/10 *:data-[slot=bubble-content]:text-destructive dark:*:data-[slot=bubble-content]:bg-destructive/20 [&>[data-slot=bubble-content]:is(button,a):hover]:bg-destructive/20 dark:[&>[data-slot=bubble-content]:is(button,a):hover]:bg-destructive/30',
				// The two Cue variants (tokens in `styles/cue.css`): flat grey
				// bubbles with a 20px radius, no tail, no shadow, ~15px text.
				// Radius uses `[&>[data-slot=bubble-content]]:` rather than
				// `*:data-[slot=…]:` because `BubbleContent` sets `rounded-xl` on
				// itself, and the attribute selector outranks it outright.
				//
				// What a person said: right-aligned, the same grey as the agent's.
				question:
					'max-w-[min(80%,560px)] [&>[data-slot=bubble-content]]:rounded-[var(--r-bubble,20px)] [&>[data-slot=bubble-content]]:px-4 [&>[data-slot=bubble-content]]:py-2.5 [&>[data-slot=bubble-content]]:text-[15px]/[22px] *:data-[slot=bubble-content]:bg-[var(--cue-bg-bubble,var(--secondary))] *:data-[slot=bubble-content]:text-foreground',
				// What an agent said: left-aligned grey bubble, no avatar beside it.
				agent: '[&>[data-slot=bubble-content]]:max-w-[min(100%,640px)] [&>[data-slot=bubble-content]]:rounded-[var(--r-bubble,20px)] [&>[data-slot=bubble-content]]:px-4 [&>[data-slot=bubble-content]]:py-2.5 [&>[data-slot=bubble-content]]:text-[15px]/[22px] *:data-[slot=bubble-content]:bg-[var(--cue-bg-bubble,var(--secondary))] *:data-[slot=bubble-content]:text-foreground',
			},
		},
		defaultVariants: {
			variant: 'default',
		},
	},
);

function Bubble({
	variant = 'default',
	align = 'start',
	className,
	...props
}: React.ComponentProps<'div'> &
	VariantProps<typeof bubbleVariants> & {
		align?: 'start' | 'end';
	}) {
	return (
		<div
			data-slot="bubble"
			data-variant={variant}
			data-align={align}
			className={cn(bubbleVariants({ variant }), className)}
			{...props}
		/>
	);
}

function BubbleContent({
	asChild = false,
	className,
	...props
}: React.ComponentProps<'div'> & {
	asChild?: boolean;
}) {
	const Comp = asChild ? Slot.Root : 'div';

	return (
		<Comp
			data-slot="bubble-content"
			className={cn(
				'w-fit max-w-full min-w-0 overflow-hidden rounded-xl border border-transparent px-3 py-2 text-sm leading-relaxed wrap-break-word group-data-[align=end]/bubble:self-end [button]:text-left [button,a]:transition-colors [button,a]:outline-none [button,a]:focus-visible:border-ring [button,a]:focus-visible:ring-3 [button,a]:focus-visible:ring-ring/50',
				className,
			)}
			{...props}
		/>
	);
}

const bubbleReactionsVariants = cva(
	'absolute z-10 flex w-fit shrink-0 items-center justify-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-sm ring-3 ring-card has-[button]:p-0',
	{
		variants: {
			side: {
				top: 'top-0 -translate-y-3/4',
				bottom: 'bottom-0 translate-y-3/4',
			},
			align: {
				start: 'left-3',
				end: 'right-3',
			},
		},
		defaultVariants: {
			side: 'bottom',
			align: 'end',
		},
	},
);

function BubbleReactions({
	side = 'bottom',
	align = 'end',
	className,
	...props
}: React.ComponentProps<'div'> & {
	align?: 'start' | 'end';
	side?: 'top' | 'bottom';
}) {
	return (
		<div
			data-slot="bubble-reactions"
			data-align={align}
			data-side={side}
			className={cn(bubbleReactionsVariants({ side, align }), className)}
			{...props}
		/>
	);
}

export { BubbleGroup, Bubble, BubbleContent, BubbleReactions };
