import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const require = createRequire(import.meta.url);
function load(file, resolve = require) {
	const context = { exports: {}, require: resolve };
	vm.runInNewContext(ts.transpileModule(readFileSync(new URL(file, import.meta.url), 'utf8'), {
		compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
	}).outputText, context);
	return context.exports;
}
const collapsible = load('../src/components/ui/collapsible.tsx');
// The thread grouping is pure logic, so the panel uses the real module.
const teamThreads = load('../src/lib/teamThreads.ts');
let activities = [];
let runtimeBySession = {};
let selection = null;
let stateIndex = 0;
let graphProps;
let exchangesOpen;
const { TeamCoordinationGraph } = load('../src/components/panel/TeamCoordinationGraph.tsx', (id) => {
	if (id.endsWith('.css')) return {};
	if (id === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
	if (id === '@/components/ui/clay-avatar') return { ClayAvatar: () => null };
	return require(id);
});
const { TeamPanel } = load('../src/components/panel/TeamPanel.tsx', (id) => {
	if (id === 'react') return { ...React, useState: (initial) => {
		const index = stateIndex++;
		// Like React, a function initialiser is called for its value.
		return index === 1 ? [selection, (value) => { selection = value; }]
			: [typeof initial === 'function' ? initial() : initial, () => {}];
	} };
	if (id === 'react-router-dom') return { useNavigate: () => () => {} };
	if (id === '@/hooks/useTeamActivity') return { useTeamActivity: () => ({ runtimeBySession, activities }) };
	if (id === '@/components/panel/TeamCoordinationGraph') return { TeamCoordinationGraph: (props) => {
		graphProps = props;
		return React.createElement(TeamCoordinationGraph, props);
	} };
	if (id === '@/i18n/useI18n') return { useTranslation: () => ({ t: (key) => key }) };
	if (id === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
	if (id === '@/components/ui/button') return { Button: ({ children, variant, size, ...props }) =>
		React.createElement('button', props, children),
	};
	if (id === '@/components/ui/collapsible') return { ...collapsible, Collapsible: (props) =>
		React.createElement(collapsible.Collapsible, props.className?.includes('group/exchanges')
			? { ...props, open: exchangesOpen } : props),
	};
	if (id === '@/lib/teamThreads') return teamThreads;
	if (id.startsWith('@/')) return new Proxy({}, { get: () => () => null });
	return require(id);
});
const activity = (id, type, extra = {}) => ({
	id, type, sessionId: 'session', sourceName: 'Leader', targetName: null,
	kind: 'handoff', toolName: 'search_hotels', detail: null, state: 'success',
	createdAt: '2026-10-20T08:30:00Z', ...extra,
});
const team = {
	team: { id: 'team', session_id: 'session', data: { name: 'Du lịch' } },
	leader_agent: { id: 'leader', data: { name: 'Leader' } },
	members: [
		{ agent: { id: 'hotel', data: { name: 'Khách sạn' } }, session_id: 'hotel-session' },
		{ agent: { id: 'food', data: { name: 'Nhà hàng' } }, session_id: 'food-session' },
	],
};
function render(items, preserveSelection = false, openExchanges = true) {
	activities = items;
	exchangesOpen = openExchanges;
	if (!preserveSelection) selection = null;
	stateIndex = 0;
	return renderToStaticMarkup(React.createElement(TeamPanel, {
		team,
		currentSessionId: 'session', agentId: 'leader', canManage: false, onMembersChanged: async () => {},
	}));
}

test('collapsed exchanges hide message bodies while the graph stays visible', () => {
	const html = render([
		activity('tool', 'tool'),
		activity('message', 'communication', { targetName: 'Khách sạn', detail: 'Tìm phòng cho hai người' }),
	], false, false);
	assert.doesNotMatch(html, /Tìm phòng cho hai người/);
	assert.match(html, /Nội dung trao đổi/);
	assert.match(html, /1 lượt trao đổi/);
	assert.match(html, /Khách sạn/);
	assert.match(html, /Hoạt động công cụ/);
	assert.match(html, /aria-expanded="false"/);
	assert.doesNotMatch(html, /search_hotels/);
});

test('collapsed tools still surface running and failed counts', () => {
	const html = render([activity('a', 'tool', { state: 'running' }), activity('b', 'tool', { state: 'error' })]);
	assert.match(html, /1 đang chạy/);
	assert.match(html, /1 thất bại/);
	assert.match(html, /Chưa có trao đổi giữa các agent/);
	assert.doesNotMatch(html, /search_hotels/);
});

test('long messages can expand and communication errors remain visible', () => {
	const html = render([activity('message', 'communication', { detail: 'Nội dung dài. '.repeat(30), state: 'error' })]);
	assert.match(html, /Xem thêm/);
	assert.match(html, /aria-expanded="false"/);
	assert.match(html, /Gửi tin thất bại/);
	assert.doesNotMatch(html, /Hoạt động công cụ/);
});

test('an empty log stays minimal without an empty tool disclosure', () => {
	const html = render([]);
	assert.match(html, /Chưa có hoạt động phối hợp/);
	assert.doesNotMatch(html, /Hoạt động công cụ/);
});

test('selecting an agent filters incoming, outgoing and group exchanges below the graph', () => {
	const items = [
		activity('hotel', 'communication', { targetName: 'Khách sạn', detail: 'Tìm phòng' }),
		activity('food', 'communication', { targetName: 'Nhà hàng', detail: 'Tìm bàn' }),
		activity('reply', 'communication', { sessionId: 'hotel-session', sourceName: 'Khách sạn', targetName: 'Leader', detail: 'Có phòng' }),
		activity('broadcast', 'communication', { targetName: 'Cả nhóm', detail: 'Cập nhật kế hoạch' }),
	];
	render(items);
	graphProps.onSelect('hotel');
	const html = render(items, true);
	assert.match(html, /Tìm phòng/);
	assert.match(html, /Có phòng/);
	assert.match(html, /Cập nhật kế hoạch/);
	assert.doesNotMatch(html, /Tìm bàn/);
	assert.match(html, /aria-pressed="true" aria-label="Xem phối hợp của Khách sạn"/);
	graphProps.onSelect(null);
	assert.match(render(items, true), /Tìm bàn/);
});

test('new exchanges and runtime updates reach the graph and selected details without losing selection', () => {
	runtimeBySession = { 'hotel-session': { status: 'idle', detail: 'Chưa hoạt động' } };
	render([]);
	graphProps.onSelect('hotel');
	runtimeBySession = { 'hotel-session': { status: 'communicating', detail: 'Đang gửi kết quả' } };
	const items = [activity('live', 'communication', { sessionId: 'hotel-session', sourceName: 'Khách sạn', targetName: 'Leader', detail: 'Kết quả mới', state: 'running' })];
	const live = render(items, true);
	assert.match(live, /team-coordination-flow/);
	assert.match(live, /Đang gửi kết quả/);
	assert.match(live, /Kết quả mới/);
	assert.equal(graphProps.selectedId, 'hotel');
	runtimeBySession = { 'hotel-session': { status: 'completed', detail: 'Đã xong lượt' } };
	const done = render([{ ...items[0], state: 'success' }], true);
	assert.doesNotMatch(done, /team-coordination-flow/);
	assert.match(done, /Đã xong lượt/);
	runtimeBySession = {};
});

test('graph draws directed exchanges, broadcasts and error links without invalid coordinates', () => {
	const html = render([
		activity('one', 'communication', { targetName: 'Khách sạn' }),
		activity('two', 'communication', { targetName: 'Khách sạn', state: 'error' }),
		activity('group', 'communication', { targetName: 'Cả nhóm' }),
	]);
	assert.match(html, /Leader → Khách sạn: 3 lượt trao đổi/);
	assert.match(html, /Leader → Nhà hàng: 1 lượt trao đổi/);
	assert.match(html, /marker-end=/);
	assert.doesNotMatch(html, /NaN|Infinity/);
});

test('members communicate directly in both directions without routing through the leader', () => {
	const items = [
		activity('hotel-food', 'communication', { sessionId: 'hotel-session', sourceName: 'Khách sạn', targetName: 'Nhà hàng', detail: 'Có bàn gần khách sạn không?', state: 'running' }),
		activity('food-hotel', 'communication', { sessionId: 'food-session', sourceName: 'Nhà hàng', targetName: 'Khách sạn', detail: 'Có bàn cách 200m' }),
		activity('leader-food', 'communication', { targetName: 'Nhà hàng', detail: 'Kiểm tra thực đơn' }),
	];
	const all = render(items);
	assert.match(all, /Khách sạn → Nhà hàng: 1 lượt trao đổi/);
	assert.match(all, /Nhà hàng → Khách sạn: 1 lượt trao đổi/);
	assert.match(all, /team-coordination-flow/);
	graphProps.onSelect('hotel');
	const selected = render(items, true);
	assert.match(selected, /Có bàn gần khách sạn không/);
	assert.match(selected, /Có bàn cách 200m/);
	assert.doesNotMatch(selected, /Kiểm tra thực đơn/);
});

test('compact agent rows retain waiting and tool details without repeating completed status', () => {
	runtimeBySession = {
		session: { status: 'completed', detail: 'Đã hoàn thành lượt xử lý', activeTool: null },
		'hotel-session': { status: 'waiting', detail: 'Đang chờ Nhà hàng trả lời', activeTool: null },
		'food-session': { status: 'active', detail: 'Đang gọi search_hotels', activeTool: 'search_hotels' },
	};
	const html = render([]);
	const rows = html.slice(html.indexOf('Agent trong team'), html.indexOf('Nhật ký phối hợp'));
	assert.match(html, /1 đang chờ/);
	assert.match(rows, /bg-orange-500/);
	assert.match(rows, /Đang chờ Nhà hàng trả lời/);
	assert.match(rows, /Đang gọi search_hotels/);
	assert.match(rows, /Xong lượt/);
	assert.doesNotMatch(rows, /Đã hoàn thành lượt xử lý/);
	assert.match(rows, /min-h-10/);
	runtimeBySession = {};
});

test('waiting count and duplicate work descriptions update with runtime changes', () => {
	runtimeBySession = { 'hotel-session': { status: 'waiting', detail: 'Đang chờ xác nhận', activeTool: null } };
	const waiting = render([]);
	assert.match(waiting, /1 đang chờ/);
	assert.doesNotMatch(waiting.slice(0, waiting.indexOf('Agent trong team')), /bg-orange-500/);
	runtimeBySession = { 'hotel-session': { status: 'active', detail: 'Đang xử lý yêu cầu', activeTool: null } };
	const html = render([]);
	const rows = html.slice(html.indexOf('Agent trong team'), html.indexOf('Nhật ký phối hợp'));
	assert.match(html, /0 đang chờ/);
	assert.match(rows, /Đang xử lý/);
	assert.doesNotMatch(rows, /Đang xử lý yêu cầu/);
	runtimeBySession = {};
});

test('the graph avatar dot is orange while waiting and turns green after completion', () => {
	for (const [status, color] of [['waiting', 'bg-orange-500'], ['completed', 'bg-emerald-500']]) {
		runtimeBySession = { 'hotel-session': { status, detail: status, activeTool: null } };
		render([]);
		const graph = renderToStaticMarkup(React.createElement(TeamCoordinationGraph, graphProps));
		assert.match(graph, new RegExp(`absolute -right-0.5 bottom-0 size-2.5 rounded-full border-2 border-background ${color}`));
		if (status === 'completed') assert.doesNotMatch(graph, /bg-orange-500/);
	}
	runtimeBySession = {};
});
