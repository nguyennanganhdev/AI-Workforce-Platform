import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

function workforce(enabled, get) {
	const source = readFileSync(
		new URL('../src/api/workforce.ts', import.meta.url),
		'utf8',
	).replace(
		'import.meta.env.VITE_ENABLE_WORKFORCE_ROOM',
		JSON.stringify(enabled ? 'true' : 'false'),
	);
	class ApiError extends Error {
		constructor(status) {
			super(String(status));
			this.status = status;
		}
	}
	const context = { exports: {}, require: () => ({ client: { get }, ApiError }) };
	vm.runInNewContext(
		ts.transpileModule(source, {
			compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
		}).outputText,
		context,
	);
	return { api: context.exports.workforceApi, ApiError };
}

test('stock FastAPI never receives an optional room request', async () => {
	const { api } = workforce(false, () => assert.fail('unexpected room request'));
	assert.equal(await api.room('session'), null);
});

test('room extension falls back on 404 and stops retrying', async () => {
	let calls = 0;
	const { api, ApiError } = workforce(true, async () => {
		calls++;
		throw new ApiError(404);
	});
	assert.equal(await api.room('one'), null);
	assert.equal(await api.room('two'), null);
	assert.equal(calls, 1);
});

test('room extension does not swallow authorization or server errors', async () => {
	for (const status of [401, 403, 500]) {
		const { api, ApiError } = workforce(true, async () => {
			throw new ApiError(status);
		});
		await assert.rejects(api.room('one'), (error) => error.status === status);
	}
});
