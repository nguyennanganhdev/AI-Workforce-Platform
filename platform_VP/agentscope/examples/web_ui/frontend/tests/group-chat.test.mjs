import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const locale = JSON.parse(readFileSync(new URL('../src/i18n/locales/en.json', import.meta.url), 'utf8'));
const translate = (key, values = {}) => Object.entries(values).reduce((text, [name, value]) => text.replaceAll(`{{${name}}}`, value), key.split('.').reduce((part, name) => part?.[name], locale) ?? key);
const agent = (id, extra = {}) => ({ id, editable: true, data: {
  name: id, system_role: 'business', lifecycle_state: 'published',
  invite_config: { invitable: true, invite_description: `${id} specialist` }, ...extra,
} });

function dialog(agents) {
  const states = [], calls = [], groups = [], navigations = [];
  let cursor = 0;
  const context = {
    exports: {}, require: (id) => {
      if (id === 'react/jsx-runtime') return require(id);
      if (id === 'react') return {
        useState: (initial) => { const i = cursor++; if (!(i in states)) states[i] = initial;
          return [states[i], (next) => { states[i] = typeof next === 'function' ? next(states[i]) : next; }]; },
        useEffect() {}, useMemo: (callback) => callback(),
      };
      if (id === '@/api') return {
        agentApi: { update: () => { throw new Error('Group creation must not PATCH agents'); } },
        workforceApi: { bootstrapLeader: async () => { calls.push(['bootstrap']); return { agent_id: 'fixed-leader', session_id: 'existing-primary' }; } },
        sessionApi: {
          create: async (body) => { calls.push(['create', body]); return { session_id: 'new-group' }; },
          update: async (...args) => { calls.push(['rename', ...args]); },
        },
      };
      if (id === '@/i18n/useI18n') return { useTranslation: () => ({ t: translate }) };
      if (id === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
      if (id === '@/lib/api-error') return { formatApiErrorForAlert: (error) => error.message };
      if (id === '@/lib/group-chats') return {
        addGroupChat: (group) => groups.push(group), agentHandle: (name, id) => `${name}@${id.slice(0, 8)}`,
      };
      return new Proxy({}, { get: (_, name) => name });
    },
  };
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../src/components/dialog/GroupChatDialog.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, context);
  const render = () => { cursor = 0; return context.exports.GroupChatDialog({
    open: true, onOpenChange() {}, agents, onCreated: (...args) => navigations.push(args),
    modelConfig: { chat: { model: 'leader-model' }, subAgent: { model: 'worker-model' }, fallback: { model: 'fallback-model' } },
  }); };
  return { render, calls, groups, navigations };
}
function find(tree, predicate) {
  if (!tree || typeof tree !== 'object') return undefined;
  if (predicate(tree)) return tree.props;
  for (const child of [tree.props?.children].flat(Infinity)) {
    const found = find(child, predicate); if (found) return found;
  }
}
const member = (tree, id) => find(tree, (node) => node.props?.role === 'checkbox' && !!find(node, (child) => child.type === 'ClayAvatar' && child.props.id === id));
const submit = (tree) => find(tree, (node) => node.type === 'Button' && node.props.type === 'submit');

test('fixed Leader owns group session; crown picks primary specialist in a single complete-roster kickoff', async () => {
  const { render, calls, groups, navigations } = dialog([agent('alpha12345'), agent('beta12345')]);
  find(render(), (node) => node.type === 'Input').onChange({ target: { value: 'New group' } });
  member(render(), 'alpha12345').onClick();
  member(render(), 'beta12345').onClick();
  find(render(), (node) => node.props?.['aria-label'] === 'Set primary beta12345').onClick();
  assert.equal(submit(render()).disabled, false);
  await find(render(), (node) => node.type === 'form').onSubmit({ preventDefault() {} });
  assert.equal(calls[0][0], 'bootstrap');
  assert.equal(calls[1][1].agent_id, 'fixed-leader');
  assert.equal(calls[1][1].sub_agent_chat_model_config.model, 'worker-model');
  assert.equal(calls[2][2], 'fixed-leader');
  assert.equal(groups[0].agentId, 'fixed-leader');
  assert.equal(JSON.stringify(groups[0].memberIds), '["alpha12345","beta12345"]');
  const kickoff = groups[0].kickoff;
  assert.ok(kickoff.indexOf('TeamCreate') < kickoff.indexOf('AgentInvite'));
  assert.equal(kickoff.match(/AgentInvite/g).length, 1);
  assert.ok(kickoff.includes('target=beta12345@beta1234'));
  assert.ok(kickoff.includes('"target":"alpha12345@alpha123"'));
  assert.ok(kickoff.includes('Start only the primary specialist'));
  assert.deepEqual(navigations, [['fixed-leader', 'new-group']]);
});

test('only published invitable specialists can be selected; one is sufficient with fixed Leader', async () => {
  const { render, groups } = dialog([
    agent('eligible'), agent('draft', { lifecycle_state: 'draft' }),
    agent('withdrawn', { lifecycle_state: 'withdrawn' }),
    agent('leader', { system_role: 'leader' }),
    agent('no-invites', { invite_config: { invitable: false, invite_description: 'No invites' } }),
  ]);
  for (const id of ['draft', 'withdrawn', 'leader', 'no-invites']) assert.equal(member(render(), id), undefined);
  find(render(), (node) => node.type === 'Input').onChange({ target: { value: 'Single specialist' } });
  member(render(), 'eligible').onClick();
  assert.equal(submit(render()).disabled, false);
  await find(render(), (node) => node.type === 'form').onSubmit({ preventDefault() {} });
  assert.ok(groups[0].kickoff.includes('additional_assignments=[]'));
  assert.equal(JSON.stringify(groups[0].memberIds), '["eligible"]');
});

test('empty eligible pool keeps creation disabled and directs the user to publish first', () => {
  const { render, calls } = dialog([agent('draft', { lifecycle_state: 'draft' })]);
  assert.equal(submit(render()).disabled, true);
  assert.ok(find(render(), (node) => node.type === 'span' && typeof node.props.children === 'string' && node.props.children.includes('Create and publish an agent')));
  assert.deepEqual(calls, []);
});
