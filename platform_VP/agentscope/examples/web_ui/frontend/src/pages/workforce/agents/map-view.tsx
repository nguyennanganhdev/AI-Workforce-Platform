import { Ellipsis, MessageSquare, Pencil, RotateCcw, Trash2, X } from 'lucide-react';
import { Component, lazy, Suspense, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import { mapAgents, STATUS, usd } from './agent-map-data';
import type { AgentSummary } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useIsMobile } from '@/hooks/use-mobile';
import { useAgentMapData } from '@/hooks/useStudioAgents';
import { cn } from '@/lib/utils';
import type { MapLink } from '@/pages/agents/AgentMap3D';


const AgentMap3D = lazy(() => import('@/pages/agents/AgentMap3D'));

/** A failed sprite-sheet load or a missing WebGL renderer falls back to the list, not the route error page. */
class MapBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
	state = { failed: false };
	static getDerivedStateFromError() {
		return { failed: true };
	}
	componentDidCatch() {
		this.props.onError();
	}
	render() {
		return this.state.failed ? null : this.props.children;
	}
}

export function AgentRowActions({ agent, onRemove }: { agent: AgentSummary; onRemove: (agent: AgentSummary) => void }) {
	const navigate = useNavigate();
	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" size="icon-sm" aria-label={`Thao tác với ${agent.name}`} onClick={(event) => event.stopPropagation()}>
					<Ellipsis />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end" className="w-auto" onClick={(event) => event.stopPropagation()}>
				<DropdownMenuItem onClick={() => navigate(`/chat/${agent.agent_id}`)}>
					<MessageSquare /> Trò chuyện
				</DropdownMenuItem>
				<DropdownMenuItem onClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}>
					<Pencil /> Sửa và kiểm thử
				</DropdownMenuItem>
				<DropdownMenuItem variant="destructive" onClick={() => onRemove(agent)}>
					<Trash2 /> Gỡ agent
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

/**
 * The map view: the agents as a list on the left and in 3D on the right,
 * both from the same cache. Selecting in one selects in the other; removing
 * an agent removes its node.
 */
export function AgentMapView({ agents, onRemove }: { agents: AgentSummary[]; onRemove: (agent: AgentSummary) => void }) {
	const navigate = useNavigate();
	const isMobile = useIsMobile();
	const { activity, links, cost } = useAgentMapData();
	const [selected, setSelected] = useState<string | null>(null);
	const [reset, setReset] = useState(0);
	const [unavailable, setUnavailable] = useState(false);
	const nodes = useMemo(() => mapAgents(agents, activity, cost), [agents, activity, cost]);
	const byId = new Map(nodes.map((node) => [node.id, node]));
	const mapLinks: MapLink[] = useMemo(
		() => links.map((link) => ({ source: link.source, target: link.target, kind: link.kind, tickets: link.tickets, lastAt: link.last_at })),
		[links],
	);
	const chosen = selected ? byId.get(selected) : undefined;
	const partners = selected ? mapLinks.filter((link) => link.source === selected || link.target === selected) : [];

	return (
		<div className="flex size-full min-h-0">
			<aside className="flex w-72 shrink-0 flex-col border-r border-border/70 max-md:w-full">
				<p className="px-4 pt-3 pb-2 text-xs text-muted-foreground">{agents.length} agent · chọn để xem trên sơ đồ, nhấp đúp để mở</p>
				<ul className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-3">
					{agents.map((agent) => {
						const node = byId.get(agent.agent_id);
						return (
							<li key={agent.agent_id}>
								<div
									role="button"
									tabIndex={0}
									aria-pressed={selected === agent.agent_id}
									onClick={() => setSelected(agent.agent_id === selected ? null : agent.agent_id)}
									onDoubleClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}
									onKeyDown={(event) => {
										if (event.key === 'Enter') setSelected(agent.agent_id);
									}}
									className={cn(
										'group flex items-center gap-2.5 rounded-xl px-2 py-2 transition-colors hover:bg-muted',
										selected === agent.agent_id && 'bg-amber-50 ring-1 ring-amber-300 dark:bg-amber-950/30',
									)}
								>
									<ClayAvatar
										id={agent.agent_id}
										label={agent.name}
										size={34}
										className={cn(agent.lifecycle_state !== 'published' && 'opacity-60 grayscale')}
									/>
									<div className="min-w-0 flex-1">
										<p className="truncate text-[13px]/[18px] font-medium">{agent.name}</p>
										<p className="truncate text-[11px] text-muted-foreground tabular-nums">
											{STATUS[agent.lifecycle_state].label} · {node?.tickets ?? 0} phiếu · {usd(node?.costUsd)}
										</p>
									</div>
									{node?.live && <span className="size-2 shrink-0 rounded-full bg-emerald-500" title="Đang xử lý" />}
									<AgentRowActions agent={agent} onRemove={onRemove} />
								</div>
							</li>
						);
					})}
				</ul>
			</aside>
			{!isMobile && (
				<div className="relative min-w-0 flex-1 bg-gradient-to-b from-[var(--cue-bg-subtle,var(--muted))]/40 to-background">
					{unavailable ? (
						<p className="p-6 text-sm text-muted-foreground">
							Không hiển thị được bản đồ 3D (trình duyệt chưa hỗ trợ WebGL hoặc lỗi tải hình). Danh sách bên trái vẫn đầy đủ các agent.
						</p>
					) : (
						<MapBoundary onError={() => setUnavailable(true)}>
						<Suspense fallback={<Skeleton className="m-4 h-[calc(100%-2rem)]" />}>
							<AgentMap3D
								agents={nodes}
								links={mapLinks}
								selectedId={selected}
								onSelect={setSelected}
								onOpen={(id) => {
									if (byId.get(id)?.role === 'business') navigate(`/workforce/agents/${id}`);
								}}
								layoutKey="awp.agent-map.layout.v1"
								resetSignal={reset}
								onUnavailable={() => setUnavailable(true)}
							/>
						</Suspense>
						</MapBoundary>
					)}
					<div className="pointer-events-none absolute inset-x-3 top-3 flex flex-wrap items-start justify-between gap-2">
						<div className="pointer-events-auto rounded-xl border border-border/70 bg-background/90 px-3 py-2 text-[11px] text-muted-foreground shadow-sm backdrop-blur">
							<p className="font-medium text-foreground">Kéo agent để sắp xếp · kéo nền để xoay · cuộn để phóng to</p>
							<p className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
								<span><i className="mr-1 inline-block h-0.5 w-4 bg-indigo-500 align-middle" />Leader giao việc</span>
								<span><i className="mr-1 inline-block h-0.5 w-4 bg-purple-500 align-middle" />Agent phối hợp cùng phiếu</span>
								<span><i className="mr-1 inline-block w-4 border-t border-dashed border-slate-400 align-middle" />Chưa có phiếu</span>
							</p>
						</div>
						<Button variant="outline" size="sm" className="pointer-events-auto bg-background/90" onClick={() => setReset((value) => value + 1)}>
							<RotateCcw /> Sắp xếp lại
						</Button>
					</div>
					{chosen && (
						<div className="absolute right-3 bottom-3 w-72 rounded-2xl border border-border/70 bg-background/95 p-3 text-sm shadow-lg backdrop-blur">
							<div className="flex items-center justify-between gap-2">
								<p className="truncate font-semibold">{chosen.name}</p>
								<Button variant="ghost" size="icon-sm" aria-label="Đóng" onClick={() => setSelected(null)}>
									<X />
								</Button>
							</div>
							<p className="mt-1 text-xs text-muted-foreground tabular-nums">
								{chosen.tickets} phiếu · chi phí {usd(chosen.costUsd)} · 30 ngày
							</p>
							{partners.length > 0 ? (
								<ul className="mt-2 space-y-1 text-xs">
									{partners.slice(0, 6).map((link) => {
										const other = byId.get(link.source === chosen.id ? link.target : link.source);
										const verb = link.kind === 'peer' ? 'Phối hợp với ' : chosen.role === 'leader' ? 'Giao cho ' : 'Nhận việc từ ';
										return (
											<li key={`${link.source}-${link.target}-${link.kind}`} className="flex justify-between gap-2">
												<span className="truncate">{verb}{other?.name ?? 'agent đã gỡ'}</span>
												<span className="shrink-0 tabular-nums text-muted-foreground">{link.tickets} phiếu</span>
											</li>
										);
									})}
								</ul>
							) : (
								<p className="mt-2 text-xs text-muted-foreground">Chưa phối hợp trong phiếu nào 30 ngày qua.</p>
							)}
							{chosen.role === 'business' && (
								<div className="mt-3 flex gap-2">
									<Button size="sm" onClick={() => navigate(`/workforce/agents/${chosen.id}`)}>
										<Pencil /> Mở agent
									</Button>
									<Button size="sm" variant="outline" onClick={() => navigate(`/chat/${chosen.id}`)}>
										<MessageSquare /> Trò chuyện
									</Button>
								</div>
							)}
						</div>
					)}
				</div>
			)}
		</div>
	);
}

export function AgentTable({ agents, onRemove }: { agents: AgentSummary[]; onRemove: (agent: AgentSummary) => void }) {
	const navigate = useNavigate();
	const { activity, cost } = useAgentMapData();
	const nodes = new Map(mapAgents(agents, activity, cost).map((node) => [node.id, node]));
	return (
		<div className="h-full overflow-y-auto px-4 pb-4">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Agent</TableHead>
						<TableHead>Trạng thái</TableHead>
						<TableHead>Phiên bản</TableHead>
						<TableHead>Kiểm thử gần nhất</TableHead>
						<TableHead>Tool</TableHead>
						<TableHead>Luật (tự học)</TableHead>
						<TableHead>Phiếu · chi phí 30 ngày</TableHead>
						<TableHead className="w-10">
							<span className="sr-only">Thao tác</span>
						</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{agents.map((agent) => (
						<TableRow key={agent.agent_id} className="h-14 cursor-pointer" onClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}>
							<TableCell className="whitespace-normal">
								<div className="flex items-center gap-3">
									<ClayAvatar id={agent.agent_id} label={agent.name} size={36} />
									<div className="min-w-0">
										<p className="truncate text-[14px]/[20px] font-medium">{agent.name}</p>
										<p className="line-clamp-1 max-w-xl text-[12px]/[16px] text-muted-foreground">{agent.description || 'Chưa có mô tả'}</p>
									</div>
								</div>
							</TableCell>
							<TableCell>
								<Badge variant={STATUS[agent.lifecycle_state].variant}>{STATUS[agent.lifecycle_state].label}</Badge>
								{agent.has_draft && agent.published_version > 0 && <Badge variant="outline" className="ml-1">Có nháp</Badge>}
							</TableCell>
							<TableCell>{agent.published_version ? `v${agent.published_version}` : '-'}</TableCell>
							<TableCell>
								{agent.last_test ? (agent.last_test.errors ? 'lỗi model' : `${agent.last_test.passed}/${agent.last_test.total}`) : '-'}
							</TableCell>
							<TableCell>{agent.tool_count}</TableCell>
							<TableCell>
								{agent.rule_count}
								{agent.learned_rule_count > 0 && <span className="text-primary"> (+{agent.learned_rule_count})</span>}
							</TableCell>
							<TableCell className="tabular-nums">
								{nodes.get(agent.agent_id)?.tickets ?? 0} · {usd(nodes.get(agent.agent_id)?.costUsd)}
							</TableCell>
							<TableCell onClick={(event) => event.stopPropagation()}>
								<AgentRowActions agent={agent} onRemove={onRemove} />
							</TableCell>
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
	);
}
