import AgentScope from '@/assets/images/agentscope_mono.svg?react';
import { cn } from '@/lib/utils';

/** The product mark and name, as the head of a sidebar. */
export function Brand({ className }: { className?: string }) {
	return (
		<div className={cn('flex items-center gap-2.5', className)}>
			<span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary">
				<AgentScope className="size-5 text-primary-foreground" />
			</span>
			<span className="truncate text-[16px]/[24px] font-semibold">AgentScope</span>
		</div>
	);
}
