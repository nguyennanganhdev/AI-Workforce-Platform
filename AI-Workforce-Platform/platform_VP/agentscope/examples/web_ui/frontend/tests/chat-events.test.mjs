import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const context = { exports: {}, require: createRequire(import.meta.url) };
vm.runInNewContext(ts.transpileModule(readFileSync(
  new URL('../src/utils/appendChatEvent.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, context);
const { appendChatEvent, mergeChatEvent } = context.exports;
const replay = (message) => {
  for (const event of [
    { type: 'TEXT_BLOCK_START' },
    { type: 'TEXT_BLOCK_DELTA', delta: 'Hello' },
    { type: 'TEXT_BLOCK_END', text: 'Hello', created_at: 'now' },
  ]) appendChatEvent(message, { reply_id: 'reply', block_id: 'text', ...event });
};
test('text replay cannot double a persisted or already streamed reply', () => {
  for (const finished of [undefined, 'before']) {
    const message = { id: 'reply', content: [
      { type: 'text', id: 'text', text: 'Hello', finished_at: finished },
    ] };
    replay(message);
    replay(message);
    assert.equal(message.content.length, 1);
    assert.equal(message.content[0].text, 'Hello');
  }
});
test('new streamed text and final server correction remain supported', () => {
  const message = { id: 'reply', content: [] };
  replay(message);
  appendChatEvent(message, { type: 'TEXT_BLOCK_END', reply_id: 'reply',
    block_id: 'text', text: 'Corrected', created_at: 'now' });
  assert.equal(message.content[0].text, 'Corrected');
  appendChatEvent(message, { type: 'TEXT_BLOCK_END', reply_id: 'another-ticket',
    block_id: 'text', text: 'Wrong ticket', created_at: 'now' });
  assert.equal(message.content[0].text, 'Corrected');
});

test('interleaved team replies keep text, tools and completion on the author bubble', () => {
  let messages = [];
  const apply = (event) => { messages = mergeChatEvent(messages, { created_at: '2026-10-14T08:00:00Z', ...event }); };
  apply({ type: 'REPLY_START', reply_id: 'hotel', name: 'Hotel', metadata: { team_agent_id: 'hotel-agent' } });
  apply({ type: 'REPLY_START', reply_id: 'flight', name: 'Flight', metadata: { team_agent_id: 'flight-agent' } });
  for (const [reply, text] of [['hotel', 'Hotel result'], ['flight', 'Flight result']]) {
    apply({ type: 'TEXT_BLOCK_START', reply_id: reply, block_id: `${reply}-text` });
    apply({ type: 'TEXT_BLOCK_DELTA', reply_id: reply, block_id: `${reply}-text`, delta: text });
  }
  apply({ type: 'REPLY_END', reply_id: 'hotel', finished_reason: 'completed' });
  assert.equal(messages[0].content[0].text, 'Hotel result');
  assert.equal(messages[1].content[0].text, 'Flight result');
  assert.equal(messages[0].finished_reason, 'completed');
  assert.equal(messages[1].finished_reason, undefined);
  assert.equal(messages[0].metadata.team_agent_id, 'hotel-agent');
  apply({ type: 'REPLY_START', reply_id: 'hotel', name: 'Hotel', metadata: { team_session_id: 'hotel-session' } });
  assert.equal(messages.length, 2);
  assert.equal(messages[0].content[0].text, 'Hotel result');
  assert.equal(messages[0].metadata.team_session_id, 'hotel-session');
});
