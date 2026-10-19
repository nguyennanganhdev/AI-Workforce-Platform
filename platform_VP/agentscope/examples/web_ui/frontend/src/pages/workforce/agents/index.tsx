import { ArrowLeft, MessageSquare, Plus, Power, Settings2, Trash2 } from 'lucide-react';
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
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { useAgents } from '@/hooks/useAgents';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';

export function AgentManagementPage() {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const { agentId } = useParams<{ agentId?: string }>();
	const [params, setParams] = useSearchParams();
	const { agents, loading, error, refetch, remove } = useAgents();
	const [search, setSearch] = useState('');
	const [deleting, setDeleting] = useState<AgentView | null>(null);
	const [pending, setPending] = useState<string | null>(null);
	const [mutationError, setMutationError] = useState('');
	const selected = agents.find((agent) => agent.id === agentId);
	const visible = agentId
		? selected
			? [selected]
			: []
		: agents.filter((agent) =>
				`${agent.data.name} ${agent.data.build_description ?? ''}`
					.toLocaleLowerCase()
					.includes(search.toLocaleLowerCase()),
			);

	const changeLifecycle = async (agent: AgentView) => {
		if (!agent.editable || pending) return;
		setPending(agent.id);
		setMutationError('');
		try {
			await workforceApi.setLifecycle(
				agent.id,
				agent.data.lifecycle_state === 'published' ? 'draft' : 'published',
			);
			await refetch();
		} catch (failure) {
			setMutationError(formatApiErrorForAlert(failure));
		} finally {
			setPending(null);
		}
	};

	return (
		<div className="h-full overflow-y-auto bg-background">
			<header className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--cue-divider,var(--border))] px-4 pt-3 pb-3">
				<div className="flex items-start gap-2">
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
					<div>
						<h1 className="text-[17px]/6 font-semibold">
							{selected?.data.name ?? t('agentManagement.title')}
						</h1>
					</div>
				</div>
				<AgentDialog onCreated={refetch}>
					<Button>
						<Plus />
						{t('agentManagement.create')}
					</Button>
				</AgentDialog>
			</header>
			<div className="mx-auto max-w-6xl space-y-4 p-4 md:p-8">
				{!agentId && (
					<Input
						aria-label={t('agentManagement.search')}
						placeholder={t('agentManagement.search')}
						value={search}
						onChange={(event) => setSearch(event.target.value)}
						className="max-w-sm"
					/>
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
					<p className="py-12 text-center text-sm text-muted-foreground">
						{t(agentId ? 'agentManagement.missing' : 'agentManagement.empty')}
					</p>
				) : (
					<div
						className={
							agentId ? 'space-y-4' : 'grid gap-4 md:grid-cols-2 xl:grid-cols-3'
						}
					>
						{visible.map((agent) => (
							<article
								key={agent.id}
								className="rounded-2xl border border-border/70 bg-card p-5"
							>
								<div className="flex items-start gap-3">
									<ClayAvatar id={agent.id} label={agent.data.name} size={44} />
									<div className="min-w-0 flex-1">
										<button
											type="button"
											className="max-w-full truncate text-left text-[15px] font-semibold hover:underline"
											onClick={() =>
												navigate(`/workforce/agents/${agent.id}`)
											}
										>
											{agent.data.name}
										</button>
										<div className="mt-1 flex flex-wrap gap-1">
											<Badge variant="secondary">
												{agent.data.system_role === 'leader'
													? 'Leader'
													: t(
															`agentManagement.${agent.data.lifecycle_state ?? 'draft'}`,
														)}
											</Badge>
											{!agent.editable && (
												<Badge variant="outline">
													{t('agentManagement.readOnly')}
												</Badge>
											)}
										</div>
									</div>
								</div>
								<p className="mt-3 line-clamp-3 text-sm text-muted-foreground">
									{agent.data.build_description ||
										agent.data.invite_config?.invite_description}
								</p>
								{agent.data.execution_mode != null && (
									<p className="mt-2 text-xs text-muted-foreground">
										{agent.data.tool_bindings?.length ?? 0}{' '}
										{t('agentManagement.tools')}
									</p>
								)}
								{agentId && (
									<>
										<p className="mt-4 rounded-xl bg-muted p-3 text-sm text-muted-foreground">
											{t('agentManagement.modelNote')}
										</p>
										{agent.data.system_role === 'leader' ? (
											<p className="mt-4 text-sm text-muted-foreground">
												{t('agentManagement.governedPrompt')}
											</p>
										) : (
											<details className="mt-4 text-sm">
												<summary className="cursor-pointer font-medium">
													{t('agentManagement.prompt')}
												</summary>
												<pre className="mt-2 whitespace-pre-wrap break-words font-sans text-muted-foreground">
													{agent.data.system_prompt}
												</pre>
											</details>
										)}
									</>
								)}
								<div className="mt-5 flex flex-wrap gap-2">
									<Button
										variant="outline"
										size="sm"
										onClick={() => navigate(`/chat/${agent.id}`)}
									>
										<MessageSquare />
										{t('agentManagement.openChat')}
									</Button>
									{agent.editable && (
										<>
											<Button
												variant="outline"
												size="sm"
												onClick={() =>
													navigate(`/workforce/agents/${agent.id}?edit=1`)
												}
											>
												<Settings2 />
												{t('agentManagement.configure')}
											</Button>
											{agent.data.system_role !== 'leader' &&
												agent.data.execution_mode != null && (
													<Button
														variant="ghost"
														size="sm"
														disabled={pending !== null}
														onClick={() => void changeLifecycle(agent)}
													>
														<Power />
														{t(
															agent.data.lifecycle_state ===
																'published'
																? 'agentManagement.withdraw'
																: 'agentManagement.publish',
														)}
													</Button>
												)}
											<Button
												variant="ghost"
												size="icon-sm"
												className="text-destructive"
												aria-label={t('agent-menu.delete')}
												onClick={() => setDeleting(agent)}
											>
												<Trash2 />
											</Button>
										</>
									)}
								</div>
							</article>
						))}
					</div>
				)}
			</div>
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
