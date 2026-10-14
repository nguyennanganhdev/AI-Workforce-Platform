import AgentScope from '@/assets/images/agentscope_mono.svg?react';
import { cn } from '@/lib/utils';

/** The product mark and name, as the head of a sidebar. */
export function Brand({ className }: { className?: string }) {
	return (
		<div className={cn('flex min-w-0 items-center gap-2', className)}>
			<span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary">
				<AgentScope className="size-4 text-primary-foreground" />
			</span>
			<span className="truncate text-[15px]/5 font-semibold">AgentScope</span>
		</div>
	);
}
