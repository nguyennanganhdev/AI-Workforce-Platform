import { client } from './client';

export interface CustomerAction {
	action: 'confirm' | 'reopen' | 'work-approval';
	label: string;
	expected_version: number;
	payload: Record<string, unknown>;
	requires_note?: boolean;
}

export interface CustomerCase {
	id: string;
	code?: string;
	title?: string;
	description?: string;
	service_status?: string;
	sync_status: string;
	as_of: string | null;
	next_action: string | null;
	error?: string;
	resolution?: { summary: string; photos: { id: string; name: string; url: string }[] };
	result_photos?: { id: string; name: string; url: string }[];
	pending_decisions?: { id: string; kind: string; status: string; request_detail: unknown }[];
	work_orders?: { id: string; status: string; scheduled_at: string | null }[];
	events: { id: string; sequence: number; at: string; label: string; note?: string }[];
	next_cursor?: number;
	has_more?: boolean;
	actions: CustomerAction[];
}

export const customerCasesApi = {
	events: (caseId: string, after: number) => client.get<{
		items: { event_id: string; sequence: number; occurred_at: string; event_type: string; data: { label?: string; note?: string } }[];
		next_cursor: number; has_more: boolean;
	}>(`/service-cases/${encodeURIComponent(caseId)}/events`, { after: String(after), limit: '100' }, { silent: true }),
	list: (agentId: string, sessionId: string) => client.get<{ items: CustomerCase[] }>(
		`/workforce/console/leader/${encodeURIComponent(agentId)}/sessions/${encodeURIComponent(sessionId)}/service-cases`,
		undefined, { silent: true, timeoutMs: 30000 },
	),
	// Invoked only by the explicit UI confirm handler. This endpoint signs C06
	// on the server; proof, bearer token and ticket grants never reach the UI.
	decide: (caseId: string, action: CustomerAction, note: string, idempotencyKey: string) => client.post(
		`/service-cases/${encodeURIComponent(caseId)}/decisions`, {
			case_id: caseId, action: action.action, expected_version: action.expected_version,
			payload: { ...action.payload, ...(action.requires_note ? { [action.action === 'reopen' ? 'reason' : 'note']: note } : {}) },
			idempotency_key: idempotencyKey,
		}, undefined, { silent: true },
	),
	photo: async (path: string) => {
		if (!/^\/service-cases\/[a-zA-Z0-9-]+\/photos\/[a-zA-Z0-9-]+$/.test(path)) throw new Error('Invalid photo reference');
		return (await client.stream(path, { silent: true })).blob();
	},
};
