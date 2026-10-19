import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const context = { exports: {}, require: () => ({}) };
vm.runInNewContext(ts.transpileModule(readFileSync(
	new URL('../src/components/chat/teamChatProjection.ts', import.meta.url),
	'utf8',
), {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, context);
const { projectTeamChatMessages } = context.exports;

const at = '2026-10-19T01:00:00Z';
const text = (id, value) => ({ type: 'text', id, text: value, created_at: at, finished_at: at });
const call = (id, to, content) => ({
	type: 'tool_call', id, name: 'TeamSay', state: 'finished', created_at: at,
	finished_at: at, input: JSON.stringify({ to, kind: 'question', content }),
});
const result = (id, state = 'success') => ({
	type: 'tool_result', id, name: 'TeamSay', state, output: '', metadata: {},
	created_at: at, finished_at: at,
});
const message = (id, name, content, metadata = {}, finished = true) => ({
	id, name, role: 'assistant', content, metadata, created_at: at,
	finished_at: finished ? at : undefined,
	finished_reason: finished ? 'completed' : undefined,
});
const user = (id, value) => ({
	id, name: 'Customer', role: 'user', content: [text(`${id}-text`, value)],
	metadata: {}, created_at: at, finished_at: at,
});

test('one customer turn exposes one trace instead of one row per agent handoff', () => {
	const projected = projectTeamChatMessages([
		user('user-1', 'Plan my trip'),
		message('coordinator', 'Coordinator', [
			call('hotel', 'Hotel', 'Find a hotel'), result('hotel', 'error'),
			call('restaurant', 'Restaurant', 'Find dinner'), result('restaurant', 'error'),
		], { team_agent_id: 'coordinator-agent', team_reply_owner: false }),
		message('hotel-reply', 'Hotel', [
			call('hotel-answer', 'Coordinator', 'Hotel options'), result('hotel-answer'),
		], { team_agent_id: 'hotel-agent', team_reply_owner: false }),
		message('leader', 'Workforce Leader', [text('answer', 'Here is your plan')], {
			team_agent_id: 'leader-agent', team_reply_owner: true,
		}),
	], 'leader-agent');

	assert.equal(projected.length, 2);
	assert.equal(projected[1].teamMode, 'customer-reply');
	assert.equal(
		projected[1].message.content.map((block) => block.type).join(','),
		'tool_call,tool_result,tool_call,tool_result,tool_call,tool_result,text',
	);
	assert.equal(projected[1].message.metadata.team_trace_sources.hotel, 'Coordinator');
	assert.equal(projected[1].message.metadata.team_trace_sources['hotel-answer'], 'Hotel');
});

test('an in-flight team turn renders one live Thinking trace', () => {
	const projected = projectTeamChatMessages([
		user('user-2', 'Continue'),
		message('coordinator-live', 'Coordinator', [
			call('flight', 'Flight', 'Find flights'),
		], { team_agent_id: 'coordinator-agent', team_reply_owner: false }, false),
		message('hotel-live', 'Hotel', [], {
			team_agent_id: 'hotel-agent', team_reply_owner: false,
		}, false),
	], 'leader-agent');

	assert.equal(projected.length, 2);
	assert.equal(projected[1].teamMode, 'activity');
	assert.equal(projected[1].message.id, 'team-trace:coordinator-live');
	assert.equal(projected[1].message.finished_at, null);
	assert.equal(projected[1].message.content.length, 1);
});
