import assert from 'node:assert/strict';
import test from 'node:test';
import { OfficeSim, buildLayout, populate } from '../src/pages/agents/office-sim.ts';

const agent = { id: 'planner', name: 'Planner', role: '', invitable: true, real: null };
const layout = buildLayout([agent]);
function office() {
	const sim = new OfficeSim();
	populate(sim, layout, [agent]);
	return sim;
}
function snapshot(overrides = {}) {
	return { id: 'mock:a', source: 'mock', phase: 'work',
		participants: [{ id: 'planner', name: 'Planner', role: '', status: 'working', message: 'Hello' }],
		activity: [{ id: 'event-a', text: 'Started' }], ...overrides };
}

test('session state updates only its own office and excludes an absent leader', () => {
	const a = office(), b = office();
	a.applySession(snapshot(), layout);
	assert.equal(a.actors.get('planner').status, 'working');
	assert.equal(a.actors.get('planner').bubble.text, 'Hello');
	assert.equal(a.actors.has('leader'), false);
	assert.equal(b.actors.get('planner').status, 'idle');
	assert.equal(b.log.length, 0);
});

test('replay replaces prior activity and clears stale speech and work', () => {
	const sim = office();
	sim.applySession(snapshot(), layout);
	sim.applySession(snapshot({ phase: 'idle', participants: [], activity: [{ id: 'event-b', text: 'Reset' }] }), layout);
	assert.equal(sim.actors.get('planner').status, 'idle');
	assert.equal(sim.actors.get('planner').bubble, null);
	assert.equal(sim.phase, 'idle');
	assert.deepEqual(sim.log.map(entry => entry.text), ['Reset']);
});

test('leader can join after the first event and subscriptions are cleaned up', () => {
	const sim = office();
	sim.applySession(snapshot(), layout);
	let notifications = 0;
	const unsubscribe = sim.subscribe(() => notifications++);
	sim.applySession(snapshot({ participants: [{ id: 'leader', name: 'Leader', status: 'working' }] }), layout);
	assert.equal(sim.actors.get('leader').status, 'working');
	assert.equal(notifications, 1);
	unsubscribe(); sim.publish();
	assert.equal(notifications, 1);
});

/* Choreography of one request: call, meet, pair up, report, approval. */

const team = ['plumbing', 'technical', 'reception', 'hotel'].map((id) => ({ id, name: id, role: '', invitable: true, real: null }));
const teamLayout = buildLayout(team);
const near = (a, b) => Math.hypot(a.x - b.x, a.y - b.y) < 0.05;

function room() {
	const sim = new OfficeSim();
	populate(sim, teamLayout, team);
	return sim;
}
function turnSnapshot(overrides = {}) {
	return {
		id: 'live:a', source: 'live', motion: 'events', phase: 'work', turn: '1', hostId: 'leader',
		called: [], exchanges: [], activity: [],
		participants: [{ id: 'leader', name: 'Leader', role: '', status: 'working' },
			...team.map(({ id }) => ({ id, name: id, role: '', status: 'idle' }))],
		...overrides,
	};
}
/** Advance simulated time, letting each arrival's continuation run between frames. */
async function run(sim, ms) {
	for (let t = 0; t < ms; t += 50) {
		sim.tick(50);
		await new Promise((resolve) => setImmediate(resolve));
	}
}
/** Advance until `done()` holds; fail after `limit` simulated ms. */
async function until(sim, done, label, limit = 30000) {
	for (let t = 0; t < limit; t += 50) {
		if (done()) return;
		await run(sim, 50);
	}
	assert.fail(`timed out: ${label}`);
}
const chair = (id) => teamLayout.desks.get(id).chair;
const at = (sim, id, point) => () => near(sim.actors.get(id).pos, point);

test('only called members meet the host; the rest stay at their desks', async () => {
	const sim = room();
	sim.applySession(turnSnapshot({ called: ['plumbing', 'technical'] }), teamLayout);
	await until(sim, at(sim, 'leader', teamLayout.head.at), 'host at the head');
	await until(sim, at(sim, 'plumbing', teamLayout.seats[0].at), 'first callee seated');
	await until(sim, at(sim, 'technical', teamLayout.seats[1].at), 'second callee seated');
	assert.ok(at(sim, 'reception', chair('reception'))(), 'uncalled stays');
	assert.ok(at(sim, 'hotel', chair('hotel'))(), 'uncalled stays');
});

test('after the one meeting everyone works at their own desk; nobody walks to report', async () => {
	const sim = room();
	sim.applySession(turnSnapshot({ called: ['plumbing', 'technical'] }), teamLayout);
	await until(sim, at(sim, 'technical', teamLayout.seats[1].at), 'meeting gathers');
	await until(sim, at(sim, 'plumbing', chair('plumbing')), 'back at own desk');
	await until(sim, at(sim, 'technical', chair('technical')), 'back at own desk');
	await until(sim, at(sim, 'leader', teamLayout.leader.chair), 'host back at its desk');
	// Called again later, or reporting progress: they stay put.
	sim.applySession(turnSnapshot({ called: ['plumbing', 'technical', 'hotel'] }), teamLayout);
	await run(sim, 6000);
	for (const id of ['plumbing', 'technical', 'hotel']) assert.ok(at(sim, id, chair(id))(), `${id} stays`);
	assert.ok(at(sim, 'leader', teamLayout.leader.chair)(), 'no second meeting');
});

test('a member who needs another walks to that desk, asks, and comes back', async () => {
	const sim = room();
	sim.applySession(turnSnapshot({ called: ['plumbing', 'technical'] }), teamLayout);
	sim.applySession(turnSnapshot({ called: ['plumbing', 'technical'], exchanges: [{ from: 'plumbing', to: 'technical' }] }), teamLayout);
	// The question waits for the meeting to split up.
	await until(sim, at(sim, 'plumbing', teamLayout.seats[0].at), 'meets first');
	await until(sim, at(sim, 'plumbing', teamLayout.desks.get('technical').visit), 'at the colleague desk');
	assert.ok(at(sim, 'technical', chair('technical'))(), 'the one asked stays at its desk');
	await until(sim, at(sim, 'plumbing', chair('plumbing')), 'back after asking');
});

test('the host takes the result to your office for approval, then back', async () => {
	const sim = room();
	sim.applySession(turnSnapshot({ called: ['reception'] }), teamLayout);
	await until(sim, at(sim, 'reception', teamLayout.seats[0].at), 'meets');
	sim.applySession(turnSnapshot({ phase: 'approval', called: ['reception'] }), teamLayout);
	await until(sim, at(sim, 'leader', teamLayout.approval.visit), 'host at your office');
	sim.applySession(turnSnapshot({ phase: 'done', called: ['reception'] }), teamLayout);
	await until(sim, at(sim, 'leader', teamLayout.leader.chair), 'host back after approval');
	assert.ok(at(sim, 'reception', chair('reception'))());
});

test('a request the host handles alone moves nobody', async () => {
	const sim = room();
	sim.applySession(turnSnapshot(), teamLayout);
	await run(sim, 3000);
	assert.ok(at(sim, 'leader', teamLayout.leader.chair)());
	for (const { id } of team) assert.ok(at(sim, id, chair(id))());
});

test('a new request sends everyone home and starts over', async () => {
	const sim = room();
	sim.applySession(turnSnapshot({ called: ['hotel'] }), teamLayout);
	await until(sim, at(sim, 'hotel', teamLayout.seats[0].at), 'first request meets');
	sim.applySession(turnSnapshot({ turn: '2', called: [] }), teamLayout);
	await until(sim, at(sim, 'hotel', chair('hotel')), 'home on the new request');
	await until(sim, at(sim, 'leader', teamLayout.leader.chair), 'host home on the new request');
});

test('one request means one meeting, however often the same state arrives', async () => {
	const sim = room();
	const seats = [teamLayout.head.at, ...teamLayout.seats.map((seat) => seat.at)];
	const seatedCount = new Map();
	const wasSeated = new Map();
	const steps = [
		{ called: ['plumbing'] },
		{ called: ['plumbing', 'technical'] },
		{ called: ['plumbing', 'technical'], exchanges: [{ from: 'plumbing', to: 'technical' }] },
		{ phase: 'approval', called: ['plumbing', 'technical'], exchanges: [{ from: 'plumbing', to: 'technical' }] },
		{ phase: 'done', called: ['plumbing', 'technical'], exchanges: [{ from: 'plumbing', to: 'technical' }] },
	];
	for (const step of steps) {
		// Re-applying the same snapshot (re-renders, React StrictMode) must not call anyone again.
		sim.applySession(turnSnapshot(step), teamLayout);
		sim.applySession(turnSnapshot(step), teamLayout);
		for (let t = 0; t < 8000; t += 50) {
			await run(sim, 50);
			for (const [id, actor] of sim.actors) {
				// Seated means stopped at a seat, not walking past one.
				const seated = actor.path.length === 0 && seats.some((seat) => near(seat, actor.pos));
				if (seated && !wasSeated.get(id)) seatedCount.set(id, (seatedCount.get(id) ?? 0) + 1);
				wasSeated.set(id, seated);
			}
		}
	}
	assert.deepEqual(Object.fromEntries(seatedCount), { leader: 1, plumbing: 1, technical: 1 });
});
