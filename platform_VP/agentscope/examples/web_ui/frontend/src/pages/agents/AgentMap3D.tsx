import { Grid, Html, Line, OrbitControls } from '@react-three/drei';
import { Canvas, type ThreeEvent, useFrame, useThree } from '@react-three/fiber';
import { UserCog, Users } from 'lucide-react';
import { type ReactNode, type RefObject, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { CanvasTexture, type Group, type Mesh, Plane, QuadraticBezierCurve3, Vector3 } from 'three';

import AgentSprite3D from './AgentSprite3D';

/**
 * The Leader and the business agents as a 3D map: the Leader in the middle,
 * agents around it, who sends work in on the left. Every agent stands as its
 * character on a white pad over a flat, painted floor (no lights: the
 * artwork is already shaded). Edges come from real ticket rooms (Leader
 * brought an agent in, two agents shared a room) and carry moving dots while
 * there is traffic. Nodes can be dragged on the floor; positions are kept
 * per browser.
 *
 * One palette, the same as the legend: indigo for the Leader's work, purple
 * for agents working a ticket together, emerald for "replying now", amber for
 * the selection. Nothing else is coloured, so those four always mean
 * something.
 */

export type MapAgent = {
	id: string;
	name: string;
	role: 'leader' | 'business';
	state: 'published' | 'draft' | 'withdrawn';
	tickets: number;
	/** Replied within the last minutes. */
	live: boolean;
	costUsd: number | null;
};

export type MapLink = { source: string; target: string; kind: 'leader' | 'peer'; tickets: number; lastAt: string };

type Overlay = RefObject<HTMLElement>;
type XZ = [number, number];

const INDIGO = '#6366f1';
const PURPLE = '#a855f7';
const EMERALD = '#10b981';
const AMBER = '#f59e0b';
const DAY_MS = 24 * 60 * 60 * 1000;
const FLOOR = new Plane(new Vector3(0, 1, 0), 0);
/** Top of a pad; characters stand and edges start here. */
const PAD_TOP = 0.18;

type Theme = { grid: string; section: string; pad: string; rim: string; shadow: string; glow: string; quiet: string };

const THEMES: Record<'light' | 'dark', Theme> = {
	light: { grid: '#dde1e8', section: '#c5cbd6', pad: '#ffffff', rim: '#d9dde6', shadow: '#1e293b', glow: '#ffffff', quiet: '#94a3b8' },
	dark: { grid: '#272a33', section: '#343946', pad: '#2a2d37', rim: '#3d4250', shadow: '#000000', glow: '#30343f', quiet: '#64748b' },
};

const usd = (value: number | null) => (value === null ? '–' : value < 1 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`);

function prefersReducedMotion() {
	return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/** Cue shells are light only; elsewhere `.dark` on the root follows the OS. */
function themeOf() {
	const dark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark') && !document.body.classList.contains('cue-theme');
	return THEMES[dark ? 'dark' : 'light'];
}

function readLayout(key: string): Record<string, XZ> {
	try {
		return JSON.parse(window.localStorage.getItem(key) ?? '{}') as Record<string, XZ>;
	} catch {
		return {};
	}
}

function writeLayout(key: string, layout: Record<string, XZ>) {
	try {
		window.localStorage.setItem(key, JSON.stringify(layout));
	} catch {
		// A private window keeps the layout for this visit only.
	}
}

/** The Leader at the centre, business agents on a ring, entry points to the left. */
function defaultLayout(agents: MapAgent[]): Record<string, XZ> {
	const business = agents.filter((agent) => agent.role === 'business');
	const radius = Math.min(10, Math.max(4.5, 3.2 + business.length * 0.5));
	const layout: Record<string, XZ> = { resident: [-radius * 1.15 - 4.2, -1.7], manager: [-radius * 1.15 - 4.2, 1.7] };
	for (const agent of agents) if (agent.role === 'leader') layout[agent.id] = [0, 0];
	business.forEach((agent, index) => {
		const angle = (index / Math.max(1, business.length)) * Math.PI * 2 - Math.PI / 2;
		layout[agent.id] = [Math.cos(angle) * radius * 1.15, Math.sin(angle) * radius];
	});
	return layout;
}

function curveBetween(from: XZ, to: XZ, lift: number) {
	const start = new Vector3(from[0], PAD_TOP, from[1]);
	const end = new Vector3(to[0], PAD_TOP, to[1]);
	const middle = start.clone().add(end).multiplyScalar(0.5);
	middle.y += lift + start.distanceTo(end) * 0.08;
	return new QuadraticBezierCurve3(start, middle, end);
}

/** A soft round light on the floor, drawn once: white in the middle, nothing at the edge. */
function useGlowTexture(color: string) {
	const texture = useMemo(() => {
		const canvas = document.createElement('canvas');
		canvas.width = canvas.height = 256;
		const context = canvas.getContext('2d');
		if (context) {
			const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128);
			// Fade the colour's own alpha, never towards black: a dark halo otherwise.
			gradient.addColorStop(0, `${color}e6`);
			gradient.addColorStop(0.5, `${color}e6`);
			gradient.addColorStop(1, `${color}00`);
			context.fillStyle = gradient;
			context.fillRect(0, 0, 256, 256);
		}
		return new CanvasTexture(canvas);
	}, [color]);
	useEffect(() => () => texture.dispose(), [texture]);
	return texture;
}

/** Dots that travel along an edge: more and faster with more recent traffic. */
function FlowDots({ curve, color, count, speed }: { curve: QuadraticBezierCurve3; color: string; count: number; speed: number }) {
	const dots = useRef<(Mesh | null)[]>([]);
	useFrame(({ clock }) => {
		dots.current.forEach((dot, index) => {
			if (!dot) return;
			const t = (clock.elapsedTime * speed + index / count) % 1;
			dot.position.copy(curve.getPoint(t));
			dot.scale.setScalar(0.6 + Math.sin(t * Math.PI) * 0.6);
		});
	});
	return (
		<>
			{Array.from({ length: count }, (_, index) => (
				<mesh key={index} ref={(mesh) => { dots.current[index] = mesh; }}>
					<sphereGeometry args={[0.075, 12, 12]} />
					<meshBasicMaterial color={color} toneMapped={false} />
				</mesh>
			))}
		</>
	);
}

function Edge({ from, to, link, active, motion, dim, now, quiet }: {
	from: XZ; to: XZ; link: MapLink | null; active: boolean; motion: boolean; dim: boolean; now: number; quiet: string;
}) {
	const peer = link?.kind === 'peer';
	const curve = useMemo(() => curveBetween(from, to, peer ? 0.9 : 0.2), [from, to, peer]);
	const points = useMemo(() => curve.getPoints(40), [curve]);
	const recent = link ? now - new Date(link.lastAt).getTime() < DAY_MS : false;
	const color = peer ? PURPLE : link?.tickets ? INDIGO : quiet;
	return (
		<group>
			<Line
				points={points}
				color={color}
				lineWidth={link?.tickets ? Math.min(4, 1.2 + link.tickets * 0.35) : 1.2}
				transparent
				opacity={dim ? 0.1 : link?.tickets ? 0.85 : 0.5}
				dashed={!link?.tickets}
				dashSize={0.28}
				gapSize={0.2}
			/>
			{motion && !dim && link && link.tickets > 0 && (
				<FlowDots curve={curve} color={color} count={Math.min(6, 2 + Math.ceil(link.tickets / 3))} speed={(recent || active ? 0.32 : 0.12)} />
			)}
		</group>
	);
}

function Label({ overlay, children, y }: { overlay: Overlay; children: ReactNode; y: number }) {
	return (
		<Html position={[0, y, 0]} center zIndexRange={[40, 10]} portal={overlay} style={{ pointerEvents: 'none', whiteSpace: 'nowrap' }}>
			{children}
		</Html>
	);
}

/** A thin flat ring on the floor; it breathes while `pulse` is on. */
function Ring({ inner, outer, color, opacity, pulse, y = PAD_TOP + 0.01 }: { inner: number; outer: number; color: string; opacity: number; pulse: boolean; y?: number }) {
	const mesh = useRef<Mesh>(null);
	useFrame(({ clock }) => {
		if (!mesh.current) return;
		const scale = pulse ? 1 + Math.sin(clock.elapsedTime * 2.2) * 0.05 : 1;
		mesh.current.scale.setScalar(scale);
	});
	return (
		<mesh ref={mesh} position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]}>
			<ringGeometry args={[inner, outer, 64]} />
			<meshBasicMaterial color={color} transparent opacity={opacity} toneMapped={false} depthWrite={false} />
		</mesh>
	);
}

/** The white disc a character stands on, with its soft shadow and rim. */
function Pad({ radius, theme, rim, opacity }: { radius: number; theme: Theme; rim: string; opacity: number }) {
	return (
		<group>
			<mesh position={[0, 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
				<circleGeometry args={[radius + 0.12, 64]} />
				<meshBasicMaterial color={theme.shadow} transparent opacity={0.07 * opacity} depthWrite={false} />
			</mesh>
			<mesh position={[0, PAD_TOP / 2, 0]}>
				<cylinderGeometry args={[radius, radius + 0.04, PAD_TOP, 64]} />
				<meshBasicMaterial color={theme.pad} transparent opacity={opacity} />
			</mesh>
			<Ring inner={radius - 0.06} outer={radius} color={rim} opacity={opacity} pulse={false} />
		</group>
	);
}

/** One draggable node: a click selects it, a double click opens it, a drag moves it on the floor. */
function Node({
	agent, at, selected, dim, motion, overlay, theme, onSelect, onOpen, onMove, onDragging,
}: {
	agent: MapAgent; at: XZ; selected: boolean; dim: boolean; motion: boolean; overlay: Overlay; theme: Theme;
	onSelect: () => void; onOpen: () => void; onMove: (to: XZ) => void; onDragging: (on: boolean) => void;
}) {
	const group = useRef<Group>(null);
	const press = useRef<{ x: number; y: number; moved: boolean } | null>(null);
	const leader = agent.role === 'leader';
	const draft = agent.state !== 'published';
	const radius = leader ? 1.25 : 1;
	let opacity = 1;
	if (dim) opacity = 0.25;
	else if (draft) opacity = 0.55;
	useFrame(({ clock }) => {
		if (!group.current) return;
		group.current.position.y = motion && agent.live ? Math.abs(Math.sin(clock.elapsedTime * 2.4 + at[0])) * 0.08 : 0;
	});
	const down = (event: ThreeEvent<PointerEvent>) => {
		event.stopPropagation();
		(event.target as unknown as Element).setPointerCapture?.(event.pointerId);
		press.current = { x: event.clientX, y: event.clientY, moved: false };
		onDragging(true);
	};
	const move = (event: ThreeEvent<PointerEvent>) => {
		if (!press.current) return;
		if (Math.hypot(event.clientX - press.current.x, event.clientY - press.current.y) > 4) press.current.moved = true;
		if (!press.current.moved) return;
		const point = new Vector3();
		if (event.ray.intersectPlane(FLOOR, point)) onMove([point.x, point.z]);
	};
	const up = (event: ThreeEvent<PointerEvent>) => {
		(event.target as unknown as Element).releasePointerCapture?.(event.pointerId);
		const clicked = press.current && !press.current.moved;
		press.current = null;
		onDragging(false);
		if (clicked) onSelect();
	};
	return (
		<group position={[at[0], 0, at[1]]}>
			<Pad radius={radius} theme={theme} rim={leader ? INDIGO : theme.rim} opacity={opacity} />
			{selected && <Ring inner={radius + 0.1} outer={radius + 0.22} color={AMBER} opacity={0.95} pulse={false} y={0.02} />}
			{agent.live && !selected && <Ring inner={radius + 0.1} outer={radius + 0.2} color={EMERALD} opacity={0.9 * opacity} pulse={motion} y={0.02} />}
			<group ref={group}>
				<group
					onPointerDown={down}
					onPointerMove={move}
					onPointerUp={up}
					onDoubleClick={(event) => { event.stopPropagation(); onOpen(); }}
					onPointerOver={() => { document.body.style.cursor = 'grab'; }}
					onPointerOut={() => { document.body.style.cursor = ''; }}
				>
					{/* Where the feet touch the pad. */}
					<mesh position={[0, PAD_TOP + 0.005, 0]} rotation={[-Math.PI / 2, 0, 0]} scale={[1, 0.45, 1]}>
						<circleGeometry args={[radius * 0.55, 32]} />
						<meshBasicMaterial color={theme.shadow} transparent opacity={0.16 * opacity} depthWrite={false} />
					</mesh>
					<Suspense fallback={null}>
						<AgentSprite3D name={agent.name} leader={leader} working={agent.live} motion={motion} opacity={opacity} />
					</Suspense>
				</group>
				<Label overlay={overlay} y={leader ? 4.3 : 3.75}>
					<div className={`rounded-xl border bg-background/95 px-2.5 py-1 text-center whitespace-nowrap shadow-sm backdrop-blur transition-opacity ${dim ? 'opacity-30' : ''} ${selected ? 'border-amber-400' : 'border-border/70'}`}>
						<p className="max-w-48 truncate text-[12px]/4 font-semibold text-foreground">{agent.name}</p>
						<p className="mt-0.5 flex items-center justify-center gap-1 text-[10px]/4 text-muted-foreground tabular-nums">
							<span className={`inline-block size-1.5 rounded-full ${agent.live ? 'bg-emerald-500' : draft ? 'bg-slate-400' : 'bg-indigo-400'}`} />
							{leader ? 'Leader' : agent.state === 'published' ? 'Phát hành' : agent.state === 'draft' ? 'Bản nháp' : 'Đã ngừng'}
							<span>· {agent.tickets} phiếu</span>
							<span>· {usd(agent.costUsd)}</span>
						</p>
					</div>
				</Label>
			</group>
		</group>
	);
}

/** Where work comes in from: a small pad with a named pill, no character. */
function Entry({ at, title, icon, overlay, theme, dim }: { at: XZ; title: string; icon: ReactNode; overlay: Overlay; theme: Theme; dim: boolean }) {
	return (
		<group position={[at[0], 0, at[1]]}>
			<Pad radius={0.6} theme={theme} rim={theme.rim} opacity={dim ? 0.3 : 1} />
			<Label overlay={overlay} y={0.95}>
				<span className={`inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-background/95 px-2.5 py-1 text-[11px] font-medium whitespace-nowrap text-muted-foreground shadow-sm transition-opacity ${dim ? 'opacity-30' : ''}`}>
					{icon}
					{title}
				</span>
			</Label>
		</group>
	);
}

type Frame = { center: XZ; radius: number };

/** The middle of everything on the floor and how far the furthest thing is from it. */
function frameOf(layout: Record<string, XZ>): Frame {
	const points = Object.values(layout);
	if (points.length === 0) return { center: [0, 0], radius: 4 };
	const xs = points.map(([x]) => x);
	const zs = points.map(([, z]) => z);
	const center: XZ = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...zs) + Math.max(...zs)) / 2];
	return { center, radius: Math.max(4, ...points.map(([x, z]) => Math.hypot(x - center[0], z - center[1]))) };
}

/**
 * Frames the whole layout when `home` changes (a reset, agents added or
 * removed), and leaves the camera alone otherwise: a drag must not move it.
 * The frame is read from a ref for that reason.
 */
function CameraHome({ frame, home }: { frame: Frame; home: string }) {
	const camera = useThree((state) => state.camera);
	const controls = useThree((state) => state.controls) as { target: Vector3; update: () => void } | null;
	const latest = useRef(frame);
	useEffect(() => {
		latest.current = frame;
	});
	useEffect(() => {
		const { center, radius } = latest.current;
		camera.position.set(center[0] + radius * 0.2, radius * 1.5 + 4, center[1] + radius * 1.2 + 4);
		if (controls) {
			controls.target.set(center[0], 0, center[1]);
			controls.update();
		} else {
			camera.lookAt(center[0], 0, center[1]);
		}
	}, [camera, controls, home]);
	return null;
}

function Floor({ radius, theme }: { radius: number; theme: Theme }) {
	const glow = useGlowTexture(theme.glow);
	const span = (radius + 5) * 2;
	return (
		<>
			<Grid
				position={[0, -0.01, 0]}
				args={[200, 200]}
				cellSize={1}
				cellThickness={0.6}
				cellColor={theme.grid}
				sectionSize={5}
				sectionThickness={0.9}
				sectionColor={theme.section}
				fadeDistance={radius * 2.6 + 12}
				fadeStrength={1.6}
			/>
			<mesh position={[0, -0.005, 0]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={-1}>
				<planeGeometry args={[span, span]} />
				<meshBasicMaterial map={glow} transparent depthWrite={false} toneMapped={false} />
			</mesh>
		</>
	);
}

export default function AgentMap3D({
	agents,
	links,
	selectedId,
	onSelect,
	onOpen,
	layoutKey,
	resetSignal,
	onUnavailable,
}: {
	agents: MapAgent[];
	links: MapLink[];
	selectedId: string | null;
	onSelect: (id: string | null) => void;
	onOpen: (id: string) => void;
	layoutKey: string;
	resetSignal: number;
	onUnavailable: () => void;
}) {
	const overlayRef = useRef<HTMLDivElement>(null);
	const overlay = overlayRef as Overlay;
	const motion = !prefersReducedMotion();
	const [theme] = useState(themeOf);
	// Only dragged positions are stored; everything else takes its ring place,
	// so a new agent is on the map in the same render it arrives.
	const [stored, setStored] = useState<Record<string, XZ>>(() => readLayout(layoutKey));
	const [resetSeen, setResetSeen] = useState(resetSignal);
	if (resetSignal !== resetSeen) {
		setResetSeen(resetSignal);
		setStored({});
	}
	useEffect(() => {
		if (resetSignal) writeLayout(layoutKey, {});
	}, [resetSignal, layoutKey]);
	const layout = useMemo(() => ({ ...defaultLayout(agents), ...stored }), [agents, stored]);
	const [dragging, setDragging] = useState(false);
	const [now, setNow] = useState(() => Date.now());
	useEffect(() => {
		const timer = window.setInterval(() => setNow(Date.now()), 60_000);
		return () => window.clearInterval(timer);
	}, []);

	const ids = agents.map((agent) => agent.id).join(',');

	const leader = agents.find((agent) => agent.role === 'leader');
	const byId = new Map(agents.map((agent) => [agent.id, agent]));
	const linkOf = new Map(links.map((link) => [`${link.source}>${link.target}`, link]));
	const neighbours = new Set<string>();
	if (selectedId) {
		neighbours.add(selectedId);
		for (const link of links) {
			if (link.source === selectedId) neighbours.add(link.target);
			if (link.target === selectedId) neighbours.add(link.source);
		}
		if (leader && selectedId !== leader.id) neighbours.add(leader.id);
	}
	const dim = (id: string) => selectedId !== null && !neighbours.has(id);
	const frame = frameOf(layout);

	const leaderEdges = leader
		? agents.filter((agent) => agent.role === 'business' && (agent.state === 'published' || linkOf.has(`${leader.id}>${agent.id}`)))
		: [];
	const peerLinks = links.filter((link) => link.kind === 'peer' && byId.has(link.source) && byId.has(link.target));

	const move = (id: string, to: XZ) => setStored((current) => ({ ...current, [id]: to }));
	const drag = (on: boolean) => {
		setDragging(on);
		if (!on) setStored((current) => { writeLayout(layoutKey, current); return current; });
	};
	const entriesDim = selectedId !== null && selectedId !== leader?.id;

	return (
		<div className="relative size-full overflow-hidden bg-[#f3f4f7] [isolation:isolate] dark:bg-[#15161b]">
			<Canvas
				dpr={[1, 1.5]}
				frameloop={motion ? 'always' : 'demand'}
				camera={{ fov: 40, near: 0.1, far: 200 }}
				gl={{ alpha: true, antialias: true }}
				onCreated={({ gl }) => gl.domElement.addEventListener('webglcontextlost', onUnavailable)}
				onPointerMissed={() => onSelect(null)}
			>
				<CameraHome frame={frame} home={`${resetSignal}:${ids}`} />
				<Floor radius={frame.radius} theme={theme} />

				<Entry at={layout.resident} title="Khách hàng" icon={<Users className="size-3" />} overlay={overlay} theme={theme} dim={entriesDim} />
				<Entry at={layout.manager} title="Người quản lý" icon={<UserCog className="size-3" />} overlay={overlay} theme={theme} dim={entriesDim} />
				{leader && (
					<>
						<Edge from={layout.resident} to={layout[leader.id]} link={null} active={leader.live} motion={motion} dim={entriesDim} now={now} quiet={theme.quiet} />
						<Edge from={layout.manager} to={layout[leader.id]} link={null} active={false} motion={motion} dim={entriesDim} now={now} quiet={theme.quiet} />
					</>
				)}
				{leader && leaderEdges.map((agent) => (
					<Edge
						key={`leader-${agent.id}`}
						from={layout[leader.id]}
						to={layout[agent.id]}
						link={linkOf.get(`${leader.id}>${agent.id}`) ?? null}
						active={agent.live}
						motion={motion}
						dim={dim(agent.id)}
						now={now}
						quiet={theme.quiet}
					/>
				))}
				{peerLinks.map((link) => (
					<Edge
						key={`peer-${link.source}-${link.target}`}
						from={layout[link.source]}
						to={layout[link.target]}
						link={link}
						active={!!byId.get(link.source)?.live || !!byId.get(link.target)?.live}
						motion={motion}
						dim={dim(link.source) || dim(link.target)}
						now={now}
						quiet={theme.quiet}
					/>
				))}
				{agents.map((agent) => layout[agent.id] && (
					<Node
						key={agent.id}
						agent={agent}
						at={layout[agent.id]}
						selected={agent.id === selectedId}
						dim={dim(agent.id)}
						motion={motion}
						overlay={overlay}
						theme={theme}
						onSelect={() => onSelect(agent.id === selectedId ? null : agent.id)}
						onOpen={() => onOpen(agent.id)}
						onMove={(to) => move(agent.id, to)}
						onDragging={drag}
					/>
				))}
				<OrbitControls makeDefault enabled={!dragging} enableDamping minDistance={6} maxDistance={55} maxPolarAngle={1.15} minPolarAngle={0.3} />
			</Canvas>
			{/* Zero-sized so the canvas keeps its pointer events; the labels overflow it. */}
			<div ref={overlayRef} className="absolute top-0 left-0" />
		</div>
	);
}
