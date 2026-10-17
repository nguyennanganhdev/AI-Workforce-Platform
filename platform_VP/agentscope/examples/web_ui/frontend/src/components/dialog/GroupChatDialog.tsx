import { Check, CircleAlert, Loader2, Plus, Search } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';

import type { AgentView, ChatModelConfig } from '@/api';
import { personalChatApi } from '@/api/personal-chat';
import { GroupAvatar } from '@/components/chat/GroupAvatar';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';
import { cn } from '@/lib/utils';

/** A manual group is persisted immediately. It does not invoke or modify agents. */
export function GroupChatDialog({ open, onOpenChange, agents, modelConfig, onCreateAgent, onCreated }: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agents: AgentView[];
	modelConfig?: { chat?: ChatModelConfig | null; fallback?: ChatModelConfig | null };
	onCreateAgent?: () => void;
	onCreated: (agentId: string, sessionId: string) => void | Promise<void>;
}) {
	const { t } = useTranslation();
	const [name, setName] = useState('');
	const [goal, setGoal] = useState('');
	const [query, setQuery] = useState('');
	const [picked, setPicked] = useState<string[]>([]);
	const [coordinator, setCoordinator] = useState('');
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState('');
	useEffect(() => {
		if (open) return;
		setName(''); setGoal(''); setQuery(''); setPicked([]); setCoordinator(''); setError('');
	}, [open]);
	const visible = agents.filter(a => a.data.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
	const preview = picked.map(id => ({ id, name: agents.find(a => a.id === id)?.data.name ?? id }));
	const ready = name.trim().length > 0 && picked.length >= 2 && picked.length <= 20;
	const submit = async (event: FormEvent) => {
		event.preventDefault();
		if (!ready || submitting) return;
		setSubmitting(true); setError('');
		try {
			const group = await personalChatApi.createGroup({
				name: name.trim(), goal: goal.trim(), agent_ids: picked,
				coordinator_agent_id: picked.includes(coordinator) ? coordinator : picked[0],
				...(modelConfig?.chat ? { chat_model_config: modelConfig.chat } : {}),
				...(modelConfig?.fallback ? { fallback_chat_model_config: modelConfig.fallback } : {}),
			});
			await onCreated(group.agentId, group.sessionId);
			onOpenChange(false);
		} catch (e) { setError(formatApiErrorForAlert(e)); }
		finally { setSubmitting(false); }
	};
	return <Dialog open={open} onOpenChange={next => !submitting && onOpenChange(next)}>
		<DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
			<form onSubmit={submit} className="flex min-w-0 flex-col gap-5">
				<DialogHeader>
					<DialogTitle>{t('personal.groupTitle')}</DialogTitle>
					<DialogDescription>{t('personal.groupDescription')}</DialogDescription>
				</DialogHeader>
				<label className="flex flex-col gap-2 text-sm font-medium">
					{t('groupChat.name')}
					<Input autoFocus required value={name} onChange={e => setName(e.target.value)} maxLength={64} disabled={submitting} placeholder={t('groupChat.namePlaceholder')} />
				</label>
				<div className="flex items-center justify-between gap-3">
					<span className="text-sm font-medium">{t('groupChat.members')} · {picked.length}/20</span>
					{preview.length > 0 && <GroupAvatar members={preview} />}
				</div>
				<div className="overflow-hidden rounded-xl border">
					<label className="flex items-center gap-2 border-b px-3">
						<Search className="size-4 text-muted-foreground" aria-hidden="true" />
						<Input className="border-0 shadow-none" value={query} onChange={e => setQuery(e.target.value)} aria-label={t('groupChat.searchPlaceholder')} placeholder={t('groupChat.searchPlaceholder')} />
					</label>
					<ul className="max-h-56 overflow-y-auto p-1">
						{visible.map(agent => {
							const selected = picked.includes(agent.id);
							return <li key={agent.id}><button type="button" role="checkbox" aria-checked={selected} disabled={submitting || (!selected && picked.length >= 20)}
								onClick={() => setPicked(prev => selected ? prev.filter(id => id !== agent.id) : [...prev, agent.id])}
								className="flex min-h-14 w-full items-center gap-3 rounded-lg px-3 text-left hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50">
								<ClayAvatar id={agent.id} label={agent.data.name} size={36} />
								<span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{agent.data.name}</span>
									<span className="block truncate text-xs text-muted-foreground">{agent.data.invite_config?.invite_description || t('personal.independent')}</span></span>
								<span className={cn('flex size-5 items-center justify-center rounded border', selected && 'border-primary bg-primary text-primary-foreground')}>
									{selected && <Check className="size-4" />}
									</span>
							</button></li>;
						})}
						{visible.length === 0 && <li className="p-4 text-sm text-muted-foreground">{t('chat.session.noResults', { query })}</li>}
					</ul>
				</div>
				{agents.length < 2 && onCreateAgent && <Button type="button" variant="outline" onClick={onCreateAgent}><Plus />{t('quickAgent.title')}</Button>}
				{picked.length > 0 && <label className="flex flex-col gap-2 text-sm font-medium">
					{t('personal.coordinator')}
					<select aria-label={t('personal.coordinator')} className="h-10 rounded-md border bg-background px-3" disabled={submitting} value={picked.includes(coordinator) ? coordinator : picked[0]} onChange={event => setCoordinator(event.target.value)}>
						{preview.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
					</select>
				</label>}
				<label className="flex flex-col gap-2 text-sm font-medium">
					{t('personal.sharedGoal')}
					<Textarea value={goal} onChange={e => setGoal(e.target.value)} disabled={submitting} maxLength={4000} placeholder={t('personal.goalPlaceholder')} />
				</label>
				<p className="text-sm text-muted-foreground">{t('personal.groupPrivacy')}</p>
				{error && <Alert variant="destructive"><CircleAlert /><AlertDescription>{error}</AlertDescription></Alert>}
				<DialogFooter>
					<Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>{t('common.cancel')}</Button>
					<Button type="submit" disabled={!ready || submitting}>{submitting && <Loader2 className="animate-spin" />}{t('groupChat.create')}</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>;
}
