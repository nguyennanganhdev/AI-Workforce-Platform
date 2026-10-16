import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const transpile = (path) => ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const eventModule = { exports: {}, require };
vm.runInNewContext(transpile('../src/utils/appendChatEvent.ts'), eventModule);
const at = '2026-10-17T01:00:00Z';
const reply = (id, text, extra = {}) => ({
  id, role: 'assistant', name: id, metadata: {}, created_at: at,
  content: [{ id: `${id}-text`, type: 'text', text, created_at: at }], ...extra,
});

// Exercise the real hook with deterministic transport, effects and browser timers.
async function messagesWith(options, events = []) {
  const state = [], refs = [], effects = [], frames = [], timers = [], writes = [];
  let cursor = 0, refCursor = 0, mounted = false, streams = 0, histories = 0;
  const context = {
    exports: {}, AbortController, crypto, setTimeout: (callback, ms) => { timers.push({ callback, ms }); return timers.length; },
    clearTimeout() {}, requestAnimationFrame: (callback) => { frames.push(callback); return frames.length; },
    require: (id) => {
      if (id === 'react') return {
        useState: (initial) => {
          const i = cursor++;
          if (!(i in state)) state[i] = typeof initial === 'function' ? initial() : initial;
          return [state[i], (next) => { state[i] = typeof next === 'function' ? next(state[i]) : next; }];
        },
        useRef: (initial) => { const i = refCursor++; return refs[i] ??= { current: initial }; },
        useCallback: (callback) => callback,
        useEffect: (callback) => { if (!mounted) effects.push(callback); },
      };
      if (id === '../utils/appendChatEvent') return eventModule.exports;
      if (id === '@/context/audio-context') return { useAudioManager: () => null };
      if (id === '@/api') return {
        takeFreshlyCreated: () => false,
        sessionApi: {
          messages: async () => { histories++; return { messages: [], is_running: false }; },
          streamEvents: async function* () { streams++; for (const event of events) yield { created_at: at, ...event }; await new Promise(() => {}); },
        },
        chatApi: { trigger: async (body) => { writes.push(body); return { status: 'ok' }; } },
      };
      return require(id);
    },
  };
  vm.runInNewContext(transpile('../src/hooks/useMessages.ts'), context);
  const render = () => { cursor = 0; refCursor = 0; return context.exports.useMessages('leader', 'session', options); };
  render();
  const cleanups = effects.map((effect) => effect());
  mounted = true;
  await new Promise((resolve) => setImmediate(resolve));
  while (frames.length) frames.shift()();
  return { render, timers, writes, streams, histories, cleanup: () => cleanups.forEach((cleanup) => cleanup?.()) };
}

test('member observer loads and polls history without opening SSE', async () => {
  const hook = await messagesWith({ stream: false });
  assert.equal(hook.histories, 1);
  assert.equal(hook.streams, 0);
  assert.equal(hook.render().loading, false);
  assert.equal(hook.timers[0].ms, 1500);
  assert.deepEqual(hook.writes, []);
  hook.cleanup();
});

test('team interleaving and target persisted-upsert updates preserve each author', async () => {
  const hook = await messagesWith({ teamChat: true }, [
    { type: 'REPLY_START', reply_id: 'a', name: 'A', metadata: { team_agent_id: 'worker-a' } },
    { type: 'REPLY_START', reply_id: 'b', name: 'B', metadata: { team_agent_id: 'worker-b' } },
    { type: 'TEXT_BLOCK_START', reply_id: 'b', block_id: 'b-text' },
    { type: 'TEXT_BLOCK_DELTA', reply_id: 'b', block_id: 'b-text', delta: 'B reply' },
    { type: 'CUSTOM', name: 'message_upserted', value: { message: reply('a', 'A persisted', { finished_reason: 'completed' }) } },
    { type: 'REPLY_END', reply_id: 'b', finished_reason: 'completed' },
  ]);
  const result = hook.render();
  assert.equal(result.msgs.length, 2);
  assert.equal(result.msgs[0].content[0].text, 'A persisted');
  assert.equal(result.msgs[1].content[0].text, 'B reply');
  assert.equal(result.msgs[1].metadata.team_agent_id, 'worker-b');
  assert.equal(result.phase, 'idle');
  await result.send([], 'worker-b');
  assert.equal(hook.writes[0].target_agent_id, 'worker-b');
  hook.cleanup();
});

test('builder revisions and canonical KB selections retain target room/eval contracts', async () => {
  const calls = [];
  const context = { exports: {}, require: () => ({ client: new Proxy({}, { get: (_, method) => async (path, body) => { calls.push({ method, path, body }); return {}; } }) }) };
  vm.runInNewContext(transpile('../src/api/workforce.ts'), context);
  const api = context.exports.workforceApi;
  await api.prepare('build', { model: 'model' }, 'conversation', true, 7);
  await api.publish('conversation', 'proposal', 8, [['kb-one'], []]);
  await api.evaluate('conversation', 'proposal', 8);
  await api.room('session');
  assert.equal(calls[0].body.expected_revision, 7);
  assert.equal(JSON.stringify(calls[1].body.knowledge_base_selections), '[["kb-one"],[]]');
  assert.equal(calls[2].path, '/workforce/console/builder/evaluate');
  assert.equal(calls[3].path, '/workforce/console/sessions/session/room');
});
