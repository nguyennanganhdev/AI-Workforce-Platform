import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { workforceApi } from '@/api';
import type { BuilderProposal } from '@/api';
import { Button } from '@/components/ui/button';

export function BatchPublication({ proposal, disabled, onPublished, onlyPassed = 0 }: {
	proposal: BuilderProposal; disabled: boolean; onPublished: () => Promise<void>;
	/** > 0: publish only the agents that passed eval (this many). */
	onlyPassed?: number;
}) {
	const [sending, setSending] = useState(false);
	const [error, setError] = useState('');
	const completed = useRef('');
	const query = useQuery({ queryKey: ['builder-publication', proposal.conversation_id, proposal.proposal_id],
		queryFn: () => workforceApi.publication(proposal.conversation_id, proposal.proposal_id!), retry: false, refetchInterval: 2000 });
	const publication = query.data?.publication;
	useEffect(() => {
		if (publication?.status !== 'published' || !publication.job_id || completed.current === publication.job_id) return;
		completed.current = publication.job_id;
		void onPublished().catch(() => setError('Đã phát hành; chưa tải lại được đề xuất. Vui lòng tải lại trang.'));
	}, [onPublished, publication]);
	const start = async (repair = false) => {
		setSending(true); setError('');
		try {
			if (repair && publication?.job_id) await workforceApi.repairPublication(publication.job_id);
			else await workforceApi.publish(proposal.conversation_id, proposal.proposal_id!, proposal.revision, onlyPassed > 0);
			await query.refetch();
		} catch { setError('Chưa phát hành được đề xuất. Hãy kiểm tra trạng thái và tải lại trước khi thử tiếp.'); }
		finally { setSending(false); }
	};
	const phases: Record<string, string> = { queued: 'Đang chờ phát hành', staging: 'Đang chuẩn bị tài nguyên riêng',
		activating: 'Đang kích hoạt toàn bộ agent', activated: 'Đã kích hoạt, đang lưu kết quả', published: 'Đã phát hành' };
	return <div className="space-y-2 text-sm">
		{publication && <p role="status">{phases[publication.phase] || 'Đang kiểm tra phát hành'} · {publication.cursor}/{publication.total}</p>}
		{publication?.status === 'failed' && <p className="text-destructive">Phát hành bị gián đoạn ({publication.error}). Chưa coi đề xuất đã hoàn tất. Khôi phục sẽ kiểm tra checkpoint và bản đang dùng.</p>}
		{(error || query.isError) && <p role="alert" className="text-destructive">{error || 'Chưa lấy được trạng thái phát hành.'}</p>}
		{publication?.can_repair ? <Button variant="outline" disabled={disabled || sending} onClick={() => void start(true)}>Khôi phục phát hành</Button>
			: !publication && <Button disabled={disabled || sending || query.isPending || query.isError} onClick={() => void start()}>{onlyPassed > 0 ? `Phát hành ${onlyPassed} agent đã đạt` : 'Phát hành toàn bộ agent'}</Button>}
	</div>;
}
