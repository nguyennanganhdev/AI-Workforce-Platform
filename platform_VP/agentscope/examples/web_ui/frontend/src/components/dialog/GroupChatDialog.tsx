import { Check, CircleAlert, Crown, Loader2, Plus, Search } from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';

import { agentApi, sessionApi, type AgentView, type ChatModelConfig } from '@/api';
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

/** What the leader is told to say an invited agent is for, when it has nothing set. */
function inviteDescription(agent: AgentView): string {
	const existing = agent.data.invite_config?.invite_description?.trim();
	if (existing) return existing;
	const prompt = agent.data.system_prompt?.trim().split('\n')[0] ?? '';
	return (prompt.length > 160 ? `${prompt.slice(0, 157)}…` : prompt) || agent.data.name;
}

const isInvitable = (agent: AgentView) =>
	!!agent.data.invite_config?.invitable && !!agent.data.invite_config?.invite_description?.trim();

/**
 * Starts a group chat: a name, two or more agents, and which of them leads.
 *
 * The backend forms teams from inside a conversation — the leader calls
 * `TeamCreate`, then `AgentInvite` for each member — so creating a group
 * here opens a session on the leader and queues the instruction to do
 * exactly that, sent as soon as the chat opens. A member the leader could
 * not invite yet is switched to "can be invited" first, and the dialog says
 * so before it happens.
 */
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
	modelConfig?: { chat?: ChatModelConfig | null; fallback?: ChatModelConfig | null };
	/** Offered when there are too few agents to make a group from. */
	onCreateAgent?: () => void;
	onCreated: (agentId: string, sessionId: string) => void | Promise<void>;
}) {
	const { t } = useTranslation();
	const [name, setName] = useState('');
	const [goal, setGoal] = useState('');
	const [query, setQuery] = useState('');
	const [picked, setPicked] = useState<string[]>([]);
	const [leaderId, setLeaderId] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState('');

	useEffect(() => {
		if (open) return;
		setName('');
		setGoal('');
		setQuery('');
		setPicked([]);
		setLeaderId(null);
		setError('');
	}, [open]);

	const byId = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);
	const visible = useMemo(() => {
		const q = query.trim().toLowerCase();
		return q ? agents.filter((a) => a.data.name.toLowerCase().includes(q)) : agents;
	}, [agents, query]);

	// The leader is the first pick until someone else is crowned.
	const leader = leaderId && picked.includes(leaderId) ? leaderId : (picked[0] ?? null);
	const members = picked.filter((id) => id !== leader);
	const toEnable = members.map((id) => byId.get(id)!).filter((a) => a && !isInvitable(a));
	const blocked = toEnable.filter((a) => !a.editable);
	const trimmed = name.trim();
	const ready = !!trimmed && !!leader && members.length > 0 && blocked.length === 0;

	const toggle = (id: string) =>
		setPicked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

	const handleSubmit = async (event: FormEvent) => {
		event.preventDefault();
		if (!ready || !leader || submitting) return;
		setSubmitting(true);
		setError('');
		try {
			for (const agent of toEnable) {
				await agentApi.update(
					agent.id,
					{
						invite_config: {
							invitable: true,
							invite_description: inviteDescription(agent),
						},
					},
					{ silent: true },
				);
			}
			const { session_id } = await sessionApi.create({
				agent_id: leader,
				...(modelConfig?.chat ? { chat_model_config: modelConfig.chat } : {}),
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

	const preview = picked.map((id) => ({ id, name: byId.get(id)?.data.name ?? id }));

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="!w-[576px] !max-w-[calc(100%-2rem)]">
				<form onSubmit={handleSubmit} className="flex min-w-0 flex-col gap-5">
					<DialogHeader className="flex-row items-center gap-3 pr-10">
						{preview.length > 1 ? (
							<GroupAvatar members={preview} size={52} />
						) : (
							<span className="flex size-[52px] shrink-0 items-center justify-center rounded-[17px] border border-dashed border-[var(--cue-border,var(--border))] text-[var(--cue-text-tertiary,var(--muted-foreground))]">
								{picked.length}
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

					{agents.length < 2 && (
						<div className="flex items-center justify-between gap-3 rounded-2xl bg-[var(--cue-bg-subtle,var(--muted))] px-4 py-3 text-[13px]/[18px] text-muted-foreground">
							<span>{t('groupChat.notEnough', { count: agents.length })}</span>
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
								{t('groupChat.selected', { count: picked.length })}
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
									const selected = picked.includes(agent.id);
									const isLeader = agent.id === leader;
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
											{/* The crown: who leads. Shown on the leader; offered on
											    hover to any other picked member. */}
											{selected && (
												<button
													type="button"
													onClick={() => setLeaderId(agent.id)}
													className={cn(
														'absolute top-1/2 right-11 flex h-6 -translate-y-1/2 items-center gap-1 rounded-full px-2 text-[12px] font-medium transition-opacity',
														isLeader
															? 'bg-[var(--amber-soft,#fdf4e3)] text-[var(--amber-ink,#8a5a00)]'
															: 'bg-[var(--cue-bg-subtle,var(--muted))] text-muted-foreground opacity-0 group-hover/member:opacity-100 focus-visible:opacity-100',
													)}
												>
													<Crown className="size-3" />
													{isLeader
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

					{toEnable.length > 0 && blocked.length === 0 && (
						<p className="text-[13px]/[18px] text-muted-foreground">
							{t('groupChat.willEnable', {
								names: toEnable.map((a) => a.data.name).join(', '),
							})}
						</p>
					)}
					{blocked.length > 0 && (
						<Alert variant="destructive">
							<CircleAlert />
							<AlertDescription>
								{t('groupChat.blocked', {
									names: blocked.map((a) => a.data.name).join(', '),
								})}
							</AlertDescription>
						</Alert>
					)}
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
							{picked.length < 2 && t('groupChat.needTwo')}
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
