import { Check, ChevronDown } from 'lucide-react';

import type { AgentView } from '@/api';
import { TeamAgentAvatar } from '@/components/team/TeamAgentAvatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useTranslation } from '@/i18n/useI18n.ts';
import { cn } from '@/lib/utils';

interface Props extends Omit<React.ComponentPropsWithoutRef<typeof Button>, 'onChange' | 'value'> {
	agents: AgentView[];
	/** Currently selected agent id, or `null` when none is selected. */
	value?: string | null;
	onChange?: (agentId: string) => void;
	/** Override the trigger label shown when no agent is selected. */
	placeholder?: string;
	className?: string;
}

/**
 * Agent picker used in the chat sidebar. Rendered on top of the
 * shadcn dropdown-menu primitives (same base as `LlmSelect`) so
 * grouping and per-row content (icons, badges) is fully composable.
 *
 * Grouping rule: when every visible agent is editable (i.e. no
 * cross-owner shares in play), the list is rendered flat. As soon
 * as at least one entry is `editable === false`, the list splits
 * into "Yours" and "Shared with you" groups so the read-only
 * origin of the shared entries is unambiguous at a glance.
 */
export function AgentSelect({ agents, value, onChange, placeholder, className, ...props }: Props) {
	const { t } = useTranslation();
	const selected = agents.find((a) => a.id === value) ?? null;
	const displayLabel = selected
		? selected.data.name
		: (placeholder ?? t('chat.agent.selectPlaceholder'));

	const hasShared = agents.some((a) => !a.editable);
	const yours = agents.filter((a) => a.editable);
	const shared = agents.filter((a) => !a.editable);

	const renderItem = (agent: AgentView) => {
		const isSelected = agent.id === value;
		return (
			<DropdownMenuItem
				key={agent.id}
				className="gap-2.5"
				onSelect={() => onChange?.(agent.id)}
			>
				<TeamAgentAvatar name={agent.data.name} size="sm" />
				<span className="min-w-0 flex-1 truncate">{agent.data.name}</span>
				{!agent.editable && (
					<Badge
						variant="secondary"
						className="text-[10px] px-1 py-0"
						title={t('common.readOnlyTooltip')}
					>
						{t('common.readOnly')}
					</Badge>
				)}
				<Check
					className={`size-3.5 shrink-0 ${isSelected ? 'opacity-100' : 'opacity-0'}`}
				/>
			</DropdownMenuItem>
		);
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="outline"
					size="sm"
					className={cn('justify-between gap-1 font-normal', className)}
					{...props}
				>
					{selected ? <TeamAgentAvatar name={selected.data.name} size="sm" /> : null}
					<span className="min-w-0 flex-1 truncate text-left">{displayLabel}</span>
					<ChevronDown className="size-3.5 text-muted-foreground" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" className="min-w-56 max-h-72 overflow-y-auto">
				{agents.length === 0 ? (
					<div className="px-2 py-3 text-center text-sm text-muted-foreground">
						<p className="font-medium">{t('chat.agent.emptyTitle')}</p>
						<p className="text-xs mt-1">{t('chat.agent.emptyDescription')}</p>
					</div>
				) : hasShared ? (
					<>
						{yours.length > 0 && (
							<DropdownMenuGroup>
								<DropdownMenuLabel>{t('chat.agent.groupYours')}</DropdownMenuLabel>
								{yours.map(renderItem)}
							</DropdownMenuGroup>
						)}
						{yours.length > 0 && shared.length > 0 && <DropdownMenuSeparator />}
						{shared.length > 0 && (
							<DropdownMenuGroup>
								<DropdownMenuLabel>{t('chat.agent.groupShared')}</DropdownMenuLabel>
								{shared.map(renderItem)}
							</DropdownMenuGroup>
						)}
					</>
				) : (
					agents.map(renderItem)
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
