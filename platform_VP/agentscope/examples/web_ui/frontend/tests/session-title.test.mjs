import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const context = {
	exports: {},
	require,
};
vm.runInNewContext(ts.transpileModule(readFileSync(
	new URL('../src/components/chat/session-row-utils.ts', import.meta.url), 'utf8',
), {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, context);

test('placeholder titles are hidden, including tickets with existing messages', () => {
	for (const name of [undefined, null, '', 'Ticket mới', 'Phiếu đối tác', 'Partner ticket',
		'Mới', 'Phiên mới', 'Nhóm mới', 'New session', '   ', 'team:37aa4e10a5744e57ad5e423', '2026-10-19 10:30', '2026-10-19T10:30:12.000Z']) {
		assert.equal(context.exports.sessionTitle(name), null);
	}
});

test('real conversation titles remain intact', () => {
	for (const name of ['Sửa điều hoà', 'Ticket mới về thang máy', 'Partner ticket update']) {
		assert.equal(context.exports.sessionTitle(name), name);
	}
});

const view = (name, extra = {}) => ({
	session: { config: { name }, created_at: '2026-10-20T08:30:00', origin: { type: 'user' } },
	status: 'idle', team: null, ...extra,
});
const team = { team: { data: { name: 'Đội du lịch' } }, members: [{ agent: { data: { name: 'Lập lịch' } } }] };

test('group labels prefer team names over session titles and opening text', () => {
	const title = context.exports.sessionDisplayTitle;
	assert.equal(title(view('Tên đã đặt', { preview: 'Tin nhắn', team }), 'Hội thoại'), 'Đội du lịch');
	assert.equal(title(view('Mới', { preview: 'Đi Hà Nội', team }), 'Hội thoại'), 'Đội du lịch');
	assert.equal(title(view('team:abc123', { team }), 'Hội thoại'), 'Đội du lịch');
	assert.equal(title(view('Tên đã đặt', { preview: 'Tin nhắn' }), 'Hội thoại'), 'Tên đã đặt');
	assert.equal(title(view('Mới', { preview: 'Đi Hà Nội' }), 'Hội thoại'), 'Đi Hà Nội');
	assert.equal(title(view('Tên đã đặt', { team: { team: { data: { name: '  ' } } } }), 'Hội thoại'), 'Tên đã đặt');
	assert.equal(title(view('', { preview: '  ' }), 'Hội thoại'), 'Hội thoại · 20/10 08:30');
	assert.equal(context.exports.sessionTitle('Team: kế hoạch'), 'Team: kế hoạch');
});

const rowContext = { exports: {}, require: (id) => {
	if (id === '@/components/ui/clay-avatar') return { ClayAvatar: () => null };
	if (id === '@/lib/utils') return { cn: (...values) => values.filter(Boolean).join(' ') };
	return require(id);
} };
vm.runInNewContext(ts.transpileModule(readFileSync(new URL(
	'../src/components/chat/SessionRow.tsx', import.meta.url,
), 'utf8'), {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText, rowContext);

test('group rows show a truncated description and a full hover label', () => {
	const html = renderToStaticMarkup(React.createElement(rowContext.exports.ChatRow, {
		avatarId: 'leader', title: 'Đội du lịch', description: 'Tìm chuyến đi Hà Nội',
		time: '06:50', onSelect() {},
	}));
	assert.match(html, /title="Đội du lịch\nTìm chuyến đi Hà Nội"/);
	assert.match(html, /class="truncate text-xs\/4 text-muted-foreground">Tìm chuyến đi Hà Nội/);
	assert.match(html, /h-14/);
	assert.match(html, /06:50/);
});

test('rows without a description retain their compact single-line layout', () => {
	const html = renderToStaticMarkup(React.createElement(rowContext.exports.ChatRow, {
		avatarId: 'agent', title: 'Hội thoại', onSelect() {},
	}));
	assert.match(html, /title="Hội thoại"/);
	assert.doesNotMatch(html, /h-14|truncate text-xs\/4/);
});
