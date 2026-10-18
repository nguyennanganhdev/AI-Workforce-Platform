import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const flush = () => new Promise(setImmediate);
const noop = () => {};
const t = (key) => key;

// Execute the actual component handlers with deterministic hook state and API I/O.
function mount(path, name, mocks, initialProps) {
	const slots = [],
		effects = [];
	let cursor,
		props = initialProps;
	const hooks = {
		useState(initial) {
			const i = cursor++;
			if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
			return [
				slots[i],
				(value) => {
					slots[i] = typeof value === 'function' ? value(slots[i]) : value;
				},
			];
		},
		useRef(initial) {
			const i = cursor++;
			return (slots[i] ??= { current: initial });
		},
		useMemo: (fn) => fn(),
		useCallback: (fn) => fn,
		useEffect(effect, deps) {
			const i = cursor++;
			if (!slots[i] || deps.some((value, j) => !Object.is(value, slots[i].deps[j]))) {
				effects.push(() => {
					slots[i]?.cleanup?.();
					slots[i] = { deps, cleanup: effect() };
				});
			}
		},
	};
	const known = {
		react: hooks,
		'react/jsx-runtime': require('react/jsx-runtime'),
		'react-router-dom': { useNavigate: () => noop },
		'react-i18next': { useTranslation: () => ({ t }) },
		'@/i18n/useI18n': { useTranslation: () => ({ t }) },
		'@/lib/api-error': { formatApiErrorForAlert: (error) => `HTTP ${error.status}` },
		...mocks,
	};
	const context = {
		exports: {},
		require: (id) => known[id] ?? new Proxy({}, { get: (_, key) => key }),
		localStorage: { getItem: () => null, setItem: noop },
		console,
	};
	vm.runInNewContext(
		ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
			compilerOptions: {
				module: ts.ModuleKind.CommonJS,
				target: ts.ScriptTarget.ES2022,
				jsx: ts.JsxEmit.ReactJSX,
			},
		}).outputText,
		context,
	);
	function render(next = props) {
		props = next;
		cursor = 0;
		const tree = context.exports[name](props);
		effects.splice(0).forEach((effect) => effect());
		return tree;
	}
	return {
		render,
		async settle(next = props) {
			render(next);
			await flush();
			render();
			await flush();
			return render();
		},
	};
}

function nodes(tree, type) {
	if (!tree || typeof tree !== 'object') return [];
	return [
		...(tree.type === type ? [tree.props] : []),
		...[tree.props?.children].flat(Infinity).flatMap((child) => nodes(child, type)),
	];
}
const model = (name) => ({
	type: 'openai',
	credential_id: 'credential',
	model: name,
	parameters: {},
});
const session = (id, coordinator, shared) => ({
	session: {
		id,
		config: {
			chat_model_config: model(coordinator),
			sub_agent_chat_model_config: model(shared),
		},
	},
	status: 'idle',
	team: null,
});

function viewport(update) {
	const views = [
		session('one', 'coordinator-one', 'shared-one'),
		session('two', 'coordinator-two', 'shared-two'),
	];
	const refetch = async () => views;
	const mounted = mount(
		'../src/pages/chat/ChatViewport.tsx',
		'ChatViewport',
		{
			'@/api': {
				sessionApi: {
					update: async (...args) => {
						const result = await update(...args);
						Object.assign(
							views.find((view) => view.session.id === args[0]).session.config,
							args[2],
						);
						return result;
					},
				},
			},
			'@/hooks/useSessions': { useSessions: () => ({ sessions: views, refetch }) },
			'@/hooks/useAvailableModels': { useAvailableModels: () => ({ groups: {} }) },
			'@/hooks/use-mobile': { useIsMobile: () => false },
			'@/hooks/useMessages': {
				useMessages: () => ({ msgs: [], phase: 'idle', subagentHitl: [] }),
			},
			'@/hooks/useWorkspace.ts': { useWorkspace: () => ({ mcps: [], skills: [] }) },
			'@/hooks/useWorkspaceStatus': { useWorkspaceStatus: () => ({ refetch: noop }) },
			'@/hooks/useKnowledgeBases': { useKnowledgeBases: () => ({ knowledgeBases: [] }) },
			'@/hooks/useKnowledgeBaseMiddlewareSchema': {
				useKnowledgeBaseMiddlewareSchema: () => ({ schema: null }),
			},
		},
		{ agentId: 'leader', sessionId: 'one' },
	);
	const selectors = (tree) => nodes(tree, 'LlmSelect');
	return { ...mounted, selectors, views };
}

test('coordinator and shared subagent models save independently and reload per session', async () => {
	const calls = [];
	const ui = viewport(async (...args) => calls.push(args));
	let pickers = ui.selectors(await ui.settle());
	assert.equal(pickers[0].value.model, 'shared-one');
	assert.equal(pickers[1].value.model, 'coordinator-one');
	await pickers[0].onChange(model('new-shared'));
	pickers = ui.selectors(await ui.settle());
	assert.equal(pickers[0].value.model, 'new-shared');
	assert.equal(pickers[1].value.model, 'coordinator-one');
	await pickers[1].onChange(model('new-coordinator'));
	pickers = ui.selectors(await ui.settle({ agentId: 'leader', sessionId: 'two' }));
	assert.equal(pickers[0].value.model, 'shared-two');
	assert.equal(pickers[1].value.model, 'coordinator-two');
	pickers = ui.selectors(await ui.settle({ agentId: 'leader', sessionId: 'one' }));
	assert.equal(pickers[0].value.model, 'new-shared');
	assert.equal(pickers[1].value.model, 'new-coordinator');
	assert.deepEqual(
		calls.map(([id, agentId, body]) => [id, agentId, Object.keys(body)]),
		[
			['one', 'leader', ['sub_agent_chat_model_config']],
			['one', 'leader', ['chat_model_config']],
		],
	);
	await pickers[0].onChange(null);
	assert.equal(ui.selectors(await ui.settle())[0].value, null);
});

test('403, 409 and 422 keep both saved model selections and permit retry', async () => {
	for (const status of [403, 409, 422]) {
		const ui = viewport(async () => {
			throw { status };
		});
		let tree = await ui.settle();
		for (const picker of ui.selectors(tree)) {
			await picker.onChange(model('rejected'));
			tree = await ui.settle();
			const pickers = ui.selectors(tree);
			assert.equal(pickers[0].value.model, 'shared-one');
			assert.equal(pickers[1].value.model, 'coordinator-one');
			assert.ok(pickers.every((value) => !value.disabled));
		}
	}
});

test('an old save completing after a session switch does not change the new session', async () => {
	let release;
	const ui = viewport(
		() =>
			new Promise((resolve) => {
				release = resolve;
			}),
	);
	const save = ui.selectors(await ui.settle())[0].onChange(model('late-shared'));
	await ui.settle({ agentId: 'leader', sessionId: 'two' });
	release();
	await save;
	const pickers = ui.selectors(await ui.settle());
	assert.equal(pickers[0].value.model, 'shared-two');
	assert.equal(pickers[1].value.model, 'coordinator-two');
	assert.ok(pickers.every((value) => !value.disabled));
});

test('read-only team inspection cannot write models, and running sessions disable selectors', async () => {
	let writes = 0;
	const ui = viewport(async () => {
		writes++;
	});
	const tree = await ui.settle({ agentId: 'worker', sessionId: 'one', readOnly: true });
	const pickers = ui.selectors(tree);
	assert.equal(pickers.length, 1);
	assert.equal(pickers[0].disabled, true);
	await pickers[0].onChange(model('forbidden'));
	assert.equal(writes, 0);
	ui.views[0].status = 'running';
	assert.ok(
		ui
			.selectors(await ui.settle({ agentId: 'leader', sessionId: 'one' }))
			.every((value) => value.disabled),
	);
});

function editor({ role = 'business', editable = true, toolFailure, agentFailure } = {}) {
	const calls = [],
		closed = [];
	const schema = {};
	const agent = {
		id: 'agent',
		editable,
		data: {
			name: 'Agent',
			system_role: role,
			system_prompt: 'Original prompt',
			execution_mode: role === 'business' ? 'tool_backed' : null,
			context_config: { trigger_ratio: 0.8 },
			react_config: { max_iters: 10 },
			invite_config: { invitable: true, invite_description: 'Help' },
		},
	};
	const settings = {
		selected_tool_ids: ['mcp:tool'],
		selected_knowledge_base_ids: ['kb'],
		mcps: [],
		knowledge_bases: [],
	};
	const ui = mount(
		'../src/components/dialog/EditAgentDialog.tsx',
		'EditAgentDialog',
		{
			'@/api': {
				workforceApi: {
					getAgentTools: async () => settings,
					updateAgentTools: async (...args) => {
						calls.push(['tools', ...args]);
						if (toolFailure) throw { status: toolFailure };
					},
				},
			},
			'@/hooks/useAgents': {
				useAgents: () => ({
					update: async (...args) => {
						calls.push(['agent', ...args]);
						if (agentFailure) throw { status: agentFailure };
					},
				}),
			},
			'@/hooks/useAgentSchema': { useAgentSchema: () => ({ schema }) },
			'@/components/form/agent-form-utils': {
				defaultAgentFormValues: () => ({
					identity: {},
					context_config: {},
					react_config: {},
					invite_config: {},
				}),
			},
		},
		{ open: true, agent, onOpenChange: (value) => closed.push(value) },
	);
	const save = (tree) =>
		nodes(tree, 'Button').find((button) => button.children?.[1] === 'common.save');
	return { ...ui, agent, calls, closed, save };
}

test('agent form saves selected tools, knowledge, prompt, context, ReAct and invite configuration', async () => {
	const ui = editor();
	const tree = await ui.settle();
	assert.equal(ui.save(tree).disabled, false);
	await ui.save(tree).onClick();
	assert.deepEqual(JSON.parse(JSON.stringify(ui.calls[0])), [
		'tools',
		'agent',
		['mcp:tool'],
		['kb'],
	]);
	assert.deepEqual(JSON.parse(JSON.stringify(ui.calls[1][2])), {
		name: 'Agent',
		system_prompt: 'Original prompt',
		context_config: { trigger_ratio: 0.8 },
		react_config: { max_iters: 10 },
		invite_config: { invitable: true, invite_description: 'Help' },
	});
	assert.deepEqual(ui.closed, [false]);
});

test('failed tool writes keep the editor open; partial saves explicitly report what was saved', async () => {
	for (const options of [
		{ toolFailure: 422 },
		{ agentFailure: 403 },
		{ agentFailure: 409 },
		{ agentFailure: 422 },
	]) {
		const ui = editor(options);
		await ui.save(await ui.settle()).onClick();
		const errors = nodes(await ui.settle(), 'AlertDescription');
		assert.equal(ui.closed.length, 0);
		assert.ok(
			errors.some((error) =>
				String(error.children).includes(
					`HTTP ${options.toolFailure ?? options.agentFailure}`,
				),
			),
		);
		assert.equal(ui.calls.length, options.toolFailure ? 1 : 2);
		if (options.agentFailure)
			assert.match(errors[0].children, /agentManagement.resourcesSaved/);
	}
});

test('Leader edits omit the governed prompt and read-only agents cannot save', async () => {
	const leader = editor({ role: 'leader' });
	const tree = await leader.settle();
	assert.equal(nodes(tree, 'AgentFormFields')[0].governedPrompt, true);
	await leader.save(tree).onClick();
	assert.equal('system_prompt' in leader.calls[0][2], false);
	const reader = editor({ editable: false });
	const readonlyTree = await reader.settle();
	assert.equal(reader.save(readonlyTree).disabled, true);
	await reader.save(readonlyTree).onClick();
	assert.equal(reader.calls.length, 0);
});

test('agent management hides read-only mutations and publishes through the existing API', async () => {
	const calls = [];
	const agents = [editor().agent, { ...editor().agent, id: 'reader', editable: false }];
	const ui = mount(
		'../src/pages/workforce/agents/index.tsx',
		'AgentManagementPage',
		{
			'react-router-dom': {
				useNavigate: () => noop,
				useParams: () => ({}),
				useSearchParams: () => [new URLSearchParams(), noop],
			},
			'@/api': { workforceApi: { setLifecycle: async (...args) => calls.push(args) } },
			'@/hooks/useAgents': {
				useAgents: () => ({ agents, refetch: async () => calls.push('refetch') }),
			},
		},
		{},
	);
	const tree = await ui.settle();
	const articles = nodes(tree, 'article');
	const buttons = (article) => nodes({ type: 'article', props: article }, 'Button');
	assert.equal(buttons(articles[1]).length, 1);
	const publish = buttons(articles[0]).find((button) =>
		button.children?.includes('agentManagement.publish'),
	);
	assert.ok(publish);
	await publish.onClick();
	await flush();
	assert.deepEqual(calls, [['agent', 'published'], 'refetch']);
});
