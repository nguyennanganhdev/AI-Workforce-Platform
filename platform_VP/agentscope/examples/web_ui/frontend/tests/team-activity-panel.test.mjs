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
let activities = [];
const { TeamPanel } = load('../src/components/panel/TeamPanel.tsx', (id) => {
	if (id === 'react-router-dom') return { useNavigate: () => () => {} };
	if (id === '@/hooks/useTeamActivity') return { useTeamActivity: () => ({ runtimeBySession: {}, activities }) };
	if (id === '@/i18n/useI18n') return { useTranslation: () => ({ t: (key) => key }) };
	if (id === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
	if (id === '@/components/ui/collapsible') return collapsible;
	if (id.startsWith('@/')) return new Proxy({}, { get: () => () => null });
	return require(id);
});
const activity = (id, type, extra = {}) => ({
	id, type, sessionId: 'session', sourceName: 'Leader', targetName: null,
	kind: 'handoff', toolName: 'search_hotels', detail: null, state: 'success',
	createdAt: '2026-10-20T08:30:00Z', ...extra,
});
function render(items) {
	activities = items;
	return renderToStaticMarkup(React.createElement(TeamPanel, {
		team: { team: { id: 'team', session_id: 'session', data: { name: 'Du lịch' } }, members: [], leader_agent: null },
		currentSessionId: 'session', agentId: 'leader', canManage: false, onMembersChanged: async () => {},
	}));
}

test('exchanges stay visible while tool names are hidden behind a closed disclosure', () => {
	const html = render([
		activity('tool', 'tool'),
		activity('message', 'communication', { targetName: 'Khách sạn', detail: 'Tìm phòng cho hai người' }),
	]);
	assert.match(html, /Tìm phòng cho hai người/);
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
