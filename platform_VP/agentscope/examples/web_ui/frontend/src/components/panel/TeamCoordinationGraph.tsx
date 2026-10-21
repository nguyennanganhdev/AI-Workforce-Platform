import { useId } from 'react';

import { ClayAvatar } from '@/components/ui/clay-avatar';
import type { TeamActivityItem, TeamActivityParticipant, TeamMemberRuntime } from '@/hooks/useTeamActivity';
import { cn } from '@/lib/utils';

import './team-coordination-graph.css';

export function TeamCoordinationGraph({ participants, communications, runtimeBySession, selectedId, onSelect }: {
	participants: TeamActivityParticipant[];
	communications: TeamActivityItem[];
	runtimeBySession: Record<string, TeamMemberRuntime>;
	selectedId: string | null;
	onSelect: (id: string | null) => void;
}) {
	const markerId = useId().replace(/:/g, '');
	const leader = participants.find((participant) => participant.role === 'leader');
	const members = participants.filter((participant) => participant !== leader);
	const size = Math.max(320, members.length * 48);
	const center = size / 2;
	const radius = center - 48;
	const nodes = participants.map((participant) => {
		const index = members.indexOf(participant);
		const angle = -Math.PI / 2 + index * 2 * Math.PI / members.length;
		return {
			...participant,
			x: participant === leader ? center : center + radius * Math.cos(angle),
			y: participant === leader ? center : center + radius * Math.sin(angle),
			runtime: participant.sessionId ? runtimeBySession[participant.sessionId] : undefined,
		};
	});
	const edges = new Map<string, { source: typeof nodes[number]; target: typeof nodes[number]; count: number; running: boolean; error: boolean }>();
	for (const item of communications) {
		const source = nodes.find((node) => node.sessionId === item.sessionId) ?? nodes.find((node) => node.name === item.sourceName);
		if (!source) continue;
		const targets = nodes.filter((node) => node !== source && (node.name === item.targetName || item.targetName === 'Cả nhóm'));
		for (const target of targets) {
			const key = `${source.agentId}:${target.agentId}`;
			const previous = edges.get(key);
			edges.set(key, { source, target, count: (previous?.count ?? 0) + 1,
				running: previous?.running || item.state === 'running', error: previous?.error ?? item.state === 'error' });
		}
	}
	return (
		<div className="rounded-2xl border border-border/60 bg-gradient-to-b from-cyan-500/5 to-background">
			<div className="flex items-center justify-between gap-2 px-3 pt-3 text-[10px] text-muted-foreground">
				<span>{communications.length} lượt trao đổi</span>
				<button type="button" onClick={() => onSelect(null)} aria-pressed={!selectedId}
					className="rounded-full border bg-background px-2 py-1 hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring">Tất cả</button>
			</div>
			<div className="max-h-96 overflow-auto">
				<div className="relative mx-auto" style={{ width: size, height: size }}>
					<svg aria-hidden="true" className="pointer-events-none absolute inset-0 size-full" viewBox={`0 0 ${size} ${size}`}>
						<defs>{['#06b6d4', 'var(--destructive)'].map((color, index) => (
							<marker key={color} id={`${markerId}-${index}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
								<path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
							</marker>
						))}</defs>
						<circle cx={center} cy={center - 16} r={radius} fill="none" className="stroke-border/60" strokeDasharray="3 6" />
						{leader && nodes.filter((node) => node.agentId !== leader.agentId).map((node) => (
							<line key={node.agentId} x1={center} y1={center - 16} x2={node.x} y2={node.y - 16} className="stroke-border" strokeWidth="1.5" />
						))}
						{[...edges.entries()].map(([key, edge]) => {
							const { source, target } = edge;
							const dx = target.x - source.x;
							const dy = target.y - source.y;
							const length = Math.hypot(dx, dy);
							const x1 = source.x + dx / length * 22;
							const y1 = source.y - 16 + dy / length * 22;
							const x2 = target.x - dx / length * 24;
							const y2 = target.y - 16 - dy / length * 24;
							const latest = communications.find((item) => item.sessionId === source.sessionId || item.sourceName === source.name);
							const active = edge.running || (source.runtime?.status === 'communicating'
								&& (latest?.targetName === target.name || latest?.targetName === 'Cả nhóm'));
							return <path key={key} d={`M ${x1} ${y1} Q ${(x1 + x2) / 2 - dy * 0.12} ${(y1 + y2) / 2 + dx * 0.12} ${x2} ${y2}`}
								fill="none" stroke="currentColor" strokeWidth="1.8" markerEnd={`url(#${markerId}-${edge.error ? 1 : 0})`}
								className={cn('transition-opacity', edge.error ? 'text-destructive' : 'text-cyan-500',
									selectedId && selectedId !== source.agentId && selectedId !== target.agentId && 'opacity-15', active && 'team-coordination-flow')}
								><title>{`${source.name} → ${target.name}: ${edge.count} lượt trao đổi`}</title></path>;
						})}
					</svg>
					{nodes.map((node) => {
						const busy = node.runtime?.status === 'active' || node.runtime?.status === 'communicating';
						return <button key={node.agentId} type="button" aria-pressed={selectedId === node.agentId}
							aria-label={`Xem phối hợp của ${node.name}`} title={`${node.name}\n${node.runtime?.detail ?? 'Chưa có hoạt động'}`}
							onClick={() => onSelect(selectedId === node.agentId ? null : node.agentId)}
							style={{ left: node.x, top: node.y }}
							className={cn('absolute flex h-[76px] w-[88px] -translate-x-1/2 -translate-y-1/2 flex-col items-center rounded-xl px-1 py-1 transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring',
								selectedId === node.agentId && 'bg-cyan-500/10 ring-1 ring-cyan-500/40')}>
							<span className={cn('relative shrink-0 rounded-full border-2 bg-background p-1 shadow-sm', node.role === 'leader' ? 'border-amber-300' : 'border-border', busy && 'border-cyan-400')}>
								<ClayAvatar id={node.agentId} label={node.name} size={28} />
								<span className={cn('absolute -right-0.5 bottom-0 size-2.5 rounded-full border-2 border-background',
									node.runtime?.status === 'error' ? 'bg-destructive' : busy ? 'bg-cyan-500 motion-safe:animate-pulse' : node.runtime?.status === 'waiting' ? 'bg-orange-500' : node.runtime?.status === 'completed' ? 'bg-emerald-500' : 'bg-muted-foreground/50')} />
							</span>
							<span className="mt-1 line-clamp-2 w-full break-words rounded bg-background/90 text-center text-[10px]/3 font-medium">{node.name}</span>
						</button>;
					})}
				</div>
			</div>
			<p className="px-3 pb-3 text-center text-[10px] text-muted-foreground">Chọn agent để xem nội dung phối hợp</p>
		</div>
	);
}
