import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const source = readFileSync(
  new URL('../src/pages/workforce/builder/index.tsx', import.meta.url), 'utf8');

// Exercise the page's handlers with browser I/O and React hooks mocked.
async function builderWith(deleteAgent, builderApi = {}) {
  const states = [];
  const effects = [];
  let cursor = 0;
  let mounted = false;
  const agents = [
    { agent_id: 'published', name: 'Hotel', lifecycle_state: 'published' },
    { agent_id: 'draft', name: 'Planner', lifecycle_state: 'draft' },
  ];
  const context = {
    exports: {},
    require: (id) => {
      if (id === 'react/jsx-runtime') return require(id);
      if (id === 'react') return {
        useState: (initial) => {
          const index = cursor++;
          if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial;
          return [states[index], (next) => {
            states[index] = typeof next === 'function' ? next(states[index]) : next;
          }];
        },
        useCallback: (callback) => callback,
        useEffect: (effect) => { if (!mounted) effects.push(effect); },
      };
      if (id === '@/api') return {
        agentApi: { delete: deleteAgent },
        workforceApi: {
          listAgents: async () => agents,
          listBuilderConversations: async () => [],
          ...builderApi,
        },
      };
      if (id === 'react-router-dom') return {
		useNavigate: () => () => {},
        useSearchParams: () => [new URLSearchParams(), () => {}],
      };
      if (id === '@/hooks/useKnowledgeBases') return {
        useKnowledgeBases: () => ({ knowledgeBases: [], loading: false }),
      };
      if (id === '@/components/chat/session-row-utils') return { sessionTime: () => '' };
      if (id === 'sonner') return { toast: { success() {} } };
      return new Proxy({}, { get: (_, name) => name });
    },
  };
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText, context);
  const render = () => { cursor = 0; return context.exports.AgentBuilderPage(); };
  render();
  effects.forEach((effect) => effect());
  await new Promise((resolve) => setImmediate(resolve));
  mounted = true;
  return render;
}

function find(tree, predicate) {
  if (!tree || typeof tree !== 'object') return undefined;
  if (predicate(tree)) return tree.props;
  for (const child of [tree.props?.children].flat(Infinity)) {
    const match = find(child, predicate);
    if (match) return match;
  }
}
const button = (tree, name) => find(tree, (node) => node.props?.['aria-label'] === `Xóa agent ${name}`);
const dialog = (tree) => find(tree, (node) => node.type === 'DeleteDialog' && node.props.confirmLabel === 'Xóa agent');

test('deleting either a published or draft agent requires confirmation and removes only that agent', async () => {
  for (const [id, name, other] of [['published', 'Hotel', 'Planner'], ['draft', 'Planner', 'Hotel']]) {
    const deleted = [];
    const render = await builderWith(async (agentId) => deleted.push(agentId));
    button(render(), name).onClick();
    assert.equal(dialog(render()).open, true);
    assert.ok(dialog(render()).title.includes(name));
    assert.deepEqual(deleted, []);
    dialog(render()).onOpenChange(false);
    assert.equal(dialog(render()).open, false);
    assert.deepEqual(deleted, []);
    button(render(), name).onClick();
    await dialog(render()).onConfirm();
    assert.deepEqual(deleted, [id]);
    assert.equal(button(render(), name), undefined);
    assert.ok(button(render(), other));
  }
});

test('a failed deletion keeps the agent and confirmation available for retry', async () => {
  const render = await builderWith(async () => { throw new Error('Forbidden'); });
  button(render(), 'Hotel').onClick();
  await assert.rejects(dialog(render()).onConfirm(), /Forbidden/);
  assert.ok(button(render(), 'Hotel'));
  assert.equal(dialog(render()).open, true);
});

test('a conversation without a proposal restores its model and can continue chatting', async () => {
  const model = { type: 'openai_credential', credential_id: 'chat', model: 'chat', parameters: {} };
  let stored = {
    conversation_id: 'builder', title: 'Chat', proposal: null, chat_model_config: model,
    messages: [{ role: 'builder', text: 'Bạn muốn agent hỗ trợ công việc gì?' }],
  };
  const requests = [];
  const render = await builderWith(async () => {}, {
    listBuilderConversations: async () => [{ conversation_id: 'builder', title: 'Chat' }],
    getBuilderConversation: async () => stored,
    prepare: async (...args) => {
      requests.push(args);
      stored = { ...stored, messages: [...stored.messages,
        { role: 'user', text: args[0] }, { role: 'builder', text: 'Chào bạn!' }] };
      return stored;
    },
  });
  assert.equal(find(render(), (node) => node.type === 'LlmSelect').value, model);
  find(render(), (node) => node.type === 'Textarea').onChange({ target: { value: 'Xin chào' } });
  await find(render(), (node) => node.props?.['aria-label'] === 'Gửi cho Builder').onClick();
  // The click starts an async handler; let its history refresh finish.
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 1);
  assert.equal(requests[0][0], 'Xin chào');
  assert.equal(requests[0][1], model);
  assert.equal(requests[0][2], 'builder');
  assert.ok(find(render(), (node) => node.type === 'Markdown' && node.props.children === 'Chào bạn!'));
  assert.equal(find(render(), (node) => node.type === 'ProposalSteps'), undefined);
});
