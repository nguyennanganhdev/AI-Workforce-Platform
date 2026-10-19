import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const context = {
	exports: {},
	require: (id) => id === '@/i18n/useI18n' ? {} : require(id),
};
vm.runInNewContext(ts.transpileModule(readFileSync(
	new URL('../src/components/chat/session-row-utils.ts', import.meta.url), 'utf8',
), {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, context);

test('placeholder titles are hidden, including tickets with existing messages', () => {
	for (const name of [undefined, null, '', 'Ticket mới', 'Phiếu đối tác', 'Partner ticket',
		'2026-10-19 10:30', '2026-10-19T10:30:12.000Z']) {
		assert.equal(context.exports.sessionTitle(name), null);
	}
});

test('real conversation titles remain intact', () => {
	for (const name of ['Sửa điều hoà', 'Ticket mới về thang máy', 'Partner ticket update']) {
		assert.equal(context.exports.sessionTitle(name), name);
	}
});
