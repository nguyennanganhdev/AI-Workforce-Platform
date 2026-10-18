// Run against the app's OpenAPI path manifest, including optional unified routers.
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const normalize = (path) => path.split('?')[0].replace(/\{[^}]*\}/g, '{}').replace(/\/+$/, '');
assert.equal(normalize('/agents/{agent_id}/'), normalize('/agents/{id}'));
assert.notEqual(normalize('/agents/{id}'), normalize('/agents/{id}/publish'));

function value(node, bindings, parameters = new Map(), depth = 0) {
	assert.ok(node && depth < 20, 'Unresolved or recursive API path');
	const evaluate = (expression) => value(expression, bindings, parameters, depth + 1);
	if (ts.isStringLiteralLike(node)) return node.text;
	if (ts.isParenthesizedExpression(node)) return evaluate(node.expression);
	if (ts.isIdentifier(node)) {
		if (parameters.has(node.text)) return parameters.get(node.text);
		return bindings.has(node.text) ? evaluate(bindings.get(node.text)) : '{}';
	}
	if (ts.isTemplateExpression(node)) {
		return node.head.text + node.templateSpans.map((span) => evaluate(span.expression) + span.literal.text).join('');
	}
	if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
		return evaluate(node.left) + evaluate(node.right);
	}
	if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
		if (node.expression.text === 'encodeURIComponent') return '{}';
		const fn = bindings.get(node.expression.text);
		if (fn && ts.isArrowFunction(fn) && !ts.isBlock(fn.body)) {
			const argumentsByName = new Map(parameters);
			fn.parameters.forEach((parameter, i) => argumentsByName.set(parameter.name.getText(), node.arguments[i] ? evaluate(node.arguments[i]) : '{}'));
			return value(fn.body, bindings, argumentsByName, depth + 1);
		}
	}
	throw new Error(`Unsupported API path expression: ${node.getText()}`);
}

const fixture = ts.createSourceFile('fixture.ts', 'const base = "/studio"; const path = (id) => `${base}/agents/${encodeURIComponent(id)}`; path(id);', ts.ScriptTarget.Latest, true);
const fixtureBindings = new Map(fixture.statements.filter(ts.isVariableStatement).flatMap((statement) => statement.declarationList.declarations.map((declaration) => [declaration.name.getText(), declaration.initializer])));
assert.equal(value(fixture.statements.at(-1).expression, fixtureBindings), '/studio/agents/{}');

assert.ok(process.argv[2], 'Usage: node scripts/check-api-routes.mjs /path/to/api-routes.json');
const manifest = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const routes = new Set(Object.entries(manifest).flatMap(([path, methods]) => methods.map((method) => `${method.toUpperCase()} ${normalize(path)}`)));
const folder = fileURLToPath(new URL('../src/api/', import.meta.url));
const missing = [];
let checked = 0;
for (const name of readdirSync(folder).filter((name) => name.endsWith('.ts') && name !== 'client.ts')) {
	const file = ts.createSourceFile(name, readFileSync(`${folder}/${name}`, 'utf8'), ts.ScriptTarget.Latest, true);
	const bindings = new Map(file.statements.filter(ts.isVariableStatement).flatMap((statement) => statement.declarationList.declarations.map((declaration) => [declaration.name.getText(), declaration.initializer])));
	function visit(node) {
		if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.expression.getText() === 'client') {
			let method = node.expression.name.text.toUpperCase();
			if (method === 'STREAM') {
				const option = node.arguments[1]?.properties?.find((property) => property.name?.getText() === 'method');
				method = option ? value(option.initializer, bindings).toUpperCase() : 'GET';
			}
			const path = value(node.arguments[0], bindings);
			assert.ok(path.startsWith('/'), `${name}: unresolved path ${path}`);
			checked += 1;
			if (!routes.has(`${method} ${normalize(path)}`)) missing.push(`${name}: ${method} ${path}`);
		}
		ts.forEachChild(node, visit);
	}
	visit(file);
}
assert.deepEqual(missing, [], `UI routes missing from the backend:\n${missing.join('\n')}`);
console.log(`Verified ${checked} UI API calls against ${routes.size} backend routes.`);
