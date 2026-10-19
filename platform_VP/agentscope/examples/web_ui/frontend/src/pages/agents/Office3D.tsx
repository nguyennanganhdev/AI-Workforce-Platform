import { Edges, Html, OrbitControls } from '@react-three/drei';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
	type ComponentRef,
	type RefObject,
	useEffect,
	useMemo,
	useRef,
	useSyncExternalStore,
} from 'react';
import { BackSide, type Group, type Side, Vector3 } from 'three';

import {
	BOARD,
	CHAIR,
	DOOR,
	EDGE,
	GLASS,
	KEYBOARD,
	LEAVES,
	MINT,
	NOTES,
	type Palette,
	POT,
	ROOM,
	SCREEN,
	SLATE,
	WHITE,
	WINDOW,
	WOOD,
} from './office-palette';
import { Bubble, Person } from './office-people';
import {
	FLOOR_W,
	type Actor,
	type Layout,
	type OfficeSim,
	type Point,
	roomLabels,
	WALL_H,
} from './office-sim';

/**
 * The office in 3D: orbit, tilt and zoom with the mouse. It draws the layout
 * from `office-sim`. One floor tile is one
 * unit; heights are written in design pixels and scaled through `px`.
 *
 * It is painted, not lit: every face takes its colour from `office-palette`,
 * with no lights or tone mapping, for the flat, illustrated look.
 *
 * Walls only render their inward face, so whichever wall stands between the
 * camera and the room disappears and the inside is always in view.
 */

/** Design pixels of height (40 per tile) → world units. */
const px = (value: number) => value / 40;

/**
 * Where every `Html` overlay mounts. Without a fixed target drei mounts into the
 * canvas wrapper, which changes once after the first render: every overlay is
 * then torn down and rebuilt, and one that never renders again (a room label)
 * comes back empty.
 */
// drei types the portal as never-null; it is only read after the div mounts.
type Overlay = RefObject<HTMLElement>;

/** A CSS colour split into what three.js takes: an opaque colour and an opacity. */
function paint(css: string) {
	const rgba = css.match(/^rgba\(([^)]+)\)$/);
	if (!rgba) return { color: css, opacity: 1 };
	const [r, g, b, a] = rgba[1].split(',').map(Number);
	return { color: `rgb(${r},${g},${b})`, opacity: a };
}

/** BoxGeometry's material slots: +x, -x, +y, -y, +z, -z. */
const BOX_FACES = ['right', 'right', 'top', 'top', 'left', 'left'] as const;

function Paint({ css, slot, side }: { css: string; slot?: number; side?: Side }) {
	const { color, opacity } = paint(css);
	const clear = opacity < 1;
	return (
		<meshBasicMaterial
			attach={slot === undefined ? 'material' : `material-${slot}`}
			color={color}
			transparent={clear}
			opacity={opacity}
			depthWrite={!clear}
			side={side}
		/>
	);
}

function Outline({ css }: { css: string }) {
	const { color, opacity } = paint(css);
	return <Edges color={color} transparent={opacity < 1} opacity={opacity} />;
}

/** A floor-standing box: `x, y, w, d` in tiles, `h` and `lift` in design pixels. */
function Block({
	x,
	y,
	w,
	d,
	h,
	lift = 0,
	palette,
}: {
	x: number;
	y: number;
	w: number;
	d: number;
	h: number;
	lift?: number;
	palette: Palette;
}) {
	return (
		<mesh position={[x + w / 2, px(lift + h / 2), y + d / 2]}>
			<boxGeometry args={[w, px(h), d]} />
			{BOX_FACES.map((face, slot) => (
				<Paint key={slot} css={palette[face]} slot={slot} />
			))}
			<Outline css={palette.stroke ?? EDGE} />
		</mesh>
	);
}

const solid = (color: string): Palette => ({ top: color, left: color, right: color });

function Desk({
	at,
	palette,
	working = false,
}: {
	at: Point;
	palette: Palette;
	working?: boolean;
}) {
	const H = 24;
	return (
		<group>
			<Block x={at.x - 0.74} y={at.y - 0.36} w={1.48} d={0.72} h={H - 4} palette={palette} />
			<Block
				x={at.x - 0.8}
				y={at.y - 0.42}
				w={1.6}
				d={0.84}
				h={4}
				lift={H - 4}
				palette={palette}
			/>
			<Block x={at.x - 0.06} y={at.y - 0.3} w={0.12} d={0.1} h={4} lift={H} palette={SLATE} />
			<Block
				x={at.x - 0.42}
				y={at.y - 0.25}
				w={0.84}
				d={0.04}
				h={27}
				lift={H + 3}
				palette={{ ...solid(working ? SCREEN.on : SCREEN.off), stroke: SCREEN.frame }}
			/>
			<Block
				x={at.x - 0.3}
				y={at.y + 0.08}
				w={0.6}
				d={0.18}
				h={0.6}
				lift={H}
				palette={solid(KEYBOARD)}
			/>
		</group>
	);
}

function AgentDesk({ at, agentId, sim }: { at: Point; agentId: string; sim: OfficeSim }) {
	const working = useSyncExternalStore(
		sim.subscribe,
		() => sim.actors.get(agentId)?.status === 'working',
	);
	return <Desk at={at} palette={WOOD} working={working} />;
}

function Chair({ at }: { at: Point }) {
	return (
		<group>
			<Block
				x={at.x - 0.24}
				y={at.y - 0.24}
				w={0.48}
				d={0.48}
				h={6}
				lift={8}
				palette={CHAIR}
			/>
			<Block
				x={at.x - 0.24}
				y={at.y + 0.16}
				w={0.48}
				d={0.08}
				h={20}
				lift={12}
				palette={CHAIR}
			/>
		</group>
	);
}

/** Round foliage over the pot; radii and offsets in design pixels. */
function Plant({ at }: { at: Point }) {
	const leaf = (key: string, r: number, dx: number, up: number, color: string) => (
		<mesh key={key} position={[at.x + dx, px(34 + up), at.y - dx]}>
			<sphereGeometry args={[px(r), 24, 16]} />
			<Paint css={color} />
		</mesh>
	);
	return (
		<group>
			<Block x={at.x - 0.22} y={at.y - 0.22} w={0.44} d={0.44} h={18} palette={POT} />
			{leaf('main', 17, 0, 0, LEAVES.main)}
			{leaf('light', 10, -0.09, 8, LEAVES.light)}
			{leaf('dark', 8, 0.1, 3, LEAVES.dark)}
		</group>
	);
}

/** A glass partition, one tile per pane, so the mullions show. */
function Glass({
	axis,
	fixed,
	from,
	to,
}: {
	axis: 'x' | 'y';
	fixed: number;
	from: number;
	to: number;
}) {
	const panes: [number, number][] = [];
	for (let start = from; start < to - 0.001; start += 1)
		panes.push([start, Math.min(to, start + 1)]);
	return (
		<group>
			{panes.map(([start, end]) =>
				axis === 'x' ? (
					<Block
						key={start}
						x={fixed - 0.04}
						y={start}
						w={0.08}
						d={end - start}
						h={54}
						palette={GLASS}
					/>
				) : (
					<Block
						key={start}
						x={start}
						y={fixed - 0.04}
						w={end - start}
						d={0.08}
						h={54}
						palette={GLASS}
					/>
				),
			)}
		</group>
	);
}

/** A flat panel hung on a back wall, facing into the room. */
function WallPanel({
	wall,
	from,
	to,
	z0,
	z1,
	fill,
	stroke,
	offset = 0.02,
}: {
	wall: 'back' | 'left';
	from: number;
	to: number;
	z0: number;
	z1: number;
	fill: string;
	stroke?: string;
	offset?: number;
}) {
	const w = to - from;
	const h = px(z1 - z0);
	const y = px(z0) + h / 2;
	const [position, rotation]: [[number, number, number], [number, number, number]] =
		wall === 'back'
			? [
					[from + w / 2, y, offset],
					[0, 0, 0],
				]
			: [
					[offset, y, from + w / 2],
					[0, Math.PI / 2, 0],
				];
	return (
		<mesh position={position} rotation={rotation}>
			<planeGeometry args={[w, h]} />
			<Paint css={fill} />
			{stroke && <Outline css={stroke} />}
		</mesh>
	);
}

function Shell({ layout }: { layout: Layout }) {
	const D = layout.depth;
	const W = FLOOR_W;
	const wallH = px(WALL_H);
	const slab = px(14);
	const grid = useMemo(() => {
		const points: number[] = [];
		for (let i = 1; i < W; i += 1) points.push(i, 0.004, 0, i, 0.004, D);
		for (let j = 1; j < D; j += 1) points.push(0, 0.004, j, W, 0.004, j);
		return new Float32Array(points);
	}, [D, W]);
	const gridPaint = paint(ROOM.grid);
	const tint = (r: Layout['rooms']['meeting'], color: string) => (
		<mesh
			position={[(r.x0 + r.x1) / 2, 0.002, (r.y0 + r.y1) / 2]}
			rotation={[-Math.PI / 2, 0, 0]}
		>
			<planeGeometry args={[r.x1 - r.x0, r.y1 - r.y0]} />
			<Paint css={color} />
		</mesh>
	);
	const { door } = layout.reception;
	// x-facing walls take the left wall colour, y-facing ones the back wall's.
	const wallFaces = [ROOM.wallLeft, ROOM.wallLeft, null, null, ROOM.wallBack, ROOM.wallBack];
	return (
		<group>
			{/* Slab: the floor on top, its cut faces round the sides. */}
			<mesh position={[W / 2, -slab / 2, D / 2]}>
				<boxGeometry args={[W, slab, D]} />
				{[
					ROOM.slabRight,
					ROOM.slabRight,
					ROOM.floor,
					ROOM.slabRight,
					ROOM.slabLeft,
					ROOM.slabLeft,
				].map((css, slot) => (
					<Paint key={slot} css={css} slot={slot} />
				))}
			</mesh>
			{tint(layout.rooms.meeting, ROOM.meeting)}
			{tint(layout.rooms.approval, ROOM.approval)}
			{tint(layout.rooms.reception, ROOM.reception)}
			<lineSegments>
				<bufferGeometry>
					<bufferAttribute attach="attributes-position" args={[grid, 3]} />
				</bufferGeometry>
				<lineBasicMaterial
					color={gridPaint.color}
					transparent
					opacity={gridPaint.opacity}
				/>
			</lineSegments>

			{/* The walls are the inside of one box: from outside, the near ones vanish. */}
			<mesh position={[W / 2, wallH / 2, D / 2]}>
				<boxGeometry args={[W, wallH, D]} />
				{wallFaces.map((css, slot) =>
					css ? (
						<Paint key={slot} css={css} slot={slot} side={BackSide} />
					) : (
						<meshBasicMaterial key={slot} attach={`material-${slot}`} visible={false} />
					),
				)}
			</mesh>

			{/* Whiteboard in the meeting room, with the plan on it. */}
			<WallPanel
				wall="back"
				from={1.4}
				to={4.6}
				z0={30}
				z1={78}
				fill={BOARD.fill}
				stroke={BOARD.stroke}
			/>
			{NOTES.map(([x0, x1, z, fill]) => (
				<WallPanel
					key={`${x0}-${z}`}
					wall="back"
					from={x0}
					to={x1}
					z0={z - 12}
					z1={z}
					fill={fill}
					offset={0.03}
				/>
			))}
			{/* Windows over the open floor, each split by a mullion. */}
			{[
				[6.8, 9.8],
				[11.8, 15.2],
			].map(([x0, x1]) => (
				<group key={x0}>
					<WallPanel
						wall="back"
						from={x0}
						to={x1}
						z0={30}
						z1={82}
						fill={WINDOW.fill}
						stroke={WINDOW.stroke}
					/>
					<WallPanel
						wall="back"
						from={(x0 + x1) / 2 - 0.03}
						to={(x0 + x1) / 2 + 0.03}
						z0={30}
						z1={82}
						fill={WINDOW.stroke}
						offset={0.03}
					/>
				</group>
			))}
			{/* The way in, by reception. */}
			<WallPanel
				wall="left"
				from={door.y - 0.6}
				to={door.y + 0.6}
				z0={0}
				z1={66}
				fill={DOOR.fill}
				stroke={DOOR.stroke}
			/>
		</group>
	);
}

function Furniture({ layout, sim }: { layout: Layout; sim: OfficeSim }) {
	const { rooms } = layout;
	const { counter } = layout.reception;
	return (
		<group>
			{/* Meeting room. */}
			<Glass axis="x" fixed={rooms.meeting.x1} from={0} to={2} />
			<Glass axis="x" fixed={rooms.meeting.x1} from={3} to={rooms.meeting.y1} />
			<Glass axis="y" fixed={rooms.meeting.y1} from={0} to={rooms.meeting.x1} />
			<Block x={1.4} y={1.85} w={3.4} d={1.3} h={20} palette={WHITE} />
			{layout.seats.map((seat, index) => (
				<Chair key={index} at={seat.at} />
			))}
			<Chair at={layout.head.at} />
			<Plant at={{ x: 5.45, y: 0.55 }} />

			{/* Your office. */}
			<Glass axis="x" fixed={rooms.approval.x0} from={0} to={2.5} />
			<Glass axis="x" fixed={rooms.approval.x0} from={3.5} to={rooms.approval.y1} />
			<Glass
				axis="y"
				fixed={rooms.approval.y1}
				from={rooms.approval.x0}
				to={rooms.approval.x1}
			/>
			<Desk at={layout.approval.desk} palette={WOOD} />
			<Chair at={layout.approval.user} />
			<Plant at={{ x: 15.5, y: 0.5 }} />

			{/* The Leader's desk. */}
			<Desk at={layout.leader.desk} palette={SLATE} />
			<Chair at={layout.leader.chair} />

			{/* Reception. */}
			<Block x={counter.x - 1} y={counter.y - 0.4} w={2} d={0.8} h={30} palette={MINT} />
			<Plant at={{ x: 5, y: layout.depth - 0.6 }} />

			{/* Open desks. */}
			{[...layout.desks.values()].map((desk) => (
				<group key={desk.agentId}>
					<AgentDesk at={desk.desk} agentId={desk.agentId} sim={sim} />
					<Chair at={desk.chair} />
				</group>
			))}
			<Plant at={{ x: 10.2, y: 0.6 }} />
			<Plant at={{ x: FLOOR_W - 0.5, y: 5.3 }} />
		</group>
	);
}

/** A room's name chip, standing on the floor. */
function RoomLabel({ at, name, overlay }: { at: Point; name: string; overlay: Overlay }) {
	return (
		<Html position={[at.x, 0.02, at.y]} zIndexRange={[90, 50]} portal={overlay}>
			<span className="of-room" style={{ left: 0, top: 0 }}>
				{name}
			</span>
		</Html>
	);
}

/** React only updates people when their visible state changes, never for a walking position. */
function ActorOverlay({
	actor,
	sim,
	selected,
	onSelect,
	offLabel,
}: {
	actor: Actor;
	sim: OfficeSim;
	selected: boolean;
	onSelect: () => void;
	offLabel: string;
}) {
	useSyncExternalStore(sim.subscribe, () =>
		JSON.stringify([
			actor.name,
			actor.status,
			actor.path.length > 0,
			actor.facing,
			actor.carrying,
			actor.bubble?.text,
		]),
	);
	return (
		<>
			<Person actor={actor} selected={selected} onSelect={onSelect} offLabel={offLabel} />
			<Bubble actor={actor} />
		</>
	);
}

/** Keep each person's overlay on their tile without rerendering the React scene. */
function Actors({
	sim,
	selectedId,
	setSelectedId,
	offLabel,
	overlay,
}: {
	overlay: Overlay;
	sim: OfficeSim;
	selectedId: string | null;
	setSelectedId: (id: string | null) => void;
	offLabel: string;
}) {
	const groups = useRef(new Map<string, Group>());
	useSyncExternalStore(sim.subscribe, () => [...sim.actors.keys()].join('\0'));
	useFrame(() => {
		for (const [id, group] of groups.current) {
			const actor = sim.actors.get(id);
			if (actor) group.position.set(actor.pos.x, 0, actor.pos.y);
		}
	});
	return (
		<>
			{[...sim.actors.values()].map((actor) => (
				<group
					key={actor.id}
					position={[actor.pos.x, 0, actor.pos.y]}
					ref={(group) => {
						if (group) groups.current.set(actor.id, group);
						else groups.current.delete(actor.id);
					}}
				>
					<Html zIndexRange={[500, 100]} portal={overlay}>
						<ActorOverlay
							actor={actor}
							sim={sim}
							selected={actor.id === selectedId}
							onSelect={() =>
								setSelectedId(actor.id === selectedId ? null : actor.id)
							}
							offLabel={offLabel}
						/>
					</Html>
				</group>
			))}
		</>
	);
}

/** The scene is shifted so the floor's centre is the origin; the camera orbits it. */
const TARGET: [number, number, number] = [0, 0, 0];

/**
 * Where the camera starts: in from the open front corner, far enough back to
 * take in the whole floor. The smallest office (two desk rows) fits at 13/15/13;
 * every extra row of desks pushes the camera back in proportion.
 */
function homeDistance(depth: number) {
	return Math.max(1, (FLOOR_W + depth) / 28);
}

function homePosition(depth: number, aspect = 1): [number, number, number] {
	const direction = new Vector3(13, 15, 13).normalize();
	const right = new Vector3(0, 1, 0).cross(direction).normalize();
	const up = direction.clone().cross(right);
	const vertical = Math.tan(Math.PI / 9); // 40 degree vertical field of view.
	const horizontal = vertical * aspect;
	let distance = 5;
	for (const x of [-FLOOR_W / 2, FLOOR_W / 2])
		for (const y of [0, px(WALL_H)])
			for (const z of [-depth / 2, depth / 2]) {
				const corner = new Vector3(x, y, z);
				distance = Math.max(
					distance,
					corner.dot(direction) +
						Math.max(
							Math.abs(corner.dot(right)) / horizontal,
							Math.abs(corner.dot(up)) / vertical,
						),
				);
			}
	return direction.multiplyScalar(distance * 1.18).toArray() as [number, number, number];
}

export type CameraCommand = {
	action: 'reset' | 'zoom-in' | 'zoom-out' | 'rotate-left' | 'rotate-right';
	sequence: number;
};

/** Fit every floor size and viewport, with single-click alternatives to dragging. */
function CameraRig({ depth, command }: { depth: number; command: CameraCommand }) {
	const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
	const camera = useThree((state) => state.camera);
	const size = useThree((state) => state.size);
	useEffect(() => {
		camera.position.set(...homePosition(depth, size.width / Math.max(1, size.height)));
		controls.current?.target.set(...TARGET);
		controls.current?.update();
	}, [camera, depth, size.width, size.height]);
	useEffect(() => {
		const orbit = controls.current;
		if (!orbit) return;
		if (command.action === 'reset') {
			camera.position.set(...homePosition(depth, size.width / Math.max(1, size.height)));
			orbit.target.set(...TARGET);
		} else {
			const offset = camera.position.clone().sub(orbit.target);
			if (command.action === 'zoom-in' || command.action === 'zoom-out')
				offset.setLength(
					Math.min(
						orbit.maxDistance,
						Math.max(
							orbit.minDistance,
							offset.length() * (command.action === 'zoom-in' ? 0.8 : 1.25),
						),
					),
				);
			else
				offset.applyAxisAngle(
					new Vector3(0, 1, 0),
					command.action === 'rotate-left' ? Math.PI / 8 : -Math.PI / 8,
				);
			camera.position.copy(orbit.target).add(offset);
		}
		orbit.update();
	}, [camera, command, depth, size.width, size.height]);
	return (
		<OrbitControls
			ref={controls}
			makeDefault
			target={TARGET}
			enableDamping={false}
			dampingFactor={0.12}
			minDistance={5}
			maxDistance={Math.max(
				45 * homeDistance(depth),
				Math.hypot(...homePosition(depth, size.width / Math.max(1, size.height))) * 2,
			)}
			minPolarAngle={0.15}
			maxPolarAngle={1.35}
			screenSpacePanning={false}
		/>
	);
}

function RendererEvents({ sim, onUnavailable }: { sim: OfficeSim; onUnavailable: () => void }) {
	const canvas = useThree((state) => state.gl.domElement);
	const invalidate = useThree((state) => state.invalidate);
	useEffect(() => {
		canvas.addEventListener('webglcontextlost', onUnavailable);
		const unsubscribe = sim.subscribe(() => invalidate());
		return () => {
			unsubscribe();
			canvas.removeEventListener('webglcontextlost', onUnavailable);
		};
	}, [canvas, invalidate, sim, onUnavailable]);
	return null;
}

export default function Office3D({
	layout,
	sim,
	selectedId,
	setSelectedId,
	roomNames,
	offLabel,
	cameraCommand,
	onUnavailable,
}: {
	layout: Layout;
	sim: OfficeSim;
	selectedId: string | null;
	setSelectedId: (id: string | null) => void;
	roomNames: Record<string, string>;
	offLabel: string;
	cameraCommand: CameraCommand;
	onUnavailable: () => void;
}) {
	const overlayRef = useRef<HTMLDivElement>(null);
	const overlay = overlayRef as Overlay;
	return (
		// `isolation` keeps the overlays' z-indexes below the page chrome; the clip keeps
		// off-screen overlays from growing the page.
		<div className="absolute inset-0 isolate overflow-hidden">
			{/* `flat` turns tone mapping off so palette colours reach the screen unchanged. */}
			<Canvas
				flat
				frameloop="demand"
				dpr={[1, 1.5]}
				camera={{
					position: homePosition(layout.depth),
					fov: 40,
					near: 0.1,
					far: Math.max(200, layout.depth * 20),
				}}
			>
				<RendererEvents sim={sim} onUnavailable={onUnavailable} />
				<color attach="background" args={[ROOM.background]} />
				<group position={[-FLOOR_W / 2, 0, -layout.depth / 2]}>
					<Shell layout={layout} />
					<Furniture layout={layout} sim={sim} />
					{roomLabels(layout).map((room) => (
						<RoomLabel
							key={room.key}
							at={room.at}
							name={roomNames[room.key]}
							overlay={overlay}
						/>
					))}
					<Actors
						sim={sim}
						selectedId={selectedId}
						setSelectedId={setSelectedId}
						offLabel={offLabel}
						overlay={overlay}
					/>
				</group>
				<CameraRig depth={layout.depth} command={cameraCommand} />
			</Canvas>
			{/* Zero-sized so the canvas keeps its pointer events; the overlays overflow it. */}
			<div ref={overlayRef} className="absolute top-0 left-0" />
		</div>
	);
}
