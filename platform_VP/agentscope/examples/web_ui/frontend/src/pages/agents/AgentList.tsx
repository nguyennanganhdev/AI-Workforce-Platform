import { Bot, Ellipsis, MessageSquare, Pencil, Trash2, TriangleAlert } from 'lucide-react';

import type { AgentView } from '@/api';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
	Empty,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from '@/components/ui/empty';
import { Skeleton } from '@/components/ui/skeleton';
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from '@/components/ui/table';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

/** A dot and a label, so the tone is never carried by colour alone. */
function Badge({ tone, children }: { tone: 'ok' | 'neutral'; children: string }) {
	return (
		<span
			className={cn(
				'inline-flex h-[22px] items-center gap-1.5 rounded-full px-2.5 text-[12px]/[16px] font-semibold',
				tone === 'ok'
					? 'bg-[var(--mint-soft)] text-[var(--mint-ink)]'
					: 'bg-[var(--sunken)] text-[var(--ink-2)]',
			)}
		>
			<span className="size-1.5 rounded-full bg-current" />
			{children}
		</span>
	);
}

/**
 * Every agent in the library as a table — the same agents the graph draws,
 * and the non-visual equivalent of it.
 */
export function AgentList({
	agents,
	loading,
	error,
	onRetry,
	onChat,
	onEdit,
	onDelete,
}: {
	agents: AgentView[];
	/** No fetch has come back yet. */
	loading: boolean;
	error: Error | null;
	onRetry: () => void;
	onChat: (agent: AgentView) => void;
	onEdit: (agent: AgentView) => void;
	onDelete: (agent: AgentView) => void;
}) {
	const { t } = useTranslation();

	if (loading) {
		return (
			<div className="flex flex-col gap-2 p-6" aria-busy="true">
				{[0, 1, 2, 3].map((row) => (
					<Skeleton key={row} className="h-14 w-full" />
				))}
			</div>
		);
	}

	if (error) {
		return (
			<Empty className="h-full border-none">
				<EmptyHeader>
					<EmptyMedia variant="icon">
						<TriangleAlert />
					</EmptyMedia>
					<EmptyTitle>{t('agents.list.errorTitle')}</EmptyTitle>
					<EmptyDescription>{t('agents.list.errorDescription')}</EmptyDescription>
				</EmptyHeader>
				<Button variant="outline" onClick={onRetry}>
					{t('agents.list.retry')}
				</Button>
			</Empty>
		);
	}

	if (agents.length === 0) {
		return (
			<Empty className="h-full border-none">
				<EmptyHeader>
					<EmptyMedia variant="icon">
						<Bot />
					</EmptyMedia>
					<EmptyTitle>{t('agents.list.emptyTitle')}</EmptyTitle>
					<EmptyDescription>{t('agents.list.emptyDescription')}</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}

	return (
		<div className="h-full overflow-y-auto px-4 pb-4">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>{t('agents.list.name')}</TableHead>
						<TableHead>{t('agents.list.reach')}</TableHead>
						<TableHead>{t('agents.list.access')}</TableHead>
						<TableHead className="w-10">
							<span className="sr-only">{t('agents.list.actions')}</span>
						</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{agents.map((agent) => {
						const description = agent.data.invite_config?.invite_description?.trim();
						return (
							<TableRow key={agent.id} className="h-14">
								<TableCell className="whitespace-normal">
									<div className="flex items-center gap-3">
										<ClayAvatar
											id={agent.id}
											label={agent.data.name}
											size={36}
										/>
										<div className="min-w-0">
											<p className="truncate text-[14px]/[20px] font-medium">
												{agent.data.name}
											</p>
											<p className="line-clamp-1 text-[12px]/[16px] text-muted-foreground">
												{description || t('agents.list.noDescription')}
											</p>
										</div>
									</div>
								</TableCell>
								<TableCell>
									{agent.data.invite_config?.invitable ? (
										<Badge tone="ok">{t('agents.graph.invitable')}</Badge>
									) : (
										<Badge tone="neutral">
											{t('agents.graph.notInvitable')}
										</Badge>
									)}
								</TableCell>
								<TableCell className="text-muted-foreground">
									{agent.editable ? t('agents.list.owner') : t('common.readOnly')}
								</TableCell>
								<TableCell>
									<DropdownMenu>
										<DropdownMenuTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												aria-label={t('agents.list.actionsFor', {
													name: agent.data.name,
												})}
											>
												<Ellipsis />
											</Button>
										</DropdownMenuTrigger>
										<DropdownMenuContent align="end" className="w-auto">
											<DropdownMenuItem onClick={() => onChat(agent)}>
												<MessageSquare />
												{t('agents.list.chat')}
											</DropdownMenuItem>
											{agent.editable && (
												<>
													<DropdownMenuItem onClick={() => onEdit(agent)}>
														<Pencil />
														{t('agents.list.edit')}
													</DropdownMenuItem>
													<DropdownMenuItem
														variant="destructive"
														onClick={() => onDelete(agent)}
													>
														<Trash2 />
														{t('agents.list.delete')}
													</DropdownMenuItem>
												</>
											)}
										</DropdownMenuContent>
									</DropdownMenu>
								</TableCell>
							</TableRow>
						);
					})}
				</TableBody>
			</Table>
		</div>
	);
}
