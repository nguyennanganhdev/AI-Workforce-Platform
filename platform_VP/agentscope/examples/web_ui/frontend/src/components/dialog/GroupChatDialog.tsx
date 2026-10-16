import { Check, CircleAlert, Crown, Loader2, Plus, Search } from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';

import { sessionApi, workforceApi, type AgentView, type ChatModelConfig } from '@/api';
import { GroupAvatar } from '@/components/chat/GroupAvatar';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';
import { addGroupChat, agentHandle } from '@/lib/group-chats';
import { cn } from '@/lib/utils';

const isInvitable = (agent: AgentView) =>
	!!agent.data.invite_config?.invitable && !!agent.data.invite_config?.invite_description?.trim();

/** Open a fixed-Leader session and queue one full-roster invitation batch. */
export function GroupChatDialog({
	open,
	onOpenChange,
	agents,
	modelConfig,
	onCreateAgent,
	onCreated,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agents: AgentView[];
	/** The model the new chat starts on: whatever the open chat uses. */
	modelConfig?: { chat?: ChatModelConfig | null; subAgent?: ChatModelConfig | null; fallback?: ChatModelConfig | null };
	/** Offered when there are too few agents to make a group from. */
	onCreateAgent?: () => void;
	onCreated: (agentId: string, sessionId: string) => void | Promise<void>;
}) {
	const { t } = useTranslation();
	const [name, setName] = useState('');
	const [goal, setGoal] = useState('');
	const [query, setQuery] = useState('');
	const [picked, setPicked] = useState<string[]>([]);
	const [primaryId, setPrimaryId] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState('');

	useEffect(() => {
		if (open) return;
		setName('');
		setGoal('');
		setQuery('');
		setPicked([]);
		setPrimaryId(null);
		setError('');
	}, [open]);

	const pool = useMemo(() => agents.filter((agent) =>
		agent.data.system_role === 'business' && agent.data.lifecycle_state === 'published' && isInvitable(agent),
	), [agents]);
	const byId = useMemo(() => new Map(pool.map((agent) => [agent.id, agent])), [pool]);
	const visible = useMemo(() => {
		const q = query.trim().toLowerCase();
		return q ? pool.filter((agent) => agent.data.name.toLowerCase().includes(q)) : pool;
	}, [pool, query]);

	const members = picked.filter((id) => byId.has(id));
	const primary = primaryId && members.includes(primaryId) ? primaryId : (members[0] ?? null);
	const trimmed = name.trim();
	const ready = !!trimmed && !!primary;

	const toggle = (id: string) =>
		setPicked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

	const handleSubmit = async (event: FormEvent) => {
		event.preventDefault();
		if (!ready || !primary || submitting) return;
		setSubmitting(true);
		setError('');
		try {
			const { agent_id: leader } = await workforceApi.bootstrapLeader();
			const { session_id } = await sessionApi.create({
				agent_id: leader,
				...(modelConfig?.chat ? { chat_model_config: modelConfig.chat } : {}),
				...(modelConfig?.subAgent ? { sub_agent_chat_model_config: modelConfig.subAgent } : {}),
				...(modelConfig?.fallback
					? { fallback_chat_model_config: modelConfig.fallback }
					: {}),
			});
			await sessionApi.update(session_id, leader, { name: trimmed }, { silent: true });

			const handles = members
				.map((id) => agentHandle(byId.get(id)!.data.name, id))
				.join(', ');
			addGroupChat({
				sessionId: session_id,
				agentId: leader,
				name: trimmed,
				memberIds: members,
				createdAt: new Date().toISOString(),
				kickoff: t('groupChat.kickoff', {
					name: trimmed,
					goal: goal.trim() ? t('groupChat.kickoffGoal', { goal: goal.trim() }) : '',
					members: handles,
					primary: agentHandle(byId.get(primary)!.data.name, primary),
					assignments: JSON.stringify(members.filter((id) => id !== primary).map((id) => ({
						target: agentHandle(byId.get(id)!.data.name, id),
						prompt: byId.get(id)!.data.invite_config.invite_description,
					}))),
				}),
			});
			await onCreated(leader, session_id);
			onOpenChange(false);
		} catch (e) {
			setError(formatApiErrorForAlert(e));
		} finally {
			setSubmitting(false);
		}
	};

	const preview = members.map((id) => ({ id, name: byId.get(id)?.data.name ?? id }));

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="!w-[576px] !max-w-[calc(100%-2rem)]">
				<form onSubmit={handleSubmit} className="flex min-w-0 flex-col gap-5">
					<DialogHeader className="flex-row items-center gap-3 pr-10">
						{preview.length > 1 ? (
							<GroupAvatar members={preview} size={52} />
						) : (
							<span className="flex size-[52px] shrink-0 items-center justify-center rounded-[17px] border border-dashed border-[var(--cue-border,var(--border))] text-[var(--cue-text-tertiary,var(--muted-foreground))]">
								{members.length}
							</span>
						)}
						<div className="flex min-w-0 flex-col gap-1">
							<DialogTitle>{t('groupChat.title')}</DialogTitle>
							<DialogDescription className="text-[13px]/[18px]">
								{t('groupChat.description')}
							</DialogDescription>
						</div>
					</DialogHeader>

					<label className="flex flex-col gap-2">
						<span className="text-[13px]/[18px] text-muted-foreground">
							{t('groupChat.name')}
						</span>
						<Input
							autoFocus
							value={name}
							onChange={(e) => setName(e.target.value)}
							placeholder={t('groupChat.namePlaceholder')}
							className="h-10 text-[15px] md:text-[15px]"
							maxLength={64}
						/>
					</label>

					{pool.length === 0 && (
						<div className="flex items-center justify-between gap-3 rounded-2xl bg-[var(--cue-bg-subtle,var(--muted))] px-4 py-3 text-[13px]/[18px] text-muted-foreground">
							<span>{t('groupChat.notEnough', { count: pool.length })}</span>
							{onCreateAgent && (
								<Button
									type="button"
									size="sm"
									className="shrink-0"
									onClick={onCreateAgent}
								>
									<Plus />
									{t('groupChat.menuAgent')}
								</Button>
							)}
						</div>
					)}

					<div className="flex flex-col gap-2">
						<span className="flex items-baseline justify-between text-[13px]/[18px] text-muted-foreground">
							{t('groupChat.members')}
							<span className="tabular-nums">
								{t('groupChat.selected', { count: members.length })}
							</span>
						</span>
						<div className="overflow-hidden rounded-2xl border border-[var(--cue-border,var(--border))]">
							<div className="flex h-10 items-center gap-2 border-b border-[var(--cue-divider,var(--border))] px-3">
								<Search className="size-4 text-[var(--cue-text-tertiary,var(--muted-foreground))]" />
								<input
									value={query}
									onChange={(e) => setQuery(e.target.value)}
									placeholder={t('groupChat.searchPlaceholder')}
									className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-[var(--cue-text-tertiary,var(--muted-foreground))]"
								/>
							</div>
							<ul className="max-h-60 overflow-y-auto p-1">
								{visible.map((agent) => {
									const selected = members.includes(agent.id);
									const isPrimary = agent.id === primary;
									return (
										<li key={agent.id} className="group/member relative">
											<button
												type="button"
												role="checkbox"
												aria-checked={selected}
												onClick={() => toggle(agent.id)}
												className="flex h-14 w-full items-center gap-3 rounded-xl px-2.5 text-left hover:bg-[var(--cue-bg-hover,var(--accent))]"
											>
												<ClayAvatar
													id={agent.id}
													label={agent.data.name}
													size={36}
												/>
												{/* Room on the right for the crown pill, once picked. */}
												<span
													className={cn(
														'min-w-0 flex-1',
														selected && 'pr-36',
													)}
												>
													<span className="block truncate text-[15px]/5 font-medium">
														{agent.data.name}
													</span>
													<span className="block truncate text-[12px]/4 text-[var(--cue-text-secondary,var(--muted-foreground))]">
														{isInvitable(agent)
															? agent.data.invite_config
																	.invite_description
															: agent.data.system_prompt?.split(
																	'\n',
																)[0] ||
																t('agents.list.noDescription')}
													</span>
												</span>
												<span
													className={cn(
														'flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors',
														selected
															? 'border-foreground bg-foreground text-background'
															: 'border-[var(--cue-radio,#d0d0d0)]',
													)}
												>
													{selected && (
														<Check className="size-3" strokeWidth={3} />
													)}
												</span>
											</button>
											{/* The primary specialist starts first; the fixed Leader coordinates. */}
											{selected && (
												<button
													type="button"
													aria-label={`${t('groupChat.makeLeader')} ${agent.data.name}`}
													onClick={() => setPrimaryId(agent.id)}
													className={cn(
														'absolute top-1/2 right-11 flex h-6 -translate-y-1/2 items-center gap-1 rounded-full px-2 text-[12px] font-medium transition-opacity',
														isPrimary
															? 'bg-[var(--amber-soft,#fdf4e3)] text-[var(--amber-ink,#8a5a00)]'
															: 'bg-[var(--cue-bg-subtle,var(--muted))] text-muted-foreground opacity-0 group-hover/member:opacity-100 focus-visible:opacity-100',
													)}
												>
													<Crown className="size-3" />
													{isPrimary
														? t('groupChat.leader')
														: t('groupChat.makeLeader')}
												</button>
											)}
										</li>
									);
								})}
								{visible.length === 0 && query.trim() && (
									<li className="px-3 py-6 text-center text-[13px] text-muted-foreground">
										{t('chat.session.noResults', { query: query.trim() })}
									</li>
								)}
							</ul>
						</div>
					</div>

					<label className="flex flex-col gap-2">
						<span className="text-[13px]/[18px] text-muted-foreground">
							{t('groupChat.goal')}
						</span>
						<Textarea
							value={goal}
							onChange={(e) => setGoal(e.target.value)}
							placeholder={t('groupChat.goalPlaceholder')}
							className="min-h-20 rounded-xl px-3 py-2.5 text-[15px]/[22px] md:text-[15px]"
						/>
					</label>

					{error && (
						<Alert variant="destructive">
							<CircleAlert />
							<AlertDescription className="whitespace-pre-wrap">
								{error}
							</AlertDescription>
						</Alert>
					)}

					<DialogFooter className="items-center sm:justify-between">
						<span className="text-[13px]/[18px] text-[var(--cue-text-tertiary,var(--muted-foreground))]">
							{members.length === 0 && t('groupChat.needTwo')}
						</span>
						<div className="flex gap-2">
							<Button
								type="button"
								variant="outline"
								size="lg"
								className="min-w-20"
								onClick={() => onOpenChange(false)}
								disabled={submitting}
							>
								{t('common.cancel')}
							</Button>
							<Button
								type="submit"
								size="lg"
								className="min-w-20"
								disabled={!ready || submitting}
							>
								{submitting && <Loader2 className="animate-spin" />}
								{submitting ? t('groupChat.creating') : t('groupChat.create')}
							</Button>
						</div>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
