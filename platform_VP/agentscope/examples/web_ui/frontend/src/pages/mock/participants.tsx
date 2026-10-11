import { UserRound } from 'lucide-react';

import { MOCK_AGENTS, type MockAgentId, type MockConversation } from './chat-mock-data';
import { AgentSticker } from './transcript';

/**
 * The right-hand rail: who is in this conversation.
 *
 * The person who asked sits on top, then the agents in the order they came in
 * — the list grows as the Leader brings each one into the session, and the one
 * working right now is marked.
 */
export function Participants({
	requester,
	agents,
	activeAgent,
}: {
	requester: MockConversation['requester'];
	/** In order of appearance. */
	agents: MockAgentId[];
	/** The agent the playback is on at this moment, if any. */
	activeAgent: MockAgentId | null;
}) {
	return (
		<aside
			aria-label="Đối tượng tham gia cuộc trò chuyện"
			className="clay-panel flex w-[280px] shrink-0 flex-col gap-5 overflow-y-auto rounded-[var(--r-panel)] bg-sidebar p-4 text-sidebar-foreground max-lg:hidden"
		>
			<section className="flex flex-col gap-2.5">
				<h2 className="text-[12px]/[16px] font-semibold text-muted-foreground">
					Người yêu cầu
				</h2>
				<div className="flex items-center gap-3">
					{/* A person, so a plain tile rather than a robot sticker. */}
					<span className="flex size-9 shrink-0 items-center justify-center rounded-[13px] bg-[var(--sunken)] text-[var(--ink-2)] shadow-[var(--clay-sunken)]">
						<UserRound className="size-4" />
					</span>
					<div className="min-w-0">
						<p className="truncate text-[14px]/[20px] font-semibold">
							{requester.name}
						</p>
						<p className="truncate text-[12px]/[16px] text-muted-foreground">
							{requester.note}
						</p>
					</div>
				</div>
			</section>

			<section className="flex flex-col gap-2.5">
				<h2 className="flex items-center gap-2 text-[12px]/[16px] font-semibold text-muted-foreground">
					Agent đang tham gia
					<span className="rounded-full bg-[var(--sunken)] px-1.5 text-[var(--ink-2)]">
						{agents.length}
					</span>
				</h2>
				{agents.length === 0 ? (
					<p className="text-[13px]/[20px] text-muted-foreground">
						Chưa có agent nào được đưa vào phiên.
					</p>
				) : (
					<ol className="flex flex-col">
						{agents.map((agent, index) => (
							<li key={agent} className="relative flex gap-3 pb-4 last:pb-0">
								{/* The thin line joining one participant to the next. */}
								{index < agents.length - 1 && (
									<span
										aria-hidden="true"
										className="absolute bottom-0 left-[17px] top-9 w-px bg-[var(--line-warm)]"
									/>
								)}
								<AgentSticker agent={agent} size={36} />
								<div className="min-w-0 flex-1">
									<p className="truncate text-[14px]/[20px] font-semibold">
										{MOCK_AGENTS[agent].name}
									</p>
									<p className="text-[12px]/[16px] text-muted-foreground">
										{MOCK_AGENTS[agent].role}
									</p>
									{agent === activeAgent && (
										<span className="mt-1 inline-flex h-[22px] items-center gap-1.5 rounded-full bg-[var(--violet-soft)] px-2.5 text-[12px]/[16px] font-semibold text-[var(--violet-ink)]">
											<span className="size-1.5 animate-pulse rounded-full bg-current" />
											đang xử lý
										</span>
									)}
								</div>
							</li>
						))}
					</ol>
				)}
			</section>
		</aside>
	);
}
