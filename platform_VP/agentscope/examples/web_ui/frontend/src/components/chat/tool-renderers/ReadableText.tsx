import { readableFields, withoutInternalIds } from '@/lib/readable';
import { cn } from '@/lib/utils';

/** A JSON object as "label: value" lines; any other text as it is. */
export function ReadableText({
	text,
	className,
	keepIds = false,
}: {
	text: string;
	className?: string;
	/** Show identifiers too (tool approvals must show exactly what is targeted). */
	keepIds?: boolean;
}) {
	const fields = readableFields(text, { keepIds });
	if (!fields) {
		return (
			<div className={cn('whitespace-pre-wrap break-words', className)}>
				{keepIds ? text : withoutInternalIds(text)}
			</div>
		);
	}
	return (
		<dl className={cn('grid gap-1', className)}>
			{fields.map(([label, value]) => (
				<div key={label} className="grid grid-cols-[minmax(80px,auto)_1fr] gap-2">
					<dt className="text-muted-foreground first-letter:uppercase">{label}</dt>
					<dd className="min-w-0 break-words text-foreground">{value}</dd>
				</div>
			))}
		</dl>
	);
}
