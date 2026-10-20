import type { ComponentProps, ReactNode } from 'react';

import type { SessionStatus } from '@/api';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { cn } from '@/lib/utils';

/**
 * One row of Cue's conversation list, shared by the sidebar (one row per
 * agent) and the search palette (agents and chats): a 36px avatar, title and
 * time on one line.
 *
 * Hover is a lighter grey than selection, and selection changes nothing but
 * the fill. `actions` sits over the time at the top right and only shows on
 * hover or keyboard focus, so the time stays readable at rest.
 *
 * `compact` is the short form for long lists (Leader, Agent Builder), with a
 * 28px avatar and tighter padding.
 */
export function ChatRow({
	avatarId,
	avatarLabel,
	avatar,
	title,
	time,
	status = 'idle',
	active = false,
	actions,
	onSelect,
	compact = false,
	className,
	...rest
}: {
	avatarId: string;
	avatarLabel?: string;
	/** Replaces the agent avatar, e.g. a group's stacked one. */
	avatar?: ReactNode;
	title: string;
	time?: string;
	/** A dot on the avatar: green while running, blue while waiting on you. */
	status?: SessionStatus;
	active?: boolean;
	actions?: ReactNode;
	onSelect: () => void;
	compact?: boolean;
	className?: string;
} & Omit<ComponentProps<'button'>, 'onClick' | 'className' | 'title'>) {
	return (
		<div className="group/row relative">
			<button
				type="button"
				onClick={onSelect}
				title={title}
				data-active={active || undefined}
				className={cn(
					'flex w-full items-center rounded-xl text-left outline-none transition-colors',
					compact ? 'h-11 gap-2.5 px-2.5' : 'h-11 gap-3 px-3',
					'hover:bg-[var(--cue-bg-hover,var(--accent))] focus-visible:bg-[var(--cue-bg-hover,var(--accent))]',
					'data-active:bg-[var(--cue-bg-subtle,var(--accent))] data-active:hover:bg-[var(--cue-bg-subtle,var(--accent))]',
					className,
				)}
				{...rest}
			>
				<span className="relative shrink-0">
					{avatar ?? (
						<ClayAvatar id={avatarId} label={avatarLabel} size={compact ? 28 : 36} />
					)}
					{status !== 'idle' && (
						<span
							className={cn(
								'absolute -top-0.5 -right-0.5 size-2.5 rounded-full border-2 border-white',
								status === 'running'
									? 'bg-[var(--cue-success,#34c759)]'
									: 'bg-[var(--cue-blue,#2f80ed)]',
							)}
						/>
					)}
				</span>
				<span className="flex min-w-0 flex-1">
					<span className="flex min-w-0 items-baseline gap-2">
						<span
							className={cn(
								'truncate font-medium text-foreground',
								compact ? 'text-sm/5' : 'text-[15px]/[20px]',
							)}
						>
							{title}
						</span>
						{time && (
							<span
								className={cn(
									'ml-auto shrink-0 text-xs/4 text-[var(--cue-text-secondary,var(--muted-foreground))] tabular-nums',
									actions &&
										'group-hover/row:invisible group-has-focus-visible/row:invisible group-has-data-[state=open]/row:invisible',
								)}
							>
								{time}
							</span>
						)}
					</span>
				</span>
			</button>
			{actions && (
				<div
					className={cn(
						'absolute right-2 opacity-0 group-hover/row:opacity-100 group-has-focus-visible/row:opacity-100 has-data-[state=open]:opacity-100',
						compact ? 'top-1/2 -translate-y-1/2' : 'top-2',
					)}
				>
					{actions}
				</div>
			)}
		</div>
	);
}
