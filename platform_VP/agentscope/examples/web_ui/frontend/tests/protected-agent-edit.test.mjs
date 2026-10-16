import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
function editor(data) {
  const states = [], effects = [], updates = [];
  let cursor = 0, mounted = false;
  const context = {
    exports: {}, require: (id) => {
      if (id === 'react/jsx-runtime') return require(id);
      if (id === 'react') return {
        useState: (initial) => { const i = cursor++; if (!(i in states)) states[i] = initial;
          return [states[i], (next) => { states[i] = typeof next === 'function' ? next(states[i]) : next; }]; },
        useEffect: (effect) => { if (!mounted) effects.push(effect); },
      };
      if (id === 'react-i18next') return { useTranslation: () => ({ t: (key) => key }) };
      if (id === '@/hooks/useAgents') return { useAgents: () => ({ update: async (...args) => updates.push(args) }) };
      if (id === '@/hooks/useAgentSchema') return { useAgentSchema: () => ({ schema: {} }) };
      if (id === '@/components/form/agent-form-utils') return { defaultAgentFormValues: () => ({ identity: {}, context_config: {}, react_config: {}, invite_config: {} }) };
      return new Proxy({}, { get: (_, name) => name });
    },
  };
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../src/components/dialog/EditAgentDialog.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, context);
  const render = () => { cursor = 0; return context.exports.EditAgentDialog({ open: true, onOpenChange() {}, agent: { id: 'agent', data: { name: 'Agent', ...data } } }); };
  render(); effects.forEach((effect) => effect()); mounted = true;
  return { tree: render(), updates };
}
function find(tree, predicate) {
  if (!tree || typeof tree !== 'object') return undefined;
  if (predicate(tree)) return tree.props;
  for (const child of [tree.props?.children].flat(Infinity)) {
    const result = find(child, predicate); if (result) return result;
  }
}
const save = (tree) => find(tree, (node) => node.type === 'Button' && node.props.onClick?.name === 'handleSubmit');

test('published business agent offers Studio instead of a rejected generic Save', () => {
  const { tree, updates } = editor({ system_role: 'business', published_version: 1 });
  assert.equal(save(tree), undefined);
  assert.equal(find(tree, (node) => node.type === 'AgentFormFields'), undefined);
  assert.equal(find(tree, (node) => node.type === 'Link').to, '/workforce/agents/agent');
  assert.deepEqual(updates, []);
});

test('fixed Leader has no editable form or Save action', () => {
  const { tree, updates } = editor({ system_role: 'leader' });
  assert.equal(save(tree), undefined);
  assert.equal(find(tree, (node) => node.type === 'AgentFormFields'), undefined);
  assert.equal(find(tree, (node) => node.type === 'Link'), undefined);
  assert.ok(find(tree, (node) => node.type === 'p').children.includes('Leader do hệ thống quản lý'));
  assert.deepEqual(updates, []);
});

test('unversioned agent keeps the existing generic edit behavior', async () => {
  const { tree, updates } = editor({ published_version: 0 });
  assert.equal(save(tree).disabled, false);
  await save(tree).onClick();
  assert.equal(updates.length, 1);
  assert.equal(updates[0][0], 'agent');
  assert.equal(updates[0][1].name, 'Agent');
});
