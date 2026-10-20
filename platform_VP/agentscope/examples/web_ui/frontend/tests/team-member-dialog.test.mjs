import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../src/components/dialog/AddTeamMemberDialog.tsx', import.meta.url), 'utf8');
const agent = (id, name, role = 'business') => ({
	id, source: 'user', data: { name, system_role: role, lifecycle_state: 'published',
		invite_config: { invitable: true, invite_description: 'Tư vấn chuyên môn' } },
});
const agents = [agent('leader', 'Leader', 'leader'), agent('hotel', 'Khách sạn'), agent('flight', 'Vé máy bay')];
const flush = () => new Promise((resolve) => setImmediate(resolve));

function dialog(addTeamMember, present = []) {
	const states = [];
	let cursor = 0;
	let refreshed = 0;
	const context = {
		exports: {},
		require: (id) => {
			if (id === 'react/jsx-runtime') return require(id);
			if (id === 'react') return { useState: (initial) => {
				const index = cursor++;
				if (!(index in states)) states[index] = initial;
				return [states[index], (next) => { states[index] = typeof next === 'function' ? next(states[index]) : next; }];
			} };
			if (id === '@/api') return { sessionApi: { addTeamMember } };
			if (id === '@/hooks/useAgents') return { useAgents: () => ({ agents, loading: false, error: null, refetch() {} }) };
			if (id === '@/i18n/useI18n') return { useTranslation: () => ({ t: (key) => key }) };
			if (id === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
			return new Proxy({}, { get: (_, name) => name });
		},
	};
	vm.runInNewContext(ts.transpileModule(source, {
		compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
	}).outputText, context);
	const render = () => {
		cursor = 0;
		return context.exports.AddTeamMemberDialog({ agentId: 'leader', sessionId: 'session', present,
			onAdded: async () => { refreshed++; } });
	};
	render().props.onOpenChange(true);
	return { render, refreshed: () => refreshed };
}

function nodes(tree, type) {
	if (!tree || typeof tree !== 'object') return [];
	return [...(tree.type === type ? [tree.props] : []),
		...[tree.props?.children].flat(Infinity).flatMap((child) => nodes(child, type))];
}
const checkbox = (tree, name) => nodes(tree, 'Checkbox').find((props) => props['aria-label'] === name);

test('ticks add multiple agents without closing the list or showing a submit button', async () => {
	const added = [];
	const view = dialog(async (...args) => { added.push(args); });
	assert.equal(nodes(view.render(), 'Button').length, 1);
	assert.equal(checkbox(view.render(), 'Leader'), undefined);
	for (const name of ['Khách sạn', 'Vé máy bay']) {
		checkbox(view.render(), name).onCheckedChange(true);
		await flush();
		assert.equal(checkbox(view.render(), name).checked, true);
		assert.equal(checkbox(view.render(), name).disabled, true);
		assert.equal(view.render().props.open, true);
	}
	assert.deepEqual(added, [['session', 'leader', 'hotel'], ['session', 'leader', 'flight']]);
	assert.equal(view.refreshed(), 2);
});

test('search ignores accents and existing members cannot be re-added', async () => {
	const added = [];
	const view = dialog(async (...args) => { added.push(args); }, ['hotel']);
	assert.equal(checkbox(view.render(), 'Khách sạn').disabled, true);
	checkbox(view.render(), 'Khách sạn').onCheckedChange(true);
	await flush();
	assert.deepEqual(added, []);
	nodes(view.render(), 'Input')[0].onChange({ target: { value: 'khach san' } });
	assert.equal(nodes(view.render(), 'Checkbox').length, 1);
	assert.equal(checkbox(view.render(), 'Khách sạn').checked, true);
});

test('pending requests disable other ticks and failed requests can be retried', async () => {
	let reject;
	let fail = true;
	const view = dialog(() => fail ? new Promise((_, rejectRequest) => { reject = rejectRequest; }) : Promise.resolve());
	checkbox(view.render(), 'Khách sạn').onCheckedChange(true);
	assert.equal(checkbox(view.render(), 'Vé máy bay').disabled, true);
	reject(new Error('Please retry'));
	await flush();
	assert.equal(checkbox(view.render(), 'Khách sạn').checked, false);
	assert.equal(checkbox(view.render(), 'Khách sạn').disabled, false);
	assert.ok(nodes(view.render(), 'p').some((props) => props.role === 'alert' && props.children === 'Please retry'));
	fail = false;
	checkbox(view.render(), 'Khách sạn').onCheckedChange(true);
	await flush();
	assert.equal(checkbox(view.render(), 'Khách sạn').checked, true);
});
