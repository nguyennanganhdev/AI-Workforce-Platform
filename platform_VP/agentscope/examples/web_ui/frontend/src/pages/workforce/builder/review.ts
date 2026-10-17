import type { BuilderProposal } from '@/api/workforce';

export const decisionLabels: Record<string, string> = {
    create: 'Tạo mới', reuse: 'Dùng lại', resume: 'Tiếp tục bản nháp',
    revise: 'Nâng cấp cùng agent', repair: 'Cần sửa agent cũ', clarify: 'Cần làm rõ',
};

export function canConfirm(proposal: BuilderProposal): boolean {
    return proposal.status === 'needs_input' && proposal.agents.length === 0 &&
        proposal.planned_agents.length > 0 && proposal.planned_agents.every((p) =>
            p.decision && !['clarify', 'repair'].includes(p.decision.action) &&
            !p.missing_tools?.length && !(p.knowledge_required && p.missing_knowledge?.length));
}

export function classifierLabel(proposal: BuilderProposal): string {
    const status = proposal.classifier_status;
    if (!status) return 'Chưa có kết quả kiểm tra trùng; hãy lập lại phương án.';
    const labels = { active: 'JEV đang hoạt động', fallback: 'Chọn tài nguyên bằng LLM dự phòng',
        unavailable: 'JEV chưa kết luận; chưa thể tạo agent', not_needed: 'Chưa cần gọi JEV' };
    return `${labels[status.state]} · ${status.model}${status.reason ? ` · ${status.reason}` : ''}`;
}
