import type { BuildProposal } from './types';

export function canConfirm(proposal: BuildProposal | null): boolean {
	return !!proposal && proposal.status === 'ready' && proposal.items.length > 0
		&& proposal.questions.length === 0
		&& proposal.items.every(item => item.blockers.length === 0 && item.selection.blockers.length === 0
			&& !['clarify', 'repair'].includes(item.reuse_decision.action));
}

export function statusLabel(proposal: BuildProposal): string {
	if (proposal.status === 'completed_reused') return 'Đã có agent phù hợp trong thư viện';
	if (proposal.status === 'confirmed') return 'Đã xác nhận đề xuất';
	if (proposal.status === 'ready') return 'Sẵn sàng xác nhận';
	return 'Cần bổ sung yêu cầu hoặc khả năng';
}
