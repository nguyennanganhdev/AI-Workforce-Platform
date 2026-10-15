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
