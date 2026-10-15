import type { GraphAgent } from './graph-model';
import type { SessionOfficeSnapshot } from '@/features/workforce/session-office/model';

/**
 * The office view: the same agents as the graph, drawn as people in an
 * isometric office who walk to a meeting, back to their desks, and over to
 * each other's desks to work something out.
 *
 * Everything here is a DEMO SCRIPT. The backend does not report meetings or
 * handoffs yet, so what the agents do is a fixed scenario on a loop; the canvas
 * says so in its own chrome.
 *
 * Coordinates are floor tiles: `x` runs down-right on screen, `y` down-left.
 */

export type Point = { x: number; y: number };

/* ------------------------------------------------------------------ */
/* Projection                                                          */
/* ------------------------------------------------------------------ */

export const HALF_W = 36;
export const HALF_H = 18;
export const WALL_H = 96;
const PAD = 48;

/** Floor width in tiles. The depth grows with the number of desk rows. */
export const FLOOR_W = 16;

export type Projection = {
	width: number;
	height: number;
	at: (p: Point, lift?: number) => { sx: number; sy: number };
};

export function projection(depth: number): Projection {
	const ox = PAD + depth * HALF_W;
	const oy = PAD + WALL_H;
	return {
		width: (FLOOR_W + depth) * HALF_W + PAD * 2,
		height: (FLOOR_W + depth) * HALF_H + WALL_H + PAD * 2,
		at: ({ x, y }, lift = 0) => ({
			sx: ox + (x - y) * HALF_W,
			sy: oy + (x + y) * HALF_H - lift,
		}),
	};
}

/* ------------------------------------------------------------------ */
/* Layout                                                              */
/* ------------------------------------------------------------------ */

/** Where an agent sits, and how it gets out to the corridor. */
export type Desk = {
	agentId: string;
	/** Centre of the desk top. */
	desk: Point;
	/** Where the agent sits, in front of the desk. */
	chair: Point;
	/** Chair → corridor, in walking order. */
	chain: Point[];
	/** Where a visiting colleague stands, beside the chair. */
	visit: Point;
	/** The row lane and aisle this desk opens onto. */
	lane: number;
	aisle: number;
};

export type Seat = { at: Point; chain: Point[] };

export type Layout = {
	depth: number;
	desks: Map<string, Desk>;
	leader: { desk: Point; chair: Point; chain: Point[] };
	/** The head of the meeting table, then the seats round it. */
	head: Seat;
	seats: Seat[];
	approval: { desk: Point; user: Point; visit: Point; chain: Point[] };
	reception: { counter: Point; door: Point; front: Point };
	rooms: {
		meeting: { x0: number; y0: number; x1: number; y1: number };
		approval: { x0: number; y0: number; x1: number; y1: number };
		reception: { x0: number; y0: number; x1: number; y1: number };
	};
};

/** The corridor between the rooms along the back wall and the open desks. */
const CORRIDOR_Y = 4.9;
const DESK_COLUMNS = [8, 11, 14];
const FIRST_ROW = 6.6;
const ROW_GAP = 3;
const MEETING_DOOR = 2.5;
const SEAT_XS = [1.9, 2.7, 3.5, 4.3];

export function buildLayout(agents: GraphAgent[]): Layout {
	const rows = Math.max(2, Math.ceil(agents.length / DESK_COLUMNS.length));
	const depth = FIRST_ROW + (rows - 1) * ROW_GAP + 2.4;

	const desks = new Map<string, Desk>();
	agents.forEach((agent, index) => {
		const cx = DESK_COLUMNS[index % DESK_COLUMNS.length];
		const ry = FIRST_ROW + Math.floor(index / DESK_COLUMNS.length) * ROW_GAP;
		const lane = ry + 1.8;
		const aisle = cx - 1.5;
		const chair = { x: cx, y: ry + 0.9 };
		desks.set(agent.id, {
			agentId: agent.id,
			desk: { x: cx, y: ry },
			chair,
			lane,
			aisle,
			visit: { x: cx + 1, y: ry + 1.1 },
			chain: [chair, { x: cx, y: lane }, { x: aisle, y: lane }, { x: aisle, y: CORRIDOR_Y }],
		});
	});

	const inside = { x: 5.3, y: MEETING_DOOR };
	const outside = [
		{ x: 6.8, y: MEETING_DOOR },
		{ x: 6.8, y: CORRIDOR_Y },
	];
	const seats: Seat[] = [];
	SEAT_XS.forEach((x) => {
		// Alternate far and near so a small meeting fills both sides.
		const far = { x, y: 1.35 };
		const near = { x, y: 3.65 };
		seats.push({ at: far, chain: [far, { x: 5.3, y: 1.35 }, inside, ...outside] });
		seats.push({ at: near, chain: [near, { x: 5.3, y: 3.65 }, inside, ...outside] });
	});
	const headAt = { x: 0.85, y: 2.5 };

	const leaderChair = { x: 8.6, y: 2.5 };
	const approvalVisit = { x: 13.3, y: 2.9 };

	return {
		depth,
		desks,
		leader: {
			desk: { x: 8.6, y: 1.6 },
			chair: leaderChair,
			chain: [leaderChair, { x: 8.6, y: 3.6 }, { x: 8.6, y: CORRIDOR_Y }],
		},
		head: {
			at: headAt,
			chain: [headAt, { x: 0.9, y: 4.3 }, { x: 5.3, y: 4.3 }, inside, ...outside],
		},
		seats,
		approval: {
			desk: { x: 13.5, y: 1.5 },
			user: { x: 13.5, y: 0.75 },
			visit: approvalVisit,
			chain: [
				approvalVisit,
				{ x: 11.9, y: 3 },
				{ x: 10.3, y: 3 },
				{ x: 10.3, y: CORRIDOR_Y },
			],
		},
		reception: {
			counter: { x: 2.8, y: depth - 3.3 },
			door: { x: 0.15, y: depth - 1.6 },
			front: { x: 2.8, y: depth - 2.25 },
		},
		rooms: {
			meeting: { x0: 0, y0: 0, x1: 6, y1: 5 },
			approval: { x0: 11, y0: 0, x1: FLOOR_W, y1: 4.5 },
			reception: { x0: 0, y0: 5.6, x1: 5.6, y1: depth },
		},
	};
}

/** A route from one place's chain out to the corridor and in along another's. */
export function route(from: Point[], to: Point[]): Point[] {
	return [...from.slice(1), ...[...to].reverse()];
}

/** Desk to desk without the corridor: along the row lane, down the aisle. */
export function deskToDesk(from: Desk, to: Desk): Point[] {
	return [
		{ x: from.chair.x, y: from.lane },
		{ x: from.aisle, y: from.lane },
		{ x: to.aisle, y: from.lane },
		{ x: to.aisle, y: to.lane },
		{ x: to.visit.x, y: to.lane },
		to.visit,
	];
}

/* ------------------------------------------------------------------ */
/* Simulation                                                          */
/* ------------------------------------------------------------------ */

export type ActorKind = 'agent' | 'leader' | 'resident' | 'user' | 'mail';
export type ActorStatus = 'idle' | 'working' | 'off';

export type Actor = {
	id: string;
	kind: ActorKind;
	name: string;
	pos: Point;
	path: Point[];
	/** Tiles per second. */
	speed: number;
	status: ActorStatus;
	carrying: boolean;
	bubble: { text: string; until: number } | null;
	onArrive: (() => void) | null;
	/** -1 facing left on screen, 1 facing right. */
	facing: 1 | -1;
};

export type LogEntry = { id: number; time: number; text: string };

export type Phase =
	| 'idle'
	| 'request'
	| 'call'
	| 'meeting'
	| 'return'
	| 'work'
	| 'collab'
	| 'approval'
	| 'done';

class Aborted extends Error {}

/**
 * The office's clock and the people in it. Time only moves while playing, so
 * a paused scene holds mid-stride and the script waits with it.
 */
export class OfficeSim {
	private listeners = new Set<() => void>();

	/** UI subscribers choose their own snapshot, excluding frame-by-frame positions. */
	subscribe = (listener: () => void) => {
		this.listeners.add(listener);
		return () => {
			this.listeners.delete(listener);
		};
	};

	publish() {
		this.listeners.forEach((listener) => listener());
	}

	/** Replace presentation state without starting the standalone demo. */
	applySession(snapshot: SessionOfficeSnapshot, layout: Layout) {
		const leader = snapshot.participants.find((participant) => participant.id === LEADER_ID);
		if (!leader) this.actors.delete(LEADER_ID);
		else if (!this.actors.has(LEADER_ID))
			this.add({
				id: LEADER_ID,
				kind: 'leader',
				name: leader.name,
				pos: layout.leader.chair,
				status: 'idle',
			});
		for (const actor of this.actors.values()) {
			const participant = snapshot.participants.find((p) => p.id === actor.id);
			actor.status = participant?.status ?? 'idle';
			actor.bubble = participant?.message
				? { text: participant.message, until: Infinity }
				: null;
		}
		this.phase = snapshot.phase;
		this.log = snapshot.activity
			.slice(-6)
			.map((entry, index) => ({ id: index, time: 0, text: entry.text }));
		this.publish();
	}

	actors = new Map<string, Actor>();
	log: LogEntry[] = [];
	phase: Phase = 'idle';
	time = 0;
	speed = 1;
	playing = true;
	private aborted = false;
	private timers: { at: number; resolve: () => void }[] = [];
	private logId = 0;

	add(
		actor: Omit<Actor, 'path' | 'bubble' | 'onArrive' | 'carrying' | 'facing' | 'speed'> & {
			speed?: number;
		},
	) {
		this.actors.set(actor.id, {
			path: [],
			bubble: null,
			onArrive: null,
			carrying: false,
			facing: 1,
			speed: 2.4,
			...actor,
		});
	}

	remove(id: string) {
		this.actors.delete(id);
	}

	togglePlaying() {
		this.playing = !this.playing;
	}

	/** 1× → 2× → 0.5× → 1×. */
	cycleSpeed() {
		this.speed = this.speed === 1 ? 2 : this.speed === 2 ? 0.5 : 1;
	}

	abort() {
		this.aborted = true;
		this.timers = [];
		this.actors.forEach((actor) => (actor.onArrive = null));
	}

	/** Advance by `dt` real milliseconds. */
	tick(dt: number) {
		if (!this.playing || this.aborted) return;
		const step = dt * this.speed;
		this.time += step;

		this.actors.forEach((actor) => {
			if (actor.bubble && actor.bubble.until <= this.time) actor.bubble = null;
			let budget = (actor.speed * step) / 1000;
			while (budget > 0 && actor.path.length > 0) {
				const next = actor.path[0];
				const dx = next.x - actor.pos.x;
				const dy = next.y - actor.pos.y;
				const distance = Math.hypot(dx, dy);
				// Screen x grows with x - y; face the way the screen motion goes.
				if (Math.abs(dx - dy) > 0.01) actor.facing = dx - dy > 0 ? 1 : -1;
				if (distance <= budget) {
					actor.pos = { ...next };
					actor.path.shift();
					budget -= distance;
				} else {
					actor.pos = {
						x: actor.pos.x + (dx / distance) * budget,
						y: actor.pos.y + (dy / distance) * budget,
					};
					budget = 0;
				}
			}
			if (actor.path.length === 0 && actor.onArrive) {
				const done = actor.onArrive;
				actor.onArrive = null;
				done();
			}
		});

		const due = this.timers.filter((timer) => timer.at <= this.time);
		if (due.length) {
			this.timers = this.timers.filter((timer) => timer.at > this.time);
			due.forEach((timer) => timer.resolve());
		}
	}

	private check() {
		if (this.aborted) throw new Aborted();
	}

	async wait(ms: number) {
		this.check();
		await new Promise<void>((resolve) => this.timers.push({ at: this.time + ms, resolve }));
		this.check();
	}

	async walk(id: string, path: Point[], delay = 0) {
		if (delay) await this.wait(delay);
		this.check();
		const actor = this.actors.get(id);
		if (!actor || path.length === 0) return;
		await new Promise<void>((resolve) => {
			actor.path = [...path];
			actor.onArrive = resolve;
		});
		this.check();
	}

	/** Show a speech bubble and wait while it is read. */
	async say(id: string, text: string, ms = 2200) {
		this.check();
		const actor = this.actors.get(id);
		if (actor) actor.bubble = { text, until: this.time + ms };
		await this.wait(ms);
	}

	/** A bubble that does not hold the script up. */
	pop(id: string, text: string, ms = 1600) {
		const actor = this.actors.get(id);
		if (actor) actor.bubble = { text, until: this.time + ms };
	}

	note(text: string, phase?: Phase) {
		if (phase) this.phase = phase;
		this.logId += 1;
		this.log = [...this.log.slice(-5), { id: this.logId, time: this.time, text }];
	}

	static isAbort(error: unknown) {
		return error instanceof Aborted;
	}
}

export const LEADER_ID = 'leader';
export const USER_ID = 'you';

/** Seat everyone at their desk. */
export function populate(sim: OfficeSim, layout: Layout, agents: GraphAgent[]) {
	sim.add({
		id: LEADER_ID,
		kind: 'leader',
		name: 'Leader',
		pos: layout.leader.chair,
		status: 'idle',
	});
	sim.add({ id: USER_ID, kind: 'user', name: 'Bạn', pos: layout.approval.user, status: 'idle' });
	agents.forEach((agent) =>
		sim.add({
			id: agent.id,
			kind: 'agent',
			name: agent.name,
			pos: layout.desks.get(agent.id)!.chair,
			status: agent.invitable ? 'idle' : 'off',
		}),
	);
}
