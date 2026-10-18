import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const normalize = (path) => path.replace(/\{[^}]+\}/g, '{}');

test('active API client paths and methods exist in this FastAPI checkout', () => {
	const routerDir = new URL('../../../../src/agentscope/app/_router/', import.meta.url);
	const routes = new Set();
	for (const file of readdirSync(routerDir).filter((file) => file.endsWith('.py'))) {
		const source = readFileSync(new URL(file, routerDir), 'utf8');
		const prefix = source.match(/prefix\s*=\s*["']([^"']*)["']/)?.[1] ?? '';
		for (const [, method, path] of source.matchAll(
			/@\w+\.(get|post|put|patch|delete)\(\s*["']([^"']*)["']/g,
		)) {
			routes.add(`${method.toUpperCase()} ${normalize(prefix + path)}`);
		}
	}
	const apiDir = new URL('../src/api/', import.meta.url);
	// These extension modules are retained source, never mounted by the main router.
	const inactive = new Set(['admin.ts', 'studio.ts', 'client.ts']);
	const missing = [];
	let checked = 0;
	for (const file of readdirSync(apiDir).filter(
		(file) => file.endsWith('.ts') && !inactive.has(file),
	)) {
		const source = ts.createSourceFile(
			file,
			readFileSync(new URL(file, apiDir), 'utf8'),
			ts.ScriptTarget.Latest,
			true,
		);
		function visit(node) {
			if (
				ts.isCallExpression(node) &&
				ts.isPropertyAccessExpression(node.expression) &&
				node.expression.expression.getText(source) === 'client'
			) {
				const method = node.expression.name.text;
				const argument = node.arguments[0];
				let path;
				if (argument && ts.isStringLiteral(argument)) path = argument.text;
				else if (argument && ts.isTemplateExpression(argument))
					path =
						argument.head.text +
						argument.templateSpans.map((span) => '{}' + span.literal.text).join('');
				assert.ok(path, `${file}: add explicit coverage for a computed API path`);
				const key = `${method === 'stream' ? 'GET' : method.toUpperCase()} ${normalize(path)}`;
				// Separately tested: feature disabled by default, null fallback on 404.
				if (key !== 'GET /workforce/console/sessions/{}/room') {
					checked++;
					if (!routes.has(key)) missing.push(`${file}: ${key}`);
				}
			}
			ts.forEachChild(node, visit);
		}
		visit(source);
	}
	assert.ok(checked >= 100, 'API inventory unexpectedly shrank');
	assert.deepEqual(missing, []);
});
