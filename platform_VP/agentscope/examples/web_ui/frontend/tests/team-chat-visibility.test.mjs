import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);

function load(path, mocks = {}) {
  const context = { exports: {}, require: (id) => mocks[id] ?? require(id) };
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX },
  }).outputText, context);
  return context.exports;
}

const mocks = (extra = {}) => new Proxy({
  react: { __esModule: true, default: { memo: (component) => component },
    memo: (component) => component,
    useMemo: (fn) => fn(), useState: (initial) => [typeof initial === 'function' ? initial() : initial, () => {}],
    useEffect() {}, useCallback: (fn) => fn, useRef: (current) => ({ current }) },
  'react/jsx-runtime': require('react/jsx-runtime'),
  '@agentscope-ai/agentscope/message': require('@agentscope-ai/agentscope/message'),
  '@agentscope-ai/agentscope/event': require('@agentscope-ai/agentscope/event'),
  '@/i18n/useI18n': { useTranslation: () => ({ t: (key, values) => (values ? `${key}:${JSON.stringify(values)}` : key), i18n: { language: 'vi' } }) },
  '@/lib/utils': { cn: () => '' },
  '@/lib/readable': load('../src/lib/readable.ts'),
  ...extra,
}, { get: (target, id) => target[id] ?? new Proxy({}, { get: (_, name) => name }) });

function nodes(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  return [...(predicate(tree) ? [tree] : []),
    ...[tree.props?.children].flat(Infinity).flatMap((child) => nodes(child, predicate))];
}
const text = (tree) => nodes(tree, () => true)
  .flatMap((node) => [node.props?.children].flat(Infinity).filter((child) => typeof child === 'string'))
  .join(' ');

const teamSay = (id, to, content) => ({ type: 'tool_call', id, name: 'TeamSay',
  input: JSON.stringify({ to, kind: to ? 'question' : 'requires_user_input', content }) });
const member = (id, name, content, finished = 'completed') => ({ id, role: 'assistant', name,
  metadata: { team_session_id: `${id}-session`, team_agent_id: `${id}-agent` },
  created_at: '2026-10-20T05:20:00Z', finished_reason: finished, content });

function chat(messages) {
  const { ChatContent } = load('../src/components/chat/ChatContent.tsx', mocks());
  return ChatContent({ msgs: messages, sessionId: 'leader', teamChat: true, phase: 'idle' });
}
const shown = (tree) => nodes(tree, (node) => node.type === 'ASMessageBubble')
  .map((node) => node.props.message.id);

test('internal member turns stay out of the customer chat', () => {
  const tree = chat([
    { id: 'u1', role: 'user', name: 'user', metadata: {}, created_at: '2026-10-20T05:18:00Z', content: [{ type: 'text', id: 't', text: 'Đi Đà Nẵng' }] },
    member('flights', 'Chuyên viên chuyến bay', [teamSay('c1', 'Lập kế hoạch@70393d9b', 'Đã tra chuyến bay')]),
    member('planner', 'Lập kế hoạch', [teamSay('c2', 'null', 'Bạn đi ngày nào?')]),
    member('hotel', 'Chuyên viên khách sạn', [{ type: 'text', id: 'x', text: 'Đây là gợi ý cho bạn.' }]),
  ]);
  assert.deepEqual(shown(tree), ['u1', 'planner', 'hotel']);
});

test('a running internal member turn shows one working line instead of a bubble', () => {
  const tree = chat([
    member('flights', 'Chuyên viên chuyến bay', [teamSay('c1', 'Lập kế hoạch@1a2b3c4d', 'Đang tra')], null),
    member('food', 'Chuyên viên nhà hàng', [], null),
  ]);
  assert.deepEqual(shown(tree), []);
  assert.match(text(tree), /messageBubble\.trace\.working.*Chuyên viên chuyến bay, Chuyên viên nhà hàng/);
});

test('a failed member turn stays visible', () => {
  const tree = chat([member('flights', 'Chuyên viên chuyến bay', [teamSay('c1', 'X@1a2b3c4d', 'a')], 'error')]);
  assert.deepEqual(shown(tree), ['flights']);
});

function bubble(message) {
  const { ASMessageBubble } = load('../src/components/chat/ASMessageBubble.tsx', mocks({
    '@/utils/common': { formatTime: () => '1s', formatNumber: String, copyToClipboard() {} },
    './tool-renderers/_shared': { getResultText: () => '', countDiffStats: () => null, getResultDiff: () => null, DiffStats: 'DiffStats' },
  }));
  return ASMessageBubble({ message });
}
const leader = (content, extra = {}) => ({ id: 'l1', role: 'assistant', name: 'Workforce Leader',
  metadata: { team_session_id: 'leader', team_agent_id: 'leader-agent' },
  created_at: '2026-10-20T05:20:00Z', finished_at: '2026-10-20T05:20:09Z', finished_reason: 'completed', content, ...extra });

test('a Leader reply that only delegated is one line naming who got the work', () => {
  const tree = bubble(leader([
    { type: 'tool_call', id: 'i1', name: 'AgentInvite', input: JSON.stringify({
      target: 'Lập kế hoạch@70393d9b', additional_assignments: [{ target: 'Chuyên viên chuyến bay@a3c4cf0c' }] }) },
    { type: 'tool_result', id: 'i1', name: 'AgentInvite', state: 'success', output: 'ok' },
    teamSay('s1', 'Chuyên viên khách sạn@b69154f8', 'Tìm khách sạn'),
  ]));
  assert.equal(tree.props['data-coordination'], 'true');
  assert.match(text(tree), /delegated.*Lập kế hoạch, Chuyên viên chuyến bay|delegated.*Chuyên viên khách sạn/);
  assert.equal(nodes(tree, (node) => node.type === 'Bubble').length, 0);
});

test('a question already in the reply text is not shown a second time as a card', () => {
  const tree = bubble({ ...leader([
    { type: 'text', id: 't1', text: 'Bạn dự định đi ngày nào trong tháng 11?' },
    teamSay('q1', 'null', 'Bạn đi ngày nào và mấy người?'),
  ]), name: 'Lập kế hoạch', metadata: { team_session_id: 'planner', team_agent_id: 'planner-agent' } });
  assert.equal(nodes(tree, (node) => node.type === 'CommunicationCard').length, 0);
  assert.equal(tree.props['data-coordination'], undefined);
});

test('a reply stored twice (start and final copy) is shown once, with its final content', () => {
  const start = member('planner', 'Lập kế hoạch', [], null);
  const done = member('planner', 'Lập kế hoạch', [{ type: 'text', id: 'x', text: 'Mình đã kiểm tra lại.' }]);
  const flightsStart = member('flights', 'Chuyên viên chuyến bay', [], null);
  const flightsDone = member('flights', 'Chuyên viên chuyến bay', [teamSay('c1', 'Lập kế hoạch@1a2b3c4d', 'Đã tra')]);
  const tree = chat([start, flightsStart, done, flightsDone]);
  assert.deepEqual(shown(tree), ['planner']);
  const [bubbleNode] = nodes(tree, (node) => node.type === 'ASMessageBubble');
  assert.equal(bubbleNode.props.message.content[0].text, 'Mình đã kiểm tra lại.');
  assert.doesNotMatch(text(tree), /trace\.working/);
});
