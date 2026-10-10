// TEST/DEMO ONLY. The production BuilderPanel requires a real injected client.
import type { BuilderClient, BuildProposal } from '../types';
import fixtures from './proposals.json';

export type Scenario = keyof typeof fixtures;

export function fakeClient(scenario: Scenario): BuilderClient {
	let current: BuildProposal | null = null;
	return {
		async prepare(input, signal) {
			signal.throwIfAborted();
			current = structuredClone(fixtures[scenario]) as BuildProposal;
			current.revision = input.expected_revision ? input.expected_revision + 1 : 1;
			return current;
		},
		async confirm(proposalId, revision, signal) {
			signal.throwIfAborted();
			if (!current || current.proposal_id !== proposalId || current.revision !== revision || current.status !== 'ready') throw new Error('Fixture conflict');
			current = { ...current, status: current.items.every(item => item.reuse_decision.action === 'reuse') ? 'completed_reused' : 'confirmed' };
			return current;
		},
		async cancel() { current = null; },
	};
}
