import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

function load() {
	const source = readFileSync(new URL('../src/lib/teamThreads.ts', import.meta.url), 'utf8');
	const context = { exports: {} };
	vm.runInNewContext(ts.transpileModule(source, {
		compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
	}).outputText, context);
	return context.exports;
}

// vm-realm arrays are not reference-equal to this realm's prototypes.
const plain = (value) => JSON.parse(JSON.stringify(value));

let sequence = 0;
const at = (minute) => `2026-11-15T09:${String(minute).padStart(2, '0')}:00.000Z`;
const message = (fields) => ({
	id: `tool:${++sequence}`,
	sessionId: 's',
	targetName: null,
	type: 'communication',
	kind: null,
	toolName: 'TeamSay',
	detail: null,
	state: 'success',
	handoffId: null,
	threadId: null,
	inReplyTo: null,
	argsSummary: null,
	...fields,
});
const tool = (fields) => message({ type: 'tool', toolName: 'mcp__Travel__search_attractions', ...fields });

test('tool inputs become a short human summary', () => {
	const { summarizeToolArgs, readableToolName, stripHandle } = load();
	assert.equal(
		summarizeToolArgs('{"time": "09:00", "session_id": "48f88bd98fab4e998fe2f13e4a0c1d2e", "city": "Đà Nẵng", "date": "2026-11-15"}'),
		'Đà Nẵng · 15/11/2026 · 09:00',
	);
	assert.equal(
		summarizeToolArgs({
			origin: 'HAN',
			destination: 'DAD',
			departure_date: '2026-11-16T14:00:00+07:00',
			flight_number: 'VN123',
			notes: 'x'.repeat(80),
			include_return: true,
			passengers: 2,
		}),
		'HAN · DAD · 16/11/2026 14:00 · VN123',
	);
	assert.equal(summarizeToolArgs('{"filters": {"city": "Huế", "time": "14:30:00"}}'), 'Huế · 14:30');
	assert.equal(summarizeToolArgs('{"booking_id": "abc", "flag": false}'), null);
	assert.equal(summarizeToolArgs('not json'), null);
	assert.equal(readableToolName('mcp__Travel__search_attractions'), 'search attractions');
	assert.equal(readableToolName('view_text_file'), 'view text file');
	assert.equal(stripHandle('Agent Khách sạn@1a2b3c4d'), 'Agent Khách sạn');
});

test('messages thread by thread_id / in_reply_to and nest the recipient tools', () => {
	const { groupTeamThreads } = load();
	const question = message({
		sourceName: 'Leader', targetName: 'Du lịch', kind: 'question', handoffId: 'h1', createdAt: at(0),
	});
	const early = tool({ sourceName: 'Du lịch', argsSummary: 'Đà Nẵng · 15/11/2026 · 09:00', createdAt: at(1) });
	const late = tool({ sourceName: 'Du lịch', argsSummary: 'Đà Nẵng · 16/11/2026 · 14:00', createdAt: at(2) });
	const answer = message({
		sourceName: 'Du lịch', targetName: 'Leader', kind: 'answer', handoffId: 'h2', threadId: 'h1', inReplyTo: 'h1', createdAt: at(3),
	});
	const followUp = message({
		sourceName: 'Leader', targetName: 'Du lịch', kind: 'progress', handoffId: 'h3', inReplyTo: 'h2', createdAt: at(4),
	});
	const afterReply = tool({ sourceName: 'Du lịch', createdAt: at(5) });
	const unrelated = message({ sourceName: 'Leader', targetName: 'Khách sạn', kind: 'handoff', handoffId: 'h9', createdAt: at(6) });

	const view = groupTeamThreads([unrelated, afterReply, followUp, answer, late, early, question]);
	assert.equal(view.threads.length, 2);
	const [newest, thread] = view.threads;
	assert.equal(newest.id, 'h9');
	assert.equal(thread.id, 'h1');
	assert.equal(thread.sourceName, 'Leader');
	assert.equal(thread.targetName, 'Du lịch');
	assert.deepEqual(plain(thread.messages.map(({ item }) => item.kind)), ['question', 'answer', 'progress']);
	// Parallel calls with different arguments stay distinct and ordered.
	assert.deepEqual(plain(thread.messages[0].tools.map((item) => item.argsSummary)), [
		'Đà Nẵng · 15/11/2026 · 09:00',
		'Đà Nẵng · 16/11/2026 · 14:00',
	]);
	assert.equal(thread.lastAt, at(4));
	// A tool after the agent replied belongs to no open request.
	assert.equal(view.otherTools.length, 1);
	assert.equal(view.otherTools[0].agentName, 'Du lịch');
	assert.deepEqual(plain(view.otherTools[0].tools.map((item) => item.id)), [afterReply.id]);
});

test('an unlinked reply chains to the assignment it answers; filters pick an agent', () => {
	const { groupTeamThreads, filterTeamThreads } = load();
	const assign = message({ sourceName: 'Leader', targetName: 'Vé máy bay', kind: 'assign', toolName: 'AgentInvite', createdAt: at(10) });
	const lookup = tool({ sourceName: 'Vé máy bay', toolName: 'search_flights', createdAt: at(11) });
	const result = message({ sourceName: 'Vé máy bay', targetName: 'Leader', kind: 'result', handoffId: 'r1', createdAt: at(12) });
	const loose = message({ sourceName: 'Khách sạn', targetName: 'Leader', kind: null, createdAt: at(13) });

	const view = groupTeamThreads([assign, lookup, result, loose]);
	assert.equal(view.threads.length, 2);
	const flights = view.threads.find((thread) => thread.targetName === 'Vé máy bay');
	assert.deepEqual(plain(flights.messages.map(({ item }) => item.kind)), ['assign', 'result']);
	assert.deepEqual(plain(flights.messages[0].tools.map((item) => item.id)), [lookup.id]);
	assert.equal(view.otherTools.length, 0);

	const onlyHotel = filterTeamThreads(view, 'Khách sạn');
	assert.equal(onlyHotel.threads.length, 1);
	assert.equal(onlyHotel.threads[0].sourceName, 'Khách sạn');
	assert.equal(filterTeamThreads(view, null), view);
	assert.ok(view.agents.includes('Leader') && view.agents.includes('Vé máy bay'));
});
