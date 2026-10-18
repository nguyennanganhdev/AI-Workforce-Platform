import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const context = {
	exports: {},
	require: (id) => {
		if (id === 'react/jsx-runtime') return require(id);
		if (id === 'react') return { ...require(id), useContext: () => null };
		if (id === './teamDialogText') return { cleanName: (name) => name, teamMessageText: (text) => text };
		return new Proxy({}, { get: (_, name) => name });
	},
};
vm.runInNewContext(ts.transpileModule(readFileSync(
	new URL('../src/components/chat/TeamDialog.tsx', import.meta.url), 'utf8',
), {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText, context);

test('dialog tool cards preserve the actual worker or leader who sent them', () => {
	for (const sender of ['Planner', 'Workforce Leader']) {
		for (const name of ['TeamSay', 'AgentInvite', 'CaseSay', 'CaseFinalize']) {
			const card = context.exports.DialogToolCard({ sender, pair: {
				call: { name, input: JSON.stringify({ to: 'Budget', target: 'Budget', content: 'Verify total', kind: 'question' }) },
			} });
			const dialog = name === 'AgentInvite' ? card.props.children[0] : card;
			assert.equal(dialog.props.from, sender);
			assert.equal(dialog.props.to, name.startsWith('Case') ? 'Cư dân' : 'Budget');
		}
	}
});

test('incoming peer answers name the receiving worker', () => {
	const card = context.exports.TeamMessageCard({ sender: 'Budget', recipient: 'Planner', kind: 'answer', text: 'Total is verified' });
	assert.equal(card.props.from, 'Budget');
	assert.equal(card.props.to, 'Planner');
});
