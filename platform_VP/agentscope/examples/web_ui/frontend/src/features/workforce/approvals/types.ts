// Component view models only; generated shared DTOs remain Foundation-owned.
export interface MoneyView {
	amount_minor: number;
	currency: string;
}

export interface ApprovalView {
	approval_id: string;
	call_id: string;
	status: 'pending' | 'approved' | 'rejected' | 'consumed' | 'expired';
	arguments_hash: string;
	quote_hash: string;
	expires_at: string;
	quote: {
		provider: string;
		option: string;
		dates: string[];
		amount: MoneyView;
		fees: MoneyView;
		cancellation_terms: string;
		quote_ref: string;
		quote_version: string;
	};
	decision_history: { decision: string; at: string }[];
}

export type ExecutionState =
	| 'proposed'
	| 'awaiting_approval'
	| 'executing'
	| 'succeeded'
	| 'confirmed'
	| 'unknown'
	| 'failed'
	| 'partial';

export interface DecisionInput {
	decision: 'approve' | 'reject';
	arguments_hash: string;
	quote_hash: string;
}
