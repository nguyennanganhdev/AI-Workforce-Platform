import { ArrowUpRight, Ellipsis, Focus, GitBranch, Info, MessageSquare, Pencil, RotateCcw, Search, SlidersHorizontal, Trash2, Users, X } from 'lucide-react';
import { lazy, Suspense, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { mapAgents, STATUS, usd } from './agent-map-data';
import type { AgentSummary } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuRadioGroup,
	DropdownMenuRadioItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useAgentMapData } from '@/hooks/useStudioAgents';
import { cn } from '@/lib/utils';
import type { MapAgent, MapLink } from '@/pages/agents/AgentMap3D';

import './map-workspace.css';


const AgentMap3D = lazy(() => import('@/pages/agents/AgentMap3D'));

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

function AgentRoster({
	agents, nodes, selectedId, onSelect, onRemove,
}: {
	agents: AgentSummary[];
	nodes: MapAgent[];
	selectedId: string | null;
	onSelect: (id: string) => void;
	onRemove: (agent: AgentSummary) => void;
}) {
	const [query, setQuery] = useState('');
	const [state, setState] = useState('all');
	const byId = new Map(nodes.map((node) => [node.id, node]));
	const leader = nodes.find((node) => node.role === 'leader');
	const needle = query.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/đ/g, 'd').trim();
	const visible = agents.filter((agent) => {
		const name = agent.name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/đ/g, 'd');
		return name.includes(needle) && (state === 'all' || agent.lifecycle_state === state);
	});
	return (
		<div className="flex h-full min-h-0 flex-col">
			<div className="space-y-3 px-4 pt-4 pb-3">
				<div className="flex items-center justify-between">
					<h2 className="text-sm font-semibold">Đội ngũ agent</h2>
					<span className="text-xs tabular-nums text-muted-foreground">{agents.length} agent</span>
				</div>
				<div className="flex gap-2">
					<div className="relative min-w-0 flex-1">
						<Search aria-hidden="true" className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
						<Input aria-label="Tìm agent" placeholder="Tìm agent..." value={query} onChange={(event) => setQuery(event.target.value)} className="h-10 pl-9" />
					</div>
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button variant="outline" size="icon" className="relative size-10 shrink-0" aria-label="Lọc trạng thái agent">
								<SlidersHorizontal />
								{state !== 'all' && <span className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-primary" />}
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end">
							<DropdownMenuLabel>Trạng thái</DropdownMenuLabel>
							<DropdownMenuRadioGroup value={state} onValueChange={setState}>
								<DropdownMenuRadioItem value="all">Tất cả agent</DropdownMenuRadioItem>
								<DropdownMenuRadioItem value="published">Đang phát hành</DropdownMenuRadioItem>
								<DropdownMenuRadioItem value="draft">Bản nháp</DropdownMenuRadioItem>
								<DropdownMenuRadioItem value="withdrawn">Đã ngừng</DropdownMenuRadioItem>
							</DropdownMenuRadioGroup>
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
			</div>
			{leader && (
				<div className="mx-3 mb-3 border-b border-border/70 pb-3">
					<button type="button" onClick={() => onSelect(leader.id)} aria-pressed={selectedId === leader.id} className={cn('map-roster-button map-roster-leader w-full', selectedId === leader.id && 'is-selected')}>
						<ClayAvatar id={leader.id} label="Leader" size={42} />
						<span className="min-w-0 flex-1 text-left">
							<span className="block text-sm font-semibold">Leader</span>
							<span className="block text-xs text-muted-foreground">Điều phối công việc</span>
						</span>
						<GitBranch aria-hidden="true" className="size-4 text-muted-foreground" />
					</button>
				</div>
			)}
			<ul aria-label="Danh sách agent" className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 pb-3">
				{visible.map((agent) => {
					const node = byId.get(agent.agent_id);
					return (
						<li key={agent.agent_id} className={cn('map-roster-row group', selectedId === agent.agent_id && 'is-selected')}>
							<button type="button" onClick={() => onSelect(agent.agent_id)} aria-pressed={selectedId === agent.agent_id} className="map-roster-button min-w-0 flex-1">
								<ClayAvatar id={agent.agent_id} label={agent.name} size={40} className={cn(agent.lifecycle_state !== 'published' && 'opacity-70 grayscale')} />
								<span className="min-w-0 flex-1 text-left">
									<span className="map-roster-name">{agent.name}</span>
									<span className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[11px] leading-4 text-muted-foreground">
										<span className={cn('map-state-mark', agent.lifecycle_state === 'published' && 'is-published')} aria-hidden="true" />
										{STATUS[agent.lifecycle_state].label}
										<span aria-hidden="true">·</span><span className="tabular-nums">{node?.tickets ?? 0} phiếu</span>
									</span>
								</span>
							</button>
							<AgentRowActions agent={agent} onRemove={onRemove} />
						</li>
					);
				})}
				{visible.length === 0 && (
					<li className="px-3 py-8 text-center text-sm text-muted-foreground">
						Không tìm thấy agent phù hợp.
						<Button variant="link" className="mt-2 w-full" onClick={() => { setQuery(''); setState('all'); }}>Xóa bộ lọc</Button>
					</li>
				)}
			</ul>
			<p className="border-t border-border/70 px-4 py-3 text-xs leading-5 text-muted-foreground">Chọn agent để xem thông tin và các kết nối trên sơ đồ.</p>
		</div>
	);
}

export function AgentMapView({ agents, onRemove }: { agents: AgentSummary[]; onRemove: (agent: AgentSummary) => void }) {
	const navigate = useNavigate();
	const { activity, links, cost } = useAgentMapData();
	const [selected, setSelected] = useState<string | null>(null);
	const [reset, setReset] = useState(0);
	const [home, setHome] = useState(0);
	const [showLabels, setShowLabels] = useState(true);
	const [showPeers, setShowPeers] = useState(true);
	const [rosterOpen, setRosterOpen] = useState(false);
	const [unavailable, setUnavailable] = useState(false);
	const nodes = useMemo(() => mapAgents(agents, activity, cost), [agents, activity, cost]);
	const byId = new Map(nodes.map((node) => [node.id, node]));
	const mapLinks: MapLink[] = useMemo(
		() => links.map((link) => ({ source: link.source, target: link.target, kind: link.kind, tickets: link.tickets, lastAt: link.last_at })),
		[links],
	);
	const chosen = selected ? byId.get(selected) : undefined;
	const partners = chosen ? mapLinks.filter((link) => link.source === chosen.id || link.target === chosen.id) : [];
	const published = agents.filter((agent) => agent.lifecycle_state === 'published').length;
	const selectAgent = (id: string) => { setSelected(id); setRosterOpen(false); };
	const roster = <AgentRoster agents={agents} nodes={nodes} selectedId={selected} onSelect={selectAgent} onRemove={onRemove} />;
	return (
		<div className="agent-map-workspace flex size-full min-h-0">
			<aside aria-label="Đội ngũ agent" className="map-roster hidden h-full w-64 shrink-0 border-r border-border/70 bg-background md:block xl:w-72">
				{roster}
			</aside>
			<section aria-label="Sơ đồ phối hợp agent" className="relative flex min-h-0 min-w-0 flex-1 flex-col">
				<div className="map-scene-toolbar">
					<div className="min-w-0">
						<h2 className="text-sm font-semibold">Sơ đồ phối hợp</h2>
						<p className="mt-1 text-xs text-muted-foreground"><span className="tabular-nums">{published}</span> đã phát hành <span className="px-1" aria-hidden="true">·</span> <span className="tabular-nums">{mapLinks.length}</span> kết nối</p>
					</div>
					<div className="flex shrink-0 items-center gap-1">
						<Tooltip>
							<TooltipTrigger asChild><Button variant="ghost" size="icon" className="hidden size-10 sm:inline-flex" aria-label="Hướng dẫn sơ đồ"><Info /></Button></TooltipTrigger>
							<TooltipContent className="max-w-64 leading-5">Chọn agent để xem kết nối. Kéo nhân vật để sắp xếp, kéo nền để xoay, cuộn để thu phóng. Khi chọn nhãn, dùng phím mũi tên để di chuyển.</TooltipContent>
						</Tooltip>
						<Sheet open={rosterOpen} onOpenChange={setRosterOpen}>
							<SheetTrigger asChild>
								<Button variant="outline" size="sm" className="h-10 md:hidden"><Users /> Agent</Button>
							</SheetTrigger>
							<SheetContent side="left" className="agent-map-workspace w-[min(340px,92vw)]! gap-0 p-0">
								<SheetHeader className="sr-only">
									<SheetTitle>Đội ngũ agent</SheetTitle>
									<SheetDescription>Tìm và chọn agent để xem trong sơ đồ.</SheetDescription>
								</SheetHeader>
								<div className="min-h-0 flex-1 pt-10">{roster}</div>
							</SheetContent>
						</Sheet>
						<Tooltip>
							<TooltipTrigger asChild>
								<Button variant="ghost" size="icon" className="size-10" aria-label="Căn giữa sơ đồ" disabled={unavailable} onClick={() => setHome((value) => value + 1)}><Focus /></Button>
							</TooltipTrigger>
							<TooltipContent>Căn giữa sơ đồ</TooltipContent>
						</Tooltip>
						<DropdownMenu>
							<DropdownMenuTrigger asChild><Button variant="outline" size="sm" className="h-10" aria-label="Tùy chọn sơ đồ"><SlidersHorizontal /><span className="hidden sm:inline">Hiển thị</span></Button></DropdownMenuTrigger>
							<DropdownMenuContent align="end" className="w-56">
								<DropdownMenuLabel>Hiển thị trên sơ đồ</DropdownMenuLabel>
								<DropdownMenuCheckboxItem checked={showLabels} onCheckedChange={setShowLabels}>Tên và trạng thái agent</DropdownMenuCheckboxItem>
								<DropdownMenuCheckboxItem checked={showPeers} onCheckedChange={setShowPeers}>Liên kết phối hợp</DropdownMenuCheckboxItem>
								<DropdownMenuSeparator />
								<DropdownMenuItem disabled={unavailable} onSelect={() => setReset((value) => value + 1)}><RotateCcw /> Sắp xếp lại sơ đồ</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					</div>
				</div>
				<div className="map-scene relative min-h-0 flex-1">
					{unavailable ? (
						<div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
							<GitBranch className="size-8 text-muted-foreground" aria-hidden="true" />
							<h3 className="text-sm font-medium">Sơ đồ 3D chưa khả dụng</h3>
							<p className="max-w-sm text-sm leading-6 text-muted-foreground">Bạn vẫn có thể chọn agent từ danh sách hoặc chuyển sang chế độ Danh sách để quản lý.</p>
							<Button variant="outline" onClick={() => navigate('/workforce/agents?view=list')}>Mở danh sách agent <ArrowUpRight /></Button>
						</div>
					) : (
						<Suspense fallback={<div className="flex h-full items-center justify-center"><Skeleton className="h-64 w-3/4 rounded-2xl" /></div>}>
							<AgentMap3D agents={nodes} links={mapLinks} selectedId={chosen?.id ?? null} onSelect={setSelected}
								onOpen={(id) => navigate(byId.get(id)?.role === 'leader' ? '/workforce/leader' : `/workforce/agents/${id}`)}
								layoutKey="awp.agent-map.layout.v2" resetSignal={reset} homeSignal={home}
								showLabels={showLabels} showPeerLinks={showPeers} onUnavailable={() => setUnavailable(true)} />
						</Suspense>
					)}
					{chosen && (
						<section aria-label={`Thông tin ${chosen.name}`} className="map-agent-inspector absolute right-4 bottom-14 left-4 z-10 max-h-[65%] overflow-y-auto rounded-xl border border-border bg-background p-4 shadow-lg sm:left-auto sm:w-80">
							<div className="flex items-start gap-3">
								<ClayAvatar id={chosen.id} label={chosen.name} size={44} />
								<div className="min-w-0 flex-1">
									<h3 className="text-sm leading-5 font-semibold">{chosen.name}</h3>
									<p className="mt-1 text-xs text-muted-foreground">{chosen.role === 'leader' ? 'Điều phối công việc' : STATUS[chosen.state].label}</p>
								</div>
								<Button variant="ghost" size="icon" className="-mt-1 -mr-1 size-9 shrink-0" aria-label="Đóng thông tin agent" onClick={() => setSelected(null)}><X /></Button>
							</div>
							<dl className="my-4 grid grid-cols-2 divide-x divide-border rounded-lg bg-muted/50 py-3">
								<div className="px-3"><dt className="text-xs text-muted-foreground">Phiếu · 30 ngày</dt><dd className="mt-1 text-base font-semibold tabular-nums">{chosen.tickets}</dd></div>
								<div className="px-3"><dt className="text-xs text-muted-foreground">Chi phí đã ghi nhận</dt><dd className="mt-1 text-base font-semibold tabular-nums">{usd(chosen.costUsd)}</dd></div>
							</dl>
							<p className="mb-2 text-xs font-medium">Kết nối công việc</p>
							{partners.length ? (
								<ul className="space-y-2.5">
									{partners.slice(0, 5).map((link) => {
										const other = byId.get(link.source === chosen.id ? link.target : link.source);
										const verb = link.kind === 'peer' ? 'Phối hợp' : link.source === chosen.id ? 'Giao việc' : 'Nhận việc';
										return <li key={`${link.source}-${link.target}-${link.kind}`} className="flex items-center justify-between gap-3 text-xs">
											<div className="min-w-0"><span className="text-muted-foreground">{verb} · </span><span>{other?.name ?? 'Agent đã gỡ'}</span></div>
											<span className="shrink-0 text-muted-foreground tabular-nums">{link.tickets} phiếu</span>
										</li>;
									})}
									{partners.length > 5 && <li className="text-xs text-muted-foreground">Và {partners.length - 5} kết nối khác.</li>}
								</ul>
							) : <p className="text-xs leading-5 text-muted-foreground">Chưa ghi nhận kết nối công việc trong 30 ngày qua.</p>}
							<div className="mt-4 flex gap-2 border-t border-border/70 pt-3">
								<Button size="sm" className="h-10 flex-1" onClick={() => navigate(chosen.role === 'leader' ? '/workforce/leader' : `/workforce/agents/${chosen.id}`)}><ArrowUpRight />{chosen.role === 'leader' ? 'Mở Leader' : 'Mở agent'}</Button>
								{chosen.role === 'business' && <Button size="sm" variant="outline" className="h-10 flex-1" onClick={() => navigate(`/chat/${chosen.id}`)}><MessageSquare />Trò chuyện</Button>}
							</div>
						</section>
					)}
					<div className="map-scene-footer absolute inset-x-0 bottom-0 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 bg-background/95 px-4 py-3 text-[11px] text-muted-foreground">
						<div className="flex flex-wrap items-center gap-x-4 gap-y-1" aria-label="Chú giải kết nối">
							<span className="flex items-center gap-1.5"><i className="map-link-key" aria-hidden="true" />Leader giao việc</span>
							{showPeers && <span className="flex items-center gap-1.5"><i className="map-link-key is-peer" aria-hidden="true" />Agent phối hợp</span>}
						</div>
						<span className="hidden items-center gap-1.5 sm:flex"><Info className="size-3.5" aria-hidden="true" />Lịch sử phối hợp · 30 ngày</span>
					</div>
				</div>
			</section>
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
