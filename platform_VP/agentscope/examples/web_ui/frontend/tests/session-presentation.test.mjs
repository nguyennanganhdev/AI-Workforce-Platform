import assert from 'node:assert/strict';
import test from 'node:test';
import { officeFromSession } from '../src/features/workforce/session/presentation.ts';
import { liveSessionPresentation } from '../src/features/workforce/session/live-adapter.ts';
import { mockSessionPresentation } from '../src/pages/mock/session-adapter.ts';
import { MOCK_CONVERSATIONS } from '../src/pages/mock/chat-mock-data.ts';

const msg = (id, content, extra = {}) => ({ id, name: 'Same name', role: 'assistant', metadata: {}, created_at: '2026-01-01T00:00:00Z', content, ...extra });
const text = (value) => ({ id: 'text', type: 'text', text: value, created_at: '2026-01-01T00:00:00Z' });
const live = (extra = {}) => liveSessionPresentation({ id: 'a', ownerId: 'owner', ownerName: 'Same name', agents: [], messages: [], replyPhase: 'idle', awaitingApproval: false, loading: false, ...extra });

test('all existing scripts project their revealed content without inventing activity', () => {
	for (const conversation of MOCK_CONVERSATIONS) {
		for (let count = 1; count <= conversation.events.length; count++) {
			const events = conversation.events.slice(0, count);
			const current = events.at(-1);
			const participant = current && 'agent' in current ? current.agent : undefined;
			const model = mockSessionPresentation(conversation.id, participant ? [participant] : [], events, current.kind !== 'gate');
			const office = officeFromSession(model);
			assert.equal(office.motion, 'events');
			assert.equal(new Set(model.messages.map(message => message.id)).size, model.messages.length);
			if (current.kind === 'gate') {
				assert.equal(model.phase, current.action === 'approval' ? 'waiting_approval' : current.action === 'reply' ? 'waiting_reply' : 'waiting_external');
				assert.ok(office.participants.every(agent => agent.status === 'idle'));
			}
		}
	}
});

test('typed answers are the same in chat and office; replay removes old activity', () => {
	const events = [{ id: 'u', kind: 'user', sender: 'User', text: 'scripted' }];
	const model = mockSessionPresentation('a', [], events, false, { u: 'My answer' });
	assert.equal(model.messages[0].content[0].text, 'My answer');
	assert.equal(officeFromSession(model).activity[0].text, 'My answer');
	assert.deepEqual(officeFromSession(mockSessionPresentation('a', [], [], false)).activity, []);
});

test('same names never attribute another member work or speech', () => {
	const model = live({ replyPhase: 'streaming', messages: [msg('r', [text('Hello')])], agents: [
		{ id: 'other', data: { name: 'Same name' } },
	] });
	const office = officeFromSession(model);
	assert.equal(office.participants.find(p => p.id === 'owner').status, 'working');
	assert.equal(office.participants.find(p => p.id === 'owner').message, 'Hello');
	assert.equal(office.participants.find(p => p.id === 'other').message, undefined);
	assert.equal(office.participants.find(p => p.id === 'other').status, 'idle');
});

test('reconnect upserts messages and loading a new session exposes no old transcript', () => {
	const model = live({ messages: [msg('r', [text('old')]), msg('r', [text('new')])] });
	assert.equal(model.messages.length, 1);
	assert.equal(officeFromSession(model).activity[0].text, 'new');
	const next = live({ id: 'b', loading: true, messages: model.messages });
	assert.notEqual(next.id, model.id);
	assert.equal(next.messages.length, 0);
});

test('approval/external waits override streaming, completed tools clear stale pending state', () => {
	const call = { id: 't', type: 'tool_call', name: 'Approve', input: '{}', state: 'asking', created_at: '2026-01-01T00:00:00Z' };
	assert.equal(live({ messages: [msg('r', [call])], replyPhase: 'streaming' }).phase, 'waiting_approval');
	assert.equal(live({ status: 'awaiting_external_result', replyPhase: 'streaming' }).phase, 'waiting_external');
	const result = { id: 't', type: 'tool_result', name: 'Approve', output: 'ok', state: 'success' };
	assert.equal(live({ messages: [msg('r', [call, result])] }).phase, 'idle');
});

test('paused tool remains unfinished and rejected branch never shows future success', () => {
	const tool = { id: 't', kind: 'tool', agent: 'planner', label: 'Book', input: '{}', summary: 'Booked', result: 'ok', effect: 'write' };
	const paused = mockSessionPresentation('a', ['planner'], [tool], false, {}, true);
	assert.equal(paused.phase, 'idle');
	assert.equal(paused.messages[0].finished_at, null);
	assert.equal(paused.messages[0].content.some(block => block.type === 'tool_result'), false);
	for (const conversation of MOCK_CONVERSATIONS) {
		const gateIndex = conversation.events.findIndex(event => event.kind === 'gate' && event.action === 'approval');
		if (gateIndex < 0) continue;
		const gate = conversation.events[gateIndex];
		const branch = [...conversation.events.slice(0, gateIndex + 1), ...gate.rejected];
		const model = mockSessionPresentation(conversation.id, [], branch, false);
		const allowed = new Set(branch.map(event => `${conversation.id}:${event.id}`));
		assert.ok(model.messages.every(message => allowed.has(message.id)));
	}
});
