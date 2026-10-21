import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const Frame = ({ children }) => React.createElement('div', null, children);
const context = { exports: {}, require: (id) => {
	if (id.endsWith('.css')) return {};
	if (id === '@agentscope-ai/agentscope/event') return { ReplyFinishedReason: { ERROR: 'error' } };
	if (id === '@/i18n/useI18n') return { useTranslation: () => ({
		t: (key, options) => key + (options?.count === undefined ? '' : `:${options.count}`),
	}) };
	if (id === '@/utils/common') return { formatTime: () => '0s', formatNumber: String };
	if (id === '@/lib/utils') return { cn: () => '' };
	if (id.startsWith('@/') || id.startsWith('./tool-renderers')) {
		return new Proxy({}, { get: () => Frame });
	}
	return require(id);
} };
vm.runInNewContext(ts.transpileModule(readFileSync(new URL(
	'../src/components/chat/ASMessageBubble.tsx', import.meta.url,
), 'utf8'), {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText, context);
const { ASBlock, ASMessageBubble } = context.exports;
const started = '2026-10-20T08:30:00Z';
const thinking = (text, finished = true) => ({
	id: 'thinking', type: 'thinking', thinking: text, created_at: started,
	...(finished ? { finished_at: started } : {}),
});
const renderBlock = (block) => renderToStaticMarkup(React.createElement(ASBlock, { block }));
function renderMessage(content, finished = true) {
	return renderToStaticMarkup(React.createElement(ASMessageBubble, { message: {
		id: 'reply', role: 'assistant', created_at: started, content,
		...(finished ? { finished_at: started } : {}),
	} }));
}

test('empty and whitespace-only thinking blocks stay hidden while running or finished', () => {
	for (const finished of [false, true]) {
		for (const text of ['', ' \n\t ']) {
			assert.equal(renderBlock(thinking(text, finished)), '');
			const html = renderMessage([thinking(text, finished)], finished);
			assert.doesNotMatch(html, /messageBubble\.thinking|messageBubble\.trace\./);
		}
	}
});

test('thinking content appears when streaming delivers non-empty text', () => {
	assert.equal(renderBlock(thinking('', false)), '');
	const html = renderBlock(thinking('Checking available rooms', false));
	assert.match(html, /messageBubble\.thinking/);
	assert.match(html, /Checking available rooms/);
});

test('empty thinking does not count as an activity or hide the final answer', () => {
	const html = renderMessage([
		thinking(''), thinking('Checking prices'),
		{ id: 'answer', type: 'text', text: 'Rooms are available', created_at: started, finished_at: started },
	]);
	assert.match(html, /messageBubble\.trace\.steps:1/);
	assert.equal((html.match(/messageBubble\.thinking/g) ?? []).length, 1);
	assert.match(html, /Checking prices/);
	assert.match(html, /Rooms are available/);
});
