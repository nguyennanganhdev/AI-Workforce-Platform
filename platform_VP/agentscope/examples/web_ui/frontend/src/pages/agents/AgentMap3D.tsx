import { ContactShadows, Html, Line, OrbitControls, RoundedBox } from '@react-three/drei';
import { Canvas, type ThreeEvent, useFrame, useThree } from '@react-three/fiber';
import { type ReactNode, type RefObject, useEffect, useMemo, useRef, useState } from 'react';
import { type Group, type Mesh, Plane, QuadraticBezierCurve3, Vector3 } from 'three';

/**
 * The Leader and the business agents as a 3D map: the Leader in the middle,
 * agents around it, who sends work in on the left. Edges come from real
 * ticket rooms (Leader brought an agent in, two agents shared a room) and
 * carry moving dots while there is traffic. Nodes can be dragged on the
 * floor; positions are kept per browser.
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

const POD_COLORS = ['#14b8a6', '#8b5cf6', '#f59e0b', '#0ea5e9', '#f43f5e', '#22c55e', '#6366f1', '#ec4899'];
const LEADER_COLOR = '#4f46e5';
const ENTRY_COLOR = '#94a3b8';
const DAY_MS = 24 * 60 * 60 * 1000;
const FLOOR = new Plane(new Vector3(0, 1, 0), 0);

const usd = (value: number | null) => (value === null ? '–' : value < 1 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`);

function colorOf(id: string) {
	let hash = 0;
	for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0;
	return POD_COLORS[Math.abs(hash) % POD_COLORS.length];
}

function prefersReducedMotion() {
	return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
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
	const radius = Math.min(9, Math.max(4, 3 + business.length * 0.45));
	const layout: Record<string, XZ> = { resident: [-radius - 3.2, -1.4], manager: [-radius - 3.2, 1.4] };
	for (const agent of agents) if (agent.role === 'leader') layout[agent.id] = [0, 0];
	business.forEach((agent, index) => {
		const angle = (index / Math.max(1, business.length)) * Math.PI * 2 - Math.PI / 2;
		layout[agent.id] = [Math.cos(angle) * radius * 1.15, Math.sin(angle) * radius];
	});
	return layout;
}

function curveBetween(from: XZ, to: XZ, lift: number) {
	const start = new Vector3(from[0], 0.55, from[1]);
	const end = new Vector3(to[0], 0.55, to[1]);
	const middle = start.clone().add(end).multiplyScalar(0.5);
	middle.y += lift + start.distanceTo(end) * 0.12;
	return new QuadraticBezierCurve3(start, middle, end);
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

function Edge({ from, to, link, active, motion, dim, now }: {
	from: XZ; to: XZ; link: MapLink | null; active: boolean; motion: boolean; dim: boolean; now: number;
}) {
	const peer = link?.kind === 'peer';
	const curve = useMemo(() => curveBetween(from, to, peer ? 1.1 : 0.35), [from, to, peer]);
	const points = useMemo(() => curve.getPoints(40), [curve]);
	const recent = link ? now - new Date(link.lastAt).getTime() < DAY_MS : false;
	const color = peer ? '#a855f7' : link?.tickets ? '#6366f1' : '#94a3b8';
	return (
		<group>
			<Line
				points={points}
				color={color}
				lineWidth={link?.tickets ? Math.min(4, 1.2 + link.tickets * 0.35) : 1}
				transparent
				opacity={dim ? 0.12 : link?.tickets ? 0.85 : 0.35}
				dashed={!link?.tickets}
				dashSize={0.25}
				gapSize={0.18}
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

/** One draggable node: a click selects it, a double click opens it, a drag moves it on the floor. */
function Node({
	agent, at, selected, dim, motion, overlay, onSelect, onOpen, onMove, onDragging,
}: {
	agent: MapAgent; at: XZ; selected: boolean; dim: boolean; motion: boolean; overlay: Overlay;
	onSelect: () => void; onOpen: () => void; onMove: (to: XZ) => void; onDragging: (on: boolean) => void;
}) {
	const group = useRef<Group>(null);
	const press = useRef<{ x: number; y: number; moved: boolean } | null>(null);
	const leader = agent.role === 'leader';
	const color = leader ? LEADER_COLOR : colorOf(agent.id);
	const draft = agent.state !== 'published';
	useFrame(({ clock }) => {
		if (!group.current) return;
		group.current.position.y = motion && agent.live ? Math.sin(clock.elapsedTime * 2.4 + at[0]) * 0.08 : 0;
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
			<group ref={group}>
				<group
					onPointerDown={down}
					onPointerMove={move}
					onPointerUp={up}
					onDoubleClick={(event) => { event.stopPropagation(); onOpen(); }}
					onPointerOver={() => { document.body.style.cursor = 'grab'; }}
					onPointerOut={() => { document.body.style.cursor = ''; }}
				>
					{leader ? (
						<mesh position={[0, 0.45, 0]} castShadow>
							<cylinderGeometry args={[1.05, 1.15, 0.5, 6]} />
							<meshStandardMaterial color={color} metalness={0.25} roughness={0.35} transparent opacity={dim ? 0.3 : 1} />
						</mesh>
					) : (
						<RoundedBox args={[1.25, 0.5, 1.25]} radius={0.22} smoothness={4} position={[0, 0.3, 0]} castShadow>
							<meshStandardMaterial color={color} metalness={0.15} roughness={0.4} transparent opacity={dim ? 0.25 : draft ? 0.55 : 1} />
						</RoundedBox>
					)}
				</group>
				{(selected || agent.live) && (
					<mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
						<ringGeometry args={[leader ? 1.35 : 0.95, leader ? 1.5 : 1.08, 48]} />
						<meshBasicMaterial color={selected ? '#f59e0b' : '#22c55e'} transparent opacity={0.9} toneMapped={false} />
					</mesh>
				)}
				<Label overlay={overlay} y={leader ? 1.35 : 1.05}>
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

function Entry({ at, title, overlay }: { at: XZ; title: string; overlay: Overlay }) {
	return (
		<group position={[at[0], 0, at[1]]}>
			<mesh position={[0, 0.35, 0]}>
				<sphereGeometry args={[0.38, 24, 24]} />
				<meshStandardMaterial color={ENTRY_COLOR} roughness={0.6} />
			</mesh>
			<Label overlay={overlay} y={0.95}>
				<span className="rounded-full border border-border/70 bg-background/90 px-2 py-0.5 text-[11px] whitespace-nowrap text-muted-foreground">{title}</span>
			</Label>
		</group>
	);
}

/** Re-frames the camera when asked: after "reset" or when the agent count changes a lot. */
function CameraHome({ radius, home }: { radius: number; home: number }) {
	const camera = useThree((state) => state.camera);
	useEffect(() => {
		camera.position.set(0, radius * 1.35 + 5, radius * 1.7 + 6);
		camera.lookAt(0, 0, 0);
	}, [camera, radius, home]);
	return null;
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
	const [layout, setLayout] = useState<Record<string, XZ>>(() => ({ ...defaultLayout(agents), ...readLayout(layoutKey) }));
	const [dragging, setDragging] = useState(false);
	const [now, setNow] = useState(() => Date.now());
	useEffect(() => {
		const timer = window.setInterval(() => setNow(Date.now()), 60_000);
		return () => window.clearInterval(timer);
	}, []);

	// New agents get a ring place; removed ones drop out of the map at once.
	const ids = agents.map((agent) => agent.id).join(',');
	useEffect(() => {
		setLayout((current) => ({ ...defaultLayout(agents), ...current }));
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [ids]);
	useEffect(() => {
		if (!resetSignal) return;
		const fresh = defaultLayout(agents);
		setLayout(fresh);
		writeLayout(layoutKey, {});
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [resetSignal]);

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
	const radius = Math.max(4, ...Object.values(layout).map(([x, z]) => Math.hypot(x, z)));

	const leaderEdges = leader
		? agents.filter((agent) => agent.role === 'business' && (agent.state === 'published' || linkOf.has(`${leader.id}>${agent.id}`)))
		: [];
	const peerLinks = links.filter((link) => link.kind === 'peer' && byId.has(link.source) && byId.has(link.target));

	const move = (id: string, to: XZ) => setLayout((current) => ({ ...current, [id]: to }));
	const drag = (on: boolean) => {
		setDragging(on);
		if (!on) setLayout((current) => { writeLayout(layoutKey, current); return current; });
	};

	return (
		<div className="relative size-full overflow-hidden [isolation:isolate]">
			<Canvas
				shadows
				dpr={[1, 1.5]}
				frameloop={motion ? 'always' : 'demand'}
				camera={{ fov: 42, near: 0.1, far: 200 }}
				gl={{ alpha: true, antialias: true }}
				onCreated={({ gl }) => gl.domElement.addEventListener('webglcontextlost', onUnavailable)}
				onPointerMissed={() => onSelect(null)}
			>
				<CameraHome radius={radius} home={resetSignal} />
				<ambientLight intensity={0.75} />
				<directionalLight position={[6, 12, 8]} intensity={1.1} castShadow shadow-mapSize={[1024, 1024]} />
				<mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
					<circleGeometry args={[radius + 6, 64]} />
					<meshStandardMaterial color="#e2e8f0" transparent opacity={0.35} roughness={1} />
				</mesh>
				<gridHelper args={[(radius + 6) * 2, Math.round(radius + 6) * 2, '#94a3b8', '#cbd5e1']} position={[0, 0.005, 0]} material-transparent material-opacity={0.25} />
				<ContactShadows position={[0, 0.01, 0]} opacity={0.35} scale={(radius + 6) * 2} blur={2.4} far={4} />

				<Entry at={layout.resident} title="Khách hàng" overlay={overlay} />
				<Entry at={layout.manager} title="Người quản lý" overlay={overlay} />
				{leader && (
					<>
						<Edge from={layout.resident} to={layout[leader.id]} link={null} active={leader.live} motion={motion} dim={selectedId !== null} now={now} />
						<Edge from={layout.manager} to={layout[leader.id]} link={null} active={false} motion={motion} dim={selectedId !== null} now={now} />
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
						onSelect={() => onSelect(agent.id === selectedId ? null : agent.id)}
						onOpen={() => onOpen(agent.id)}
						onMove={(to) => move(agent.id, to)}
						onDragging={drag}
					/>
				))}
				<OrbitControls makeDefault enabled={!dragging} enableDamping minDistance={5} maxDistance={60} maxPolarAngle={1.32} minPolarAngle={0.2} />
			</Canvas>
			{/* Zero-sized so the canvas keeps its pointer events; the labels overflow it. */}
			<div ref={overlayRef} className="absolute top-0 left-0" />
		</div>
	);
}
