import './dom';
import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { WorkforceAgentsPage, WorkforceAgentSettingsPage, WorkforceEvaluationPage, WorkforceBatchResults } from '../../../../examples/web_ui/frontend/src/features/workforce/agents';
import type { AgentsApi } from '../../../../examples/web_ui/frontend/src/features/workforce/agents/api';
import type { AgentDraft, AgentDefinition, EvaluationRecord } from '../../../../examples/web_ui/frontend/src/features/workforce/agents/types';

afterEach(cleanup);

const agent: AgentDefinition = { agent_id: 'hotel', name: 'Hotel', status: 'published', revision: 1,
	active_version_id: 'v1', draft_id: 'd1', business_profile: { capabilities: ['lookup'] } };
const draft: AgentDraft = { draft_id: 'd1', agent_id: 'hotel', revision: 1, manifest_hash: 'hash', reuse_decision: {},
	manifest: { schema_version: '1', business_profile: {}, spec: {
		agent_key: 'hotel', name: 'Hotel', system_prompt: 'Old prompt', model_config_ref: { credential_ref: 'credential' },
	}, protocol_snapshot_hashes: [] } };
const evaluation: EvaluationRecord = { snapshot: { draft_id: 'd1', draft_revision: 1, manifest_hash: 'hash' },
	report: { evaluation_id: 'e1', status: 'passed', suite_version: 'lifecycle-patterns-v1',
		metrics: { cost: '0.01', latency_ms: 5 }, hard_gate_failures: [], cases: [] } };

function api(overrides: Partial<AgentsApi>): AgentsApi {
	// Every unspecified call fails, making accidental requests observable.
	return new Proxy(overrides, { get(target, key) {
		if (key in target) return target[key as keyof typeof target];
		return () => Promise.reject(new Error(`Unexpected API call: ${String(key)}`));
	} }) as AgentsApi;
}

test('library renders independent agents and only published chat is enabled', async () => {
	const clicked: string[] = [];
	render(<WorkforceAgentsPage api={api({ listAgents: async () => ({ items: [agent, { ...agent, agent_id: 'car', name: 'Car', status: 'draft' }] }) })}
		onSettings={value => clicked.push(value.agent_id)} onChat={id => clicked.push(id)} />);
	await screen.findByText('Hotel');
	assert.equal(screen.getAllByRole('button', { name: 'Chat' })[1].hasAttribute('disabled'), true);
	fireEvent.click(screen.getAllByRole('button', { name: 'Settings' })[1]);
	assert.deepEqual(clicked, ['car']);
});

test('library displays transport failures', async () => {
	render(<WorkforceAgentsPage api={api({ listAgents: async () => { throw new Error('Access revoked'); } })} onSettings={() => {}} onChat={() => {}} />);
	assert.match((await screen.findByRole('alert')).textContent ?? '', /Access revoked/);
});

test('settings saves current revision and disables eval while changes are unsaved', async () => {
	let saved: AgentDraft = draft;
	let opened = '';
	const port = api({ history: async () => ({ items: [] }), getDraft: async () => draft,
		updateDraft: async (original, manifest) => {
			assert.equal(original.revision, 1);
			saved = { ...original, manifest, revision: 2 }; return saved;
		}, diff: async () => ({ items: [{ path: '/spec/system_prompt' }] }),
		evaluate: async original => { assert.equal(original.revision, 2); return evaluation; },
	});
	render(<WorkforceAgentSettingsPage api={port} agent={agent} onEvaluation={id => { opened = id; }} />);
	await screen.findByText(/Bản nháp revision 1/);
	const updated = { ...draft.manifest, spec: { ...draft.manifest.spec, system_prompt: 'New prompt' } };
	fireEvent.change(screen.getByLabelText('Cấu hình agent'), { target: { value: JSON.stringify(updated, null, 2) } });
	assert.equal(screen.getByRole('button', { name: 'Đánh giá' }).hasAttribute('disabled'), true);
	fireEvent.click(screen.getByRole('button', { name: 'Lưu bản nháp' }));
	await screen.findByText(/Bản nháp revision 2/);
	await waitFor(() => assert.equal(screen.getByRole('button', { name: 'Đánh giá' }).hasAttribute('disabled'), false));
	fireEvent.click(screen.getByRole('button', { name: 'Đánh giá' }));
	await waitFor(() => assert.equal(opened, 'e1'));
	assert.equal(saved.manifest.spec.system_prompt, 'New prompt');
});

test('report rejects stale publish and retains the same idempotency key on retry', async () => {
	const keys: string[] = [];
	render(<WorkforceEvaluationPage api={api({ getEvaluation: async () => evaluation,
		publish: async (selection, key) => {
			assert.equal(selection.expected_revision, 1); keys.push(key); throw new Error('EVALUATION_STALE');
		},
	})} evaluationId="e1" />);
	await waitFor(() => assert.equal(screen.getByRole('button', { name: 'Phát hành agent' }).hasAttribute('disabled'), false));
	fireEvent.click(screen.getByRole('button', { name: 'Phát hành agent' }));
	assert.match((await screen.findByRole('alert')).textContent ?? '', /EVALUATION_STALE/);
	fireEvent.click(screen.getByRole('button', { name: 'Phát hành agent' }));
	await waitFor(() => assert.equal(keys.length, 2));
	assert.equal(keys[0], keys[1]);
});

test('hard gate report disables publish even when metrics look good', async () => {
	const failed = { ...evaluation, report: { ...evaluation.report, status: 'failed', hard_gate_failures: ['cross_audience'] } };
	render(<WorkforceEvaluationPage api={api({ getEvaluation: async () => failed })} evaluationId="e1" />);
	await screen.findByText(/Chặn phát hành: cross_audience/);
	assert.equal(screen.getByRole('button', { name: 'Phát hành agent' }).hasAttribute('disabled'), true);
});

test('batch only publishes selected passed items and shows existing agents', async () => {
	let chosen = '';
	const batch = { batch_id: 'b1', revision: 3, status: 'partially_ready', items: [
		{ item_id: 'i1', agent_key: 'hotel', status: 'passed', draft_id: 'd1', evaluation_id: 'e1' },
		{ item_id: 'i2', agent_key: 'car', status: 'failed' },
		{ item_id: 'i3', agent_key: 'planner', status: 'completed_reused', reuse_agent_id: 'planner' },
	] };
	render(<WorkforceBatchResults api={api({ getBatch: async () => batch, getEvaluation: async () => evaluation,
		publishBatch: async (original, selections) => {
			assert.equal(original.revision, 3); assert.equal(selections.length, 1); chosen = selections[0].draft_id;
			return { ...batch, revision: 4 };
		},
	})} batchId="b1" />);
	await screen.findByText(/Đã có — không cần tạo lại/);
	const boxes = screen.getAllByRole('checkbox');
	assert.equal(boxes[1].hasAttribute('disabled'), true);
	assert.equal(boxes[2].hasAttribute('disabled'), true);
	fireEvent.click(boxes[0]);
	fireEvent.click(screen.getByRole('button', { name: 'Phát hành 1 agent đã chọn' }));
	await waitFor(() => assert.equal(chosen, 'd1'));
});
