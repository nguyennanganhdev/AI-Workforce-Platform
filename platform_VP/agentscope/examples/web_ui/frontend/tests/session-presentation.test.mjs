import assert from 'node:assert/strict';
import test from 'node:test';
import { officeFromSession } from '../src/features/workforce/session/presentation.ts';
import { liveSessionPresentation } from '../src/features/workforce/session/live-adapter.ts';

const msg = (id, content, extra = {}) => ({ id, name: 'Same name', role: 'assistant', metadata: {}, created_at: '2026-01-01T00:00:00Z', content, ...extra });
const text = (value) => ({ id: 'text', type: 'text', text: value, created_at: '2026-01-01T00:00:00Z' });
const live = (extra = {}) => liveSessionPresentation({ id: 'a', ownerId: 'owner', ownerName: 'Same name', agents: [], messages: [], replyPhase: 'idle', awaitingApproval: false, loading: false, ...extra });

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
