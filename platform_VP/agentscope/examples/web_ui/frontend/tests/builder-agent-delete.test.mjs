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
async function builderWith(deleteAgent) {
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
          if (!(index in states)) states[index] = initial;
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
        },
      };
      if (id === 'react-router-dom') return {
        useLocation: () => ({ state: null }),
        useSearchParams: () => [new URLSearchParams(), () => {}],
      };
      if (id === '@/lib/utils') return { cn: (...names) => names.filter(Boolean).join(' ') };
      if (id === '@/hooks/useKnowledgeBases') return {
        useKnowledgeBases: () => ({ knowledgeBases: [], loading: false }),
      };
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
  // The page's own hook-free sections (the agent roster) render inline.
  if (typeof tree.type === 'function') return find(tree.type(tree.props), predicate);
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
