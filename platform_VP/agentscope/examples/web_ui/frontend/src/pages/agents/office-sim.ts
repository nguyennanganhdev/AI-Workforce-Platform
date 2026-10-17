import type { GraphAgent } from './graph-model';
import type { SessionOfficeSnapshot } from '@/features/workforce/session-office/model';

/**
 * The office view: the same agents as the graph, drawn as people in a
 * 3D office who walk to a meeting, back to their desks, and over to
 * each other's desks to work something out.
 *
 * A live session drives it (see `applySession`): the host calls the members a
 * request needs to the meeting table once, they work at their own desks and
 * report progress from there, a member who needs another walks over to that
 * one's desk, and the host takes the result to your office for approval. The
 * last one to speak shows a bubble.
 *
 * Coordinates are floor tiles: `x` runs along the back wall, `y` away from it.
 */

export type Point = { x: number; y: number };

/** Wall height, in the design pixels the 3D view scales from (40 per tile). */
export const WALL_H = 96;

/** Floor width in tiles. The depth grows with the number of desk rows. */
export const FLOOR_W = 16;

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

/** How long, in simulated ms, people stay at the table and at a colleague's desk. */
const MEETING_MS = 3500;
const COLLAB_MS = 4500;

/** A spot someone can stand at, with its way out to the corridor (`chain`, spot first). */
type Place = { key: string; chain: Point[] };

/** Under reduced motion people are placed, not walked. */
function prefersStill() {
	return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

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

/** Where each room's name label sits on the floor. */
export function roomLabels(layout: Layout): { key: string; at: Point }[] {
	return [
		{ key: 'meeting', at: { x: 3, y: 4.55 } },
		{ key: 'approval', at: { x: 13.6, y: 4.1 } },
		{ key: 'reception', at: { x: 2.8, y: layout.depth - 0.55 } },
		{ key: 'workspace', at: { x: 11, y: 5.45 } },
	];
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
	/** Which way the figure is mirrored: 1 when walking towards +x−y, else -1. */
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
		this.direct(snapshot, layout);
		this.phase = snapshot.phase;
		this.log = snapshot.activity
			.slice(-6)
			.map((entry, index) => ({ id: index, time: 0, text: entry.text }));
		this.publish();
	}

	/* ---------------------------------------------------------------- */
	/* Session choreography                                             */
	/* ---------------------------------------------------------------- */

	/** Where each person stands now, as a way out to the corridor. */
	private placeOf = new Map<string, Place>();
	/** Each person's moves, run one after another. */
	private queues = new Map<string, Promise<void>>();
	private turn: string | null = null;
	/** Called members already seated at this turn's meeting. */
	private seated = new Set<string>();
	/** How many of this turn's exchanges have been walked. */
	private exchangesSeen = 0;
	/** The meeting, open while people still gather; settles once they split up. */
	private meeting: Promise<void> | null = null;
	private meetingOpen = false;
	private meetingMembers: string[] = [];
	private atApproval = false;

	/**
	 * Move the room through one request: the host calls the members it needs to
	 * the meeting table once, they go back to work at their own desks (progress
	 * shows as speech, nobody walks to report), and a member who needs another
	 * walks over to that one's desk to ask, then back. The host takes the result
	 * to your office for approval. Members nobody called stay at their desks.
	 */
	private direct(snapshot: SessionOfficeSnapshot, layout: Layout) {
		const host = snapshot.hostId && this.home(snapshot.hostId, layout) ? snapshot.hostId : null;
		const turn = snapshot.turn ?? '';

		if (turn !== this.turn) {
			this.turn = turn;
			this.seated.clear();
			this.exchangesSeen = 0;
			this.meeting = null;
			this.meetingOpen = false;
			this.meetingMembers = [];
			for (const id of this.actors.keys()) this.go(id, this.home(id, layout), layout);
		}
		if (!host) return;

		if (snapshot.phase === 'work') {
			for (const id of snapshot.called ?? []) {
				if (id === host || this.seated.has(id) || !layout.desks.has(id)) continue;
				this.call(host, id, layout);
			}
		}
		const exchanges = snapshot.exchanges ?? [];
		for (const { from, to } of exchanges.slice(this.exchangesSeen)) {
			if (from === to || !layout.desks.has(from) || !layout.desks.has(to)) continue;
			this.afterMeeting(() => {
				this.go(from, this.visit(to, layout), layout, COLLAB_MS);
				this.go(from, this.home(from, layout), layout);
			});
		}
		this.exchangesSeen = Math.max(this.exchangesSeen, exchanges.length);
		const approval = snapshot.phase === 'approval';
		if (approval !== this.atApproval) {
			this.atApproval = approval;
			this.afterMeeting(() =>
				this.go(
					host,
					approval ? { key: 'approval', chain: layout.approval.chain } : this.home(host, layout),
					layout,
				),
			);
		}
		if (snapshot.phase === 'idle' || snapshot.phase === 'done') {
			this.afterMeeting(() => {
				for (const id of this.actors.keys()) this.go(id, this.home(id, layout), layout);
			});
		}
	}

	/**
	 * Seat a called member at the meeting, opening it on the first call. There is
	 * one meeting a request: called once it has split up, a member takes the work
	 * at its own desk.
	 */
	private call(host: string, id: string, layout: Layout) {
		if (!this.meeting) {
			this.meetingOpen = true;
			this.go(host, { key: 'head', chain: layout.head.chain }, layout);
			this.meeting = this.meet(host, layout);
		}
		const seat = layout.seats[this.meetingMembers.length];
		if (!this.meetingOpen || !seat) return;
		this.seated.add(id);
		this.go(id, { key: `seat:${this.meetingMembers.length}`, chain: seat.chain }, layout);
		this.meetingMembers.push(id);
	}

	/** Hold the meeting until everyone called so far is seated, then send all back to their desks. */
	private async meet(host: string, layout: Layout) {
		const turn = this.turn;
		try {
			// Calls usually arrive one by one; wait until nobody new is on the way.
			let seen = -1;
			while (seen !== this.meetingMembers.length) {
				seen = this.meetingMembers.length;
				await Promise.all([host, ...this.meetingMembers].map((id) => this.queues.get(id)));
				await this.wait(MEETING_MS);
				if (this.turn !== turn) return;
			}
			this.meetingOpen = false;
			for (const id of [host, ...this.meetingMembers]) this.go(id, this.home(id, layout), layout);
			await Promise.all([host, ...this.meetingMembers].map((id) => this.queues.get(id)));
		} catch (error) {
			if (!OfficeSim.isAbort(error)) throw error;
		}
	}

	/** Run `then` once the meeting (if any) has split up, unless a new request came in. */
	private afterMeeting(then: () => void) {
		const turn = this.turn;
		void (this.meeting ?? Promise.resolve()).then(() => {
			if (this.turn === turn) then();
		});
	}

	/** Queue a walk to `place`, then an optional pause there. */
	private go(id: string, place: Place | null, layout: Layout, hold = 0) {
		const actor = this.actors.get(id);
		if (!actor || !place) return;
		const next = (this.queues.get(id) ?? Promise.resolve())
			.then(async () => {
				const from = this.placeOf.get(id) ?? this.home(id, layout);
				if (from && from.key !== place.key) {
					const path = route(from.chain, place.chain);
					if (prefersStill()) {
						actor.pos = { ...path[path.length - 1] };
						actor.path = [];
					} else {
						await this.walk(id, path);
					}
				}
				this.placeOf.set(id, place);
				if (hold) await this.wait(hold);
			})
			.catch((error: unknown) => {
				if (!OfficeSim.isAbort(error)) throw error;
			});
		this.queues.set(id, next);
	}

	/** Someone's own seat: an agent's desk chair, or the Leader's. */
	private home(id: string, layout: Layout): Place | null {
		if (id === LEADER_ID) return { key: 'home', chain: layout.leader.chain };
		const desk = layout.desks.get(id);
		return desk ? { key: 'home', chain: desk.chain } : null;
	}

	/** Beside a colleague's chair, reached along their row. */
	private visit(id: string, layout: Layout): Place | null {
		const desk = layout.desks.get(id);
		if (!desk) return null;
		return {
			key: `visit:${id}`,
			chain: [
				desk.visit,
				{ x: desk.visit.x, y: desk.lane },
				{ x: desk.aisle, y: desk.lane },
				{ x: desk.aisle, y: CORRIDOR_Y },
			],
		};
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
