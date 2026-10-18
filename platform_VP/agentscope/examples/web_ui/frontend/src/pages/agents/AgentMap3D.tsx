import { Html, Line, OrbitControls, RoundedBox } from '@react-three/drei';
import { Canvas, type ThreeEvent, useThree } from '@react-three/fiber';
import { type RefObject, useEffect, useMemo, useRef, useState } from 'react';
import { type OrthographicCamera, Plane, QuadraticBezierCurve3, Vector3 } from 'three';

import { ClayPortrait, portraitFor } from '@/components/ui/clay-portrait';

import './agent-map-scene.css';

export type MapAgent = {
	id: string;
	name: string;
	role: 'leader' | 'business';
	state: 'published' | 'draft' | 'withdrawn';
	tickets: number;
	/** A recent reply is history, not proof that the agent is currently working. */
	live: boolean;
	costUsd: number | null;
};

export type MapLink = { source: string; target: string; kind: 'leader' | 'peer'; tickets: number; lastAt: string };

type Overlay = RefObject<HTMLElement>;
type XZ = [number, number];
type FigureRole = 'leader' | 'technical' | 'support' | 'security' | 'report' | 'generic';
const FLOOR = new Plane(new Vector3(0, 1, 0), 0);
const ACCENT = '#168478';
const usd = (value: number | null) => (value === null ? 'Chưa có chi phí' : value < 1 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`);
const statusOf = (agent: MapAgent) => agent.role === 'leader' ? 'Điều phối đội ngũ' : agent.state === 'published' ? 'Đang phát hành' : agent.state === 'draft' ? 'Bản nháp' : 'Đã ngừng';

function figureRole(agent: MapAgent): FigureRole {
	if (agent.role === 'leader') return 'leader';
	const name = agent.name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').toLowerCase();
	if (/ky thuat|bao tri|technical|technician|repair/.test(name)) return 'technical';
	if (/an ninh|security/.test(name)) return 'security';
	if (/bao cao|thong ke|report|calculat|tinh toan/.test(name)) return 'report';
	if (/ho tro|le tan|support|reception|dieu phoi/.test(name)) return 'support';
	return 'generic';
}

function readLayout(key: string): Record<string, XZ> {
	try {
		const saved: unknown = JSON.parse(window.localStorage.getItem(key) ?? '{}');
		if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {};
		return Object.fromEntries(Object.entries(saved).filter(([, at]) => Array.isArray(at) && at.length === 2 && at.every((n) => typeof n === 'number' && Number.isFinite(n) && Math.abs(n) < 100)));
	} catch {
		return {};
	}
}

function writeLayout(key: string, layout: Record<string, XZ>) {
	try { window.localStorage.setItem(key, JSON.stringify(layout)); } catch { /* Private browsing keeps positions for this visit. */ }
}

/** Keep a readable inner ring; larger teams grow into additional rings. */
function defaultLayout(agents: MapAgent[]): Record<string, XZ> {
	const layout: Record<string, XZ> = {};
	const business = agents.filter((agent) => agent.role === 'business');
	for (const agent of agents) if (agent.role === 'leader') layout[agent.id] = [0, 0];
	let offset = 0;
	for (let ring = 0; offset < business.length; ring += 1) {
		const count = Math.min(10 + ring * 6, business.length - offset);
		const radius = (count <= 4 && ring === 0 ? 4.8 : 6.1) + ring * 4.7;
		for (let index = 0; index < count; index += 1) {
			const angle = (index / count) * Math.PI * 2 - Math.PI / 2 + (ring % 2 ? Math.PI / count : 0);
			layout[business[offset + index].id] = [Math.cos(angle) * radius * 1.15, Math.sin(angle) * radius];
		}
		offset += count;
	}
	return layout;
}

function useScenePreferences(sceneRef: RefObject<HTMLDivElement | null>) {
	const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
	const [dark, setDark] = useState(false);
	useEffect(() => {
		const media = window.matchMedia('(prefers-reduced-motion: reduce)');
		const updateMotion = () => setReducedMotion(media.matches);
		const updateTheme = () => setDark(document.documentElement.classList.contains('dark') && !sceneRef.current?.closest('.cue-theme'));
		updateTheme();
		media.addEventListener('change', updateMotion);
		const observer = new MutationObserver(updateTheme);
		observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => { media.removeEventListener('change', updateMotion); observer.disconnect(); };
	}, [sceneRef]);
	return { reducedMotion, dark };
}

/** Historical links stay still. Their presence means shared work, never live traffic. */
function Edge({ from, to, peer, focused, dim, dark }: { from: XZ; to: XZ; peer: boolean; focused: boolean; dim: boolean; dark: boolean }) {
	const points = useMemo(() => {
		const start = new Vector3(from[0], 0.2, from[1]);
		const end = new Vector3(to[0], 0.2, to[1]);
		const middle = start.clone().add(end).multiplyScalar(0.5);
		middle.y = peer ? 0.38 : 0.32;
		return new QuadraticBezierCurve3(start, middle, end).getPoints(24);
	}, [from, to, peer]);
	return <Line points={points} color={peer ? (dark ? '#7c91a4' : '#8fa3b3') : ACCENT} lineWidth={focused ? 2 : peer ? 1 : 1.4} transparent opacity={dim ? 0.08 : focused ? 0.9 : peer ? 0.44 : 0.56} dashed={peer} dashSize={0.14} gapSize={0.14} />;
}

/** Small authored 3D figures, with a shared silhouette and role-specific equipment. */
function AgentFigure({ role, dim, draft, compact }: { role: FigureRole; dim: boolean; draft: boolean; compact: boolean }) {
	const leader = role === 'leader';
	const opacity = dim ? 0.38 : draft ? 0.76 : 1;
	const shell = draft ? '#e1e5e8' : '#eef2f2';
	const uniform = leader ? '#255d5c' : '#617b82';
	const material = (color: string) => <meshStandardMaterial color={color} roughness={0.78} metalness={0.04} transparent={opacity < 1} opacity={opacity} />;
	return (
		<group scale={leader ? 1.12 : 1}>
			<RoundedBox args={[1.62, 0.16, 1.3]} radius={0.14} smoothness={3} position={[0, 0.1, 0]} receiveShadow castShadow>{material(leader ? '#d9e9e6' : '#e4e9eb')}</RoundedBox>
			{[-0.3, 0.3].map((x) => <RoundedBox key={x} args={[0.4, 0.24, 0.63]} radius={0.09} smoothness={3} position={[x, 0.32, 0.09]} castShadow>{material('#506773')}</RoundedBox>)}
			<RoundedBox args={[1.04, 0.85, 0.69]} radius={0.24} smoothness={4} position={[0, 0.88, 0]} castShadow>{material(uniform)}</RoundedBox>
			<RoundedBox args={[0.56, 0.39, 0.06]} radius={0.07} smoothness={3} position={[0, 0.96, 0.36]}>{material(leader ? '#bcd9d3' : '#d3dfe1')}</RoundedBox>
			<mesh position={[0, 1.33, 0]} castShadow><cylinderGeometry args={[0.22, 0.22, 0.16, 12]} />{material('#8fa4aa')}</mesh>
			<RoundedBox args={[1.31, 0.95, 0.87]} radius={0.31} smoothness={5} position={[0, 1.77, 0]} castShadow>{material(shell)}</RoundedBox>
			<RoundedBox args={[1.06, 0.53, 0.09]} radius={0.19} smoothness={4} position={[0, 1.79, 0.431]}>{material('#263e4b')}</RoundedBox>
			{[-0.23, 0.23].map((x) => <mesh key={x} position={[x, 1.83, 0.489]} scale={[1, 1.2, 0.5]}><sphereGeometry args={[0.075, 12, 12]} />{material(leader ? '#9ee0d0' : '#c7ece4')}</mesh>)}
			<RoundedBox args={[0.19, 0.035, 0.025]} radius={0.012} smoothness={2} position={[0, 1.65, 0.494]}>{material('#9eb7be')}</RoundedBox>
			{!compact && [-1, 1].map((side) => <group key={side} position={[side * 0.67, 1, 0]} rotation={[0, 0, side * 0.13]}>
				<RoundedBox args={[0.26, 0.64, 0.32]} radius={0.12} smoothness={3} castShadow>{material(shell)}</RoundedBox>
				<mesh position={[0, -0.34, 0]} castShadow><sphereGeometry args={[0.16, 12, 12]} />{material('#8da4a9')}</mesh>
			</group>)}
			{(role === 'leader' || role === 'support') && <>
				{[-0.69, 0.69].map((x) => <RoundedBox key={x} args={[0.14, 0.42, 0.4]} radius={0.07} smoothness={3} position={[x, 1.79, 0]} castShadow>{material(ACCENT)}</RoundedBox>)}
				<RoundedBox args={[0.3, 0.06, 0.08]} radius={0.025} smoothness={2} position={[0.6, 1.59, 0.39]}>{material('#4b6871')}</RoundedBox>
			</>}
			{role === 'technical' && <>
				<mesh position={[0, 2.12, 0]} castShadow><sphereGeometry args={[0.72, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />{material('#d7b574')}</mesh>
				<RoundedBox args={[1.49, 0.1, 1.02]} radius={0.045} smoothness={3} position={[0, 2.12, 0.04]} castShadow>{material('#c29b5b')}</RoundedBox>
			</>}
			{role === 'security' && <RoundedBox args={[0.5, 0.12, 0.24]} radius={0.045} smoothness={3} position={[0, 2.25, 0.31]} castShadow>{material('#536c79')}</RoundedBox>}
			{role === 'report' && <group position={[0.62, 0.9, 0.42]} rotation={[-0.15, -0.2, -0.12]}>
				<RoundedBox args={[0.44, 0.59, 0.08]} radius={0.05} smoothness={2} castShadow>{material('#d3dfdf')}</RoundedBox>
				<RoundedBox args={[0.31, 0.36, 0.02]} radius={0.015} smoothness={2} position={[0, 0.02, 0.05]}>{material('#759e97')}</RoundedBox>
			</group>}
			{!compact && role !== 'technical' && <>
				<mesh position={[0.38, 2.32, 0]}><cylinderGeometry args={[0.025, 0.025, 0.24, 8]} />{material('#80999e')}</mesh>
				<mesh position={[0.38, 2.46, 0]}><sphereGeometry args={[0.075, 12, 12]} />{material(ACCENT)}</mesh>
			</>}
		</group>
	);
}

function Node({ agent, at, selected, dim, overlay, showLabel, compact, compactLabel, onSelect, onOpen, onMove, onDragging }: {
	agent: MapAgent; at: XZ; selected: boolean; dim: boolean; overlay: Overlay; showLabel: boolean; compact: boolean; compactLabel: boolean;
	onSelect: () => void; onOpen: () => void; onMove: (to: XZ) => void; onDragging: (on: boolean) => void;
}) {
	const press = useRef<{ x: number; y: number; moved: boolean; offset: XZ } | null>(null);
	const [hovered, setHovered] = useState(false);
	const leader = agent.role === 'leader';
	const down = (event: ThreeEvent<PointerEvent>) => {
		if (event.button !== 0) return;
		event.stopPropagation();
		(event.target as unknown as Element).setPointerCapture?.(event.pointerId);
		const point = new Vector3();
		event.ray.intersectPlane(FLOOR, point);
		press.current = { x: event.clientX, y: event.clientY, moved: false, offset: [at[0] - point.x, at[1] - point.z] };
		onDragging(true);
	};
	const move = (event: ThreeEvent<PointerEvent>) => {
		if (!press.current) return;
		event.stopPropagation();
		if (Math.hypot(event.clientX - press.current.x, event.clientY - press.current.y) > 4) press.current.moved = true;
		if (!press.current.moved) return;
		const point = new Vector3();
		if (event.ray.intersectPlane(FLOOR, point)) onMove([Math.max(-60, Math.min(60, point.x + press.current.offset[0])), Math.max(-60, Math.min(60, point.z + press.current.offset[1]))]);
	};
	const up = (event: ThreeEvent<PointerEvent>) => {
		if (!press.current) return;
		event.stopPropagation();
		(event.target as unknown as Element).releasePointerCapture?.(event.pointerId);
		const clicked = !press.current.moved;
		press.current = null;
		onDragging(false);
		if (clicked) onSelect();
	};
	return <group position={[at[0], 0, at[1]]}>
		<group onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={() => { press.current = null; onDragging(false); }} onDoubleClick={(event) => { event.stopPropagation(); onOpen(); }} onPointerOver={() => setHovered(true)} onPointerOut={() => setHovered(false)}>
			<AgentFigure role={figureRole(agent)} dim={dim} draft={agent.state !== 'published'} compact={compact} />
			{/* A generous hit area preserves selection and dragging between the figure's parts. */}
			<mesh position={[0, 1.2, 0]}><boxGeometry args={[1.9, 2.5, 1.4]} /><meshBasicMaterial transparent opacity={0} depthWrite={false} /></mesh>
		</group>
		{(selected || hovered) && <mesh position={[0, 0.024, 0]} rotation={[-Math.PI / 2, 0, 0]}>
			<ringGeometry args={[leader ? 1.18 : 1.02, leader ? 1.25 : 1.08, 48]} /><meshBasicMaterial color={ACCENT} transparent opacity={selected ? 0.8 : 0.35} depthWrite={false} />
		</mesh>}
		{(showLabel || selected || hovered) && <Html position={[0, -0.9, 0]} center zIndexRange={[30, 10]} portal={overlay} style={{ pointerEvents: 'none' }}>
			<button type="button" className="agent-map-label" data-agent-id={agent.id} data-compact={compactLabel || undefined} data-leader={leader || undefined} data-selected={selected || undefined} data-dim={dim || undefined} aria-pressed={selected} aria-label={`${agent.name}, ${statusOf(agent)}, ${agent.tickets} phiếu, ${usd(agent.costUsd)}`} title={`${agent.name}. Nhấp đúp hoặc nhấn Enter để mở. Phím mũi tên để di chuyển.`} onClick={onSelect} onDoubleClick={onOpen} onKeyDown={(event) => {
				if (event.key === 'Enter') { event.preventDefault(); onOpen(); }
				const step: Record<string, XZ> = { ArrowLeft: [-0.5, 0], ArrowRight: [0.5, 0], ArrowUp: [0, -0.5], ArrowDown: [0, 0.5] };
				if (step[event.key]) { event.preventDefault(); onMove([at[0] + step[event.key][0], at[1] + step[event.key][1]]); onDragging(false); }
			}}>
				<span className="agent-map-label-identity"><ClayPortrait size={28} which={leader ? 'leader' : portraitFor(agent.name)} /><span className="agent-map-label-name">{agent.name}</span></span>
				<span className="agent-map-label-status" data-state={agent.state}>{statusOf(agent)}</span>
			</button>
		</Html>}
	</group>;
}

/** Fit on entry, resize or explicit Home. Dragging never moves the camera. */
function CameraHome({ layout, defaults, home, reset, count }: { layout: Record<string, XZ>; defaults: Record<string, XZ>; home: number; reset: number; count: number }) {
	const { get, size, invalidate } = useThree();
	const layoutRef = useRef(layout);
	const defaultsRef = useRef(defaults);
	const lastReset = useRef(reset);
	useEffect(() => { layoutRef.current = layout; defaultsRef.current = defaults; }, [layout, defaults]);
	useEffect(() => {
		const { camera, controls } = get();
		const resetChanged = lastReset.current !== reset;
		lastReset.current = reset;
		const positions = Object.entries(defaultsRef.current).map(([id, fallback]) => resetChanged ? fallback : layoutRef.current[id] ?? fallback);
		const xs = positions.map(([x]) => x), zs = positions.map(([, z]) => z);
		const minX = Math.min(-2, ...xs), maxX = Math.max(2, ...xs), minZ = Math.min(-2, ...zs), maxZ = Math.max(2, ...zs);
		const x = (minX + maxX) / 2, z = (minZ + maxZ) / 2;
		const target = new Vector3(x, 0.7, z);
		camera.position.set(x, 22.7, z + 27);
		camera.lookAt(target);
		if ('isOrthographicCamera' in camera) {
			const orthographic = camera as OrthographicCamera;
			const horizontalGutter = size.width < 600 ? 48 : Math.min(184, size.width * 0.25);
			orthographic.zoom = Math.max(8, Math.min((size.width - horizontalGutter) / (maxX - minX + 2.7), (size.height - 150) / ((maxZ - minZ) * 0.632 + 3.1)));
			orthographic.updateProjectionMatrix();
		}
		const orbit = controls as unknown as { target: Vector3; update: () => void } | null;
		orbit?.target.copy(target);
		orbit?.update();
		invalidate();
	}, [get, size.width, size.height, home, reset, count, invalidate]);
	return null;
}

function ContextLifecycle({ onUnavailable }: { onUnavailable: () => void }) {
	const canvas = useThree((state) => state.gl.domElement);
	useEffect(() => {
		const lost = (event: Event) => { event.preventDefault(); onUnavailable(); };
		canvas.addEventListener('webglcontextlost', lost);
		return () => { canvas.removeEventListener('webglcontextlost', lost); };
	}, [canvas, onUnavailable]);
	return null;
}

function Scene({ agents, links, selectedId, onSelect, onOpen, layout, move, drag, dragging, overlay, homeSignal, resetSignal, showPeerLinks, showLabels, reducedMotion, dark, onUnavailable }: {
	agents: MapAgent[]; links: MapLink[]; selectedId: string | null; onSelect: (id: string | null) => void; onOpen: (id: string) => void;
	layout: Record<string, XZ>; move: (id: string, to: XZ) => void; drag: (on: boolean) => void; dragging: boolean; overlay: Overlay;
	homeSignal: number; resetSignal: number; showPeerLinks: boolean; showLabels: boolean; reducedMotion: boolean; dark: boolean; onUnavailable: () => void;
}) {
	const width = useThree((state) => state.size.width);
	const byId = new Map(agents.map((agent) => [agent.id, agent]));
	const visibleLinks = links.filter((link) => link.tickets > 0 && link.source !== link.target && byId.has(link.source) && byId.has(link.target) && (showPeerLinks || link.kind !== 'peer'));
	const neighbours = new Set<string>(selectedId ? [selectedId] : []);
	for (const link of visibleLinks) {
		if (link.source === selectedId) neighbours.add(link.target);
		if (link.target === selectedId) neighbours.add(link.source);
	}
	const dim = (id: string) => selectedId !== null && !neighbours.has(id);
	const radius = Math.max(9, ...Object.values(layout).map(([x, z]) => Math.hypot(x, z))) + 3;
	return <>
		<color attach="background" args={[dark ? '#111b25' : '#f7f9fb']} />
		<ambientLight intensity={1.45} />
		<hemisphereLight args={['#ffffff', '#7b8e9c', 1.35]} />
		<directionalLight position={[-8, 16, 12]} intensity={2.3} castShadow shadow-mapSize={[1024, 1024]} shadow-camera-left={-radius} shadow-camera-right={radius} shadow-camera-top={radius} shadow-camera-bottom={-radius} shadow-normalBias={0.04} shadow-bias={-0.0001} shadow-radius={4} />
		<mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow><planeGeometry args={[300, 300]} /><shadowMaterial color={dark ? '#02070d' : '#52697c'} transparent opacity={dark ? 0.2 : 0.11} /></mesh>
		<gridHelper args={[radius * 2, Math.round(radius), dark ? '#45525e' : '#c5d0d9', dark ? '#33424f' : '#d6dfe5']} position={[0, 0.012, 0]} material-transparent material-opacity={dark ? 0.16 : 0.26} />
		{visibleLinks.map((link) => layout[link.source] && layout[link.target] && <Edge key={`${link.kind}-${link.source}-${link.target}`} from={layout[link.source]} to={layout[link.target]} peer={link.kind === 'peer'} focused={selectedId === link.source || selectedId === link.target} dim={dim(link.source) || dim(link.target)} dark={dark} />)}
		{agents.map((agent) => layout[agent.id] && <Node key={agent.id} agent={agent} at={layout[agent.id]} selected={agent.id === selectedId} dim={dim(agent.id)} compact={agents.length > 24} compactLabel={width < 600} overlay={overlay} showLabel={showLabels && (agent.role === 'leader' || (agents.length <= 18 && width >= 600))} onSelect={() => onSelect(agent.id === selectedId ? null : agent.id)} onOpen={() => onOpen(agent.id)} onMove={(to) => move(agent.id, to)} onDragging={drag} />)}
		<OrbitControls makeDefault enabled={!dragging} enableDamping={!reducedMotion} dampingFactor={0.12} minZoom={8} maxZoom={120} maxPolarAngle={1.2} minPolarAngle={0.35} />
		<CameraHome layout={layout} defaults={defaultLayout(agents)} home={homeSignal} reset={resetSignal} count={agents.length} />
		<ContextLifecycle onUnavailable={onUnavailable} />
	</>;
}

export default function AgentMap3D({ agents, links, selectedId, onSelect, onOpen, layoutKey, resetSignal, onUnavailable, homeSignal = 0, showPeerLinks = true, showLabels = true }: {
	agents: MapAgent[]; links: MapLink[]; selectedId: string | null; onSelect: (id: string | null) => void; onOpen: (id: string) => void;
	layoutKey: string; resetSignal: number; onUnavailable: () => void; homeSignal?: number; showPeerLinks?: boolean; showLabels?: boolean;
}) {
	const overlayRef = useRef<HTMLDivElement>(null);
	const sceneRef = useRef<HTMLDivElement>(null);
	const { reducedMotion, dark } = useScenePreferences(sceneRef);
	// The new geometry has its own layout version; old cube positions are preserved under their original key.
	const storageKey = `${layoutKey}:figures-v1`;
	const [layout, setLayout] = useState<Record<string, XZ>>(() => ({ ...defaultLayout(agents), ...readLayout(storageKey) }));
	const [dragging, setDragging] = useState(false);
	const [webglReady, setWebglReady] = useState(false);
	useEffect(() => {
		// Fail before mounting Canvas so an unsupported GPU does not take down the page.
		const probe = document.createElement('canvas');
		try {
			const context = probe.getContext('webgl2');
			if (!context) { onUnavailable(); return; }
			context.getExtension('WEBGL_lose_context')?.loseContext();
			setWebglReady(true);
		} catch { onUnavailable(); }
		// A parent callback may be inline; capability is checked once per mount.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);
	const ids = agents.map((agent) => agent.id).join(',');
	useEffect(() => {
		const defaults = defaultLayout(agents);
		setLayout((current) => Object.fromEntries(agents.map((agent) => [agent.id, current[agent.id] ?? defaults[agent.id]])));
		// Agent statistics must not reset saved positions.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [ids]);
	useEffect(() => {
		setLayout({ ...defaultLayout(agents), ...readLayout(storageKey) });
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [storageKey]);
	useEffect(() => {
		if (!resetSignal) return;
		setLayout(defaultLayout(agents));
		writeLayout(storageKey, {});
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [resetSignal]);
	const move = (id: string, to: XZ) => setLayout((current) => ({ ...current, [id]: to }));
	const drag = (on: boolean) => {
		setDragging(on);
		if (!on) setLayout((current) => { writeLayout(storageKey, current); return current; });
	};
	return <div ref={sceneRef} className="agent-map-scene relative size-full overflow-hidden [isolation:isolate]" data-theme={dark ? 'dark' : 'light'} data-dragging={dragging || undefined}>
		{webglReady && <Canvas orthographic shadows dpr={[1, 1.5]} frameloop="demand" camera={{ zoom: 45, near: 0.1, far: 200, position: [0, 22.7, 27] }} gl={{ alpha: false, antialias: true }} onPointerMissed={() => onSelect(null)}>
			<Scene agents={agents} links={links} selectedId={selectedId} onSelect={onSelect} onOpen={onOpen} layout={layout} move={move} drag={drag} dragging={dragging} overlay={overlayRef as Overlay} homeSignal={homeSignal} resetSignal={resetSignal} showPeerLinks={showPeerLinks} showLabels={showLabels} reducedMotion={reducedMotion} dark={dark} onUnavailable={onUnavailable} />
		</Canvas>}
		<div ref={overlayRef} className="pointer-events-none absolute top-0 left-0" />
	</div>;
}
