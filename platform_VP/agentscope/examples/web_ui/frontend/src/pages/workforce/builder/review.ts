import type { BuilderProposal } from '@/api/workforce';

export const decisionLabels: Record<string, string> = {
    create: 'Tạo mới', reuse: 'Dùng lại', resume: 'Tiếp tục bản nháp',
    revise: 'Nâng cấp cùng agent', repair: 'Cần sửa agent cũ', clarify: 'Cần làm rõ',
};

export function canConfirm(proposal: BuilderProposal): boolean {
    return proposal.classifier_status?.state !== 'unavailable' &&
        proposal.status === 'needs_input' && proposal.agents.length === 0 &&
        proposal.planned_agents.length > 0 && proposal.planned_agents.every((p) =>
            p.decision && !['clarify', 'repair'].includes(p.decision.action) &&
            !p.missing_tools?.length && !(p.knowledge_required && p.missing_knowledge?.length));
}

export function canRetryClassification(proposal: BuilderProposal): boolean {
    return proposal.classifier_status?.state === 'unavailable' &&
        proposal.status === 'needs_input' && proposal.agents.length === 0 &&
        proposal.planned_agents.length > 0;
}

export function planDecisionLabel(proposal: BuilderProposal, action: string): string {
    return canRetryClassification(proposal) && action === 'clarify'
        ? 'Lỗi kiểm tra JEV' : decisionLabels[action];
}

export function classifierLabel(proposal: BuilderProposal): string {
    const status = proposal.classifier_status;
    if (!status) return 'Chưa có kết quả kiểm tra trùng; hãy lập lại phương án.';
    const labels = { active: 'JEV đang hoạt động', fallback: 'Chọn tài nguyên bằng LLM dự phòng',
        unavailable: 'JEV chưa kết luận; chưa thể tạo agent', not_needed: 'Chưa cần gọi JEV' };
    const recovery = canRetryClassification(proposal)
        ? ' · Đây là lỗi kiểm tra hệ thống; giữ nguyên mô tả và chọn Lập lại phương án sau khi khắc phục.' : '';
    return `${labels[status.state]} · ${status.model}${status.reason ? ` · ${status.reason}` : ''}${recovery}`;
}
