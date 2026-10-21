import { Check, ChevronDown, Pin } from 'lucide-react';

import type { AgentView } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
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
	onSelectBuilder?: () => void;
	builderSelected?: boolean;
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
export function AgentSelect({
	agents,
	value,
	onChange,
	onSelectBuilder,
	builderSelected = false,
	placeholder,
	className,
	size = 'sm',
	...props
}: Props) {
	const { t } = useTranslation();
	const selected = agents.find((a) => a.id === value) ?? null;
	const selectedLeader = !builderSelected && selected?.data.system_role === 'leader';
	const selectedId = builderSelected ? 'agent-builder' : selected?.id;
	const selectedName = builderSelected
		? t('shell.builder')
		: selectedLeader ? 'Agent group' : selected?.data.name;
	const displayLabel = selectedName ?? placeholder ?? t('chat.agent.selectPlaceholder');

	const leaders = agents.filter((a) => a.data.system_role === 'leader');
	const others = agents.filter((a) => a.data.system_role !== 'leader');
	const hasShared = others.some((a) => !a.editable);
	const yours = others.filter((a) => a.editable);
	const shared = others.filter((a) => !a.editable);

	const renderItem = (agent: AgentView) => {
		const isSelected = !builderSelected && agent.id === value;
		const isLeader = agent.data.system_role === 'leader';
		const name = isLeader ? 'Agent group' : agent.data.name;
		return (
			<DropdownMenuItem
				key={agent.id}
				onSelect={() => onChange?.(agent.id)}
				className={isLeader ? 'bg-amber-50 font-semibold dark:bg-amber-950/30' : undefined}
			>
				<Check
					className={`size-3.5 shrink-0 ${isSelected ? 'opacity-100' : 'opacity-0'}`}
				/>
				<ClayAvatar
					id={agent.id}
					label={name}
					size={24}
					className={isLeader ? 'ring-1 ring-amber-400 dark:ring-amber-600' : undefined}
				/>
				<span className="min-w-0 flex-1 truncate">{name}</span>
				{!agent.editable && (
					<Badge
						variant="secondary"
						className="text-[10px] px-1 py-0"
						title={t('common.readOnlyTooltip')}
					>
						{t('common.readOnly')}
					</Badge>
				)}
				{isLeader && <Pin className="size-3.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />}
			</DropdownMenuItem>
		);
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="outline"
					size={size}
					className={cn(
						'justify-between gap-1 font-normal',
						(selectedLeader || builderSelected) && 'font-semibold',
						className,
					)}
					{...props}
				>
					<span className="flex min-w-0 items-center gap-2">
						{selectedId && (
							<ClayAvatar
								id={selectedId}
								label={selectedName}
								size={size === 'lg' ? 28 : 24}
								className={selectedLeader ? 'ring-1 ring-amber-400 dark:ring-amber-600' : undefined}
							/>
						)}
						<span className="truncate">{displayLabel}</span>
					</span>
					<ChevronDown className="size-3.5 text-muted-foreground" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" className="min-w-56 max-h-72 overflow-y-auto">
				{leaders.map(renderItem)}
				{onSelectBuilder && (
					<DropdownMenuItem
						onSelect={onSelectBuilder}
						className="bg-sky-50 font-semibold dark:bg-sky-950/30"
					>
						<Check
							className={`size-3.5 shrink-0 ${builderSelected ? 'opacity-100' : 'opacity-0'}`}
						/>
						<ClayAvatar id="agent-builder" label={t('shell.builder')} size={24} />
						<span className="min-w-0 flex-1 truncate">{t('shell.builder')}</span>
						<Pin className="size-3.5 text-sky-600 dark:text-sky-400" aria-hidden="true" />
					</DropdownMenuItem>
				)}
				{others.length > 0 && (leaders.length > 0 || onSelectBuilder) && <DropdownMenuSeparator />}
				{agents.length === 0 && !onSelectBuilder ? (
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
					others.map(renderItem)
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
