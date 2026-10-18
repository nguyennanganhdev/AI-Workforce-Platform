import {
	Bot,
	Ellipsis,
	List,
	MessageSquare,
	Pencil,
	Plus,
	Rocket,
	Undo2,
	Workflow,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { workforceApi } from '@/api';
import type { AgentView, WorkforceAgent } from '@/api';
import { EditAgentDialog } from '@/components/dialog/EditAgentDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useIsMobile } from '@/hooks/use-mobile';
import { useAgents } from '@/hooks/useAgents';
import { useSettled } from '@/hooks/useSettled';
import { AgentGraph } from '@/pages/agents/AgentGraph';

const STATUS = {
	draft: { label: 'Bản nháp', variant: 'secondary' },
	published: { label: 'Đang phát hành', variant: 'default' },
	withdrawn: { label: 'Đã ngừng', variant: 'outline' },
} as const;

const MODE = {
	context_only: 'Chỉ ngữ cảnh',
	tool_backed: 'Dùng tool',
} as const;

/** The Leader and its agents as a map; a click on an agent opens its settings. */
function AgentMap({ agents, loading }: { agents: AgentView[]; loading: boolean }) {
	const navigate = useNavigate();
	const isMobile = useIsMobile();
	const settled = useSettled(loading);

	if (!settled) return <Skeleton className="m-4 h-[calc(100%-2rem)]" />;
	// A node canvas has no usable form on a phone; the list carries the same agents.
	if (isMobile) {
		return <p className="p-4 text-sm text-muted-foreground">Sơ đồ cần màn hình rộng. Xem các agent ở tab Danh sách.</p>;
	}
	return (
		<AgentGraph
			agents={agents}
			onChat={(agent: AgentView) => navigate(`/chat/${agent.id}`)}
			onEdit={(agent: AgentView) => navigate(`/workforce/agents/${agent.id}`)}
		/>
	);
}

function AgentTable({
	agents,
	onLifecycle,
}: {
	agents: WorkforceAgent[];
	onLifecycle: (agent: WorkforceAgent, state: 'draft' | 'published') => void;
}) {
	const navigate = useNavigate();
	return (
		<div className="h-full overflow-y-auto px-4 pb-4">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Agent</TableHead>
						<TableHead>Trạng thái</TableHead>
						<TableHead>Chế độ</TableHead>
						<TableHead>Tool</TableHead>
						<TableHead>Knowledge Base</TableHead>
						<TableHead className="w-10">
							<span className="sr-only">Thao tác</span>
						</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{agents.map((agent) => (
						<TableRow
							key={agent.agent_id}
							className="h-14 cursor-pointer"
							onClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}
						>
							<TableCell className="whitespace-normal">
								<div className="flex items-center gap-3">
									<ClayAvatar id={agent.agent_id} label={agent.name} size={36} />
									<div className="min-w-0">
										<p className="truncate text-[14px]/[20px] font-medium">{agent.name}</p>
										<p className="line-clamp-1 max-w-xl text-[12px]/[16px] text-muted-foreground">
											{agent.objective || 'Chưa có mô tả'}
										</p>
									</div>
								</div>
							</TableCell>
							<TableCell>
								<Badge variant={STATUS[agent.lifecycle_state].variant}>{STATUS[agent.lifecycle_state].label}</Badge>
							</TableCell>
							<TableCell>{agent.execution_mode ? MODE[agent.execution_mode] : '-'}</TableCell>
							<TableCell>{agent.tool_count}</TableCell>
							<TableCell>{agent.knowledge_base_count}</TableCell>
							<TableCell onClick={(event) => event.stopPropagation()}>
								<DropdownMenu>
									<DropdownMenuTrigger asChild>
										<Button variant="ghost" size="icon" aria-label={`Thao tác với ${agent.name}`}>
											<Ellipsis />
										</Button>
									</DropdownMenuTrigger>
									<DropdownMenuContent align="end" className="w-auto">
										<DropdownMenuItem onClick={() => navigate(`/chat/${agent.agent_id}`)}>
											<MessageSquare /> Trò chuyện
										</DropdownMenuItem>
										<DropdownMenuItem onClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}>
											<Pencil /> Sửa cấu hình
										</DropdownMenuItem>
										{agent.lifecycle_state === 'published' ? (
											<DropdownMenuItem onClick={() => onLifecycle(agent, 'draft')}>
												<Undo2 /> Đưa về bản nháp
											</DropdownMenuItem>
										) : (
											<DropdownMenuItem onClick={() => onLifecycle(agent, 'published')}>
												<Rocket /> Phát hành
											</DropdownMenuItem>
										)}
									</DropdownMenuContent>
								</DropdownMenu>
							</TableCell>
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
	);
}

const VIEWS = [
	{ key: 'list', label: 'Danh sách', icon: List },
	{ key: 'graph', label: 'Sơ đồ', icon: Workflow },
] as const;

/**
 * Agent management: the Builder's agents as a table or as a map around the
 * Leader. The view is in the URL (`?view=graph`); `/workforce/agents/:agentId`
 * opens that agent's settings over the list.
 */
export function AgentManagementPage() {
	const navigate = useNavigate();
	const { agentId } = useParams<{ agentId?: string }>();
	const [params, setParams] = useSearchParams();
	const view = params.get('view') === 'graph' ? 'graph' : 'list';
	const { agents: records, loading: recordsLoading, refetch: refetchRecords } = useAgents();
	const [agents, setAgents] = useState<WorkforceAgent[] | null>(null);

	const load = useCallback(() => {
		workforceApi
			.listAgents()
			.then(setAgents)
			.catch((error) => {
				toast.error(error instanceof Error ? error.message : String(error));
				setAgents([]);
			});
	}, []);
	useEffect(load, [load]);

	const editing = agentId ? (records.find((record) => record.id === agentId) ?? null) : null;

	const changeLifecycle = async (agent: WorkforceAgent, state: 'draft' | 'published') => {
		try {
			await workforceApi.setLifecycle(agent.agent_id, state);
			load();
			await refetchRecords();
		} catch (error) {
			toast.error(error instanceof Error ? error.message : String(error));
		}
	};

	return (
		<div className="flex size-full">
			<main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
				<div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3 pb-3">
					<div>
						<h1 className="text-[17px]/6 font-semibold">Quản lý agent</h1>
						<p className="mt-0.5 text-[13px]/[18px] text-muted-foreground">
							Agent do Builder tạo: sửa cấu hình, tool và Knowledge Base, phát hành để Leader mời vào team.
						</p>
					</div>
					<div className="flex flex-wrap items-center gap-2">
						<Tabs
							value={view}
							onValueChange={(next) => setParams(next === 'graph' ? { view: 'graph' } : {}, { replace: true })}
						>
							<TabsList>
								{VIEWS.map(({ key, label, icon: Icon }) => (
									<TabsTrigger key={key} value={key} className="px-2.5">
										<Icon /> {label}
									</TabsTrigger>
								))}
							</TabsList>
						</Tabs>
						<Button onClick={() => navigate('/workforce/builder')}>
							<Plus /> Tạo agent
						</Button>
					</div>
				</div>
				<Separator />
				<div className="min-h-0 flex-1">
					{view === 'graph' ? (
						<AgentMap agents={records} loading={recordsLoading} />
					) : agents === null ? (
						<div className="flex flex-col gap-2 p-4" aria-busy="true">
							{[0, 1, 2, 3].map((row) => (
								<Skeleton key={row} className="h-14 w-full" />
							))}
						</div>
					) : agents.length === 0 ? (
						<Empty className="h-full border-none">
							<EmptyHeader>
								<EmptyMedia variant="icon"><Bot /></EmptyMedia>
								<EmptyTitle>Chưa có agent</EmptyTitle>
								<EmptyDescription>Mô tả công việc trong Builder để tạo agent đầu tiên.</EmptyDescription>
							</EmptyHeader>
						</Empty>
					) : (
						<AgentTable agents={agents} onLifecycle={changeLifecycle} />
					)}
				</div>
			</main>
			{editing && (
				<EditAgentDialog
					open
					onOpenChange={(open) => !open && navigate(`/workforce/agents${view === 'graph' ? '?view=graph' : ''}`)}
					agent={editing}
					onUpdated={() => {
						load();
						void refetchRecords();
					}}
				/>
			)}
		</div>
	);
}

/** An agent's page is its settings dialog over the list. */
export const AgentDetailPage = AgentManagementPage;
