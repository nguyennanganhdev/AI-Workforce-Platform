import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const flush = async () => {
  await new Promise(setImmediate);
  await new Promise(setImmediate);
};
function load(path, mocks = {}, globals = {}) {
  const context = { exports: {}, require: (id) => mocks[id] ?? require(id), ...globals };
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX },
  }).outputText, context);
  return context.exports;
}
const call = (id) => ({ type: 'tool_call', id, name: `mcp__travel__book_${id}`,
  input: '{}', state: 'asking' });
const reply = (id, session, calls) => ({ id, role: 'assistant', name: session,
  metadata: { team_session_id: session }, created_at: '2026-10-18T04:13:00Z',
  content: [{ type: 'text', id: `${id}-text`, text: 'Peer result' }, ...calls] });
const entry = (id, session, calls) => ({ reply_id: id, worker_session_id: session,
  worker_agent_id: `${session}-agent`, worker_agent_name: session,
  event_type: 'require_user_confirm', event: { tool_calls: calls } });
const projected = (value) => ({ type: 'CUSTOM', name: 'subagent_require_user_confirm', value });

function chatTree(messages, sessionId = 'leader', footerSlot = 'subagent-confirmation') {
  const mocks = new Proxy({
    react: { __esModule: true, default: { memo: (component) => component },
      useMemo: (fn) => fn(), useState: (initial) => [initial, () => {}], useEffect() {} },
    'react/jsx-runtime': require('react/jsx-runtime'),
    '@agentscope-ai/agentscope/message': require('@agentscope-ai/agentscope/message'),
    '@agentscope-ai/agentscope/event': require('@agentscope-ai/agentscope/event'),
    '@/i18n/useI18n': { useTranslation: () => ({ t: (key) => key, i18n: { language: 'vi' } }) },
    '@/lib/utils': { cn: () => '' },
  }, { get: (target, id) => target[id] ?? new Proxy({}, { get: (_, name) => name }) });
  const { ChatContent } = load('../src/components/chat/ChatContent.tsx', mocks);
  return ChatContent({ msgs: messages, sessionId, footerSlot, teamChat: true, phase: 'idle' });
}
function nodes(tree, type) {
  if (!tree || typeof tree !== 'object') return [];
  return [...(tree.type === type ? [tree] : []),
    ...[tree.props?.children].flat(Infinity).flatMap((child) => nodes(child, type))];
}

async function conversation(t, messages, trigger = async () => {}) {
  const slots = [], effects = [], timers = [];
  let cursor = 0, mounted = false, wake;
  const react = {
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial;
      return [slots[index], (next) => {
        slots[index] = typeof next === 'function' ? next(slots[index]) : next;
      }];
    },
    useRef(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = { current: initial };
      return slots[index];
    },
    useCallback: (fn) => fn,
    useEffect: (fn) => { if (!mounted) effects.push(fn); },
  };
  const { useMessages } = load('../src/hooks/useMessages.ts', {
    react,
    '../utils/appendChatEvent': load('../src/utils/appendChatEvent.ts'),
    '@/context/AudioContext': { useAudioManager: () => null },
    '@/api': {
      chatApi: { trigger }, takeFreshlyCreated: () => false,
      sessionApi: {
        messages: async () => ({ messages: structuredClone(messages), is_running: false }),
        async *streamEvents(_session, _agent, signal) {
          while (!signal.aborted) {
            const event = await new Promise((resolve) => {
              wake = resolve;
              signal.addEventListener('abort', () => resolve(null), { once: true });
            });
            if (event) yield event;
          }
        },
      },
    },
  }, {
    AbortController, crypto: globalThis.crypto,
    requestAnimationFrame: setImmediate, cancelAnimationFrame: clearImmediate,
    setTimeout: (callback) => timers.push(callback), clearTimeout() {},
  });
  const render = () => { cursor = 0; return useMessages('leader-agent', 'leader', { teamChat: true }); };
  render();
  const cleanups = effects.map((effect) => effect());
  mounted = true;
  t.after(() => cleanups.forEach((cleanup) => cleanup?.()));
  await flush();
  return { render, emit: async (event) => { wake(event); await flush(); },
    poll: async () => { timers.shift()(); await flush(); } };
}

test('a mirrored worker booking uses only the subagent card; own-session confirmations remain visible', () => {
  const message = reply('hotel-reply', 'hotel-session', [call('hotel')]);
  const leader = chatTree([message]);
  assert.equal(nodes(leader, 'ConfirmCard').length, 0);
  assert.equal(nodes(leader, 'FlipCard')[0].props.children, 'subagent-confirmation');
  assert.equal(nodes(chatTree([message], 'hotel-session', null), 'ConfirmCard').length, 1);
  assert.equal(nodes(chatTree([{ ...message, metadata: {} }]), 'ConfirmCard').length, 1);
});

test('each booking asks once across mirrored and projected events, including stale replay', async (t) => {
  const sent = [];
  const messages = ['hotel', 'bus_trip', 'restaurant'].map((type) => reply(type, type, [call(type)]));
  const { render, emit, poll } = await conversation(t, messages, async (request) => sent.push(request));
  for (const message of messages) await emit(projected(entry(message.id, message.id, [call(message.id)])));
  assert.equal(render().subagentHitl.length, 3);
  for (const message of messages) {
    const pending = render().subagentHitl.find((item) => item.reply_id === message.id);
    await render().onSubagentConfirm(pending, call(message.id), true);
    await flush();
    await emit({ type: 'REQUIRE_USER_CONFIRM', reply_id: message.id, tool_calls: [call(message.id)] });
    await emit(projected(pending));
    await poll();
    await render().onUserConfirm(call(message.id), true, message.id);
    assert.ok(!render().subagentHitl.some((item) => item.reply_id === message.id));
    assert.notEqual(render().msgs.find((item) => item.id === message.id).content[1].state, 'asking');
  }
  assert.equal(sent.length, 3);
  assert.ok(sent.every((request) => request.session_id === 'leader' && request.agent_id === 'leader-agent'));
  assert.ok(sent.every((request) => request.input.confirm_results.length === 1));
  assert.ok(render().msgs.every((message) => message.content[0].text === 'Peer result'));
});

test('failed confirmation stays available for retry; denial clears only its call, keeping siblings and peers', async (t) => {
  let attempts = 0;
  const { render, emit } = await conversation(t, [reply('hotel', 'hotel', [call('hotel'), call('other')])], async () => {
    if (++attempts === 1) throw new Error('Network failed');
  });
  const pending = entry('hotel', 'hotel', [call('hotel'), call('other')]);
  await emit(projected(pending));
  await emit(projected(entry('bus', 'bus', [call('bus')])));
  await assert.rejects(render().onSubagentConfirm(pending, call('hotel'), false), /Network failed/);
  assert.equal(render().subagentHitl[0].event.tool_calls.length, 2);
  await render().onSubagentConfirm(pending, call('hotel'), false);
  await emit(projected(pending));
  assert.equal(attempts, 2);
  assert.equal(render().msgs[0].content[1].state, 'finished');
  assert.deepEqual(Array.from(render().subagentHitl.flatMap((item) => item.event.tool_calls.map((tool) => tool.id))).sort(), ['bus', 'other']);
});

test('a decision from another tab clears the projected card before reply end and survives replay', async (t) => {
  const { render, emit } = await conversation(t, [reply('hotel', 'hotel', [call('hotel')])]);
  const pending = entry('hotel', 'hotel', [call('hotel')]);
  await emit(projected(pending));
  await emit({ type: 'USER_CONFIRM_RESULT', reply_id: 'hotel',
    confirm_results: [{ confirmed: true, tool_call: call('hotel'), rules: null }] });
  assert.equal(render().subagentHitl.length, 0);
  await emit(projected(pending));
  assert.equal(render().subagentHitl.length, 0);
  await emit({ type: 'TOOL_RESULT_START', reply_id: 'hotel', tool_call_id: 'hotel', tool_call_name: 'mcp__travel__book_hotel' });
  await emit({ type: 'TOOL_RESULT_END', reply_id: 'hotel', tool_call_id: 'hotel', state: 'success' });
  assert.ok(render().msgs[0].content.some((block) => block.type === 'tool_result'));
  assert.equal(render().msgs[0].content[0].text, 'Peer result');
});

test('a leader booking also stays confirmed when polling or SSE replays an old pending request', async (t) => {
  let sent = 0;
  const { render, emit, poll } = await conversation(t, [reply('leader-reply', 'leader', [call('hotel')])], async () => { sent++; });
  assert.equal(nodes(chatTree(render().msgs), 'ConfirmCard').length, 1);
  await render().onUserConfirm(call('hotel'), true, 'leader-reply');
  await emit({ type: 'REQUIRE_USER_CONFIRM', reply_id: 'leader-reply', tool_calls: [call('hotel')] });
  await poll();
  assert.equal(nodes(chatTree(render().msgs), 'ConfirmCard').length, 0);
  await render().onUserConfirm(call('hotel'), true, 'leader-reply');
  assert.equal(sent, 1);
});
