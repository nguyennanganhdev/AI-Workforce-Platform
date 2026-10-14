import {
	Background,
	BackgroundVariant,
	EdgeLabelRenderer,
	getBezierPath,
	Handle,
	Panel,
	Position,
	ReactFlow,
	useReactFlow,
	type EdgeProps,
	type EdgeTypes,
	type NodeProps,
	type NodeTypes,
} from '@xyflow/react';
import {
	Maximize,
	MessageSquare,
	Minimize,
	Minus,
	Pencil,
	Plus,
	Scan,
	ShieldCheck,
	UserRound,
	UsersRound,
	X,
} from 'lucide-react';
import { type CSSProperties, memo, useEffect, useMemo, useRef, useState } from 'react';

import {
	buildGraph,
	toGraphAgents,
	type AgentData,
	type EntryData,
	type FlowEdge,
	type FlowNode,
	type HumanData,
	type SupervisorData,
} from './graph-model';
import type { AgentView } from '@/api';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';
import '@xyflow/react/dist/style.css';
import './agent-graph.css';

/** Ports stay invisible: edges meet the card's edge, there is nothing to drag. */
const PORT = '!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent';

/** White card, hairline border, lifting a little on hover. */
const CARD =
	'ag-card rounded-2xl border border-[var(--cue-border,#e8e8e8)] bg-white transition-[box-shadow,transform] duration-200 hover:-translate-y-px hover:shadow-[0_6px_24px_rgba(0,0,0,0.08)]';

const stage = (delay: number) => ({ '--ag-delay': `${delay}ms` }) as CSSProperties;

/** Three moving bars: shown while an agent has sessions running. */
function Activity() {
	return (
		<span className="ag-eq" aria-hidden="true">
			<i />
			<i />
			<i />
		</span>
	);
}

/** Who sends requests in: a person, so a round tile rather than a sticker. */
const EntryNode = memo(function EntryNode({ data }: NodeProps<FlowNode & { data: EntryData }>) {
	const Icon = data.icon === 'resident' ? UsersRound : UserRound;
	return (
		<div
			className={cn('ag-node-in flex w-[184px] items-center gap-3 px-3 py-2.5', CARD)}
			style={stage(data.delay)}
		>
			<span
				className={cn(
					'flex size-9 shrink-0 items-center justify-center rounded-full',
					data.icon === 'manager'
						? 'bg-[var(--cue-avatar-user,#e5484d)] text-white'
						: 'bg-[var(--cue-bg-subtle,#f4f4f4)] text-[var(--cue-text-secondary,#6b6b6b)]',
				)}
			>
				<Icon className="size-4" />
			</span>
			<span className="min-w-0">
				<span className="block truncate text-[14px]/5 font-semibold">{data.title}</span>
				<span className="block truncate text-[12px]/4 text-[var(--cue-text-secondary,#6b6b6b)]">
					{data.note}
				</span>
			</span>
			<Handle
				type="source"
				position={Position.Right}
				className={PORT}
				isConnectable={false}
			/>
		</div>
	);
});

const AgentNode = memo(function AgentNode({ data }: NodeProps<FlowNode & { data: AgentData }>) {
	const { t } = useTranslation();
	const { agent, metrics } = data;
	const busy = metrics.running > 0;
	return (
		<div className={cn('ag-node-in w-[248px] p-3', CARD)} style={stage(data.delay)}>
			<Handle type="target" position={Position.Left} className={PORT} isConnectable={false} />
			<div className="flex items-center gap-3">
				<span className="relative shrink-0">
					<ClayAvatar id={agent.id} label={agent.name} size={40} />
					{/* Green and breathing: working. Grey: not yet open to the Leader. */}
					<span
						className={cn(
							'absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-white',
							busy
								? 'ag-ping bg-[var(--cue-success,#34c759)]'
								: agent.invitable
									? 'bg-[#cfcfcf]'
									: 'bg-[var(--amber-ink,#8a5a00)]',
						)}
					/>
				</span>
				<span className="min-w-0 flex-1">
					<span className="block truncate text-[14px]/5 font-semibold">{agent.name}</span>
					<span className="block truncate text-[12px]/4 text-[var(--cue-text-secondary,#6b6b6b)]">
						{agent.role || t('agents.list.noDescription')}
					</span>
				</span>
			</div>
			<div className="mt-3 flex items-center justify-between gap-2 text-[12px]/4">
				<span
					className={
						agent.invitable
							? 'text-[var(--cue-text-tertiary,#a8a8a8)]'
							: 'font-medium text-[var(--amber-ink,#8a5a00)]'
					}
				>
					{agent.invitable ? t('agents.graph.invitable') : t('agents.graph.notInvitable')}
				</span>
				{busy ? (
					<span className="inline-flex h-6 items-center gap-1.5 rounded-full bg-[var(--cue-blue-soft,#e8f1fd)] px-2.5 font-semibold text-[var(--cue-blue,#2f80ed)]">
						<Activity />
						{t('agents.graph.sessionCount', { count: metrics.running })}
					</span>
				) : (
					<span className="inline-flex h-6 items-center rounded-full bg-[var(--cue-bg-subtle,#f4f4f4)] px-2.5 text-[var(--cue-text-secondary,#6b6b6b)]">
						{t('agents.graph.idle')}
					</span>
				)}
			</div>
		</div>
	);
});

/** The Leader: the one dark element on the canvas, ringed in light while it works. */
const SupervisorNode = memo(function SupervisorNode({
	data,
}: NodeProps<FlowNode & { data: SupervisorData }>) {
	const { t } = useTranslation();
	const busy = data.running > 0;
	return (
		<div className="ag-node-in" style={stage(data.delay)}>
			<div className="ag-leader" data-idle={busy ? undefined : ''}>
				<div
					className={cn(
						'ag-card w-[260px] rounded-[20px] border border-white/10 bg-[#1a1a1a] p-3.5 text-white',
					)}
				>
					<Handle
						type="target"
						position={Position.Left}
						className={PORT}
						isConnectable={false}
					/>
					<div className="flex items-center gap-3">
						<ClayAvatar id="leader" label="Leader" size={44} />
						<span className="min-w-0 flex-1">
							<span className="block truncate text-[15px]/5 font-semibold">
								{data.title}
							</span>
							<span className="block truncate text-[12px]/4 text-white/60">
								{data.note}
							</span>
						</span>
					</div>
					<div className="mt-3 flex items-center justify-between rounded-xl bg-white/[0.06] px-3 py-2 text-[12px]/4">
						<span className="flex items-center gap-2 text-white/70">
							<span
								className={cn(
									'size-2 rounded-full',
									busy
										? 'ag-ping relative bg-[var(--cue-success,#34c759)]'
										: 'bg-white/30',
								)}
							/>
							{busy ? t('agents.graph.legendLive') : t('agents.graph.idle')}
						</span>
						<span className="font-semibold tabular-nums">
							{t('agents.graph.sessionCount', { count: data.running })}
						</span>
					</div>
					<Handle
						type="source"
						position={Position.Right}
						className={PORT}
						isConnectable={false}
					/>
					<Handle
						id="bottom"
						type="source"
						position={Position.Bottom}
						className={PORT}
						isConnectable={false}
					/>
				</div>
			</div>
		</div>
	);
});

/** Where a person has to decide before anything is written. */
const HumanNode = memo(function HumanNode({ data }: NodeProps<FlowNode & { data: HumanData }>) {
	return (
		<div
			className={cn(
				'ag-node-in flex w-[208px] items-center gap-3 px-3 py-2.5',
				CARD,
				'border-[#f3e2bd] bg-[var(--amber-soft,#fdf4e3)]',
			)}
			style={stage(data.delay)}
		>
			<Handle type="target" position={Position.Top} className={PORT} isConnectable={false} />
			<span className="relative flex size-9 shrink-0 items-center justify-center rounded-full bg-white text-[var(--amber-ink,#8a5a00)]">
				<ShieldCheck className="size-4" />
				{data.count > 0 && (
					<span className="ag-ping absolute -top-1 -right-1 flex size-4 items-center justify-center rounded-full bg-[#e8a317] text-[10px] font-bold text-white">
						<span className="relative z-10">{data.count}</span>
					</span>
				)}
			</span>
			<span className="min-w-0 text-[var(--amber-ink,#8a5a00)]">
				<span className="block truncate text-[14px]/5 font-semibold">{data.title}</span>
				<span className="block truncate text-[12px]/4 opacity-80">{data.note}</span>
			</span>
		</div>
	);
});

const nodeTypes: NodeTypes = {
	entry: EntryNode,
	agent: AgentNode,
	supervisor: SupervisorNode,
	human: HumanNode,
};

const EDGE_COLOUR = { live: '#2f80ed', human: '#e8a317', idle: '#d4d4d4' } as const;

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * A bezier whose look says what is happening on it. A live edge draws itself
 * in, then carries a bright streak and a glowing dot along it, Leader to
 * agent; one waiting on a person does the same, slower, in amber. An idle one
 * is a faint dashed line that only fades in.
 */
function FlowEdgeView({
	id,
	sourceX,
	sourceY,
	sourcePosition,
	targetX,
	targetY,
	targetPosition,
	data,
}: EdgeProps<FlowEdge>) {
	const [path, labelX, labelY] = getBezierPath({
		sourceX,
		sourceY,
		sourcePosition,
		targetX,
		targetY,
		targetPosition,
		curvature: 0.4,
	});
	const state = data?.state ?? 'idle';
	const colour = EDGE_COLOUR[state];
	const style = stage(data?.delay ?? 0);
	const moving = state !== 'idle' && !prefersReducedMotion();
	const duration = state === 'human' ? 3.2 : 2;
	return (
		<>
			<g className="ag-edge" style={style}>
				{state === 'idle' ? (
					<path
						d={path}
						fill="none"
						stroke={colour}
						strokeWidth={1.25}
						strokeDasharray="3 5"
						className="ag-edge-fade"
					/>
				) : (
					<>
						{/* A wide pale track under the line: the edge's glow. */}
						<path
							d={path}
							fill="none"
							stroke={colour}
							strokeOpacity={0.14}
							strokeWidth={7}
							strokeLinecap="round"
							pathLength={1}
							className="ag-edge-draw"
						/>
						<path
							d={path}
							fill="none"
							stroke={colour}
							strokeWidth={1.75}
							pathLength={1}
							className="ag-edge-draw"
						/>
						{moving && (
							<path
								d={path}
								fill="none"
								stroke="#ffffff"
								strokeOpacity={0.85}
								strokeWidth={1.75}
								strokeLinecap="round"
								pathLength={1}
								className={cn('ag-edge-streak', state === 'human' && 'ag-slow')}
							/>
						)}
						{moving &&
							// A negative begin starts the second dot halfway along, so
							// neither waits parked at the canvas origin; the group
							// fades in once the edge has drawn.
							[0, duration / 2].map((begin) => (
								<g key={begin} className="ag-edge-dots">
									<circle r="6" fill={colour} opacity="0.18">
										<animateMotion
											dur={`${duration}s`}
											begin={`${-begin}s`}
											repeatCount="indefinite"
											path={path}
										/>
									</circle>
									<circle r="2.5" fill={colour}>
										<animateMotion
											dur={`${duration}s`}
											begin={`${-begin}s`}
											repeatCount="indefinite"
											path={path}
										/>
									</circle>
								</g>
							))}
					</>
				)}
			</g>
			{data?.label && (
				<EdgeLabelRenderer>
					<span
						data-edge={id}
						className="ag-label pointer-events-none absolute"
						style={{
							transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
						}}
					>
						<span
							className="ag-node-in flex h-6 items-center gap-1.5 rounded-full border border-[var(--cue-border,#e8e8e8)] bg-white px-2.5 text-[11px]/4 font-semibold text-[var(--cue-text,#1a1a1a)] shadow-[0_2px_8px_rgba(0,0,0,0.06)]"
							style={stage((data.delay ?? 0) + 500)}
						>
							<span
								className="size-1.5 rounded-full"
								style={{ background: colour }}
							/>
							{data.label}
						</span>
					</span>
				</EdgeLabelRenderer>
			)}
		</>
	);
}

const edgeTypes: EdgeTypes = { flow: FlowEdgeView };

/** The floating chrome: white, hairline, the one soft shadow things that float get. */
const FLOAT =
	'rounded-full border border-[var(--cue-border,#e8e8e8)] bg-white/90 shadow-[0_2px_8px_rgba(0,0,0,0.06)] backdrop-blur';

/** Zoom, fit, and what the three edge styles mean. Must render inside `ReactFlow`. */
function Controls() {
	const { t } = useTranslation();
	const { zoomIn, zoomOut, fitView } = useReactFlow();
	const legend = [
		{ label: t('agents.graph.legendLive'), colour: EDGE_COLOUR.live, dashed: false },
		{ label: t('agents.graph.legendHuman'), colour: EDGE_COLOUR.human, dashed: false },
		{ label: t('agents.graph.legendIdle'), colour: EDGE_COLOUR.idle, dashed: true },
	];
	const tools = [
		{ label: t('agents.graph.zoomIn'), icon: Plus, run: () => zoomIn({ duration: 200 }) },
		{ label: t('agents.graph.zoomOut'), icon: Minus, run: () => zoomOut({ duration: 200 }) },
		{
			label: t('agents.graph.fit'),
			icon: Scan,
			run: () => fitView({ padding: 0.2, duration: 400 }),
		},
	];
	return (
		<Panel position="bottom-left" className="flex items-end gap-3">
			<div className={cn(FLOAT, 'flex flex-col rounded-2xl p-1')}>
				{tools.map(({ label, icon: Icon, run }) => (
					<Button
						key={label}
						variant="ghost"
						size="icon-sm"
						tooltip={label}
						aria-label={label}
						onClick={run}
					>
						<Icon />
					</Button>
				))}
			</div>
			<ul className={cn(FLOAT, 'flex h-9 items-center gap-4 px-4 text-[12px]/4')}>
				{legend.map((item) => (
					<li
						key={item.label}
						className="flex items-center gap-2 text-[var(--cue-text-secondary,#6b6b6b)]"
					>
						<svg width="20" height="4" aria-hidden="true">
							<line
								x1="1"
								y1="2"
								x2="19"
								y2="2"
								stroke={item.colour}
								strokeWidth="2"
								strokeLinecap="round"
								strokeDasharray={item.dashed ? '3 4' : undefined}
							/>
						</svg>
						{item.label}
					</li>
				))}
			</ul>
		</Panel>
	);
}

/** What the selected node is, with the ways onward for a real agent. */
function Inspector({
	node,
	onClose,
	onChat,
	onEdit,
}: {
	node: FlowNode;
	onClose: () => void;
	onChat: (agent: AgentView) => void;
	onEdit: (agent: AgentView) => void;
}) {
	const { t } = useTranslation();
	const data = node.data;
	const agent = data.kind === 'agent' ? data.agent : null;
	const title = agent ? agent.name : data.kind === 'agent' ? '' : data.title;
	const note = agent
		? agent.role || t('agents.list.noDescription')
		: data.kind === 'agent'
			? ''
			: data.note;

	return (
		<Panel position="top-right" className="w-[300px]">
			<section
				aria-label={title}
				className="ag-panel-in flex flex-col gap-4 rounded-[20px] border border-[var(--cue-border,#e8e8e8)] bg-white p-4 shadow-[var(--cue-shadow-float,0_8px_32px_rgba(0,0,0,0.1))]"
			>
				<header className="flex items-start gap-3">
					{agent && <ClayAvatar id={agent.id} label={agent.name} size={40} />}
					{data.kind === 'supervisor' && (
						<ClayAvatar id="leader" label="Leader" size={40} />
					)}
					<div className="min-w-0 flex-1">
						<h2 className="truncate text-[16px]/[24px] font-semibold">{title}</h2>
						<p className="text-[12px]/[16px] text-muted-foreground">{note}</p>
					</div>
					<Button
						variant="ghost"
						size="icon-sm"
						tooltip={t('common.close')}
						aria-label={t('common.close')}
						onClick={onClose}
					>
						<X />
					</Button>
				</header>

				{data.kind === 'agent' && (
					<dl className="grid grid-cols-3 gap-2 text-center">
						{[
							[t('agents.graph.inspectorSessions'), data.metrics.today],
							[t('agents.graph.inspectorRunning'), data.metrics.running],
							[
								t('agents.graph.inspectorResponse'),
								t('agents.graph.seconds', {
									seconds: data.metrics.responseSeconds.toFixed(1),
								}),
							],
						].map(([label, value]) => (
							<div
								key={label}
								className="rounded-xl bg-[var(--cue-bg-subtle,#f4f4f4)] px-1 py-2.5"
							>
								<dd className="text-[18px]/[24px] font-semibold tabular-nums">
									{value}
								</dd>
								<dt className="text-[12px]/[16px] text-muted-foreground">
									{label}
								</dt>
							</div>
						))}
					</dl>
				)}

				{agent && (
					<p className="text-[12px]/[16px] text-muted-foreground">
						{agent.invitable
							? t('agents.graph.invitableHelp')
							: t('agents.graph.notInvitableHelp')}
					</p>
				)}

				{agent?.real && (
					<footer className="flex gap-2">
						<Button
							variant="outline"
							className="flex-1"
							onClick={() => onChat(agent.real!)}
						>
							<MessageSquare />
							{t('agents.list.chat')}
						</Button>
						{agent.real.editable && (
							<Button className="flex-1" onClick={() => onEdit(agent.real!)}>
								<Pencil />
								{t('agents.list.edit')}
							</Button>
						)}
					</footer>
				)}
			</section>
		</Panel>
	);
}

/**
 * The agents as a live topology: who sends requests in, the Leader, and the
 * agents it can bring into a session.
 *
 * Read-only. Routing is decided by the Leader and by each agent's own
 * configuration, so nothing here can be dragged into a new connection.
 *
 * The agents and whether the Leader can reach each one are real. The live
 * figures — sessions, response time, pending approvals — are SAMPLE numbers
 * until the backend reports them, and the canvas says so.
 */
export function AgentGraph({
	agents,
	onChat,
	onEdit,
}: {
	agents: AgentView[];
	onChat: (agent: AgentView) => void;
	onEdit: (agent: AgentView) => void;
}) {
	const { t } = useTranslation();
	const container = useRef<HTMLDivElement>(null);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [hoverId, setHoverId] = useState<string | null>(null);
	const [fullscreen, setFullscreen] = useState(false);

	const model = useMemo(() => {
		const { agents: graphAgents, sample } = toGraphAgents(agents);
		return { ...buildGraph(graphAgents, t), sample, count: graphAgents.length };
	}, [agents, t]);

	// Hovering (or, failing that, selecting) a node puts the focus on it: its
	// own edges and neighbours stay, everything else steps back.
	const focusId = hoverId ?? selectedId;
	const neighbours = useMemo(() => {
		if (!focusId) return null;
		const ids = new Set([focusId]);
		for (const edge of model.edges) {
			if (edge.source === focusId) ids.add(edge.target);
			if (edge.target === focusId) ids.add(edge.source);
		}
		return ids;
	}, [focusId, model.edges]);

	// The dimming is a stylesheet, not node data: handing React Flow new node
	// objects on every hover makes it re-measure them, and it hides a node
	// until it has.
	const focusStyle = useMemo(() => {
		if (!focusId || !neighbours) return '';
		const nodes = model.nodes
			.filter((node) => !neighbours.has(node.id))
			.map((node) => `.react-flow__node[data-id="${node.id}"]`);
		const edges = model.edges
			.filter((edge) => edge.source !== focusId && edge.target !== focusId)
			.flatMap((edge) => [
				`[data-testid="rf__edge-${edge.id}"]`,
				`.ag-label[data-edge="${edge.id}"]`,
			]);
		const selectors = [...nodes, ...edges];
		return selectors.length ? `${selectors.join(',')}{opacity:.28}` : '';
	}, [focusId, neighbours, model.nodes, model.edges]);

	// Selection too: a dark hairline plus a soft halo, so it is not colour alone.
	const selectStyle = selectedId
		? `.react-flow__node[data-id="${selectedId}"] .ag-card{border-color:#1a1a1a;box-shadow:0 0 0 4px rgba(0,0,0,.06)}`
		: '';
	const selected = model.nodes.find((node) => node.id === selectedId) ?? null;

	useEffect(() => {
		const onKey = (event: KeyboardEvent) => {
			if (event.key === 'Escape') setSelectedId(null);
		};
		const onFullscreen = () => setFullscreen(document.fullscreenElement === container.current);
		window.addEventListener('keydown', onKey);
		document.addEventListener('fullscreenchange', onFullscreen);
		return () => {
			window.removeEventListener('keydown', onKey);
			document.removeEventListener('fullscreenchange', onFullscreen);
		};
	}, []);

	const toggleFullscreen = () => {
		if (document.fullscreenElement) void document.exitFullscreen();
		else void container.current?.requestFullscreen();
	};

	return (
		<div ref={container} className="size-full bg-white">
			{(focusStyle || selectStyle) && <style>{focusStyle + selectStyle}</style>}
			<ReactFlow<FlowNode, FlowEdge>
				nodes={model.nodes}
				edges={model.edges}
				nodeTypes={nodeTypes}
				edgeTypes={edgeTypes}
				nodesDraggable={false}
				nodesConnectable={false}
				elementsSelectable
				fitView
				fitViewOptions={{ padding: 0.2 }}
				minZoom={0.5}
				maxZoom={1.5}
				onNodeClick={(_event, node) => setSelectedId(node.id)}
				onPaneClick={() => setSelectedId(null)}
				onNodeMouseEnter={(_event, node) => setHoverId(node.id)}
				onNodeMouseLeave={() => setHoverId(null)}
				proOptions={{ hideAttribution: true }}
			>
				<Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="#e3e3e3" />

				<Panel position="top-left" className="flex flex-wrap items-center gap-2">
					{/* Said first and in the warning tone: the numbers on this
					    canvas are not measurements. */}
					<span className="inline-flex h-8 items-center gap-1.5 rounded-full bg-[var(--amber-soft,#fdf4e3)] px-3 text-[12px]/4 font-medium text-[var(--amber-ink,#8a5a00)]">
						<span className="size-1.5 rounded-full bg-current" />
						{model.sample ? t('agents.graph.sampleAll') : t('agents.graph.sample')}
					</span>
					{/* The three figures as one strip, live ones marked by a breathing dot. */}
					<div className={cn(FLOAT, 'flex h-8 items-center px-1 text-[12px]/4')}>
						<span className="px-3">
							{t('agents.graph.agentCount', { count: model.count })}
						</span>
						<span className="h-3.5 w-px bg-[var(--cue-border,#e8e8e8)]" />
						<span className="flex items-center gap-2 px-3">
							{model.totalRunning > 0 && (
								<span className="ag-ping relative size-1.5 rounded-full bg-[var(--cue-success,#34c759)]" />
							)}
							{t('agents.graph.running', { count: model.totalRunning })}
						</span>
						<span className="h-3.5 w-px bg-[var(--cue-border,#e8e8e8)]" />
						<span className="px-3">
							{t('agents.graph.response', {
								seconds: model.averageResponse.toFixed(1),
							})}
						</span>
					</div>
				</Panel>

				{/* Moves aside when the inspector takes the top-right corner. */}
				<Panel position={selected ? 'bottom-right' : 'top-right'}>
					<Button
						variant="outline"
						size="sm"
						className="bg-white/90 backdrop-blur"
						onClick={toggleFullscreen}
					>
						{fullscreen ? <Minimize /> : <Maximize />}
						{fullscreen
							? t('agents.graph.exitFullscreen')
							: t('agents.graph.fullscreen')}
					</Button>
				</Panel>

				<Controls />

				{selected && (
					<Inspector
						node={selected}
						onClose={() => setSelectedId(null)}
						onChat={onChat}
						onEdit={onEdit}
					/>
				)}
			</ReactFlow>
		</div>
	);
}
