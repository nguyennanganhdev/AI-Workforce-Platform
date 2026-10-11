import * as React from 'react';

import { cn } from '@/lib/utils';

function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
	return (
		<textarea
			data-slot="textarea"
			className={cn(
				// Sunken under the clay theme (see `styles/clay.css`): a field is
				// pressed INTO its surface. Each `var()` falls back to the stock look.
				// No resize handle: the field already grows with its content.
				'flex field-sizing-content min-h-16 w-full resize-none rounded-lg border border-[color:var(--sunken,var(--input))] bg-[var(--sunken,transparent)] shadow-[var(--clay-sunken,none)] px-2.5 py-2 text-base transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40',
				className,
			)}
			{...props}
		/>
	);
}

export { Textarea };
