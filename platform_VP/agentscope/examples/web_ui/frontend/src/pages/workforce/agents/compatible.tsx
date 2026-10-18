import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import type { AgentView } from '@/api';
import { AgentDialog } from '@/components/dialog/AgentDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { EditAgentDialog } from '@/components/dialog/EditAgentDialog';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { useAgents } from '@/hooks/useAgents';
import { useTranslation } from '@/i18n/useI18n';

/** AgentScope CRUD, without requiring the optional Studio backend. */
export function AgentManagementPage() {
	const { agentId } = useParams();
	const navigate = useNavigate();
	const { t } = useTranslation();
	const { agents, loading, error, refetch, remove } = useAgents();
	const [editing, setEditing] = useState<AgentView | null>(null);
	const [deleting, setDeleting] = useState<AgentView | null>(null);
	const [mutationError, setMutationError] = useState('');
	const visible = agentId ? agents.filter((agent) => agent.id === agentId) : agents;
	return (
		<main className="h-full overflow-auto bg-background p-4 md:p-6">
			<header className="mb-6 flex flex-wrap items-center justify-between gap-3">
				<h1 className="text-xl font-semibold">{t('shell.agentStudio')}</h1>
				<div className="flex flex-wrap gap-2">
					{agentId && (
						<Button variant="outline" asChild>
							<Link to="/workforce/agents">{t('shell.agentStudio')}</Link>
						</Button>
					)}
					<Button variant="outline" asChild>
						<Link to="/workforce/builder">{t('shell.builder')}</Link>
					</Button>
					<AgentDialog onCreated={() => refetch()}>
						<Button>{t('common.create')}</Button>
					</AgentDialog>
				</div>
			</header>
			{loading ? (
				<p role="status">{t('common.loading')}</p>
			) : error ? (
				<div role="alert">
					<p>{error.message}</p>
					<Button onClick={() => void refetch()}>{t('common.retry')}</Button>
				</div>
			) : visible.length === 0 ? (
				<p>{t('agentManagement.empty')}</p>
			) : (
				<div className="grid gap-4 lg:grid-cols-2">
					{visible.map((agent) => (
						<article key={agent.id} className="rounded-xl border p-4">
							<div className="flex items-center gap-3">
								<ClayAvatar id={agent.id} label={agent.data.name} size={40} />
								<Link
									className="font-medium underline-offset-4 hover:underline"
									to={`/workforce/agents/${encodeURIComponent(agent.id)}`}
								>
									{agent.data.name}
								</Link>
							</div>
							<p className="my-3 line-clamp-4 whitespace-pre-wrap text-sm text-muted-foreground">
								{agent.data.system_prompt}
							</p>
							<div className="flex flex-wrap gap-2">
								<Button variant="outline" asChild>
									<Link to={`/chat/${encodeURIComponent(agent.id)}`}>
										{t('shell.backToChat')}
									</Link>
								</Button>
								{agent.editable && (
									<>
										<Button variant="outline" onClick={() => setEditing(agent)}>
											{t('common.edit')}
										</Button>
										<Button
											variant="destructive"
											onClick={() => setDeleting(agent)}
										>
											{t('common.delete')}
										</Button>
									</>
								)}
							</div>
						</article>
					))}
				</div>
			)}
			{mutationError && (
				<p role="alert" className="mt-4 text-destructive">
					{mutationError}
				</p>
			)}
			{editing && (
				<EditAgentDialog
					open
					agent={editing}
					onOpenChange={(open) => !open && setEditing(null)}
					onUpdated={() => void refetch()}
				/>
			)}
			{deleting && (
				<DeleteDialog
					open
					title={t('common.delete')}
					description={deleting.data.name}
					onOpenChange={(open) => !open && setDeleting(null)}
					onConfirm={async () => {
						try {
							await remove(deleting.id);
							setMutationError('');
							if (agentId === deleting.id) navigate('/workforce/agents');
						} catch (error) {
							setMutationError(
								error instanceof Error ? error.message : String(error),
							);
						}
					}}
				/>
			)}
		</main>
	);
}

export const AgentDetailPage = AgentManagementPage;
