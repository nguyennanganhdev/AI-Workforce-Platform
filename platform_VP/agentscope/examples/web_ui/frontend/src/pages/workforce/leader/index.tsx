import { Bot } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { workforceApi } from '@/api';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Spinner } from '@/components/ui/spinner';

/** Keep existing Leader links and bootstrap, using the main chat for every conversation. */
export function LeaderPage() {
	const navigate = useNavigate();
	const [failed, setFailed] = useState(false);

	useEffect(() => {
		let active = true;
		workforceApi
			.bootstrapLeader()
			.then((leader) => {
				if (!active) return;
				navigate(`/chat/${leader.agent_id}/${leader.session_id ?? 'new'}`, {
					replace: true,
					state: {
						draftConfig: { agent_id: leader.agent_id, chat_model_config: leader.chat_model_config },
					},
				});
			})
			.catch(() => {
				if (active) setFailed(true);
			});
		return () => {
			active = false;
		};
	}, [navigate]);

	if (failed) {
		return (
			<Empty className="size-full border-none">
				<EmptyHeader>
					<EmptyMedia variant="icon"><Bot /></EmptyMedia>
					<EmptyTitle>Không thể mở Leader</EmptyTitle>
					<EmptyDescription>Kiểm tra credential rồi tải lại.</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}

	return <div className="flex size-full items-center justify-center"><Spinner /></div>;
}
