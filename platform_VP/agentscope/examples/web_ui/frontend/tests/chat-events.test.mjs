import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const context = { exports: {}, require: createRequire(import.meta.url) };
vm.runInNewContext(
	ts.transpileModule(
		readFileSync(new URL('../src/utils/appendChatEvent.ts', import.meta.url), 'utf8'),
		{
			compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
		},
	).outputText,
	context,
);
const { appendChatEvent } = context.exports;
const replay = (message) => {
	for (const event of [
		{ type: 'TEXT_BLOCK_START' },
		{ type: 'TEXT_BLOCK_DELTA', delta: 'Hello' },
		{ type: 'TEXT_BLOCK_END', text: 'Hello', created_at: 'now' },
	])
		appendChatEvent(message, { reply_id: 'reply', block_id: 'text', ...event });
};
test('text replay cannot double a persisted or already streamed reply', () => {
	for (const finished of [undefined, 'before']) {
		const message = {
			id: 'reply',
			content: [{ type: 'text', id: 'text', text: 'Hello', finished_at: finished }],
		};
		replay(message);
		replay(message);
		assert.equal(message.content.length, 1);
		assert.equal(message.content[0].text, 'Hello');
	}
});
test('new streamed text and final server correction remain supported', () => {
	const message = { id: 'reply', content: [] };
	replay(message);
	appendChatEvent(message, {
		type: 'TEXT_BLOCK_END',
		reply_id: 'reply',
		block_id: 'text',
		text: 'Corrected',
		created_at: 'now',
	});
	assert.equal(message.content[0].text, 'Corrected');
	appendChatEvent(message, {
		type: 'TEXT_BLOCK_END',
		reply_id: 'another-ticket',
		block_id: 'text',
		text: 'Wrong ticket',
		created_at: 'now',
	});
	assert.equal(message.content[0].text, 'Corrected');
});

test('interleaved team replies retain their own text and reply-owner metadata', () => {
	const { mergeChatEvent } = context.exports;
	let messages = [];
	for (const [id, owner] of [
		['leader', false],
		['worker', true],
	]) {
		messages = mergeChatEvent(messages, {
			type: 'REPLY_START',
			reply_id: id,
			name: id,
			created_at: '2026-10-18T00:00:00Z',
			metadata: { team_reply_owner: owner },
		});
	}
	for (const id of ['leader', 'worker']) {
		for (const event of [
			{ type: 'TEXT_BLOCK_START' },
			{ type: 'TEXT_BLOCK_DELTA', delta: id },
			{ type: 'TEXT_BLOCK_END', text: id, created_at: '2026-10-18T00:00:01Z' },
		]) {
			messages = mergeChatEvent(messages, { reply_id: id, block_id: 'text-' + id, ...event });
		}
	}
	assert.equal(messages[0].content[0].text, 'leader');
	assert.equal(messages[1].content[0].text, 'worker');
	assert.equal(messages[0].metadata.team_reply_owner, false);
	assert.equal(messages[1].metadata.team_reply_owner, true);
	const originalWorker = messages[1];
	messages = mergeChatEvent(messages, {
		type: 'REPLY_START',
		reply_id: 'leader',
		name: 'leader',
		metadata: { team_agent_id: 'agent-id' },
	});
	assert.equal(messages.length, 2);
	assert.equal(messages[0].metadata.team_reply_owner, false);
	assert.equal(messages[0].metadata.team_agent_id, 'agent-id');
	assert.equal(messages[1], originalWorker);
});
