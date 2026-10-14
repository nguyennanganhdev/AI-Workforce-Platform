import { Search, XIcon } from 'lucide-react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';

import type { AgentView, SessionView } from '@/api';
import {
	ChatRow,
	sessionTime,
	sessionTitle,
	useSessionPreview,
} from '@/components/chat/SessionRow';
import { Button } from '@/components/ui/button';
import { useTranslation } from '@/i18n/useI18n';

type Result = { kind: 'agent'; agent: AgentView } | { kind: 'session'; view: SessionView };

const newestFirst = (a: string, b: string) => new Date(b).getTime() - new Date(a).getTime();

/**
 * The search command palette: a 680 × 440 sheet 180px from the top, with no
 * backdrop — the page behind it stays as it was.
 *
 * Searches two things at once: every agent by name, and the open agent's
 * chats by title. Results reuse the sidebar row. The first row carries the
 * keyboard cursor; ↑/↓ move it, Enter opens, Esc closes. While the lists are
 * still loading the body shows three skeleton rows instead.
 */
export function SearchPalette({
	open,
	onOpenChange,
	agents,
	sessions,
	loading = false,
	currentAgent,
	onSelectAgent,
	onSelectSession,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agents: AgentView[];
	/** The open agent's chats. */
	sessions: SessionView[];
	loading?: boolean;
	currentAgent: AgentView | null;
	onSelectAgent: (agentId: string) => void;
	onSelectSession: (sessionId: string) => void;
}) {
	const { t } = useTranslation();
	const preview = useSessionPreview();
	const [query, setQuery] = useState('');
	const [cursor, setCursor] = useState(0);
	const listRef = useRef<HTMLDivElement>(null);

	const { agentResults, sessionResults } = useMemo(() => {
		const q = query.trim().toLowerCase();
		const matches = (text: string) => !q || text.toLowerCase().includes(q);
		return {
			agentResults: agents
				.filter((a) => matches(a.data.name))
				.sort((a, b) => newestFirst(a.updated_at, b.updated_at)),
			sessionResults: sessions
				.filter((v) => matches(v.session.config.name || v.session.id))
				.sort((a, b) => newestFirst(a.session.created_at, b.session.created_at)),
		};
	}, [agents, sessions, query]);

	const results: Result[] = useMemo(
		() => [
			...agentResults.map((agent) => ({ kind: 'agent' as const, agent })),
			...sessionResults.map((view) => ({ kind: 'session' as const, view })),
		],
		[agentResults, sessionResults],
	);

	// A fresh query starts from the top; reopening starts from scratch.
	useEffect(() => setCursor(0), [query]);
	useEffect(() => {
		if (!open) setQuery('');
	}, [open]);

	useEffect(() => {
		listRef.current
			?.querySelector(`[data-index="${cursor}"]`)
			?.scrollIntoView({ block: 'nearest' });
	}, [cursor]);

	const choose = (result: Result | undefined) => {
		if (!result) return;
		if (result.kind === 'agent') onSelectAgent(result.agent.id);
		else onSelectSession(result.view.session.id);
		onOpenChange(false);
	};

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			setCursor((c) => Math.min(c + 1, results.length - 1));
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			setCursor((c) => Math.max(c - 1, 0));
		} else if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
			event.preventDefault();
			choose(results[cursor]);
		}
	};

	const label = (text: string) => (
		<p className="px-3 pt-2 pb-1 text-[13px]/[18px] text-[var(--cue-text-secondary,var(--muted-foreground))]">
			{text}
		</p>
	);

	const renderRow = (result: Result, index: number) => {
		const common = {
			'data-index': index,
			active: index === cursor,
			tabIndex: -1,
			onMouseMove: () => setCursor(index),
			onSelect: () => choose(result),
		};
		if (result.kind === 'agent') {
			const { agent } = result;
			return (
				<ChatRow
					key={`a:${agent.id}`}
					{...common}
					avatarId={agent.id}
					avatarLabel={agent.data.name}
					title={agent.data.name}
					time={sessionTime(agent.updated_at)}
					preview={t('chat.session.previewAgent', { name: agent.data.name })}
				/>
			);
		}
		const { view } = result;
		const name = currentAgent?.data.name ?? '';
		return (
			<ChatRow
				key={`s:${view.session.id}`}
				{...common}
				avatarId={view.session.agent_id}
				avatarLabel={name || undefined}
				title={sessionTitle(view.session.config.name) || t('chat.newSession')}
				time={sessionTime(view.session.created_at)}
				status={view.status}
				preview={preview(view, name)}
			/>
		);
	};

	return (
		<DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
			<DialogPrimitive.Portal>
				<DialogPrimitive.Content
					aria-describedby={undefined}
					onKeyDown={handleKeyDown}
					className="fixed top-[180px] left-1/2 z-50 flex h-[440px] max-h-[calc(100vh-200px)] w-[680px] max-w-[calc(100vw-2rem)] -translate-x-1/2 flex-col overflow-hidden rounded-3xl border border-[var(--cue-border,var(--border))] bg-background text-foreground shadow-[var(--cue-shadow-float,0_8px_32px_rgba(0,0,0,.1))] outline-none duration-120 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0"
				>
					<DialogPrimitive.Title className="sr-only">
						{t('chat.session.search')}
					</DialogPrimitive.Title>
					<div className="flex h-[66px] shrink-0 items-center gap-3 border-b border-[var(--cue-divider,var(--border))] pr-3 pl-5">
						<Search className="size-5 text-[var(--cue-text-tertiary,var(--muted-foreground))]" />
						<input
							autoFocus
							value={query}
							onChange={(e) => setQuery(e.target.value)}
							placeholder={t('chat.session.searchPlaceholder')}
							className="min-w-0 flex-1 bg-transparent text-[17px]/6 outline-none placeholder:text-[var(--cue-text-tertiary,var(--muted-foreground))]"
						/>
						<DialogPrimitive.Close asChild>
							<Button
								variant="ghost"
								size="icon"
								aria-label={t('chat.session.close')}
							>
								<XIcon className="size-5" />
							</Button>
						</DialogPrimitive.Close>
					</div>
					<div ref={listRef} className="min-h-0 flex-1 overflow-y-auto p-2">
						{loading ? (
							<div className="flex flex-col">
								{[0, 1, 2].map((i) => (
									<div key={i} className="flex h-[60px] items-center gap-3 px-3">
										<span className="cue-skeleton size-9 shrink-0 rounded-full" />
										<span className="flex flex-1 flex-col gap-2">
											<span className="cue-skeleton h-3 w-1/3 rounded-full" />
											<span className="cue-skeleton h-3 w-2/3 rounded-full" />
										</span>
									</div>
								))}
							</div>
						) : results.length === 0 ? (
							<p className="px-3 py-6 text-center text-[13px]/[18px] text-[var(--cue-text-secondary,var(--muted-foreground))]">
								{t('chat.session.noResults', { query })}
							</p>
						) : (
							<>
								{agentResults.length > 0 && label(t('chat.agents.label'))}
								{results
									.slice(0, agentResults.length)
									.map((result, index) => renderRow(result, index))}
								{sessionResults.length > 0 &&
									label(
										currentAgent
											? t('chat.agents.chatsOf', {
													name: currentAgent.data.name,
												})
											: t('chat.session.recent'),
									)}
								{results
									.slice(agentResults.length)
									.map((result, index) =>
										renderRow(result, agentResults.length + index),
									)}
							</>
						)}
					</div>
				</DialogPrimitive.Content>
			</DialogPrimitive.Portal>
		</DialogPrimitive.Root>
	);
}
