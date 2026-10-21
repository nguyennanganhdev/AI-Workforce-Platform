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

test('a finished answer offers its case file', () => {
  const opened = [];
  const { ASMessageBubble } = load('../src/components/chat/ASMessageBubble.tsx', mocks({
    '@/utils/common': { formatTime: () => '1s', formatNumber: String, copyToClipboard() {} },
    './tool-renderers/_shared': { getResultText: () => '', countDiffStats: () => null, getResultDiff: () => null, DiffStats: 'DiffStats' },
  }));
  const tree = ASMessageBubble({ message: leader([{ type: 'text', id: 't', text: 'Có chuyến QH118' }]), onOpenCaseFile: (id) => opened.push(id) });
  const [button] = nodes(tree, (node) => node.props?.['aria-label'] === 'caseFile.open');
  button.props.onClick();
  assert.deepEqual(opened, ['l1']);
});

test('the case file shows evidence, per-agent tokens and says when no price is set', () => {
  const caseFile = {
    turn: { customer_message_id: 'u', customer_text: 'Đi Đà Nẵng', started_at: null, ended_at: null },
    agents: [{ agent_id: 'f', name: 'Chuyên viên chuyến bay', model: 'gpt-6-luna', replies: 1, input_tokens: 2000, output_tokens: 200, cache_input_tokens: 0, cost_usd: null }],
    totals: { input_tokens: 2000, output_tokens: 200, cache_input_tokens: 0, cost_usd: null, priced: false },
    evidence: [{ agent_id: 'f', agent_name: 'Chuyên viên chuyến bay', tool: 'mcp__Travelling__search_flights', arguments: { destination: 'Đà Nẵng' }, state: 'success', result: '{"count": 1}', at: null }],
  };
  let call = 0;
  const { CaseFileSheet } = load('../src/components/chat/CaseFileSheet.tsx', mocks({
    react: { __esModule: true, useEffect() {}, useState: () => [call++ === 0 ? caseFile : false, () => {}] },
    '@/lib/teamThreads': load('../src/lib/teamThreads.ts'),
  }));
  const html = text(CaseFileSheet({ sessionId: 's', agentId: 'a', messageId: 'm', onClose() {} }));
  assert.match(html, /search flights/);
  assert.match(html, /Đà Nẵng/);
  assert.match(html, /caseFile\.unpriced/);
  assert.match(html, /Chuyên viên chuyến bay/);
});

test('the test-case dialog shows recorded lookups, the pass rate and a regression', () => {
  const cases = [{ id: 'c1', created_at: '', scenario: 'Bay đi Đà Nẵng', expected: 'Tra chuyến', expect_tool: '',
    recorded: { search_flights: ['{}'] }, source_session_id: 's', source_message_id: 'm' }];
  const run = { id: 'r2', created_at: '', version: 'abc123def456', model: 'gpt-6-luna', status: 'completed',
    started_at: '2026-10-22T08:00:00Z', finished_at: null, error: null,
    report: { total: 1, passed: 0, errors: 0, pass_rate: 0 },
    tests: [{ case_id: 'c1', scenario: 'Bay đi Đà Nẵng', expected: 'Tra chuyến', status: 'failed', result: { passed: false, summary: 'Bịa giá' } }],
    comparison: { run_id: 'r1', version: '000111222333', cases: [{ case_id: 'c1', scenario: '', before: 'passed', after: 'failed', change: 'worse' }] } };
  const states = [cases, [run], run, false, '', '', false, ''];
  let index = 0;
  const { AgentEvalDialog } = load('../src/components/workforce/AgentEvalDialog.tsx', mocks({
    react: { __esModule: true, useEffect() {}, useCallback: (fn) => fn, useState: () => [states[index++], () => {}] },
  }));
  const tree = AgentEvalDialog({ agentId: 'a', agentName: 'Chuyên viên chuyến bay', open: true, onOpenChange() {} });
  const html = text(tree);
  assert.match(html, /agentEval\.recorded.*search_flights/);
  assert.match(html, /agentEval\.passRate.*"passed":0.*"total":1/);
  assert.match(html, /Bịa giá/);
  assert.equal(nodes(tree, (node) => node.props?.['aria-label'] === 'agentEval.worse').length, 1);
});

test('the memory dialog separates proposals from approved memories and marks fading ones', () => {
  const memories = [
    { id: 'p', content: 'Khách thích ghế cửa sổ.', reason: 'Khách nói vậy', status: 'proposed', pinned: false, confirmations: 0,
      proposed_at: '', approved_at: null, last_confirmed_at: null, source_session_id: null, priority: 0, active: false },
    { id: 'a', content: 'Khách bay từ Hà Nội.', reason: '', status: 'approved', pinned: false, confirmations: 0,
      proposed_at: '', approved_at: '', last_confirmed_at: null, source_session_id: null, priority: 0.1, active: false },
  ];
  const states = [memories, {}, '', ''];
  let index = 0;
  const { AgentMemoryDialog } = load('../src/components/workforce/AgentMemoryDialog.tsx', mocks({
    react: { __esModule: true, useEffect() {}, useCallback: (fn) => fn, useState: () => [states[index++], () => {}] },
  }));
  const tree = AgentMemoryDialog({ agentId: 'a', agentName: 'Chuyên viên chuyến bay', open: true, onOpenChange() {} });
  const html = text(tree);
  assert.match(html, /agentMemory\.proposals.*"count":1/);
  assert.match(html, /agentMemory\.approved.*"count":1/);
  assert.match(html, /Khách bay từ Hà Nội\./);
  assert.match(html, /agentMemory\.fading/);
  assert.equal(nodes(tree, (node) => node.props?.['aria-label'] === 'agentMemory.edit').length, 1);
});
