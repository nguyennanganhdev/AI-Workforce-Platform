import { format, isToday } from 'date-fns';
import type { ComponentProps, ReactNode } from 'react';

import type { SessionStatus, SessionView } from '@/api';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

/** Today's timestamps show the time; older ones the day. */
export function sessionTime(at: string): string {
	const date = new Date(at);
	return format(date, isToday(date) ? 'HH:mm' : 'dd/MM');
}

/**
 * A session's title, or `null` while it still carries the timestamp it was
 * created with — the first reply replaces that with a real one, and a date
 * reads worse than no title at all.
 */
export function sessionTitle(name: string | null | undefined): string | null {
	if (!name || /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?/.test(name)) return null;
	return name;
}

/**
 * The second line of a session row: what the session is waiting on when it
 * is waiting on something, otherwise which agent it belongs to.
 */
export function useSessionPreview() {
	const { t } = useTranslation();
	return (view: SessionView, agentName: string) => {
		if (view.status === 'running') return t('chat.session.previewRunning');
		if (view.status === 'awaiting_permission') return t('chat.session.previewAwaiting');
		return (
			sessionTitle(view.session.config.name) ||
			t('chat.session.previewAgent', { name: agentName })
		);
	};
}

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
