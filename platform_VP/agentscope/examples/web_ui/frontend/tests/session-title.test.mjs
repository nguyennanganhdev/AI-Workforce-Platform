import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
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

test('session labels prefer real titles, then opening text, then team names', () => {
	const title = context.exports.sessionDisplayTitle;
	assert.equal(title(view('Tên đã đặt', { preview: 'Tin nhắn', team }), 'Hội thoại'), 'Tên đã đặt');
	assert.equal(title(view('Mới', { preview: 'Đi Hà Nội', team }), 'Hội thoại'), 'Đi Hà Nội');
	assert.equal(title(view('team:abc123', { team }), 'Hội thoại'), 'Đội du lịch');
	assert.equal(title(view('', { preview: '  ' }), 'Hội thoại'), 'Hội thoại · 20/10 08:30');
	assert.equal(context.exports.sessionTitle('Team: kế hoạch'), 'Team: kế hoạch');
});
