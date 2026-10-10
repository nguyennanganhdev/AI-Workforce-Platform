import type {
	AgentDefinition, AgentDraft, AgentManifest, Batch, EvaluationRecord,
	Page, PublishedVersion, PublishSelection,
} from './types';

/** Inject Foundation's shared Bearer/refresh transport; never create a token store here. */
export interface WorkforceTransport {
	request<T>(path: string, options?: {
		method?: string; body?: unknown; headers?: Record<string, string>;
	}): Promise<T>;
}

export function createAgentsApi(transport: WorkforceTransport) {
	const path = (resource: string, id: string) => `/workforce/v1/${resource}/${encodeURIComponent(id)}`;
	const post = <T>(url: string, body?: unknown, key?: string) => transport.request<T>(url, {
		method: 'POST', body, headers: key ? { 'Idempotency-Key': key } : undefined,
	});
	return {
		listAgents: (cursor?: string) => transport.request<Page<AgentDefinition>>(
			`/workforce/v1/agents${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`,
		),
		getDraft: (id: string) => transport.request<AgentDraft>(path('drafts', id)),
		updateDraft: (draft: AgentDraft, manifest: AgentManifest) => transport.request<AgentDraft>(
			path('drafts', draft.draft_id), { method: 'PATCH', body: {
				expected_revision: draft.revision, manifest, reuse_decision: draft.reuse_decision,
			} },
		),
		validateDraft: (id: string) => post<{ valid: boolean; blockers: string[] }>(`${path('drafts', id)}/validate`),
		evaluate: (draft: AgentDraft, suiteVersion: string, key: string) => post<EvaluationRecord>(
			`${path('drafts', draft.draft_id)}/evaluations`, {
				expected_revision: draft.revision, suite_version: suiteVersion,
			}, key,
		),
		getEvaluation: (id: string) => transport.request<EvaluationRecord>(path('evaluations', id)),
		cancelEvaluation: (id: string) => post<EvaluationRecord>(`${path('evaluations', id)}/cancel`),
		publish: (selection: PublishSelection, key: string) => post<PublishedVersion>(
			`${path('drafts', selection.draft_id)}/publish`, {
				expected_revision: selection.expected_revision,
				evaluation_id: selection.evaluation_id, manifest_hash: selection.manifest_hash,
			}, key,
		),
		getVersion: (id: string) => transport.request<PublishedVersion>(path('versions', id)),
		fork: (id: string) => post<AgentDraft>(`${path('versions', id)}/fork`),
		history: (agentId: string) => transport.request<Page<PublishedVersion>>(`${path('agents', agentId)}/versions`),
		diff: (draftId: string) => transport.request<{ items: unknown[] }>(`${path('drafts', draftId)}/diff`),
		deployments: () => transport.request<Page<{
			deployment_id: string; agent_id: string; revision: number; active_version_id: string;
		}>>('/workforce/v1/deployments'),
		rollback: (deploymentId: string, versionId: string, revision: number) => post(
			`${path('deployments', deploymentId)}/rollback`, { version_id: versionId, expected_revision: revision },
		),
		getBatch: (id: string) => transport.request<Batch>(path('batches', id)),
		publishBatch: (batch: Batch, selections: PublishSelection[]) => post<Batch>(
			`${path('batches', batch.batch_id)}/publish`, { expected_revision: batch.revision, selections },
		),
	};
}
export type AgentsApi = ReturnType<typeof createAgentsApi>;
