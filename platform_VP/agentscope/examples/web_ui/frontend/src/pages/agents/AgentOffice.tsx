import { FileText, Mail, MessageCircle, Pause, Pencil, Play, RotateCcw, User, Users, X } from 'lucide-react';
import { memo, type ReactNode, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import { type GraphAgent, toGraphAgents } from './graph-model';
import {
	type Actor,
	buildLayout,
	FLOOR_W,
	LEADER_ID,
	type Layout,
	OfficeSim,
	type Point,
	type Projection,
	populate,
	projection,
	runDemo,
	WALL_H,
} from './office-sim';
import type { AgentView } from '@/api';
import { Button } from '@/components/ui/button';
import { ClayAvatar, clayTone } from '@/components/ui/clay-avatar';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';
import './agent-graph.css';
import './agent-office.css';

/* ------------------------------------------------------------------ */
/* Drawing helpers                                                     */
/* ------------------------------------------------------------------ */

type Faces = { top: string; left: string; right: string };

/** The three visible faces of a floor-standing box, as SVG point lists. */
function box(P: Projection, x: number, y: number, w: number, d: number, h: number, lift = 0): Faces {
	const pt = (px: number, py: number, z: number) => {
		const { sx, sy } = P.at({ x: px, y: py }, z);
		return `${sx},${sy}`;
	};
	const top = lift + h;
	return {
		top: [pt(x, y, top), pt(x + w, y, top), pt(x + w, y + d, top), pt(x, y + d, top)].join(' '),
		left: [pt(x, y + d, lift), pt(x + w, y + d, lift), pt(x + w, y + d, top), pt(x, y + d, top)].join(' '),
		right: [pt(x + w, y, lift), pt(x + w, y + d, lift), pt(x + w, y + d, top), pt(x + w, y, top)].join(' '),
	};
}

function poly(P: Projection, points: [number, number, number?][]) {
	return points
		.map(([x, y, z]) => {
			const { sx, sy } = P.at({ x, y }, z ?? 0);
			return `${sx},${sy}`;
		})
		.join(' ');
}

type Palette = { top: string; left: string; right: string; stroke?: string };

const WOOD: Palette = { top: '#ecd8bb', left: '#d6b892', right: '#c4a079' };
const WHITE: Palette = { top: '#ffffff', left: '#e9e9ee', right: '#dcdce4' };
const SLATE: Palette = { top: '#4a4f5c', left: '#353945', right: '#2a2d36' };
const MINT: Palette = { top: '#f7fffc', left: '#bfe8dc', right: '#a6d9cb' };
const CHAIR: Palette = { top: '#9aa3b5', left: '#7d8699', right: '#6c7487' };
const GLASS: Palette = {
	top: 'rgba(140,170,230,0.55)',
	left: 'rgba(170,200,255,0.16)',
	right: 'rgba(150,185,250,0.22)',
	stroke: 'rgba(110,140,205,0.45)',
};

function Box({ faces, palette }: { faces: Faces; palette: Palette }) {
	const stroke = palette.stroke ?? 'rgba(0,0,0,0.06)';
	return (
		<>
			<polygon points={faces.left} fill={palette.left} stroke={stroke} strokeWidth={0.8} />
			<polygon points={faces.right} fill={palette.right} stroke={stroke} strokeWidth={0.8} />
			<polygon points={faces.top} fill={palette.top} stroke={stroke} strokeWidth={0.8} />
		</>
	);
}

/* ------------------------------------------------------------------ */
/* Furniture                                                           */
/* ------------------------------------------------------------------ */

/** One depth-sorted piece of the office. `desk` marks an agent's desk, whose screen lights up. */
type Piece = { key: string; depth: number; desk?: string; draw: (working: boolean) => ReactNode };

function deskPiece(P: Projection, key: string, at: Point, palette: Palette, desk?: string): Piece {
	const H = 24;
	const top = box(P, at.x - 0.8, at.y - 0.42, 1.6, 0.84, H);
	const legs = box(P, at.x - 0.74, at.y - 0.36, 1.48, 0.72, H - 4);
	const screen = poly(P, [
		[at.x - 0.42, at.y - 0.22, H + 3],
		[at.x + 0.42, at.y - 0.22, H + 3],
		[at.x + 0.42, at.y - 0.22, H + 30],
		[at.x - 0.42, at.y - 0.22, H + 30],
	]);
	const stand = box(P, at.x - 0.06, at.y - 0.3, 0.12, 0.1, 4, H);
	const keyboard = poly(P, [
		[at.x - 0.3, at.y + 0.08, H + 0.5],
		[at.x + 0.3, at.y + 0.08, H + 0.5],
		[at.x + 0.3, at.y + 0.26, H + 0.5],
		[at.x - 0.3, at.y + 0.26, H + 0.5],
	]);
	return {
		key,
		desk,
		depth: at.x + at.y,
		draw: (working) => (
			<>
				<Box faces={legs} palette={{ ...palette, top: palette.top }} />
				<Box faces={top} palette={palette} />
				<Box faces={stand} palette={SLATE} />
				<polygon points={keyboard} fill="#cfd3dc" />
				<polygon
					points={screen}
					fill={working ? '#5b8def' : '#30343f'}
					stroke="#1d2029"
					strokeWidth={1.4}
					className={working ? 'of-screen-on' : undefined}
				/>
				{working &&
					[0.35, 0.55, 0.75].map((f) => {
						const a = P.at({ x: at.x - 0.3, y: at.y - 0.22 }, H + 3 + 27 * f);
						const b = P.at({ x: at.x + 0.3 - f * 0.25, y: at.y - 0.22 }, H + 3 + 27 * f);
						return (
							<line
								key={f}
								x1={a.sx}
								y1={a.sy}
								x2={b.sx}
								y2={b.sy}
								stroke="#dce7ff"
								strokeWidth={1.5}
								strokeLinecap="round"
							/>
						);
					})}
			</>
		),
	};
}

function chairPiece(P: Projection, key: string, at: Point): Piece {
	const seat = box(P, at.x - 0.24, at.y - 0.24, 0.48, 0.48, 6, 8);
	const back = box(P, at.x - 0.24, at.y + 0.16, 0.48, 0.08, 20, 12);
	return {
		key,
		depth: at.x + at.y - 0.05,
		draw: () => (
			<>
				<Box faces={seat} palette={CHAIR} />
				<Box faces={back} palette={CHAIR} />
			</>
		),
	};
}

function plantPiece(P: Projection, key: string, at: Point): Piece {
	const pot = box(P, at.x - 0.22, at.y - 0.22, 0.44, 0.44, 18);
	const leaf = P.at(at, 34);
	return {
		key,
		depth: at.x + at.y,
		draw: () => (
			<>
				<Box faces={pot} palette={{ top: '#8c6b52', left: '#d98f6a', right: '#c47a57' }} />
				<ellipse cx={leaf.sx} cy={leaf.sy} rx={17} ry={15} fill="#6fbf8a" />
				<ellipse cx={leaf.sx - 6} cy={leaf.sy - 8} rx={10} ry={9} fill="#8fd6a4" />
				<ellipse cx={leaf.sx + 7} cy={leaf.sy - 3} rx={8} ry={7} fill="#5aab76" />
			</>
		),
	};
}

/** A glass partition, one tile at a time so each piece sorts against people on its own. */
function glassRun(P: Projection, key: string, axis: 'x' | 'y', fixed: number, from: number, to: number): Piece[] {
	const pieces: Piece[] = [];
	for (let start = from; start < to - 0.001; start += 1) {
		const end = Math.min(to, start + 1);
		const faces =
			axis === 'x'
				? box(P, fixed - 0.04, start, 0.08, end - start, 54)
				: box(P, start, fixed - 0.04, end - start, 0.08, 54);
		const centre = (start + end) / 2;
		pieces.push({
			key: `${key}-${start}`,
			depth: axis === 'x' ? fixed + centre : centre + fixed,
			draw: () => <Box faces={faces} palette={GLASS} />,
		});
	}
	return pieces;
}

function buildPieces(P: Projection, layout: Layout): Piece[] {
	const { rooms } = layout;
	const pieces: Piece[] = [];

	// Meeting room.
	pieces.push(...glassRun(P, 'mw-x-a', 'x', rooms.meeting.x1, 0, 2));
	pieces.push(...glassRun(P, 'mw-x-b', 'x', rooms.meeting.x1, 3, rooms.meeting.y1));
	pieces.push(...glassRun(P, 'mw-y', 'y', rooms.meeting.y1, 0, rooms.meeting.x1));
	const table = box(P, 1.4, 1.85, 3.4, 1.3, 20);
	pieces.push({ key: 'table', depth: 3.1 + 2.5, draw: () => <Box faces={table} palette={WHITE} /> });
	layout.seats.forEach((seat, index) => pieces.push(chairPiece(P, `seat-${index}`, seat.at)));
	pieces.push(chairPiece(P, 'seat-head', layout.head.at));
	pieces.push(plantPiece(P, 'plant-meeting', { x: 5.45, y: 0.55 }));

	// Your office.
	pieces.push(...glassRun(P, 'aw-x-a', 'x', rooms.approval.x0, 0, 2.5));
	pieces.push(...glassRun(P, 'aw-x-b', 'x', rooms.approval.x0, 3.5, rooms.approval.y1));
	pieces.push(...glassRun(P, 'aw-y', 'y', rooms.approval.y1, rooms.approval.x0, rooms.approval.x1));
	pieces.push(deskPiece(P, 'desk-you', layout.approval.desk, WOOD));
	pieces.push(chairPiece(P, 'chair-you', layout.approval.user));
	pieces.push(plantPiece(P, 'plant-you', { x: 15.5, y: 0.5 }));

	// The Leader's desk, by the meeting room.
	pieces.push(deskPiece(P, 'desk-leader', layout.leader.desk, SLATE));
	pieces.push(chairPiece(P, 'chair-leader', layout.leader.chair));

	// Reception.
	const { counter } = layout.reception;
	const counterBox = box(P, counter.x - 1, counter.y - 0.4, 2, 0.8, 30);
	pieces.push({ key: 'counter', depth: counter.x + counter.y, draw: () => <Box faces={counterBox} palette={MINT} /> });
	pieces.push(plantPiece(P, 'plant-reception', { x: 5, y: layout.depth - 0.6 }));

	// Open desks.
	layout.desks.forEach((desk) => {
		pieces.push(deskPiece(P, `desk-${desk.agentId}`, desk.desk, WOOD, desk.agentId));
		pieces.push(chairPiece(P, `chair-${desk.agentId}`, desk.chair));
	});
	pieces.push(plantPiece(P, 'plant-a', { x: 10.2, y: 0.6 }));
	pieces.push(plantPiece(P, 'plant-b', { x: FLOOR_W - 0.5, y: 5.3 }));

	return pieces.sort((a, b) => a.depth - b.depth);
}

/** The floor, the two back walls, and what hangs on them. */
const Floor = memo(function Floor({ P, layout }: { P: Projection; layout: Layout }) {
	const D = layout.depth;
	const rect = (r: { x0: number; y0: number; x1: number; y1: number }) =>
		poly(P, [
			[r.x0, r.y0],
			[r.x1, r.y0],
			[r.x1, r.y1],
			[r.x0, r.y1],
		]);
	const lines: ReactNode[] = [];
	for (let i = 1; i < FLOOR_W; i += 1) {
		const a = P.at({ x: i, y: 0 });
		const b = P.at({ x: i, y: D });
		lines.push(<line key={`gx${i}`} x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy} />);
	}
	for (let j = 1; j < D; j += 1) {
		const a = P.at({ x: 0, y: j });
		const b = P.at({ x: FLOOR_W, y: j });
		lines.push(<line key={`gy${j}`} x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy} />);
	}
	const { door } = layout.reception;
	return (
		<svg className="absolute inset-0" width={P.width} height={P.height} aria-hidden="true">
			{/* Back walls. */}
			<polygon points={poly(P, [[0, 0], [0, D], [0, D, WALL_H], [0, 0, WALL_H]])} fill="#ebe5da" />
			<polygon
				points={poly(P, [[0, 0], [FLOOR_W, 0], [FLOOR_W, 0, WALL_H], [0, 0, WALL_H]])}
				fill="#f5f0e8"
			/>
			<polyline
				points={poly(P, [[0, D, WALL_H], [0, 0, WALL_H], [FLOOR_W, 0, WALL_H]])}
				fill="none"
				stroke="#d8cfc0"
				strokeWidth={5}
				strokeLinejoin="round"
			/>
			{/* Whiteboard in the meeting room, with the plan on it. */}
			<polygon points={poly(P, [[1.4, 0, 30], [4.6, 0, 30], [4.6, 0, 78], [1.4, 0, 78]])} fill="#fff" stroke="#c9ccd6" strokeWidth={2} />
			{[
				[1.7, 2.3, 66, '#ffd166'],
				[2.5, 3.1, 66, '#9ce3d5'],
				[3.3, 3.9, 66, '#aec4ff'],
				[1.7, 2.3, 48, '#ffc0a7'],
				[2.5, 3.1, 48, '#ffd166'],
			].map(([x0, x1, z, fill]) => (
				<polygon
					key={`${x0}-${z}`}
					points={poly(P, [
						[x0 as number, 0, z as number],
						[x1 as number, 0, z as number],
						[x1 as number, 0, (z as number) - 12],
						[x0 as number, 0, (z as number) - 12],
					])}
					fill={fill as string}
				/>
			))}
			{/* Windows over the open floor. */}
			{[
				[6.8, 9.8],
				[11.8, 15.2],
			].map(([x0, x1]) => (
				<g key={x0}>
					<polygon points={poly(P, [[x0, 0, 30], [x1, 0, 30], [x1, 0, 82], [x0, 0, 82]])} fill="#d9ecff" stroke="#c4d3e6" strokeWidth={3} />
					<line {...seg(P, { x: (x0 + x1) / 2, y: 0 }, 30, 82)} stroke="#c4d3e6" strokeWidth={3} />
				</g>
			))}
			{/* The way in, by reception. */}
			<polygon
				points={poly(P, [[0, door.y - 0.6, 0], [0, door.y + 0.6, 0], [0, door.y + 0.6, 66], [0, door.y - 0.6, 66]])}
				fill="#c9a27c"
				stroke="#b08a66"
				strokeWidth={2}
			/>

			{/* Floor and rooms. */}
			<polygon points={poly(P, [[0, 0], [FLOOR_W, 0], [FLOOR_W, D], [0, D]])} fill="#faf7f2" />
			<polygon points={rect(layout.rooms.meeting)} fill="#eef2ff" />
			<polygon points={rect(layout.rooms.approval)} fill="#fff4dc" />
			<polygon points={rect(layout.rooms.reception)} fill="#e9f7f1" />
			<g stroke="rgba(120,100,70,0.08)" strokeWidth={1}>
				{lines}
			</g>
			{/* Floor edge, so the slab reads as a slab. */}
			<polygon
				points={poly(P, [[FLOOR_W, 0], [FLOOR_W, D], [FLOOR_W, D, -14], [FLOOR_W, 0, -14]])}
				fill="#e3dbcd"
			/>
			<polygon points={poly(P, [[0, D], [FLOOR_W, D], [FLOOR_W, D, -14], [0, D, -14]])} fill="#ece5d8" />
		</svg>
	);
});

function seg(P: Projection, at: Point, z0: number, z1: number) {
	const a = P.at(at, z0);
	const b = P.at(at, z1);
	return { x1: a.sx, y1: a.sy, x2: b.sx, y2: b.sy };
}

const PieceLayer = memo(function PieceLayer({
	P,
	piece,
	working,
}: {
	P: Projection;
	piece: Piece;
	working: boolean;
}) {
	return (
		<svg
			className="pointer-events-none absolute inset-0"
			width={P.width}
			height={P.height}
			style={{ zIndex: Math.round(piece.depth * 100) }}
			aria-hidden="true"
		>
			{piece.draw(working)}
		</svg>
	);
});

/* ------------------------------------------------------------------ */
/* People                                                              */
/* ------------------------------------------------------------------ */

const BODY: Record<Exclude<Actor['kind'], 'agent' | 'mail'>, string> = {
	leader: '#24262d',
	user: '#e5484d',
	resident: '#9aa0a6',
};

function Person({
	actor,
	P,
	selected,
	onSelect,
	offLabel,
}: {
	actor: Actor;
	P: Projection;
	selected: boolean;
	onSelect: () => void;
	offLabel: string;
}) {
	const { sx, sy } = P.at(actor.pos);
	const walking = actor.path.length > 0;
	const depth = actor.kind === 'mail' ? 999_999 : Math.round((actor.pos.x + actor.pos.y) * 100) + 1;

	if (actor.kind === 'mail') {
		return (
			<div className="of-mail absolute" style={{ left: sx, top: sy - 46, zIndex: depth }} aria-hidden="true">
				<Mail className="size-4" />
			</div>
		);
	}

	const body = actor.kind === 'agent' ? clayTone(actor.id).background : BODY[actor.kind];
	const clickable = actor.kind === 'agent' || actor.kind === 'leader';
	const Tag = clickable ? 'button' : 'div';

	return (
		<Tag
			type={clickable ? 'button' : undefined}
			onClick={clickable ? onSelect : undefined}
			aria-label={clickable ? actor.name : undefined}
			className={cn(
				'of-person absolute flex flex-col items-center',
				clickable && 'cursor-pointer',
				actor.status === 'off' && 'of-off',
			)}
			style={{ left: sx, top: sy, zIndex: depth }}
		>
			<span className="of-shadow" />
			<span className={cn('of-figure flex flex-col items-center', walking && 'of-walking')}>
				<span
					className={cn('of-head', selected && 'of-selected')}
					style={{ transform: `scaleX(${actor.facing})` }}
				>
					{actor.kind === 'agent' || actor.kind === 'leader' ? (
						<ClayAvatar
							id={actor.kind === 'leader' ? 'leader' : actor.id}
							label={actor.name}
							size={40}
							working={actor.status === 'working'}
							className="rounded-full!"
						/>
					) : (
						<span
							className="flex size-10 items-center justify-center rounded-full border-2 border-white text-white"
							style={{ background: BODY[actor.kind] }}
						>
							{actor.kind === 'user' ? <User className="size-5" /> : <Users className="size-5" />}
						</span>
					)}
				</span>
				<span className="of-body" style={{ background: body }}>
					{actor.carrying && (
						<span className="of-carry">
							<FileText className="size-3" />
						</span>
					)}
				</span>
			</span>
			{actor.status === 'working' && (
				<span className="of-badge text-[#2f6fe0]">
					<span className="ag-eq">
						<i />
						<i />
						<i />
					</span>
				</span>
			)}
			{actor.status === 'off' && <span className="of-zz">Zz</span>}
			<span className={cn('of-name', actor.kind === 'leader' && 'of-name-leader')} title={actor.status === 'off' ? offLabel : undefined}>
				{actor.name}
			</span>
		</Tag>
	);
}

function Bubble({ actor, P }: { actor: Actor; P: Projection }) {
	if (!actor.bubble) return null;
	const { sx, sy } = P.at(actor.pos);
	return (
		<div className="of-bubble" style={{ left: sx, top: sy - 84 }} key={actor.bubble.text}>
			{actor.bubble.text}
		</div>
	);
}

/* ------------------------------------------------------------------ */
/* The view                                                            */
/* ------------------------------------------------------------------ */

const FLOAT =
	'rounded-full border border-[var(--cue-border,#e8e8e8)] bg-white/90 shadow-[0_2px_8px_rgba(0,0,0,0.06)] backdrop-blur';

function useOffice(agents: GraphAgent[], resetKey: number) {
	const layout = useMemo(() => buildLayout(agents), [agents]);
	const [sim, setSim] = useState<OfficeSim | null>(null);
	const [, setFrame] = useState(0);

	useEffect(() => {
		const next = new OfficeSim();
		populate(next, layout, agents);
		setSim(next);
		void runDemo(next, layout, agents);

		let last = performance.now();
		let raf = requestAnimationFrame(function loop(now) {
			// A hidden tab sends one huge step on return; cap it.
			next.tick(Math.min(now - last, 64));
			last = now;
			setFrame((frame) => (frame + 1) % 1_000_000);
			raf = requestAnimationFrame(loop);
		});
		return () => {
			cancelAnimationFrame(raf);
			next.abort();
		};
	}, [layout, agents, resetKey]);

	return { layout, sim };
}

/** Fit the fixed-size stage into the space the page gives it. */
function useFit(width: number, height: number) {
	const ref = useRef<HTMLDivElement>(null);
	const [box, setBox] = useState({ w: width, h: height });
	useLayoutEffect(() => {
		const element = ref.current;
		if (!element) return;
		const observer = new ResizeObserver(([entry]) =>
			setBox({ w: entry.contentRect.width, h: entry.contentRect.height }),
		);
		observer.observe(element);
		return () => observer.disconnect();
	}, []);
	const scale = Math.min(box.w / width, box.h / height, 1.3);
	return [ref, { scale, left: (box.w - width * scale) / 2, top: (box.h - height * scale) / 2 }] as const;
}

export function AgentOffice({
	agents: apiAgents,
	onChat,
	onEdit,
}: {
	agents: AgentView[];
	onChat: (agent: AgentView) => void;
	onEdit: (agent: AgentView) => void;
}) {
	const { t } = useTranslation();
	const { agents, sample } = useMemo(() => toGraphAgents(apiAgents), [apiAgents]);
	const [resetKey, setResetKey] = useState(0);
	const { layout, sim } = useOffice(agents, resetKey);
	const P = useMemo(() => projection(layout.depth), [layout.depth]);
	const pieces = useMemo(() => buildPieces(P, layout), [P, layout]);
	const [fitRef, fit] = useFit(P.width, P.height);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [, rerender] = useState(0);

	if (!sim) return null;
	const actors = [...sim.actors.values()];
	const selected = selectedId === LEADER_ID ? null : agents.find((agent) => agent.id === selectedId);
	const selectedActor = selectedId ? sim.actors.get(selectedId) : undefined;

	const toggle = () => {
		sim.togglePlaying();
		rerender((n) => n + 1);
	};
	const cycleSpeed = () => {
		sim.cycleSpeed();
		rerender((n) => n + 1);
	};

	const rooms = [
		{ key: 'meeting', at: { x: 3, y: 4.55 } },
		{ key: 'approval', at: { x: 13.6, y: 4.1 } },
		{ key: 'reception', at: { x: 2.8, y: layout.depth - 0.55 } },
		{ key: 'workspace', at: { x: 11, y: 5.45 } },
	];

	return (
		<div className="relative size-full overflow-hidden bg-[#f3f1ec]">
			<div ref={fitRef} className="absolute inset-0 top-14 bottom-4">
				<div
					className="absolute origin-top-left"
					style={{
						width: P.width,
						height: P.height,
						left: fit.left,
						top: fit.top,
						transform: `scale(${fit.scale})`,
					}}
				>
					<Floor P={P} layout={layout} />
					{rooms.map((room) => {
						const { sx, sy } = P.at(room.at);
						return (
							<span key={room.key} className="of-room" style={{ left: sx, top: sy }}>
								{t(`agents.office.rooms.${room.key}`)}
							</span>
						);
					})}
					{pieces.map((piece) => (
						<PieceLayer
							key={piece.key}
							P={P}
							piece={piece}
							working={!!piece.desk && sim.actors.get(piece.desk)?.status === 'working'}
						/>
					))}
					{actors.map((actor) => (
						<Person
							key={actor.id}
							actor={actor}
							P={P}
							selected={actor.id === selectedId}
							onSelect={() => setSelectedId(actor.id === selectedId ? null : actor.id)}
							offLabel={t('agents.graph.notInvitable')}
						/>
					))}
					<div className="absolute inset-0" style={{ zIndex: 1_000_000, pointerEvents: 'none' }}>
						{actors.map((actor) => (
							<Bubble key={actor.id} actor={actor} P={P} />
						))}
					</div>
				</div>
			</div>

			{/* Chrome. */}
			<div className="absolute top-3 right-4 left-4 flex flex-wrap items-center gap-2">
				<span className="flex h-8 items-center gap-2 rounded-full bg-[#fff4dc] px-3 text-[12px] font-medium text-[#8a5a00]">
					<span className="size-1.5 rounded-full bg-[#d99a00]" />
					{t(sample ? 'agents.office.sampleAll' : 'agents.office.sample')}
				</span>
				<span className={cn(FLOAT, 'flex h-8 items-center gap-2 px-3 text-[12px] font-medium')}>
					<span
						className={cn(
							'relative size-2 rounded-full',
							sim.phase === 'idle' ? 'bg-[#b5b5b5]' : 'ag-ping bg-[#34c759]',
						)}
					/>
					{t(`agents.office.phase.${sim.phase}`)}
				</span>
				<div className={cn(FLOAT, 'ml-auto flex items-center gap-0.5 p-0.5')}>
					<Button
						variant="ghost"
						size="icon-sm"
						className="rounded-full"
						tooltip={t(sim.playing ? 'agents.office.pause' : 'agents.office.play')}
						aria-label={t(sim.playing ? 'agents.office.pause' : 'agents.office.play')}
						onClick={toggle}
					>
						{sim.playing ? <Pause /> : <Play />}
					</Button>
					<Button
						variant="ghost"
						size="sm"
						className="h-7 rounded-full px-2 text-[12px] tabular-nums"
						tooltip={t('agents.office.speed')}
						onClick={cycleSpeed}
					>
						{sim.speed}×
					</Button>
					<Button
						variant="ghost"
						size="icon-sm"
						className="rounded-full"
						tooltip={t('agents.office.restart')}
						aria-label={t('agents.office.restart')}
						onClick={() => setResetKey((key) => key + 1)}
					>
						<RotateCcw />
					</Button>
				</div>
			</div>

			{/* What just happened, newest last. */}
			<section
				aria-label={t('agents.office.log')}
				className="absolute right-4 bottom-4 w-[280px] rounded-[18px] border border-[var(--cue-border,#e8e8e8)] bg-white/92 p-3 shadow-[0_2px_8px_rgba(0,0,0,0.06)] backdrop-blur"
			>
				<h2 className="mb-2 text-[12px] font-semibold text-muted-foreground">{t('agents.office.log')}</h2>
				<ol className="flex flex-col gap-1.5" aria-live="polite">
					{sim.log.map((entry, index) => (
						<li
							key={entry.id}
							className={cn(
								'of-log flex gap-2 text-[12px]/4',
								index === sim.log.length - 1 ? 'text-foreground' : 'text-muted-foreground',
							)}
						>
							<span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-current opacity-60" />
							{entry.text}
						</li>
					))}
				</ol>
			</section>

			{selectedActor && (selected || selectedId === LEADER_ID) && (
				<section className="ag-panel-in absolute bottom-4 left-4 flex w-[280px] flex-col gap-3 rounded-[20px] border border-[var(--cue-border,#e8e8e8)] bg-white p-4 shadow-[var(--cue-shadow-float,0_8px_32px_rgba(0,0,0,0.1))]">
					<header className="flex items-start gap-3">
						<ClayAvatar id={selectedId === LEADER_ID ? 'leader' : selectedId!} label={selectedActor.name} size={40} />
						<div className="min-w-0 flex-1">
							<h2 className="truncate text-[15px]/6 font-semibold">{selectedActor.name}</h2>
							<p className="text-[12px]/4 text-muted-foreground">
								{selectedId === LEADER_ID
									? t('agents.graph.leaderNote')
									: selected?.role || t('agents.list.noDescription')}
							</p>
						</div>
						<Button
							variant="ghost"
							size="icon-sm"
							aria-label={t('common.close')}
							onClick={() => setSelectedId(null)}
						>
							<X />
						</Button>
					</header>
					<p className="text-[12px] text-muted-foreground">
						{t(`agents.office.status.${selectedActor.path.length ? 'walking' : selectedActor.status}`)}
					</p>
					{selected?.real && (
						<div className="flex gap-2">
							<Button size="sm" className="flex-1" onClick={() => onChat(selected.real!)}>
								<MessageCircle />
								{t('agents.list.chat')}
							</Button>
							<Button size="sm" variant="outline" className="flex-1" onClick={() => onEdit(selected.real!)}>
								<Pencil />
								{t('agents.list.edit')}
							</Button>
						</div>
					)}
				</section>
			)}
		</div>
	);
}
