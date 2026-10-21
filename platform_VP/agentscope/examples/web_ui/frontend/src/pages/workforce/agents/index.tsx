import {
	ArrowLeft,
	BookOpen,
	Crown,
	Ellipsis,
	FlaskConical,
	MessageSquare,
	PencilRuler,
	Power,
	Search,
	Settings2,
	Sparkles,
	Trash2,
	Wrench,
} from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { workforceApi } from '@/api';
import type { AgentView } from '@/api';
import { AgentDialog } from '@/components/dialog/AgentDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { EditAgentDialog } from '@/components/dialog/EditAgentDialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { AgentEvalDialog } from '@/components/workforce/AgentEvalDialog';
import { useAgents } from '@/hooks/useAgents';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';
import { cn } from '@/lib/utils';

type Filter = 'all' | 'published' | 'draft';

const isLeader = (agent: AgentView) => agent.data.system_role === 'leader';
const isPublished = (agent: AgentView) => agent.data.lifecycle_state === 'published';

/** Leader first, then published agents, then drafts; names alphabetically within each. */
function rank(agent: AgentView) {
	return isLeader(agent) ? 0 : isPublished(agent) ? 1 : 2;
}

export function AgentManagementPage() {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const { agentId } = useParams<{ agentId?: string }>();
	const [params, setParams] = useSearchParams();
	const { agents, loading, error, refetch, remove } = useAgents();
	const [search, setSearch] = useState('');
	const [filter, setFilter] = useState<Filter>('all');
	const [manualOpen, setManualOpen] = useState(false);
	const [deleting, setDeleting] = useState<AgentView | null>(null);
	const [testing, setTesting] = useState<AgentView | null>(null);
	const [pending, setPending] = useState<string | null>(null);
	const [mutationError, setMutationError] = useState('');
	const selected = agents.find((agent) => agent.id === agentId);
	const business = agents.filter((agent) => !isLeader(agent));
	const counts = {
		total: agents.length,
		published: business.filter(isPublished).length,
		draft: business.filter((agent) => !isPublished(agent)).length,
	};
	const visible = agentId
		? selected
			? [selected]
			: []
		: agents
				.filter((agent) =>
					filter === 'all'
						? true
						: filter === 'published'
							? !isLeader(agent) && isPublished(agent)
							: !isLeader(agent) && !isPublished(agent),
				)
				.filter((agent) =>
					`${agent.data.name} ${agent.data.build_description ?? ''}`
						.toLocaleLowerCase()
						.includes(search.trim().toLocaleLowerCase()),
				)
				.sort((a, b) => rank(a) - rank(b) || a.data.name.localeCompare(b.data.name));

	const changeLifecycle = async (agent: AgentView) => {
		if (!agent.editable || pending) return;
		setPending(agent.id);
		setMutationError('');
		try {
			await workforceApi.setLifecycle(agent.id, isPublished(agent) ? 'draft' : 'published');
			await refetch();
		} catch (failure) {
			setMutationError(formatApiErrorForAlert(failure));
		} finally {
			setPending(null);
		}
	};

	return (
		<div className="h-full overflow-y-auto bg-background">
			<header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-[var(--cue-divider,var(--border))] bg-background/90 px-4 py-3 backdrop-blur md:px-8">
				<div className="flex min-w-0 items-center gap-2">
					{agentId && (
						<Button
							variant="ghost"
							size="icon-sm"
							aria-label={t('agentManagement.title')}
							onClick={() => navigate('/workforce/agents')}
						>
							<ArrowLeft />
						</Button>
					)}
					<h1 className="truncate text-[17px]/6 font-semibold">
						{selected?.data.name ?? t('agentManagement.title')}
					</h1>
				</div>
			</header>

			<div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
				{!agentId && (
					<section className="relative overflow-hidden rounded-3xl border border-border/70 bg-[linear-gradient(135deg,var(--cue-bg-subtle,var(--muted))_0%,transparent_65%)] p-6 md:p-8">
						<div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
							<div className="max-w-xl">
								<p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
									{t('agentManagement.heroEyebrow')}
								</p>
								<h2 className="mt-2 text-2xl/8 font-bold tracking-tight md:text-[28px]/9">
									{t('agentManagement.heroTitle')}
								</h2>
								<p className="mt-2 text-sm/6 text-muted-foreground">
									{t('agentManagement.heroDescription')}
								</p>
								<div className="mt-5 flex flex-wrap gap-2">
									<Button onClick={() => navigate('/workforce/builder')}>
										<Sparkles />
										{t('agentManagement.createWithBuilder')}
									</Button>
									<Button variant="outline" onClick={() => setManualOpen(true)}>
										<PencilRuler />
										{t('agentManagement.createManual')}
									</Button>
								</div>
							</div>
							<dl className="grid grid-cols-3 gap-3 md:w-80">
								{(
									[
										['statTotal', counts.total],
										['statPublished', counts.published],
										['statDraft', counts.draft],
									] as const
								).map(([key, value]) => (
									<div key={key} className="rounded-2xl border border-border/70 bg-background/80 px-3 py-3">
										<dd className="text-2xl/8 font-bold tabular-nums">{value}</dd>
										<dt className="text-xs text-muted-foreground">{t(`agentManagement.${key}`)}</dt>
									</div>
								))}
							</dl>
						</div>
					</section>
				)}

				{!agentId && (
					<div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
						<div role="tablist" className="inline-flex w-fit rounded-full bg-[var(--cue-bg-subtle,var(--muted))] p-1">
							{(['all', 'published', 'draft'] as const).map((value) => (
								<button
									key={value}
									type="button"
									role="tab"
									aria-selected={filter === value}
									onClick={() => setFilter(value)}
									className={cn(
										'rounded-full px-3.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors',
										filter === value && 'bg-background text-foreground shadow-sm',
									)}
								>
									{t(`agentManagement.filter.${value}`)}
								</button>
							))}
						</div>
						<div className="relative sm:w-72">
							<Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
							<Input
								aria-label={t('agentManagement.search')}
								placeholder={t('agentManagement.search')}
								value={search}
								onChange={(event) => setSearch(event.target.value)}
								className="pl-9"
							/>
						</div>
					</div>
				)}

				{(error || mutationError) && (
					<Alert variant="destructive">
						<AlertDescription>
							{mutationError || formatApiErrorForAlert(error)}
							<Button variant="ghost" size="sm" onClick={refetch}>
								{t('agentManagement.retry')}
							</Button>
						</AlertDescription>
					</Alert>
				)}

				{loading ? (
					<div className="flex justify-center p-12">
						<Spinner />
					</div>
				) : visible.length === 0 ? (
					<div className="rounded-3xl border border-dashed px-6 py-14 text-center">
						<p className="text-sm text-muted-foreground">
							{t(agentId ? 'agentManagement.missing' : 'agentManagement.empty')}
						</p>
						{!agentId && (
							<Button className="mt-4" onClick={() => navigate('/workforce/builder')}>
								<Sparkles />
								{t('agentManagement.createWithBuilder')}
							</Button>
						)}
					</div>
				) : (
					<div className={agentId ? 'max-w-3xl' : 'grid gap-4 md:grid-cols-2 xl:grid-cols-3'}>
						{visible.map((agent) => (
							<article
								key={agent.id}
								className="group flex h-full flex-col rounded-2xl border border-border/70 bg-card p-5 transition-shadow hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.18)]"
							>
								<div className="flex items-start gap-3">
									<ClayAvatar id={agent.id} label={agent.data.name} size={48} />
									<div className="min-w-0 flex-1">
										<button
											type="button"
											className="block max-w-full truncate text-left text-[15px]/6 font-semibold hover:underline"
											onClick={() => navigate(`/workforce/agents/${agent.id}`)}
										>
											{agent.data.name}
										</button>
										<div className="mt-1 flex flex-wrap items-center gap-1.5">
											<StatusBadge agent={agent} />
											{!agent.editable && (
												<Badge variant="outline">{t('agentManagement.readOnly')}</Badge>
											)}
										</div>
									</div>
								</div>

								<p className={cn('mt-3 text-sm/6 text-muted-foreground', !agentId && 'line-clamp-3 min-h-[4.5rem]')}>
									{isLeader(agent)
										? t('agentManagement.leaderDescription')
										: agent.data.build_description ||
											agent.data.invite_config?.invite_description ||
											t('agentManagement.noDescription')}
								</p>

								{!isLeader(agent) && (
									<div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
										<span className="inline-flex items-center gap-1">
											<Wrench className="size-3.5" />
											{agent.data.tool_bindings?.length ?? 0} {t('agentManagement.tools')}
										</span>
										<span className="inline-flex items-center gap-1">
											<BookOpen className="size-3.5" />
											{agent.data.knowledge_base_ids?.length ?? 0} {t('agentManagement.knowledge')}
										</span>
									</div>
								)}

								{agentId && (
									<div className="mt-5 space-y-3">
										<p className="rounded-xl bg-muted p-3 text-sm text-muted-foreground">
											{t('agentManagement.modelNote')}
										</p>
										{isLeader(agent) ? (
											<p className="text-sm text-muted-foreground">
												{t('agentManagement.governedPrompt')}
											</p>
										) : (
											<details className="rounded-xl border border-border/70 p-3 text-sm">
												<summary className="cursor-pointer font-medium">
													{t('agentManagement.prompt')}
												</summary>
												<p className="mt-2 whitespace-pre-wrap break-words text-muted-foreground">
													{agent.data.system_prompt}
												</p>
											</details>
										)}
									</div>
								)}

								<div className="mt-auto flex items-center gap-2 border-t border-border/60 pt-4">
									<Button className="flex-1" size="sm" onClick={() => navigate(`/chat/${agent.id}`)}>
										<MessageSquare />
										{t('agentManagement.openChat')}
									</Button>
									{agent.editable && (
										<Button
											variant="outline"
											size="sm"
											onClick={() => navigate(`/workforce/agents/${agent.id}?edit=1`)}
										>
											<Settings2 />
											{t('agentManagement.configureShort')}
										</Button>
									)}
									{agent.editable && !isLeader(agent) && (
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button variant="ghost" size="icon-sm" aria-label={t('agentManagement.more')}>
													<Ellipsis />
												</Button>
											</DropdownMenuTrigger>
											<DropdownMenuContent align="end">
												<DropdownMenuItem
													disabled={pending !== null}
													onSelect={() => void changeLifecycle(agent)}
												>
													<Power />
													{t(isPublished(agent) ? 'agentManagement.withdraw' : 'agentManagement.publish')}
												</DropdownMenuItem>
												<DropdownMenuItem onSelect={() => setTesting(agent)}>
													<FlaskConical />
													{t('agentEval.menu')}
												</DropdownMenuItem>
												<DropdownMenuSeparator />
												<DropdownMenuItem variant="destructive" onSelect={() => setDeleting(agent)}>
													<Trash2 />
													{t('agent-menu.delete')}
												</DropdownMenuItem>
											</DropdownMenuContent>
										</DropdownMenu>
									)}
								</div>
							</article>
						))}
					</div>
				)}
			</div>

			<AgentDialog open={manualOpen} onOpenChange={setManualOpen} onCreated={refetch} />
			{testing && (
				<AgentEvalDialog
					key={testing.id}
					agentId={testing.id}
					agentName={testing.data.name}
					open
					onOpenChange={(open) => !open && setTesting(null)}
				/>
			)}
			{selected?.editable && (
				<EditAgentDialog
					key={selected.id}
					agent={selected}
					open={params.get('edit') === '1'}
					onOpenChange={(open) => setParams(open ? { edit: '1' } : {})}
					onUpdated={refetch}
				/>
			)}
			<DeleteDialog
				open={deleting !== null}
				onOpenChange={(open) => !open && setDeleting(null)}
				title={t('common.deleteTitle', {
					entity: t('dialog-agent-delete.entity'),
					name: deleting?.data.name ?? '',
				})}
				description={t('common.deleteDescription')}
				confirmLabel={t('dialog-agent-delete.confirm')}
				onConfirm={async () => {
					if (!deleting?.editable) return;
					await remove(deleting.id);
					if (deleting.id === agentId) navigate('/workforce/agents', { replace: true });
				}}
			/>
		</div>
	);
}

function StatusBadge({ agent }: { agent: AgentView }) {
	const { t } = useTranslation();
	if (isLeader(agent)) {
		return (
			<Badge variant="secondary" className="gap-1">
				<Crown className="size-3" />
				Leader
			</Badge>
		);
	}
	const published = isPublished(agent);
	return (
		<Badge variant="secondary" className="gap-1.5">
			<span
				className={cn(
					'size-1.5 rounded-full',
					published ? 'bg-[var(--cue-success,#34c759)]' : 'bg-muted-foreground/50',
				)}
			/>
			{t(`agentManagement.${agent.data.lifecycle_state ?? 'draft'}`)}
		</Badge>
	);
}
