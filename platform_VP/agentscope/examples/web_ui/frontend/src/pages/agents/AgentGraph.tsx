import {
	Background,
	BackgroundVariant,
	BaseEdge,
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
	ShieldCheck,
	UserRound,
	UsersRound,
	X,
} from 'lucide-react';
import { memo, useEffect, useMemo, useRef, useState } from 'react';

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

/** The ports edges attach to: small, round, and not something to drag from. */
const PORT = '!size-2 !border !border-[var(--line)] !bg-[var(--raised)]';

/** Selected is the action colour plus a soft ring, so it is not colour alone. */
const SELECTED = 'border-[var(--action)] ring-[3px] ring-[var(--action-soft)]';

/** Who sends requests in: dashed, because it is outside the platform. */
const EntryNode = memo(function EntryNode({
	data,
	selected,
}: NodeProps<FlowNode & { data: EntryData }>) {
	const Icon = data.icon === 'resident' ? UsersRound : UserRound;
	return (
		<div
			className={cn(
				'flex w-[168px] items-center gap-2.5 rounded-[var(--r-tile)] border border-dashed border-[var(--ink-3)] bg-[var(--surface)] px-3 py-2',
				selected && SELECTED,
			)}
		>
			<span className="flex size-7 shrink-0 items-center justify-center rounded-[10px] bg-[var(--sunken)] text-[var(--ink-2)]">
				<Icon className="size-4" />
			</span>
			<span className="min-w-0">
				<span className="block truncate text-[13px]/[20px] font-semibold">
					{data.title}
				</span>
				<span className="block truncate text-[12px]/[16px] text-muted-foreground">
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

const AgentNode = memo(function AgentNode({
	data,
	selected,
}: NodeProps<FlowNode & { data: AgentData }>) {
	const { t } = useTranslation();
	const { agent, metrics } = data;
	return (
		<div
			className={cn(
				'w-[224px] rounded-[var(--r-tile)] border border-white bg-[var(--raised)] shadow-[var(--clay-bubble)]',
				selected && SELECTED,
			)}
		>
			<Handle type="target" position={Position.Left} className={PORT} isConnectable={false} />
			<div className="flex items-center gap-2.5 px-3 py-2.5">
				<ClayAvatar
					id={agent.id}
					label={agent.name}
					size={36}
					working={metrics.running > 0}
				/>
				<span className="min-w-0 flex-1">
					<span className="block truncate text-[13px]/[20px] font-semibold">
						{agent.name}
					</span>
					<span className="block truncate text-[12px]/[16px] text-muted-foreground">
						{agent.role || t('agents.list.noDescription')}
					</span>
				</span>
				{/* Green: reachable. Grey: not yet open to the Leader. */}
				<span
					className={cn(
						'size-2 shrink-0 rounded-full',
						agent.invitable ? 'bg-[var(--mint-ink)]' : 'bg-[var(--ink-3)]',
					)}
				/>
			</div>
			<div className="flex items-center justify-between gap-2 border-t border-[var(--line-warm)] px-3 py-1.5 text-[12px]/[16px]">
				<span className="rounded-full bg-[var(--sunken)] px-2 py-0.5 text-[var(--ink-2)]">
					{agent.invitable ? t('agents.graph.invitable') : t('agents.graph.notInvitable')}
				</span>
				{metrics.running > 0 ? (
					<span className="font-semibold text-[var(--violet-ink)]">
						{t('agents.graph.sessionCount', { count: metrics.running })}
					</span>
				) : (
					<span className="text-[var(--ink-3)]">{t('agents.graph.idle')}</span>
				)}
			</div>
		</div>
	);
});

/** The Leader: the one emphasised element on the canvas. */
const SupervisorNode = memo(function SupervisorNode({
	data,
	selected,
}: NodeProps<FlowNode & { data: SupervisorData }>) {
	const { t } = useTranslation();
	return (
		<div
			className={cn(
				'w-[236px] rounded-[var(--r-tile)] border border-[var(--ink)] bg-[var(--ink)] text-white shadow-[0_5px_0_#1d2538]',
				selected && SELECTED,
			)}
		>
			<Handle type="target" position={Position.Left} className={PORT} isConnectable={false} />
			<div className="flex items-center gap-2.5 px-3 py-2.5">
				<ClayAvatar id="leader" label="Leader" size={36} working={data.running > 0} />
				<span className="min-w-0 flex-1">
					<span className="block truncate text-[13px]/[20px] font-semibold">
						{data.title}
					</span>
					<span className="block truncate text-[12px]/[16px] text-white/70">
						{data.note}
					</span>
				</span>
			</div>
			<div className="border-t border-white/15 px-3 py-1.5 text-right text-[12px]/[16px] text-white/80">
				{t('agents.graph.sessionCount', { count: data.running })}
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
	);
});

/** Where a person has to decide before anything is written. */
const HumanNode = memo(function HumanNode({
	data,
	selected,
}: NodeProps<FlowNode & { data: HumanData }>) {
	return (
		<div
			className={cn(
				'flex w-[184px] items-center gap-2.5 rounded-[var(--r-tile)] border border-[#f0d9a8] bg-[var(--amber-soft)] px-3 py-2 text-[var(--amber-ink)]',
				selected && SELECTED,
			)}
		>
			<Handle type="target" position={Position.Top} className={PORT} isConnectable={false} />
			<span className="flex size-7 shrink-0 items-center justify-center rounded-[10px] bg-white/70">
				<ShieldCheck className="size-4" />
			</span>
			<span className="min-w-0">
				<span className="block truncate text-[13px]/[20px] font-semibold">
					{data.title}
				</span>
				<span className="block truncate text-[12px]/[16px]">{data.note}</span>
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

const EDGE_COLOUR = { live: '#65588b', human: '#b07a12', idle: '#b9c2d6' } as const;

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** A bezier whose look says what is happening on it; live ones carry travelling dots. */
function FlowEdgeView({
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
	});
	const state = data?.state ?? 'idle';
	const colour = EDGE_COLOUR[state];
	return (
		<>
			<BaseEdge
				path={path}
				style={{
					stroke: colour,
					strokeWidth: state === 'idle' ? 1.5 : 2,
					strokeDasharray: state === 'idle' ? '4 5' : undefined,
				}}
			/>
			{state === 'live' &&
				!prefersReducedMotion() &&
				[0, 1.2].map((delay) => (
					<circle key={delay} r="3" fill={colour}>
						<animateMotion
							dur="2.4s"
							begin={`${delay}s`}
							repeatCount="indefinite"
							path={path}
						/>
					</circle>
				))}
			{data?.label && (
				<EdgeLabelRenderer>
					<span
						className="pointer-events-none absolute rounded-full border border-white bg-[var(--raised)] px-2 py-0.5 text-[12px]/[16px] font-semibold shadow-[var(--clay-bubble)]"
						style={{
							transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
							color: colour,
						}}
					>
						{data.label}
					</span>
				</EdgeLabelRenderer>
			)}
		</>
	);
}

const edgeTypes: EdgeTypes = { flow: FlowEdgeView };

const PILL =
	'inline-flex h-7 items-center gap-1.5 rounded-full border border-white bg-[var(--raised)] px-3 text-[12px]/[16px] shadow-[var(--clay-bubble)]';

/** Zoom, fit, and what the three edge styles mean. Must render inside `ReactFlow`. */
function Controls() {
	const { t } = useTranslation();
	const { zoomIn, zoomOut, fitView } = useReactFlow();
	const legend = [
		{ label: t('agents.graph.legendLive'), colour: EDGE_COLOUR.live, dashed: false },
		{ label: t('agents.graph.legendHuman'), colour: EDGE_COLOUR.human, dashed: false },
		{ label: t('agents.graph.legendIdle'), colour: EDGE_COLOUR.idle, dashed: true },
	];
	return (
		<Panel position="bottom-left" className="flex items-end gap-3">
			<div className="flex flex-col gap-1">
				<Button
					variant="outline"
					size="icon"
					tooltip={t('agents.graph.zoomIn')}
					aria-label={t('agents.graph.zoomIn')}
					onClick={() => zoomIn()}
				>
					<Plus />
				</Button>
				<Button
					variant="outline"
					size="icon"
					tooltip={t('agents.graph.zoomOut')}
					aria-label={t('agents.graph.zoomOut')}
					onClick={() => zoomOut()}
				>
					<Minus />
				</Button>
				<Button
					variant="outline"
					size="icon"
					tooltip={t('agents.graph.fit')}
					aria-label={t('agents.graph.fit')}
					onClick={() => fitView({ padding: 0.2 })}
				>
					<Maximize />
				</Button>
			</div>
			<ul className={cn(PILL, 'h-8 gap-4')}>
				{legend.map((item) => (
					<li
						key={item.label}
						className="flex items-center gap-1.5 text-muted-foreground"
					>
						<svg width="22" height="4" aria-hidden="true">
							<line
								x1="0"
								y1="2"
								x2="22"
								y2="2"
								stroke={item.colour}
								strokeWidth="2"
								strokeDasharray={item.dashed ? '4 4' : undefined}
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
				className="flex flex-col gap-4 rounded-[var(--r-card)] border border-white bg-[var(--raised)] p-4 shadow-[var(--clay)]"
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
								className="rounded-[var(--r-chip)] bg-[var(--sunken)] px-1 py-2"
							>
								<dd className="text-[16px]/[24px] font-semibold tabular-nums">
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
	const [fullscreen, setFullscreen] = useState(false);

	const model = useMemo(() => {
		const { agents: graphAgents, sample } = toGraphAgents(agents);
		return { ...buildGraph(graphAgents, t), sample, count: graphAgents.length };
	}, [agents, t]);

	const nodes = useMemo(
		() => model.nodes.map((node) => ({ ...node, selected: node.id === selectedId })),
		[model.nodes, selectedId],
	);
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
		<div ref={container} className="size-full bg-[var(--surface)]">
			<ReactFlow<FlowNode, FlowEdge>
				nodes={nodes}
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
			>
				<Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#d9d5ca" />

				<Panel position="top-left" className="flex flex-wrap items-center gap-2">
					{/* Said first and in the warning tone: the numbers on this
					    canvas are not measurements. */}
					<span
						className={cn(
							PILL,
							'border-[#f0d9a8] bg-[var(--amber-soft)] font-semibold text-[var(--amber-ink)]',
						)}
					>
						<span className="size-1.5 rounded-full bg-current" />
						{model.sample ? t('agents.graph.sampleAll') : t('agents.graph.sample')}
					</span>
					<span className={PILL}>
						{t('agents.graph.agentCount', { count: model.count })}
					</span>
					<span className={PILL}>
						{t('agents.graph.running', { count: model.totalRunning })}
					</span>
					<span className={PILL}>
						{t('agents.graph.response', { seconds: model.averageResponse.toFixed(1) })}
					</span>
				</Panel>

				{/* Moves aside when the inspector takes the top-right corner. */}
				<Panel position={selected ? 'bottom-right' : 'top-right'}>
					<Button variant="outline" size="sm" onClick={toggleFullscreen}>
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
