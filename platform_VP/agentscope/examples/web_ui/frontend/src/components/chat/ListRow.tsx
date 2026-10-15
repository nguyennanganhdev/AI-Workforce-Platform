import { Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * A one-line row of a page's list column (Leader sessions, Builder
 * conversations): an optional status dot, the title, and a delete button
 * that shows on hover or focus.
 */
export function ListRow({
	title,
	active,
	dot,
	dotLabel,
	disabled,
	onSelect,
	onDelete,
}: {
	title: string;
	active: boolean;
	/** Background class of the status dot; none when the item is at rest. */
	dot?: string;
	/** What the dot means, for screen readers. */
	dotLabel?: string;
	disabled?: boolean;
	onSelect: () => void;
	onDelete: () => void;
}) {
	return (
		<li className="group/row relative">
			<button
				type="button"
				data-active={active || undefined}
				disabled={disabled}
				onClick={onSelect}
				className={cn(
					'flex h-9 w-full items-center gap-2 rounded-lg pr-9 pl-3 text-left text-[14px]/5 outline-none transition-colors',
					'hover:bg-[var(--cue-bg-hover,var(--accent))] focus-visible:bg-[var(--cue-bg-hover,var(--accent))]',
					'data-active:bg-[var(--cue-bg-subtle,var(--accent))] data-active:font-medium disabled:opacity-60',
				)}
			>
				<span aria-hidden className={cn('size-1.5 shrink-0 rounded-full', dot ?? 'bg-transparent')} />
				<span className="truncate">{title}</span>
				{dot && dotLabel && <span className="sr-only">{dotLabel}</span>}
			</button>
			<Button
				variant="ghost"
				size="icon-sm"
				aria-label={`Xoá ${title}`}
				title="Xoá"
				disabled={disabled}
				className="absolute top-1/2 right-1 -translate-y-1/2 text-muted-foreground opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100 max-md:opacity-100"
				onClick={onDelete}
			>
				<Trash2 />
			</Button>
		</li>
	);
}
