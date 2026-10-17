// TEST/DEMO ONLY. The production BuilderPanel requires a real injected client.
import type { BuilderClient, BuildProposal } from '../types';
import fixtures from './proposals.json';

export type Scenario = keyof typeof fixtures | 'refresh' | 'permission' | 'optional_missing' | 'late_confirm';

export function fakeClient(scenario: Scenario): BuilderClient {
	let current: BuildProposal | null = null;
	let refreshed = false;
	return {
		async prepare(input, signal) {
			signal.throwIfAborted();
			const fixture = scenario in fixtures ? scenario as keyof typeof fixtures : 'ready';
			current = structuredClone(fixtures[fixture]) as BuildProposal;
			current.revision = input.expected_revision ? input.expected_revision + 1 : 1;
			if (scenario === 'optional_missing') {
				current.items[0].requirement.capabilities.push({ capability: 'optional', required: false, reason: 'TEST optional capability' });
				current.items[0].selection.missing_optional.push('optional');
			}
			return current;
		},
		async confirm(proposalId, revision, signal) {
			signal.throwIfAborted();
			if (!current || current.proposal_id !== proposalId || current.revision !== revision || current.status !== 'ready') throw new Error('Fixture conflict');
			if (scenario === 'permission') throw new Error('TEST permission denied');
			if (scenario === 'refresh' && !refreshed) {
				refreshed = true;
				current = { ...current, revision: revision + 1, notices: ['TEST catalog changed. Review and confirm again.'] };
				return current;
			}
			current = { ...current, status: current.items.every(item => item.reuse_decision.action === 'reuse') ? 'completed_reused' : 'confirmed' };
			const result = current;
			if (scenario === 'late_confirm') {
				// Deliberately ignore abort to test the panel's stale-response guard.
				await new Promise<void>(resolve => window.addEventListener('builder-demo-release', () => resolve(), { once: true }));
			}
			return result;
		},
		async cancel() { current = null; },
	};
}
