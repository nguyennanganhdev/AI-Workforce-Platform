import { Library, List, Plus, Workflow } from 'lucide-react';
import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';

import { AgentGraph } from './AgentGraph';
import { AgentLibrary } from './AgentLibrary';
import { AgentList } from './AgentList';
import type { AgentView } from '@/api';
import { AgentDialog } from '@/components/dialog/AgentDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { EditAgentDialog } from '@/components/dialog/EditAgentDialog';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useIsMobile } from '@/hooks/use-mobile';
import { useAgents } from '@/hooks/useAgents';
import { useSettled } from '@/hooks/useSettled';
import { useTranslation } from '@/i18n/useI18n';

const VIEWS = [
	{ key: 'graph', icon: Workflow },
	{ key: 'list', icon: List },
	{ key: 'library', icon: Library },
] as const;

type View = (typeof VIEWS)[number]['key'];

/**
 * Agent management: one set of agents, three ways of looking at it.
 *
 * - **Sơ đồ** — the agents as a topology around the Leader.
 * - **Danh sách** — the same agents as a table, with edit and delete.
 * - **Thư viện** — what the agents can be given.
 *
 * The view is in the URL (`/agents/:view?`), so each one can be linked to and
 * the back button moves between them.
 */
export function AgentsPage() {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const isMobile = useIsMobile();
	const { view: urlView } = useParams<{ view?: string }>();
	const view: View = VIEWS.some((v) => v.key === urlView) ? (urlView as View) : 'graph';

	const { agents, loading, error, refetch, remove } = useAgents();
	const settled = useSettled(loading);
	const [editing, setEditing] = useState<AgentView | null>(null);
	const [deleting, setDeleting] = useState<AgentView | null>(null);

	const openChat = (agent: AgentView) => navigate(`/chat/${agent.id}`);
	// A dialog renders outside the fullscreen canvas and would open unseen
	// behind it, so leave fullscreen first.
	const openEdit = (agent: AgentView) => {
		if (document.fullscreenElement) void document.exitFullscreen();
		setEditing(agent);
	};

	const list = (
		<AgentList
			agents={agents}
			loading={!settled}
			error={error}
			onRetry={() => void refetch()}
			onChat={openChat}
			onEdit={openEdit}
			onDelete={setDeleting}
		/>
	);

	if (urlView === 'office') return <Navigate to="/chat" replace />;

	return (
		<div className="flex size-full">
			<main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
				<header className="flex min-h-[52px] shrink-0 flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
					<h1 className="text-[17px]/6 font-semibold">{t('agents.title')}</h1>
					<Tabs value={view} onValueChange={(next) => navigate(`/agents/${next}`)}>
						<TabsList>
							{VIEWS.map(({ key, icon: Icon }) => (
								<TabsTrigger key={key} value={key} className="px-2.5">
									<Icon />
									{t(`agents.view.${key}`)}
								</TabsTrigger>
							))}
						</TabsList>
					</Tabs>
					<div className="ml-auto">
						<AgentDialog onCreated={() => void refetch()}>
							<Button>
								<Plus />
								{t('agents.create')}
							</Button>
						</AgentDialog>
					</div>
				</header>

				<div className="min-h-0 flex-1">
					{view === 'list' && list}
					{view === 'library' && <AgentLibrary />}
					{view === 'graph' &&
						settled &&
						// A node canvas has no usable form on a phone; the list
						// carries the same agents.
						(isMobile ? (
							<div className="flex h-full flex-col">
								<p className="px-6 pt-2 text-sm text-muted-foreground">
									{t('agents.graph.mobile')}
								</p>
								<div className="min-h-0 flex-1">{list}</div>
							</div>
						) : (
							<AgentGraph agents={agents} onChat={openChat} onEdit={openEdit} />
						))}
				</div>
			</main>

			{editing && (
				<EditAgentDialog
					open
					onOpenChange={(open) => !open && setEditing(null)}
					agent={editing}
					onUpdated={() => void refetch()}
				/>
			)}
			<DeleteDialog
				open={!!deleting}
				onOpenChange={(open) => !open && setDeleting(null)}
				title={t('common.deleteTitle', {
					entity: t('dialog-agent-delete.entity'),
					name: deleting?.data.name ?? '',
				})}
				description={t('common.deleteDescription')}
				confirmLabel={t('dialog-agent-delete.confirm')}
				onConfirm={async () => {
					if (deleting) await remove(deleting.id);
				}}
			/>
		</div>
	);
}
