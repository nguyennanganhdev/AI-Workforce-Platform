import type { ComponentProps, ReactNode } from 'react';

import type { SessionStatus } from '@/api';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { cn } from '@/lib/utils';

/**
 * One row of Cue's conversation list, shared by the sidebar (one row per
 * agent) and the search palette (agents and chats): 60px tall, a 36px
 * avatar, the title and time on the first line and a one-line preview under
 * it.
 *
 * Hover is a lighter grey than selection, and selection changes nothing but
 * the fill. `actions` sits over the time at the top right and only shows on
 * hover or keyboard focus, so the time stays readable at rest.
 */
export function ChatRow({
	avatarId,
	avatarLabel,
	avatar,
	title,
	time,
	preview,
	status = 'idle',
	active = false,
	icon,
	actions,
	onSelect,
	className,
	...rest
}: {
	avatarId: string;
	avatarLabel?: string;
	/** Replaces the agent avatar, e.g. a group's stacked one. */
	avatar?: ReactNode;
	title: string;
	time?: string;
	preview: ReactNode;
	/** A dot on the avatar: green while running, blue while waiting on you. */
	status?: SessionStatus;
	active?: boolean;
	/** A small icon before the preview. */
	icon?: ReactNode;
	actions?: ReactNode;
	onSelect: () => void;
	className?: string;
} & Omit<ComponentProps<'button'>, 'onClick' | 'className' | 'title'>) {
	return (
		<div className="group/row relative">
			<button
				type="button"
				onClick={onSelect}
				data-active={active || undefined}
				className={cn(
					'flex h-[60px] w-full items-center gap-3 rounded-xl px-3 text-left outline-none transition-colors',
					'hover:bg-[var(--cue-bg-hover,var(--accent))] focus-visible:bg-[var(--cue-bg-hover,var(--accent))]',
					'data-active:bg-[var(--cue-bg-subtle,var(--accent))] data-active:hover:bg-[var(--cue-bg-subtle,var(--accent))]',
					className,
				)}
				{...rest}
			>
				<span className="relative">
					{avatar ?? <ClayAvatar id={avatarId} label={avatarLabel} size={36} />}
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
				<span className="flex min-w-0 flex-1 flex-col">
					<span className="flex min-w-0 items-baseline gap-2">
						<span className="truncate text-[15px]/[20px] font-medium text-foreground">
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
					<span className="flex min-w-0 items-center gap-1 text-[13px]/[18px] text-[var(--cue-text-secondary,var(--muted-foreground))]">
						{icon}
						<span className="truncate">{preview}</span>
					</span>
				</span>
			</button>
			{actions && (
				<div className="absolute top-2 right-2 opacity-0 group-hover/row:opacity-100 group-has-focus-visible/row:opacity-100 has-data-[state=open]:opacity-100">
					{actions}
				</div>
			)}
		</div>
	);
}
