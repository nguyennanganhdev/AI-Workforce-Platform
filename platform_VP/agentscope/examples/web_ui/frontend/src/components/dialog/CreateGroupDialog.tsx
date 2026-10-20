import { Search, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { isInvitableMember } from './team-members';
import { sessionApi, workforceApi } from '@/api';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
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
import { useAgents } from '@/hooks/useAgents';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Called with the Leader agent and the new group session. */
	onCreated: (leaderAgentId: string, sessionId: string) => void;
}

/**
 * A group is a new Leader session whose roster the user picks: the Leader
 * coordinates, the chosen published agents are its members.
 */
export function CreateGroupDialog({ open, onOpenChange, onCreated }: Props) {
	const { t } = useTranslation();
	const { agents, loading, error: loadError, refetch } = useAgents({ fetchOnMount: false });
	const [name, setName] = useState('');
	const [query, setQuery] = useState('');
	const [selected, setSelected] = useState<string[]>([]);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const available = useMemo(() => agents.filter(isInvitableMember), [agents]);
	const shown = available.filter((agent) =>
		agent.data.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
	);

	// The parent opens the dialog, so reset and load here rather than in onOpenChange.
	useEffect(() => {
		if (!open) return;
		setName('');
		setQuery('');
		setSelected([]);
		setError(null);
		void refetch();
	}, [open, refetch]);

	const changeOpen = (next: boolean) => {
		if (!busy) onOpenChange(next);
	};

	const toggle = (agentId: string) =>
		setSelected((current) =>
			current.includes(agentId)
				? current.filter((id) => id !== agentId)
				: [...current, agentId],
		);

	const create = async () => {
		setBusy(true);
		setError(null);
		try {
			await workforceApi.bootstrapLeader();
			const group = await workforceApi.createTicket();
			await sessionApi.update(group.session_id, group.agent_id, {
				name: name.trim() || t('groupChat.defaultName'),
			});
			// One at a time: each add holds the Leader session lock.
			const failed: string[] = [];
			for (const agentId of selected) {
				try {
					await sessionApi.addTeamMember(group.session_id, group.agent_id, agentId);
				} catch {
					failed.push(available.find((agent) => agent.id === agentId)?.data.name ?? '');
				}
			}
			if (failed.length === selected.length) {
				await sessionApi.delete(group.session_id, group.agent_id).catch(() => undefined);
				setError(t('groupChat.noMemberAdded'));
				return;
			}
			if (failed.length) {
				setError(t('groupChat.partialFailed', { names: failed.join(', ') }));
			} else {
				onOpenChange(false);
			}
			onCreated(group.agent_id, group.session_id);
		} catch (e) {
			setError((e as Error).message);
		} finally {
			setBusy(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={changeOpen}>
			<DialogContent className="sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>{t('groupChat.title')}</DialogTitle>
					<DialogDescription>{t('groupChat.description')}</DialogDescription>
				</DialogHeader>
				<div className="grid gap-4">
					<label className="grid gap-1.5 text-sm font-medium">
						{t('groupChat.name')}
						<Input
							value={name}
							maxLength={80}
							placeholder={t('groupChat.namePlaceholder')}
							onChange={(event) => setName(event.target.value)}
							disabled={busy}
						/>
					</label>
					<div className="grid gap-2">
						<div className="flex items-center justify-between text-sm font-medium">
							<span>{t('groupChat.members')}</span>
							<span className="text-xs font-normal text-muted-foreground">
								{t('groupChat.selected', { count: selected.length })}
							</span>
						</div>
						{available.length > 4 && (
							<div className="relative">
								<Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
								<Input
									className="pl-8"
									value={query}
									placeholder={t('groupChat.searchPlaceholder')}
									onChange={(event) => setQuery(event.target.value)}
								/>
							</div>
						)}
						{loading ? (
							<p className="py-6 text-center text-sm text-muted-foreground">
								{t('common.loading')}
							</p>
						) : available.length === 0 ? (
							<p className="rounded-xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
								{t('groupChat.noAgents')}
							</p>
						) : (
							<ul className="grid max-h-72 gap-1 overflow-y-auto pr-1">
								{shown.map((agent) => {
									const checked = selected.includes(agent.id);
									return (
										<li key={agent.id}>
											<label
												className={cn(
													'flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-2.5 transition-colors',
													checked
														? 'border-foreground/30 bg-muted/60'
														: 'border-transparent hover:bg-muted/40',
												)}
											>
												<Checkbox
													className="mt-1"
													checked={checked}
													onCheckedChange={() => toggle(agent.id)}
													disabled={busy}
												/>
												<ClayAvatar id={agent.id} label={agent.data.name} size={32} />
												<span className="min-w-0 flex-1">
													<span className="block truncate text-sm font-medium">
														{agent.data.name}
													</span>
													<span className="line-clamp-2 text-xs text-muted-foreground">
														{agent.data.invite_config.invite_description}
													</span>
												</span>
											</label>
										</li>
									);
								})}
							</ul>
						)}
					</div>
					{(error || loadError) && (
						<p role="alert" className="text-sm text-destructive">
							{error || loadError?.message}
						</p>
					)}
				</div>
				<DialogFooter>
					<Button variant="outline" disabled={busy} onClick={() => changeOpen(false)}>
						{t('common.cancel')}
					</Button>
					<Button disabled={busy || loading || selected.length === 0} onClick={create}>
						<Users />
						{busy
							? t('groupChat.creating')
							: selected.length === 0
								? t('groupChat.needOne')
								: t('groupChat.create')}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
