import { Bot, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';

import { workforceApi } from '@/api';
import type { LeaderSession } from '@/api';
import { sessionTime, useSessionPreview } from '@/components/chat/session-row-utils';
import { ChatRow } from '@/components/chat/SessionRow';
import { Button } from '@/components/ui/button';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Spinner } from '@/components/ui/spinner';
import { AudioProvider } from '@/context/AudioContext';
import { useSessions } from '@/hooks/useSessions';
import { ChatViewport } from '@/pages/chat/ChatViewport';

/**
 * The management board's Leader: one row per ticket, the ticket's chat (and
 * its room) beside it. Same column and rows as the chat page, so a ticket
 * reads like any other conversation.
 */
function LeaderPageInner() {
	const [leader, setLeader] = useState<LeaderSession | null>(null);
	const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [creating, setCreating] = useState(false);
	const { sessions, refetch } = useSessions(leader?.agent_id ?? null);
	const preview = useSessionPreview();

	useEffect(() => {
		let active = true;
		workforceApi
			.bootstrapLeader()
			.then((value) => {
				if (!active) return;
				setLeader(value);
				setSelectedSessionId(value.session_id);
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, []);

	const createTicket = async () => {
		setCreating(true);
		try {
			const value = await workforceApi.createTicket();
			setLeader(value);
			setSelectedSessionId(value.session_id);
			await refetch();
		} finally {
			setCreating(false);
		}
	};

	if (loading) {
		return (
			<div className="flex size-full items-center justify-center">
				<Spinner />
			</div>
		);
	}

	if (!leader) {
		return (
			<Empty className="size-full border-none">
				<EmptyHeader>
					<EmptyMedia variant="icon">
						<Bot />
					</EmptyMedia>
					<EmptyTitle>Leader chưa thể khởi tạo</EmptyTitle>
					<EmptyDescription>Hãy kiểm tra model credential rồi tải lại trang.</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}

	return (
		<div className="flex size-full min-h-0">
			<aside className="cue-column flex w-80 shrink-0 flex-col border-r border-sidebar-border bg-sidebar max-md:hidden">
				<header className="flex h-12 shrink-0 items-center justify-between gap-2 pr-2 pl-4">
					<div className="min-w-0">
						<h1 className="truncate text-[15px]/5 font-semibold">Ticket của Leader</h1>
					</div>
					<Button
						variant="ghost"
						size="icon"
						aria-label="Tạo ticket thử nghiệm"
						title="Tạo ticket thử nghiệm"
						disabled={creating}
						onClick={createTicket}
					>
						{creating ? <Spinner className="size-4" /> : <Plus className="size-5" />}
					</Button>
				</header>
				<div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2">
					{sessions.length === 0 ? (
						<p className="px-3 py-6 text-center text-[13px]/[18px] text-muted-foreground">
							Chưa có ticket. Ticket của đối tác hiện ở đây; bấm + để thử một ticket.
						</p>
					) : (
						sessions.map((view) => (
							<ChatRow
								key={view.session.id}
								avatarId="leader"
								avatarLabel="Leader"
								title={view.session.config.name || 'Ticket'}
								time={sessionTime(view.session.updated_at ?? view.session.created_at)}
								preview={preview(view, 'Leader')}
								status={view.status}
								active={selectedSessionId === view.session.id}
								onSelect={() => setSelectedSessionId(view.session.id)}
							/>
						))
					)}
				</div>
			</aside>

			<main className="flex min-w-0 flex-1 overflow-hidden">
				<ChatViewport agentId={leader.agent_id} sessionId={selectedSessionId} onSessionsChanged={refetch} />
			</main>
		</div>
	);
}

export function LeaderPage() {
	return (
		<AudioProvider>
			<LeaderPageInner />
		</AudioProvider>
	);
}
