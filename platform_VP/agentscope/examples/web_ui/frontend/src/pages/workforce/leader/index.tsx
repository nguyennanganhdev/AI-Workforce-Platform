import { Bot, Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { sessionApi, workforceApi } from '@/api';
import type { LeaderSession, SessionView } from '@/api';
import { sessionTime } from '@/components/chat/session-row-utils';
import { ChatRow } from '@/components/chat/SessionRow';
import { cleanName } from '@/components/chat/teamDialogText';
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

/** A row's second line: what the session is doing, or who is in its room. */
function rowPreview(view: SessionView): string {
	if (view.status === 'running') return 'Đang xử lý…';
	if (view.status === 'awaiting_permission') return 'Chờ bạn duyệt';
	if (view.status === 'awaiting_external_result') return 'Chờ kết quả từ đối tác';
	const members = view.team?.members.map(({ agent }) => cleanName(agent.data.name)) ?? [];
	return members.length > 0 ? members.join(', ') : 'Leader';
}

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
			<aside className="cue-column flex w-80 shrink-0 flex-col border-r border-sidebar-border bg-sidebar max-md:hidden">
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
				<div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2">
					{sessions.length === 0 ? (
						<p className="px-3 py-6 text-center text-[13px]/[18px] text-muted-foreground">
							Chưa có session. Ticket từ khách hàng hiện ở đây.
						</p>
					) : (
						sessions.map((view, index) => {
							const title = rowTitle(view.session.config.name);
							return (
								<ChatRow
									key={view.session.id}
									className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-left-1 motion-safe:fill-mode-both"
									style={{ animationDelay: `${Math.min(index, 10) * 30}ms` }}
									avatarId={leader.agent_id}
									avatarLabel="Leader"
									title={title}
									time={sessionTime(view.session.updated_at ?? view.session.created_at)}
									preview={rowPreview(view)}
									status={view.status}
									active={selectedSessionId === view.session.id}
									onSelect={() => setSelectedSessionId(view.session.id)}
									actions={
										<Button
											variant="ghost"
											size="icon-sm"
											aria-label={`Xoá session ${title}`}
											title="Xoá session"
											className="text-muted-foreground"
											onClick={() => setDeleting({ id: view.session.id, title })}
										>
											<Trash2 />
										</Button>
									}
								/>
							);
						})
					)}
				</div>
			</aside>

			<main className="flex min-w-0 flex-1 overflow-hidden">
				<ChatViewport
					agentId={leader.agent_id}
					sessionId={selectedSessionId}
					onSessionsChanged={refetch}
					agentName="Leader"
					ticketView
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
