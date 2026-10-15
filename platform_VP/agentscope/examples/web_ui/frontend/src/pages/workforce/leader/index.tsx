import { Bot, MessageSquareText, Plus, Users } from 'lucide-react';
import { useEffect, useState } from 'react';

import { workforceApi } from '@/api';
import type { LeaderSession } from '@/api';
import { Button } from '@/components/ui/button';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Spinner } from '@/components/ui/spinner';
import { AudioProvider } from '@/context/AudioContext';
import { useSessions } from '@/hooks/useSessions';
import { ChatViewport } from '@/pages/chat/ChatViewport';

function LeaderPageInner() {
	const [leader, setLeader] = useState<LeaderSession | null>(null);
	const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
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
		const value = await workforceApi.createTicket();
		setLeader(value);
		setSelectedSessionId(value.session_id);
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
					<EmptyMedia variant="icon"><Bot /></EmptyMedia>
					<EmptyTitle>Leader chưa thể khởi tạo</EmptyTitle>
					<EmptyDescription>Hãy kiểm tra model credential rồi tải lại trang.</EmptyDescription>
				</EmptyHeader>
			</Empty>
		);
	}

	return (
		<div className="flex size-full min-h-0 gap-2 p-2">
			<aside className="flex w-72 shrink-0 flex-col overflow-hidden rounded-[22px] bg-card shadow-panel">
				<header className="border-b p-5">
					<div className="flex items-center gap-3">
						<div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
							<Users className="size-4" />
						</div>
						<div>
							<h1 className="font-medium">Leader</h1>
							<p className="text-xs text-muted-foreground">Mỗi cuộc chat là một ticket riêng</p>
						</div>
					</div>
					<Button className="mt-4 w-full" size="sm" onClick={createTicket}>
						<Plus /> Tạo ticket thử nghiệm
					</Button>
				</header>
				<div className="min-h-0 flex-1 overflow-y-auto p-2">
					<p className="px-2 py-2 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
						Ticket đang có
					</p>
					<div className="space-y-1">
						{sessions.map(({ session }) => (
							<button
								key={session.id}
								type="button"
								onClick={() => setSelectedSessionId(session.id)}
								className={`flex w-full items-start gap-2 rounded-xl px-3 py-2.5 text-left transition-colors ${
									selectedSessionId === session.id
										? 'bg-primary text-primary-foreground'
										: 'hover:bg-muted'
								}`}
							>
								<MessageSquareText className="mt-0.5 size-4 shrink-0" />
								<span className="min-w-0">
									<span className="block truncate text-sm font-medium">{session.config.name}</span>
									<span className="block truncate text-[10px] opacity-65">
										{new Date(session.updated_at ?? session.created_at).toLocaleString('vi-VN')}
									</span>
								</span>
							</button>
						))}
					</div>
				</div>
			</aside>

			<main className="flex min-w-0 flex-1 overflow-hidden rounded-[22px] bg-card shadow-panel">
				<ChatViewport
					agentId={leader.agent_id}
					sessionId={selectedSessionId}
					onSessionsChanged={refetch}
				/>
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
