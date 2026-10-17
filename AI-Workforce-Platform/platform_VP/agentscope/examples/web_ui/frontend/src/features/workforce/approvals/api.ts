import type { ApprovalView, DecisionInput } from './types';

// Inject the shared authenticated transport once Foundation exports it.
export interface ApprovalTransport {
	request<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T>;
}

export function createApprovalApi(transport: ApprovalTransport) {
	return {
		list: (conversationId: string) =>
			transport.request<{ items: ApprovalView[]; next_cursor: string | null }>(
				`/workforce/v1/conversations/${encodeURIComponent(conversationId)}/approvals`,
			),
		decide: (approvalId: string, body: DecisionInput) =>
			transport.request<ApprovalView>(
				`/workforce/v1/approvals/${encodeURIComponent(approvalId)}/decision`,
				{ method: 'POST', body },
			),
	};
}
