import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const flush = () => new Promise(setImmediate);
const model = { type: 'openai', credential_id: 'credential', model: 'test-model', parameters: {} };
const content = [{ type: 'text', id: 'text-1', text: 'Hello', created_at: new Date().toISOString() }];

function environment(overrides = {}, storage) {
  const slots = [], effects = [];
  let cursor = 0;
  const changed = (previous, next) => !previous || !next || previous.some((value, i) => value !== next[i]);
  const hooks = {
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
    useMemo(fn, dependencies) {
      const index = cursor++;
      if (!slots[index] || changed(slots[index].dependencies, dependencies)) {
        slots[index] = { dependencies, value: fn() };
      }
      return slots[index].value;
    },
    useCallback(fn, dependencies) { return hooks.useMemo(() => fn, dependencies); },
    useEffect(fn, dependencies) {
      const index = cursor++;
      if (!slots[index] || changed(slots[index].dependencies, dependencies)) {
        const previous = slots[index];
        slots[index] = { dependencies };
        effects.push(() => { previous?.cleanup?.(); slots[index].cleanup = fn(); });
      }
    },
    useLayoutEffect() {},
    useImperativeHandle() {},
    memo: (component) => component,
    forwardRef: (component) => component,
  };
  const calls = { created: [], triggered: [], navigated: [], sent: [], updated: [] };
  const noop = () => {};
  const create = async (body) => { calls.created.push(body); return { session_id: 'saved' }; };
  const useSessions = () => ({ sessions: [], refetch: async () => [], create, update: noop, remove: noop });
  const mocks = {
    react: { __esModule: true, default: hooks, ...hooks },
    'react/jsx-runtime': require('react/jsx-runtime'),
    'react-router-dom': {
      useNavigate: () => (...args) => calls.navigated.push(args),
      useParams: () => ({ agentId: 'agent' }),
      useLocation: () => ({ pathname: '/chat/agent', key: 'route', state: null }),
      useSearchParams: () => [new URLSearchParams(), noop],
    },
    '@/api': {
      chatApi: { trigger: async (body) => calls.triggered.push(body) },
      sessionApi: { update: async (...args) => calls.updated.push(args) },
      workforceApi: {
        listAgents: async () => [], listBuilderConversations: async () => [],
        bootstrapLeader: async () => ({ agent_id: 'leader', session_id: null, chat_model_config: model }),
      },
    },
    '@/hooks/useSessions': { useSessions },
    '@/hooks/useAgents': { useAgents: () => ({ agents: [{ id: 'agent', data: {} }] }) },
    '@/hooks/useMessages': { useMessages: () => ({
      msgs: [], loading: false, phase: 'idle', subagentHitl: [],
      send: async (...args) => calls.sent.push(args),
    }) },
    '@/hooks/useAvailableModels': { useAvailableModels: () => ({ groups: {} }) },
    '@/hooks/useWorkspace': { useWorkspace: () => ({ mcps: [], skills: [] }) },
    '@/hooks/useWorkspaceStatus': { useWorkspaceStatus: () => ({ status: null, refetch: noop }) },
    '@/hooks/useKnowledgeBases': { useKnowledgeBases: () => ({ knowledgeBases: [], loading: false }) },
    '@/hooks/useKnowledgeBaseMiddlewareSchema': { useKnowledgeBaseMiddlewareSchema: () => ({}) },
    '@/hooks/use-mobile': { useIsMobile: () => false },
    '@/components/ui/sidebar': { useSidebar: () => ({ isMobile: false, setOpen: noop, setOpenMobile: noop }) },
    '@/components/chat/session-row-utils': {
      sessionTitle: (title) => title,
      sessionTime: () => '',
      sessionDisplayTitle: () => 'Existing chat',
    },
    '@/i18n/useI18n': { useTranslation: () => ({ t: (key) => key }) },
    '@/i18n/useI18n.ts': { useTranslation: () => ({ t: (key) => key }) },
    '@/lib/utils': { cn: () => '' },
    ...overrides,
  };
  function load(path) {
    const fallback = (id) => {
      try { return require(id); } catch { return new Proxy({}, { get: (_, name) => name }); }
    };
    const context = {
      exports: {}, require: (id) => mocks[id] ?? mocks[id.replace(/\.tsx?$/, '')] ?? fallback(id),
      crypto: globalThis.crypto, URLSearchParams,
      localStorage: storage ?? { getItem: () => null, setItem: noop },
    };
    vm.runInNewContext(ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
    }).outputText, context);
    return context.exports;
  }
  return { calls, load, mocks, render(component, props) { cursor = 0; return component(props); },
    effects() { effects.splice(0).forEach((effect) => effect()); } };
}
function nodes(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  return [...(predicate(tree) ? [tree] : []),
    ...[tree.props?.children].flat(Infinity).flatMap((child) => nodes(child, predicate))];
}
const component = (tree, name) => nodes(tree, (node) => node.type === name)[0];
function builderPage(env) {
  const { AgentBuilderPage } = env.load('../src/pages/workforce/builder/index.tsx');
  return nodes(AgentBuilderPage(), (node) => node.type?.name === 'AgentBuilderPageInner')[0].type;
}

test('Leader chat hides agent deletion while editing and business agent deletion stay available', async () => {
  for (const role of ['leader', 'business']) {
    const removed = [];
    const env = environment({
      '@/hooks/useAgents': { useAgents: () => ({
        agents: [{ id: 'agent', editable: true, data: { system_role: role } }],
        remove: async (id) => removed.push(id), refetch: async () => {},
      }) },
    });
    const { ChatPage } = env.load('../src/pages/chat/index.tsx');
    const inner = nodes(ChatPage(), (node) => node.type?.name === 'ChatPageInner')[0].type;
    const tree = env.render(inner);
    for (const label of ['agent-menu.settings', 'agent-menu.delete']) {
      const actions = nodes(tree, (node) => node.type === 'DropdownMenuItem'
        && node.props.children.includes(label));
      assert.equal(actions.length, role === 'leader' && label === 'agent-menu.delete' ? 0 : 1);
    }
    assert.ok(component(tree, 'EditAgentDialog'));
    const deleteDialogs = nodes(tree, (node) => node.type === 'DeleteDialog'
      && node.props.confirmLabel === 'dialog-agent-delete.confirm');
    deleteDialogs[0].props.onOpenChange(true);
    const opened = env.render(inner);
    const dialog = nodes(opened, (node) => node.type === 'DeleteDialog'
      && node.props.confirmLabel === 'dialog-agent-delete.confirm')[0];
    assert.equal(dialog.props.open, role !== 'leader');
    await dialog.props.onConfirm();
    assert.deepEqual(removed, role === 'leader' ? [] : ['agent']);
    assert.ok(component(tree, 'ChatViewport'));
  }
});

test('a session created with a message must load its history on first open', async () => {
  const env = environment({ './client': { client: { post: async () => ({ session_id: 'saved' }) } } });
  const { sessionApi, takeFreshlyCreated } = env.load('../src/api/session.ts');
  await sessionApi.create({ agent_id: 'agent', initial_message: { role: 'user', content } });
  assert.equal(takeFreshlyCreated('saved'), false);
  await sessionApi.create({ agent_id: 'agent' });
  assert.equal(takeFreshlyCreated('saved'), true);
});

test('opening a new chat creates no session and the draft URL is not redirected to history', () => {
  const env = environment();
  const { ChatPage } = env.load('../src/pages/chat/index.tsx');
  const inner = nodes(ChatPage(), (node) => node.type?.name === 'ChatPageInner')[0].type;
  const tree = env.render(inner);
  nodes(tree, (node) => node.props?.id === 'tour-create-session')[0].props.onClick();
  assert.equal(env.calls.created.length, 0);
  assert.equal(env.calls.navigated[0][0], '/chat/agent/new');

  const previous = env.mocks['react-router-dom'];
  Object.assign(env.mocks['react-router-dom'], {
    ...previous, useParams: () => ({ agentId: 'agent', sessionId: 'new' }),
    useLocation: () => ({ key: 'new-route', state: env.calls.navigated[0][1].state }),
  });
  env.mocks['@/hooks/useSessions'].useSessions = () => ({
    sessions: [{ session: { id: 'old', origin: { type: 'user' }, config: { name: 'Old chat' } }, status: 'idle', preview: 'Hello' }],
  });
  const draft = env.render(inner);
  env.effects();
  assert.equal(env.calls.navigated.length, 1);
  assert.equal(component(draft, 'ChatViewport').props.sessionId, null);
  assert.equal(component(draft, 'ChatViewport').props.draft, true);
});

for (const role of ['leader', 'business']) {
  test(role + ' chat saves its first message once and preserves draft model choices', async () => {
    const env = environment();
    const { ChatViewport } = env.load('../src/pages/chat/ChatViewport.tsx');
    const props = { agentId: role, agentRole: role, sessionId: null, draft: true,
      draftConfig: { agent_id: role, chat_model_config: model } };
    env.render(ChatViewport, props);
    env.effects();
    let tree = env.render(ChatViewport, props);
    assert.equal(env.calls.created.length, 0);
    const alternate = { ...model, model: 'selected-before-first-message' };
    const controls = component(tree, 'ChatContent').props.modelControls;
    assert.equal(nodes(tree, (node) => node.type === 'LlmSelect').length, 0);
    assert.equal(nodes(controls, (node) => node.type === 'LlmSelect').length, role === 'leader' ? 2 : 1);
    await nodes(controls, (node) => node.props?.id === 'coordinator-llm-select')[0].props.onChange(alternate);
    tree = env.render(ChatViewport, props);
    assert.equal(env.calls.updated.length, 0);
    assert.equal(component(tree, 'ChatContent').props.disabled, false);
    await component(tree, 'ChatContent').props.onSend(content);
    assert.equal(env.calls.created.length, 1);
    const saved = env.calls.created[0];
    assert.equal(saved.chat_model_config.model, alternate.model);
    assert.equal(saved.initial_message.role, 'user');
    assert.equal(saved.initial_message.content[0].text, 'Hello');
    assert.ok(saved.workspace_id);
    assert.ok(!('knowledge_config' in saved), 'omitted KBs still inherit agent defaults');
    assert.equal(env.calls.triggered.length, 1);
    assert.equal(env.calls.triggered[0].input.id, saved.initial_message.id);
    assert.equal(env.calls.navigated[0][0], '/chat/' + role + '/saved');
  });
}

for (const sessionId of [null, 'existing']) {
  test(`Leader entry opens the main chat with ${sessionId ?? 'a draft'} and preserves its model`, async () => {
    const env = environment();
    env.mocks['@/api'].workforceApi.bootstrapLeader = async () => ({
      agent_id: 'leader', session_id: sessionId, chat_model_config: model,
    });
    const { LeaderPage } = env.load('../src/pages/workforce/leader/index.tsx');
    env.render(LeaderPage);
    env.effects();
    await flush();
    assert.equal(env.calls.created.length, 0);
    assert.equal(env.calls.navigated.length, 1);
    const [path, options] = env.calls.navigated[0];
    assert.equal(path, `/chat/leader/${sessionId ?? 'new'}`);
    assert.equal(options.replace, true);
    assert.equal(options.state.draftConfig.agent_id, 'leader');
    assert.deepEqual(options.state.draftConfig.chat_model_config, model);
  });
}

test('Leader bootstrap failure keeps the error visible without navigating', async () => {
  const env = environment();
  env.mocks['@/api'].workforceApi.bootstrapLeader = async () => { throw new Error('Offline'); };
  const { LeaderPage } = env.load('../src/pages/workforce/leader/index.tsx');
  env.render(LeaderPage);
  env.effects();
  await flush();
  const tree = env.render(LeaderPage);
  assert.equal(component(tree, 'EmptyTitle').props.children, 'Không thể mở Leader');
  assert.equal(env.calls.navigated.length, 0);
});

test('a failed first run still opens the session containing the saved user message', async () => {
  const env = environment();
  env.mocks['@/api'].chatApi.trigger = async () => { throw new Error('Model unavailable'); };
  const { ChatViewport } = env.load('../src/pages/chat/ChatViewport.tsx');
  const selected = [];
  const props = { agentId: 'leader', sessionId: null, draft: true,
    draftConfig: { agent_id: 'leader', chat_model_config: model },
    onSessionCreated: (id) => selected.push(id) };
  env.render(ChatViewport, props);
  env.effects();
  const tree = env.render(ChatViewport, props);
  await assert.rejects(component(tree, 'ChatContent').props.onSend(content), /Model unavailable/);
  assert.equal(env.calls.created[0].initial_message.content[0].text, 'Hello');
  assert.deepEqual(selected, ['saved']);
  assert.equal(env.calls.navigated.length, 0);
});

test('an existing sub-agent conversation sends normally without creating another session', async () => {
  const env = environment();
  const { ChatViewport } = env.load('../src/pages/chat/ChatViewport.tsx');
  const props = { agentId: 'sub-agent', sessionId: 'existing' };
  env.render(ChatViewport, props);
  env.effects();
  const tree = env.render(ChatViewport, props);
  await component(tree, 'ChatContent').props.onSend(content, 'target-agent');
  assert.equal(env.calls.created.length, 0);
  assert.equal(env.calls.sent.length, 1);
  assert.equal(env.calls.sent[0][1], 'target-agent');
});

test('Builder new conversation stays local until the user sends text', async () => {
  const env = environment();
  const api = env.mocks['@/api'].workforceApi;
  api.prepare = async (...args) => { env.calls.sent.push(args); return { conversation_id: 'builder-saved' }; };
  api.getBuilderConversation = async () => ({ messages: [], proposal: null });
  const Builder = builderPage(env);
  let tree = env.render(Builder);
  nodes(tree, (node) => node.props?.['aria-label'] === 'Hội thoại mới')[0].props.onClick();
  tree = env.render(Builder);
  assert.equal(env.calls.sent.length, 0);
  const selector = component(tree, 'LlmSelect');
  assert.equal(nodes(component(tree, 'header'), (node) => node.type === 'LlmSelect').length, 0);
  const composer = nodes(tree, (node) => node.type === 'div' &&
    nodes(node, (child) => child.type === 'Textarea').length === 1 &&
    node.props.className?.includes('rounded-[28px]'))[0];
  assert.equal(component(composer, 'LlmSelect'), selector);
  assert.ok(nodes(composer, (node) => node.props?.['aria-label'] === 'Gửi cho Builder').length);
  component(tree, 'LlmSelect').props.onChange(model);
  component(tree, 'Textarea').props.onChange({ target: { value: 'Build an agent' } });
  tree = env.render(Builder);
  nodes(tree, (node) => node.props?.['aria-label'] === 'Gửi cho Builder')[0].props.onClick();
  await flush();
  assert.equal(env.calls.sent.length, 1);
  assert.equal(env.calls.sent[0][0], 'Build an agent');
  assert.equal(env.calls.sent[0][2], null);
});

test('failed draft creation keeps typed text; concurrent submits cannot create duplicates', async () => {
  const env = environment();
  const { TextInput } = env.load('../src/components/chat/TextInput.tsx');
  let attempts = 0, finish;
  const props = { allowedInputTypes: [], fileProcessor: async () => null,
    onSend: async () => { attempts++; await new Promise((resolve, reject) => { finish = { resolve, reject }; }); } };
  let tree = env.render(TextInput, props);
  component(tree, 'textarea').props.onChange({ target: { value: 'Keep this draft' } });
  tree = env.render(TextInput, props);
  const button = nodes(tree, (node) => node.type === 'Button' && node.props?.onClick?.constructor.name === 'AsyncFunction')[0];
  const first = button.props.onClick();
  await button.props.onClick();
  assert.equal(attempts, 1);
  finish.reject(new Error('Offline'));
  await first;
  tree = env.render(TextInput, props);
  assert.equal(component(tree, 'textarea').props.value, 'Keep this draft');
  const retry = nodes(tree, (node) => node.type === 'Button' && node.props?.onClick?.constructor.name === 'AsyncFunction')[0].props.onClick();
  finish.resolve();
  await retry;
  tree = env.render(TextInput, props);
  assert.equal(component(tree, 'textarea').props.value, '');
  assert.equal(attempts, 2);
});


test('chat has its own shell and settings opens agent management', () => {
  const env = environment();
  let routes;
  env.mocks.react.lazy = () => null;
  env.mocks['react-router-dom'].createBrowserRouter = (value) => { routes = value; };
  env.load('../src/App.tsx');
  const chat = routes.find((route) => route.element?.type === 'ChatLayout');
  assert.ok(chat.children.some((route) => route.path === '/chat/:agentId?/:sessionId?/:memberId?'));
  assert.ok(chat.children.some((route) => route.path === '/workforce/leader'));
  assert.ok(chat.children.some((route) => route.path === '/workforce/builder'));
  const settings = routes.find((route) => route.element?.type === 'SettingsLayout').children[0].children;
  assert.ok(!settings.some((route) => route.path.startsWith('/chat')));
  assert.ok(!settings.some((route) => route.path === '/workforce/builder'));
  assert.equal(settings.find((route) => route.path === '/settings').element.props.to, '/workforce/agents');
});

test('settings navigation omits the chat icon and keeps the return button', () => {
  const env = environment();
  const { SettingsSidebar } = env.load('../src/components/layout/SettingsSidebar.tsx');
  const tree = env.render(SettingsSidebar);
  assert.equal(nodes(tree, (node) => node.props?.tooltip === 'common.chat').length, 0);
  assert.equal(nodes(tree, (node) => node.props?.tooltip === 'shell.builder').length, 0);
  const back = nodes(tree, (node) => node.props?.tooltip === 'shell.backToChat')[0];
  back.props.onClick();
  assert.equal(env.calls.navigated[0][0], '/chat');
});

test('Builder is pinned after Leader in flat and shared agent lists, only when enabled', () => {
  for (const shared of [false, true]) {
    const env = environment({ 'lucide-react': {
      Check: 'Check', ChevronDown: 'ChevronDown', Crown: 'Crown', Pin: 'Pin',
    } });
    const { AgentSelect } = env.load('../src/components/select/AgentSelect.tsx');
    const agents = [
      { id: 'worker', editable: !shared, data: { name: 'Worker' } },
      { id: 'leader', editable: true, data: { name: 'Leader', system_role: 'leader' } },
    ];
    const selected = [];
    const tree = env.render(AgentSelect, { agents, value: 'leader', builderSelected: true,
      onSelectBuilder: () => selected.push('builder'), onChange: (id) => selected.push(id) });
    const items = nodes(tree, (node) => node.type === 'DropdownMenuItem');
    assert.deepEqual(items.map((item) => component(item, 'ClayAvatar').props.id),
      ['leader', 'agent-builder', 'worker']);
    assert.equal(component(items[0], 'Crown'), undefined);
    assert.equal(component(items[0], 'ClayAvatar').props.label, 'Agent group');
    assert.ok(nodes(items[0], (node) => node.props?.children === 'Agent group').length);
    assert.ok(component(items[0], 'Pin'));
    assert.ok(component(items[1], 'Pin'));
    assert.equal(component(items[2], 'Pin'), undefined);
    assert.ok(items[0].props.className.includes('font-semibold'));
    assert.ok(items[1].props.className.includes('font-semibold'));
    assert.equal(items[2].props.className, undefined);
    assert.equal(component(tree, 'ClayAvatar').props.id, 'agent-builder');
    assert.ok(component(items[1], 'Check').props.className.includes('opacity-100'));
    assert.ok(component(items[0], 'Check').props.className.includes('opacity-0'));
    const leaderSelected = env.render(AgentSelect, { agents, value: 'leader' });
    const trigger = component(leaderSelected, 'DropdownMenuTrigger');
    assert.equal(component(trigger, 'ClayAvatar').props.label, 'Agent group');
    assert.ok(nodes(trigger, (node) => node.props?.children === 'Agent group').length);
    items[1].props.onSelect();
    items[0].props.onSelect();
    assert.deepEqual(selected, ['builder', 'leader']);
    const resourcePicker = env.render(AgentSelect, { agents });
    assert.equal(nodes(resourcePicker, (node) => node.type === 'DropdownMenuItem').length, 2);
    const empty = env.render(AgentSelect, { agents: [], onSelectBuilder: () => {} });
    assert.equal(nodes(empty, (node) => node.type === 'DropdownMenuItem').length, 1);
  }
});

test('Agent group and Builder use different existing animated portrait roles', () => {
  const env = environment();
  const { portraitFor } = env.load('../src/components/ui/clay-portrait.tsx');
  assert.equal(portraitFor('Agent group'), 'leader');
  assert.equal(portraitFor('Builder'), 'builder');
});

test('chat opens the existing Builder and Builder can switch back to agents on desktop and mobile', () => {
  const chat = environment();
  const { ChatPage } = chat.load('../src/pages/chat/index.tsx');
  const inner = nodes(ChatPage(), (node) => node.type?.name === 'ChatPageInner')[0].type;
  component(chat.render(inner), 'AgentSelect').props.onSelectBuilder();
  assert.equal(chat.calls.navigated[0][0], '/workforce/builder');

  const closed = [];
  const builder = environment({ '@/components/ui/sidebar': {
    useSidebar: () => ({ isMobile: true, setOpenMobile: (open) => closed.push(open) }),
  } });
  const tree = builder.render(builderPage(builder));
  const pickers = nodes(tree, (node) => node.type === 'AgentSelect');
  assert.equal(pickers.length, 1);
  for (const picker of pickers) {
    assert.equal(picker.props.builderSelected, true);
    picker.props.onSelectBuilder();
    assert.equal(builder.calls.navigated.length, 0);
    picker.props.onChange('leader');
  }
  assert.deepEqual(builder.calls.navigated.map(([path]) => path), ['/chat/leader']);
  assert.deepEqual(closed, [false, false]);
  assert.equal(component(tree, 'AccountMenu').props.showSettings, true);
});

test('Builder new session and group actions share the chat layout and reuse group creation', async () => {
  let refreshed = 0;
  const env = environment({ '@/hooks/useAgents': { useAgents: () => ({
    agents: [], refetch: async () => { refreshed++; },
  }) }, '@/components/ui/sidebar': {
    SidebarHeader: 'SidebarHeader',
    useSidebar: () => ({ isMobile: false, setOpenMobile() {} }),
  } });
  const Builder = builderPage(env);
  let tree = env.render(Builder);
  const header = component(tree, 'SidebarHeader');
  const actions = nodes(header, (node) => node.props?.className === 'grid grid-cols-2 gap-2')[0];
  const buttons = nodes(actions, (node) => node.type === 'Button');
  assert.equal(buttons.length, 2);
  assert.ok(buttons[0].props.children.includes('chat.newSession'));
  assert.ok(buttons[1].props.children.includes('groupChat.create'));
  component(tree, 'Textarea').props.onChange({ target: { value: 'Builder draft' } });
  buttons[1].props.onClick();
  tree = env.render(Builder);
  assert.equal(component(tree, 'CreateGroupDialog').props.open, true);
  assert.equal(component(tree, 'Textarea').props.value, 'Builder draft');
  assert.equal(env.calls.created.length, 0);
  await component(tree, 'CreateGroupDialog').props.onCreated('leader', 'group-session');
  assert.equal(refreshed, 1);
  assert.equal(env.calls.navigated[0][0], '/chat/leader/group-session');
  buttons[0].props.onClick();
  tree = env.render(Builder);
  assert.equal(component(tree, 'Textarea').props.value, '');
  assert.equal(env.calls.created.length, 0);
});

test('Builder uses the same sidebar frame as chat on desktop and mobile', () => {
  for (const isMobile of [false, true]) {
    const env = environment({
      '@/hooks/use-mobile': { useIsMobile: () => isMobile },
      '@/components/ui/sidebar': {
        useSidebar: () => ({ isMobile, setOpenMobile() {} }), Sidebar: 'Sidebar', SidebarProvider: 'SidebarProvider',
        SidebarHeader: 'SidebarHeader', SidebarContent: 'SidebarContent',
        SidebarFooter: 'SidebarFooter', SidebarTrigger: 'SidebarTrigger',
      },
    });
    const { ChatPage } = env.load('../src/pages/chat/index.tsx');
    const chatPage = ChatPage();
    const inner = nodes(chatPage, (node) => node.type?.name === 'ChatPageInner')[0].type;
    const chat = env.render(inner);
    const builderEnv = environment(env.mocks);
    const { AgentBuilderPage } = builderEnv.load('../src/pages/workforce/builder/index.tsx');
    const builderWrapper = AgentBuilderPage();
    const builder = builderEnv.render(builderPage(builderEnv));
    assert.equal(component(builderWrapper, 'SidebarProvider').props.style['--sidebar-width'],
      component(chatPage, 'SidebarProvider').props.style['--sidebar-width']);
    for (const part of ['Sidebar', 'SidebarHeader', 'SidebarContent', 'SidebarFooter']) {
      assert.equal(component(builder, part).props.className, component(chat, part).props.className);
    }
    assert.equal(component(builder, 'Sidebar').props.collapsible,
      component(chat, 'Sidebar').props.collapsible);
    assert.ok(component(component(builder, 'SidebarHeader'), 'Brand'));
    assert.ok(component(component(builder, 'SidebarHeader'), 'AgentSelect'));
    assert.ok(component(builder, 'SidebarTrigger'));
    assert.equal(nodes(builder, (node) => node.type === 'AgentSelect').length, 1);
  }
});

test('a saved team panel starts unchecked in a new viewport while other panels persist', () => {
  const stored = new Map([['chat_panel_layout', JSON.stringify([['team', 'mcp'], ['knowledge']])]]);
  const env = environment({}, {
    getItem: (key) => stored.get(key) ?? null,
    setItem: (key, value) => stored.set(key, value),
  });
  const { ChatViewport } = env.load('../src/pages/chat/ChatViewport.tsx');
  const props = { agentId: 'business', sessionId: null, draft: true };
  const checkbox = (tree, label) => nodes(tree, (node) =>
    node.type === 'DropdownMenuCheckboxItem' && node.props.children.includes(label))[0];
  let tree = env.render(ChatViewport, props);
  assert.equal(checkbox(tree, 'common.team').props.checked, false);
  assert.equal(checkbox(tree, 'MCP').props.checked, true);
  assert.equal(checkbox(tree, 'panel.knowledge.title').props.checked, true);
  checkbox(tree, 'common.team').props.onCheckedChange();
  tree = env.render(ChatViewport, props);
  assert.equal(checkbox(tree, 'common.team').props.checked, true);
});


for (const internalOnly of [false, true]) {
  test(`personal chat hides team worker sessions${internalOnly ? ' and shows the empty state' : ' but keeps user and leader chats'}`, () => {
    const env = environment();
    const view = (id, origin, team = null) => ({
      session: { id, origin: { type: origin }, config: { name: id }, updated_at: '2026-10-21T00:00:00Z' },
      status: 'idle', preview: 'Message', team,
    });
    const internal = view('internal', 'team', { team: { session_id: 'leader-session' }, members: [] });
    const sessions = internalOnly ? [internal] : [internal, view('personal', 'user'),
      view('leader-session', 'user', { team: { session_id: 'leader-session' }, members: [] }),
      view('team-leader-session', 'team', { team: { session_id: 'team-leader-session' }, members: [] })];
    env.mocks['@/hooks/useSessions'].useSessions = () => ({ sessions });
    const { ChatPage } = env.load('../src/pages/chat/index.tsx');
    const inner = nodes(ChatPage(), (node) => node.type?.name === 'ChatPageInner')[0].type;
    const tree = env.render(inner);
    const rows = nodes(tree, (node) => node.type === 'ChatRow');
    assert.deepEqual(rows.map((row) => row.key), internalOnly ? [] : ['personal', 'leader-session', 'team-leader-session']);
    assert.equal(nodes(tree, (node) => node.type === 'p' &&
      node.props.children === 'chat.session.emptyTitle').length, internalOnly ? 1 : 0);
    env.effects();
    assert.equal(env.calls.navigated[0]?.[0], internalOnly ? undefined : '/chat/agent/personal');
  });
}

test('a team worker session remains accessible by its direct link', () => {
  const env = environment();
  env.mocks['react-router-dom'].useParams = () => ({ agentId: 'agent', sessionId: 'internal' });
  env.mocks['@/hooks/useSessions'].useSessions = () => ({ sessions: [{
    session: { id: 'internal', origin: { type: 'team' }, config: { name: 'Internal' } },
    status: 'idle', preview: 'Message', team: null,
  }] });
  const { ChatPage } = env.load('../src/pages/chat/index.tsx');
  const inner = nodes(ChatPage(), (node) => node.type?.name === 'ChatPageInner')[0].type;
  const tree = env.render(inner);
  assert.equal(component(tree, 'ChatViewport').props.sessionId, 'internal');
  assert.equal(nodes(tree, (node) => node.type === 'ChatRow').length, 0);
  env.effects();
  assert.equal(env.calls.navigated.length, 0);
});


test('the Leader group panel opens after loading, can be closed, and closes when switching to a member or draft', () => {
  const env = environment();
  let sessions = [];
  env.mocks['@/hooks/useSessions'].useSessions = () => ({ sessions, refetch: async () => sessions });
  const { ChatViewport } = env.load('../src/pages/chat/ChatViewport.tsx');
  const props = { agentId: 'leader-agent', sessionId: 'leader-session' };
  const checkbox = (tree) => nodes(tree, (node) => node.type === 'DropdownMenuCheckboxItem'
    && node.props.children.includes('common.team'))[0];
  env.render(ChatViewport, props);
  env.effects();
  const team = { team: { session_id: 'leader-session', data: { name: 'Group' } }, members: [] };
  const view = (id) => ({ session: { id, config: {}, origin: { type: 'team' }, state: {} }, team });
  sessions = [view('leader-session')];
  env.render(ChatViewport, props);
  env.effects();
  let tree = env.render(ChatViewport, props);
  assert.equal(checkbox(tree).props.checked, true);
  checkbox(tree).props.onCheckedChange();
  env.render(ChatViewport, props);
  env.effects();
  tree = env.render(ChatViewport, props);
  assert.equal(checkbox(tree).props.checked, false, 'refresh must not undo manual closure');

  checkbox(tree).props.onCheckedChange();
  sessions = [view('member-session')];
  const member = { agentId: 'member-agent', sessionId: 'member-session', readOnly: true };
  env.render(ChatViewport, member);
  env.effects();
  tree = env.render(ChatViewport, member);
  assert.equal(checkbox(tree).props.checked, false);

  sessions = [view('leader-session')];
  env.render(ChatViewport, props);
  env.effects();
  tree = env.render(ChatViewport, props);
  assert.equal(checkbox(tree).props.checked, true);
  const draft = { agentId: 'leader-agent', sessionId: null, draft: true };
  env.render(ChatViewport, draft);
  env.effects();
  tree = env.render(ChatViewport, draft);
  assert.equal(checkbox(tree).props.checked, false);
});

test('chat and settings each keep one account menu in their own footer', () => {
  const env = environment();
  env.mocks['react-router-dom'].useLocation = () => ({ pathname: '/workforce/agents/agent' });
  env.mocks['@/components/ui/sidebar'].SidebarFooter = 'SidebarFooter';
  const { SettingsSidebar } = env.load('../src/components/layout/SettingsSidebar.tsx');
  const tree = env.render(SettingsSidebar);
  const accounts = nodes(tree, (node) => node.type === 'AccountMenu');
  assert.equal(accounts.length, 1);
  assert.equal(component(component(tree, 'SidebarFooter'), 'AccountMenu'), accounts[0]);
  assert.ok(!accounts[0].props.showSettings);
  assert.ok(!accounts[0].props.showTour);
  const management = nodes(tree, (node) => node.props?.tooltip === 'shell.agentStudio')[0];
  assert.equal(management.props.isActive, true);
  management.props.onClick();
  assert.equal(env.calls.navigated[0][0], '/workforce/agents');
  const { ChatPage } = env.load('../src/pages/chat/index.tsx');
  const inner = nodes(ChatPage(), (node) => node.type?.name === 'ChatPageInner')[0].type;
  const chatTree = env.render(inner);
  const chatAccounts = nodes(chatTree, (node) => node.type === 'AccountMenu');
  assert.equal(chatAccounts.length, 1);
  assert.equal(component(component(chatTree, 'SidebarFooter'), 'AccountMenu'), chatAccounts[0]);
  assert.equal(chatAccounts[0].props.showSettings, true);
  assert.equal(chatAccounts[0].props.showTour, true);
});

for (const memberCount of [0, 1, 4]) {
  test(`room avatar represents ${memberCount} other agents without duplicating the coordinator`, () => {
    const env = environment({ '@/components/ui/clay-avatar': {
      ClayAvatar: 'ClayAvatar', clayTone: (id) => ({ background: `color-${id}` }),
    } });
    const { TeamSessionAvatar } = env.load('../src/components/chat/TeamSessionAvatar.tsx');
    const leader = { id: 'leader', data: { name: 'Workforce Leader' } };
    const workers = Array.from({ length: memberCount }, (_, index) => ({
      id: `worker-${index}`, data: { name: `Specialist ${index}` },
    }));
    const team = { leader_agent: leader, members: [leader, ...workers].map((agent) => ({ agent })) };
    const props = { team, agentId: leader.id, working: true };
    const tree = env.render(TeamSessionAvatar, props);
    const portraits = nodes(tree, (node) => node.type === 'ClayAvatar');
    assert.equal(portraits.length, Math.min(3, memberCount + 1));
    assert.equal(portraits[0].props.id, 'leader');
    const count = nodes(tree, (node) => node.type === 'span' &&
      Array.isArray(node.props.children) && node.props.children[0] === '+');
    if (memberCount === 0) {
      assert.equal(tree.type, 'ClayAvatar');
      assert.equal(count.length, 0);
    } else {
      assert.equal(count[0].props.children[1], memberCount);
      assert.equal(portraits[0].props.working, true);
      assert.ok(tree.props['aria-label'].includes(workers[memberCount - 1].data.name));
      const tiles = nodes(tree, (node) => node.props?.style?.borderColor);
      assert.equal(new Set(tiles.map((tile) => tile.props.style.borderColor)).size, tiles.length);
      assert.ok(tiles.every((tile) => tile.props.className.includes('motion-safe:')));
      const idle = env.render(TeamSessionAvatar, { ...props, working: false });
      assert.ok(nodes(idle, (node) => node.props?.style?.borderColor)
        .every((tile) => !tile.props.className.includes('animate-')));
    }
  });
}
