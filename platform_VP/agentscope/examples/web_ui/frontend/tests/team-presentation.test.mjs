import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const context = { exports: {}, require: createRequire(import.meta.url) };
vm.runInNewContext(
	ts.transpileModule(
		readFileSync(
			new URL('../src/components/chat/team-presentation.ts', import.meta.url),
			'utf8',
		),
		{
			compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
		},
	).outputText,
	context,
);
const { visibleTeamMessages, teamSayTarget } = context.exports;
const text = { id: 'text', type: 'text', text: 'Answer' };
const message = (metadata, content = [text], extra = {}) => ({
	id: 'reply',
	role: 'assistant',
	name: 'Leader',
	content,
	metadata,
	created_at: '2026-10-18T00:00:00Z',
	finished_reason: 'stop',
	...extra,
});
const call = {
	id: 'call',
	type: 'tool_call',
	name: 'TeamSay',
	input: JSON.stringify({ to: 'customer', content: 'private task' }),
};
const result = {
	id: 'call',
	type: 'tool_result',
	state: 'success',
	metadata: { effective_to: 'Worker@123' },
};

test('reply ownership overrides agent identity; internal completed prose stays hidden', () => {
	const msgs = [
		message({ team_agent_id: 'leader', team_reply_owner: false }),
		message({ team_agent_id: 'worker', team_reply_owner: true }),
	];
	const visible = visibleTeamMessages(msgs, 'leader', true);
	assert.equal(visible.length, 1);
	assert.equal(visible[0].message.metadata.team_agent_id, 'worker');
	assert.equal(visible[0].teamMode, 'customer-reply');
	assert.equal(visible[0].message.content[0].text, 'Answer');
});

test('effective recipient controls internal activity even when requested recipient was customer', () => {
	const msg = message({ team_reply_owner: true }, [text, call, result]);
	assert.equal(teamSayTarget(msg, call), 'Worker@123');
	const [visible] = visibleTeamMessages([msg], 'leader', true);
	assert.equal(
		visible.message.content.some((b) => b.type === 'text'),
		false,
	);
	assert.equal(visible.message.content.length, 2);
	assert.equal(msg.content.length, 3, 'filter must not mutate raw history used for HITL');
});

test('failed delegation retains the customer answer', () => {
	const msg = message({ team_reply_owner: true }, [text, call, { ...result, state: 'error' }]);
	assert.equal(visibleTeamMessages([msg], 'leader', true)[0].message.content[0].text, 'Answer');
});

test('finished reason without timestamp is terminal; running internal activity remains visible', () => {
	assert.equal(
		visibleTeamMessages([message({ team_reply_owner: false })], 'leader', true).length,
		0,
	);
	const running = message({ team_reply_owner: false }, [text], { finished_reason: null });
	const [visible] = visibleTeamMessages([running], 'leader', true);
	assert.equal(visible.teamMode, 'activity');
	assert.equal(visible.message.content.length, 0);
});

test('non-team chat keeps original messages and tool results', () => {
	const msg = message({}, [text, call, result]);
	assert.equal(visibleTeamMessages([msg], null, false)[0].message, msg);
});
