import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const context = {
	exports: {},
	require: (id) => {
		if (id === 'react/jsx-runtime') return require(id);
		if (id === 'react') return { useState: () => ['', () => {}] };
		if (id === '@/i18n/useI18n') return { useTranslation: () => ({ t: (key) => key }) };
		return new Proxy({}, { get: (_, name) => name });
	},
};
vm.runInNewContext(ts.transpileModule(readFileSync(
	new URL('../src/components/panel/AgentToolsPanel.tsx', import.meta.url), 'utf8',
), {
	compilerOptions: {
		module: ts.ModuleKind.CommonJS,
		target: ts.ScriptTarget.ES2022,
		jsx: ts.JsxEmit.ReactJSX,
	},
}).outputText, context);

const binding = {
	mcp_id: 'restaurant-id', mcp_name: 'abcd', tool_name: 'search_restaurants',
	description: 'Saved description',
};
function render({ name = 'mcp__abcd__search_restaurants', healthy = true, bindings = [binding], mcps } = {}) {
	return context.exports.AgentToolsPanel({
		bindings,
		mcps: mcps ?? [{
			name: 'abcd', is_healthy: healthy, error: null,
			tools: [{ name, description: 'Live description' }],
		}],
		loading: false,
	});
}
function nodes(tree, type) {
	if (!tree || typeof tree !== 'object') return [];
	return [
		...(tree.type === type ? [tree.props] : []),
		...[tree.props?.children].flat(Infinity).flatMap((child) => nodes(child, type)),
	];
}
const status = (tree) => nodes(tree, 'span').find((node) => node.role === 'img')['aria-label'];

test('a healthy tool with the runtime MCP prefix is available', () => {
	const tree = render();
	assert.equal(status(tree), 'panel.mcp.healthy');
	assert.ok(nodes(tree, 'ItemDescription').some((node) => node.children === 'Live description'));
});

test('raw tool names and direct/gateway names containing special characters are supported', () => {
	assert.equal(status(render({ name: 'search_restaurants' })), 'panel.mcp.healthy');
	for (const name of ['mcp__abcd__searchxrestaurants', 'mcp__abcd__search.restaurants']) {
		assert.equal(status(render({
			name, bindings: [{ ...binding, tool_name: 'search.restaurants' }],
		})), 'panel.mcp.healthy');
	}
});

test('missing, unhealthy and unrelated tools stay unavailable', () => {
	for (const props of [
		{ mcps: [] }, { healthy: false }, { name: 'mcp__other__search_restaurants' },
		{ name: 'mcp__abcd__book_restaurant' },
	]) {
		assert.equal(status(render(props)), 'panel.agentTools.unavailable');
	}
});

test('unassigned tools from the server are not displayed', () => {
	const tree = render({ mcps: [{ name: 'abcd', is_healthy: true, tools: [
		{ name: 'mcp__abcd__search_restaurants' },
		{ name: 'mcp__abcd__unassigned_admin_tool' },
	] }] });
	assert.equal(nodes(tree, 'Item').length, 1);
	assert.ok(!JSON.stringify(tree).includes('unassigned_admin_tool'));
});
