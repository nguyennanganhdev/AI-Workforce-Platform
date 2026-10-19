import { useQueryClient } from '@tanstack/react-query';
import { Bot, FlaskConical, Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { CustomerCases } from './CustomerCases';
import { sessionApi, workforceApi } from '@/api';
import type { LeaderSession, SessionView } from '@/api';
import { sessionTime } from '@/components/chat/session-row-utils';
import { ChatRow } from '@/components/chat/SessionRow';
import { cleanName } from '@/components/chat/teamDialogText';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { Button } from '@/components/ui/button';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Spinner } from '@/components/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AudioProvider } from '@/context/AudioContext';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { usePlatformAccess } from '@/context/platform-access';
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
	const privateAccount = useCurrentUser()?.role === 'VIN_USER';
	const access = usePlatformAccess();
	const queryClient = useQueryClient();
	const personal = access?.workspace?.kind === 'personal';
	const [leader, setLeader] = useState<LeaderSession | null>(null);
	const [scope, setScope] = useState<'leader' | 'leader_tests'>('leader');
	const [selection, setSelection] = useState<Record<string, string | null>>({});
	const [loading, setLoading] = useState(true);
	const [creating, setCreating] = useState(false);
	const [bootstrapError, setBootstrapError] = useState(false);
	const [deleting, setDeleting] = useState<{ id: string; title: string } | null>(null);
	// A personal account's conversations are not partner tickets, so no ticket/test scope.
	const { sessions, refetch, error, loading: sessionsLoading } = useSessions(leader?.agent_id ?? null, personal ? undefined : scope);
	const selectedSessionId = selection[scope] ?? sessions[0]?.session.id ?? null;
	const isTest = scope === 'leader_tests';
	const setSelectedSessionId = (id: string | null) => setSelection((value) => ({ ...value, [scope]: id }));

	useEffect(() => {
		let active = true;
		workforceApi
			.bootstrapLeader()
			.then((value) => {
				if (!active) return;
				setLeader(value);
				if (!value.is_test) setSelection((current) => ({ ...current, leader: value.session_id }));
			})
			.catch(() => { if (active) setBootstrapError(true); })
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, []);

	const createTest = async () => {
		setCreating(true);
		try {
			if (personal) {
				const value = await workforceApi.createTicket();
				setLeader(value);
				setSelection((current) => ({ ...current, leader: value.session_id }));
				await refetch();
				return;
			}
			const value = await workforceApi.createLeaderTest();
			setLeader(value);
			setScope('leader_tests');
			setSelection((current) => ({ ...current, leader_tests: value.session_id }));
			await queryClient.invalidateQueries({ queryKey: ['sessions', value.agent_id] });
		} catch {
			toast.error(personal ? 'Chưa tạo được cuộc trò chuyện. Hãy thử lại.' : 'Chưa tạo được phiên thử. Hãy thử lại.');
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
					<EmptyDescription>{access ? 'Dịch vụ AI chưa sẵn sàng cho tài khoản này. Vui lòng thử lại sau hoặc liên hệ quản trị để kiểm tra quyền và hạn mức.' : bootstrapError ? 'Không tải được Leader. Kiểm tra kết nối rồi tải lại trang.' : 'Hãy kiểm tra model credential rồi tải lại trang.'}</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}

	return (
		<div className="flex size-full min-h-0 flex-col md:flex-row">
			<aside aria-label="Danh sách phiên Leader" className="cue-column flex w-full shrink-0 flex-col border-sidebar-border bg-sidebar max-md:border-b md:w-80 md:border-r">
				<header className="flex h-12 shrink-0 items-center justify-between gap-2 pr-2 pl-4">
					<div className="min-w-0">
						<h1 className="truncate text-[15px]/5 font-semibold">Leader</h1>
						<p className="truncate text-xs text-muted-foreground">{personal ? 'Không gian cá nhân · Leader của bạn' : isTest ? 'Phiên thử nội bộ · Ban quản lý' : 'Phiếu cư dân · Ban quản lý điều hành'}</p>
					</div>
					<Button
						variant="ghost"
						size="icon"
						aria-label={personal ? 'Tạo cuộc trò chuyện' : 'Tạo phiên thử'}
						title={personal ? 'Tạo cuộc trò chuyện' : 'Tạo phiên thử'}
						disabled={creating}
						onClick={createTest}
					>
						{creating ? <Spinner className="size-4" /> : <Plus className="size-5" />}
					</Button>
				</header>
				<Tabs value={scope} onValueChange={(value) => setScope(value as typeof scope)} className="min-h-0 flex-1 gap-0">
					<TabsList aria-label="Loại phiên Leader" className={personal ? 'hidden' : 'mx-3 mb-2 w-auto shrink-0'}>
						<TabsTrigger value="leader" className="min-h-9">Phiếu cư dân</TabsTrigger>
						<TabsTrigger value="leader_tests" className="min-h-9"><FlaskConical className="size-3.5" />Phiên thử</TabsTrigger>
					</TabsList>
					<TabsContent value={scope} className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2">
					{error ? (
						<div role="alert" className="px-3 py-4 text-sm">Không tải được danh sách phiên. <Button variant="link" onClick={() => void refetch()}>Thử lại</Button></div>
					) : sessionsLoading ? <div role="status" className="flex justify-center py-4"><Spinner /><span className="sr-only">Đang tải phiên</span></div> : sessions.length === 0 ? (
						<p className="px-3 py-6 text-center text-[13px]/[18px] text-muted-foreground">
							{personal ? 'Bắt đầu cuộc trò chuyện mới với Leader.' : isTest ? 'Chưa có phiên thử. Chọn dấu + để bắt đầu.' : 'Chưa có phiếu cư dân. Phiếu từ đối tác sẽ hiện ở đây.'}
						</p>
					) : (
						<>
						<label className="block px-1 md:hidden"><span className="sr-only">{personal ? 'Chọn cuộc trò chuyện' : isTest ? 'Chọn phiên thử' : 'Chọn phiếu cư dân'}</span>
							<select className="min-h-11 w-full rounded-md border bg-background px-3 text-sm" value={selectedSessionId ?? ''} onChange={(event) => setSelectedSessionId(event.target.value)}>
								{sessions.map((view) => <option key={view.session.id} value={view.session.id}>{rowTitle(view.session.config.name)}</option>)}
							</select>
						</label>
						<div className="max-md:hidden">{sessions.map((view, index) => {
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
						})}</div>
						</>
					)}
					</TabsContent>
				</Tabs>
			</aside>

			<main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
				{isTest && <div className="flex shrink-0 items-start gap-2 border-b px-4 py-2 text-xs text-muted-foreground"><FlaskConical className="mt-0.5 size-3.5 shrink-0" /><p>Phiên thử để trao đổi với Leader, không liên kết phiếu cư dân.</p></div>}
				{privateAccount && selectedSessionId && <CustomerCases key={selectedSessionId} agentId={leader.agent_id} sessionId={selectedSessionId} />}
				<div className="flex min-h-0 flex-1 overflow-hidden">
				<ChatViewport
					agentId={leader.agent_id}
					sessionId={selectedSessionId}
					onSessionsChanged={refetch}
					agentName="Leader"
					ticketView={personal || !isTest}
					sessionScope={personal ? undefined : scope}
				/>
				</div>
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
