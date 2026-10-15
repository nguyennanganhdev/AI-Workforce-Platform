import { Bot, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';

import { sessionApi, workforceApi } from '@/api';
import type { LeaderSession, SessionStatus } from '@/api';
import { ListRow } from '@/components/chat/ListRow';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { Button } from '@/components/ui/button';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Spinner } from '@/components/ui/spinner';
import { AudioProvider } from '@/context/AudioContext';
import { useSessions } from '@/hooks/useSessions';
import { ChatViewport } from '@/pages/chat/ChatViewport';

/** Names a session had before the first turn titled it. */
const UNTITLED = /^(Phiếu đối tác|Ticket mới|Partner ticket|\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?)$/;

/** A row's name: the session's title without the unit code it once led with. */
function rowTitle(name: string | undefined): string {
	const title = (name ?? '').replace(/^[A-Z0-9][A-Z0-9-]{3,}\s*·\s*/, '').trim();
	return !title || UNTITLED.test(title) ? 'Session mới' : title;
}

const STATUS_DOT: Partial<Record<SessionStatus, string>> = {
	running: 'bg-[var(--cue-success,#34c759)]',
	awaiting_permission: 'bg-[var(--cue-blue,#2f80ed)]',
	awaiting_external_result: 'bg-[var(--cue-blue,#2f80ed)]',
};

/**
 * The Leader: one session per ticket a customer's reception sent, one line
 * each, and the selected session's chat (and its room) beside them.
 */
function LeaderPageInner() {
	const [leader, setLeader] = useState<LeaderSession | null>(null);
	const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [creating, setCreating] = useState(false);
	const [deleting, setDeleting] = useState<{ id: string; title: string } | null>(null);
	const { sessions, refetch } = useSessions(leader?.agent_id ?? null);

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

	const removeSession = async (sessionId: string) => {
		if (!leader) return;
		await sessionApi.delete(sessionId, leader.agent_id);
		const rest = sessions.filter((view) => view.session.id !== sessionId);
		if (selectedSessionId === sessionId) setSelectedSessionId(rest[0]?.session.id ?? null);
		await refetch();
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
			<aside className="cue-column flex w-72 shrink-0 flex-col border-r border-sidebar-border bg-sidebar max-md:hidden">
				<header className="flex h-12 shrink-0 items-center justify-between gap-2 pr-2 pl-4">
					<div className="min-w-0">
						<h1 className="truncate text-[15px]/5 font-semibold">Leader</h1>
						<p className="truncate text-xs text-muted-foreground">Session nhận ticket từ khách hàng</p>
					</div>
					<Button
						variant="ghost"
						size="icon"
						aria-label="Tạo session thử"
						title="Tạo session thử"
						disabled={creating}
						onClick={createTicket}
					>
						{creating ? <Spinner className="size-4" /> : <Plus className="size-5" />}
					</Button>
				</header>
				<ul className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pt-1 pb-2">
					{sessions.length === 0 ? (
						<li className="px-3 py-6 text-center text-[13px]/[18px] text-muted-foreground">
							Chưa có session. Ticket từ khách hàng hiện ở đây.
						</li>
					) : (
						sessions.map((view) => {
							const title = rowTitle(view.session.config.name);
							return (
								<ListRow
									key={view.session.id}
									title={title}
									active={selectedSessionId === view.session.id}
									dot={STATUS_DOT[view.status]}
									dotLabel={view.status === 'running' ? 'đang xử lý' : 'đang chờ'}
									onSelect={() => setSelectedSessionId(view.session.id)}
									onDelete={() => setDeleting({ id: view.session.id, title })}
								/>
							);
						})
					)}
				</ul>
			</aside>

			<main className="flex min-w-0 flex-1 overflow-hidden">
				<ChatViewport
					agentId={leader.agent_id}
					sessionId={selectedSessionId}
					onSessionsChanged={refetch}
					agentName="Leader"
					compact
				/>
			</main>

			<DeleteDialog
				open={deleting !== null}
				onOpenChange={(open) => !open && setDeleting(null)}
				title={`Xoá session "${deleting?.title ?? ''}"?`}
				description="Session, phòng và tin nhắn của nó bị xoá. Các agent trong phòng vẫn giữ nguyên. Nếu khách gửi tiếp vào ticket này, Leader mở lại một session mới."
				confirmLabel="Xoá session"
				onConfirm={async () => {
					if (deleting) await removeSession(deleting.id);
				}}
			/>
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
