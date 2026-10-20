import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

function load() {
	const source = readFileSync(new URL('../src/lib/readable.ts', import.meta.url), 'utf8');
	const context = { exports: {} };
	vm.runInNewContext(ts.transpileModule(source, {
		compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
	}).outputText, context);
	return context.exports;
}

test('internal ids and handles are removed from user-facing text', () => {
	const { withoutInternalIds, isInternalId } = load();
	assert.equal(
		withoutInternalIds('Không gửi được cho Agent Khách sạn@1a2b3c4d: handoff ["48f88bd98fab4e998fe2f13e4a0c1d2e"] đã đóng.'),
		'Không gửi được cho Agent Khách sạn: handoff đã đóng.',
	);
	assert.equal(withoutInternalIds('TeamSay thất bại → 48f88bd98fab4e998fe2f13e4a0c1d2e'), 'TeamSay thất bại →');
	assert.ok(isInternalId('48f88bd98fab4e998fe2f13e4a0c1d2e'));
	assert.ok(!isInternalId('Agent Khách sạn'));
});

test('JSON objects become label/value lines, other text is left alone', () => {
	const { readableFields } = load();
	assert.deepEqual(
		[...readableFields('{"city": "Đà Nẵng", "check_in": "2026-10-24", "guests": 2, "note": null, "session_id": "48f88bd98fab4e998fe2f13e4a0c1d2e"}')].map((pair) => [...pair]),
		[['city', 'Đà Nẵng'], ['check in', '2026-10-24'], ['guests', '2']],
	);
	assert.equal(readableFields('plain text'), null);
	assert.equal(readableFields('[1, 2]'), null);
});

test('nested results are summarised, ids kept when asked, layout preserved', () => {
	const { readableFields, withoutInternalIds } = load();
	const fields = readableFields('{"items": [{"hotel": "Sala", "price": 1450000}, {"hotel": "Haian", "price": 1200000}]}');
	assert.deepEqual([...fields[0]], ['items', 'hotel: Sala · price: 1450000; hotel: Haian · price: 1200000']);
	const approval = readableFields('{"booking_id": "48f88bd98fab4e998fe2f13e4a0c1d2e"}', { keepIds: true });
	assert.deepEqual([...approval[0]], ['booking id', '48f88bd98fab4e998fe2f13e4a0c1d2e']);
	assert.equal(withoutInternalIds('name    price\nSala    1450000'), 'name    price\nSala    1450000');
});
