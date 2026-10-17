import { type KeyboardEvent, useId, useState } from 'react';

import { cn } from '@/lib/utils';

const LETTERS = 'ABCDEFGHIJ';

/**
 * Cue's choice card: a question from the agent with lettered answers, one of
 * which the reader picks before pressing Continue.
 *
 * The whole row is the hit target, not just the radio. A–E pick (while the
 * card has focus), Enter continues. Once `submitted` is set the card goes
 * read-only: choices locked, Continue gone — the answer is expected to appear
 * as the person's own message below it.
 */
export function ChoiceCard({
	question,
	options,
	hint,
	continueLabel = 'Continue',
	submitted,
	disabled = false,
	onSubmit,
	className,
}: {
	question?: string;
	options: string[];
	/** Under the options, e.g. "No desired options? Just type your reply." */
	hint?: string;
	continueLabel?: string;
	/** Index of the answer already sent; locks the card. */
	submitted?: number | null;
	/** Choices stay pickable, but Continue cannot send (e.g. no model yet). */
	disabled?: boolean;
	onSubmit: (index: number) => void;
	className?: string;
}) {
	const [picked, setPicked] = useState<number | null>(null);
	const name = useId();
	const locked = submitted !== undefined && submitted !== null;
	const selected = locked ? submitted : picked;

	const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
		if (locked || event.metaKey || event.ctrlKey || event.altKey) return;
		const index = LETTERS.indexOf(event.key.toUpperCase());
		if (event.key.length === 1 && index >= 0 && index < options.length) {
			event.preventDefault();
			setPicked(index);
		} else if (event.key === 'Enter' && picked !== null && !disabled) {
			event.preventDefault();
			onSubmit(picked);
		}
	};

	return (
		<div
			onKeyDown={handleKeyDown}
			className={cn(
				'w-[384px] max-w-full rounded-[20px] border border-[var(--cue-border,var(--border))] bg-background p-4',
				className,
			)}
		>
			{question && <p className="mb-2 text-[15px]/[22px] text-foreground">{question}</p>}
			<div role="radiogroup" aria-label={question}>
				{options.map((option, index) => {
					const isSelected = selected === index;
					return (
						<label
							key={index}
							className={cn(
								'flex min-h-16 items-center gap-2.5 border-b border-[var(--cue-divider,var(--border))] py-3 last:border-b-0',
								locked ? 'cursor-default' : 'cursor-pointer',
								locked && !isSelected && 'opacity-50',
							)}
						>
							<span className="flex size-5 shrink-0 items-center justify-center rounded bg-[var(--cue-bg-subtle,var(--muted))] text-xs text-[var(--cue-text-tertiary,var(--muted-foreground))]">
								{LETTERS[index]}
							</span>
							<span className="line-clamp-2 min-w-0 flex-1 text-[15px]/5 text-foreground">
								{option}
							</span>
							<input
								type="radio"
								name={name}
								className="peer sr-only"
								checked={isSelected}
								disabled={locked}
								onChange={() => setPicked(index)}
							/>
							<span
								aria-hidden
								className={cn(
									'flex size-4 shrink-0 items-center justify-center rounded-full border peer-focus-visible:ring-2 peer-focus-visible:ring-ring',
									isSelected
										? 'border-foreground bg-foreground'
										: 'border-[var(--cue-radio,#d0d0d0)]',
								)}
							>
								{isSelected && <span className="size-1.5 rounded-full bg-white" />}
							</span>
						</label>
					);
				})}
			</div>
			{!locked && (
				<>
					{hint && (
						<p className="mt-3 text-[13px]/[18px] text-[var(--cue-text-tertiary,var(--muted-foreground))]">
							{hint}
						</p>
					)}
					<button
						type="button"
						disabled={picked === null || disabled}
						onClick={() => picked !== null && onSubmit(picked)}
						className="mt-3 h-8 w-full rounded-full bg-foreground text-sm font-medium text-background transition-colors disabled:bg-[var(--cue-disabled,var(--muted))] disabled:text-[var(--cue-text-tertiary,var(--muted-foreground))]"
					>
						{continueLabel}
					</button>
				</>
			)}
		</div>
	);
}
