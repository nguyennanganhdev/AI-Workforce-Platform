import { Brain, Check, Pin, PinOff, Plus, RotateCcw, Trash2, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { agentMemoryApi, type AgentMemory } from '@/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

interface Props {
	agentId: string;
	agentName: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

/** Review what an agent may remember: approve proposals, keep facts fresh. */
export function AgentMemoryDialog({ agentId, agentName, open, onOpenChange }: Props) {
	const { t } = useTranslation();
	const [memories, setMemories] = useState<AgentMemory[]>([]);
	const [drafts, setDrafts] = useState<Record<string, string>>({});
	const [adding, setAdding] = useState('');
	const [error, setError] = useState('');

	const load = useCallback(async () => {
		setMemories(await agentMemoryApi.list(agentId));
	}, [agentId]);

	useEffect(() => {
		if (open) load().catch(() => setError(t('agentMemory.loadFailed')));
	}, [open, load, t]);

	const act = async (action: () => Promise<unknown>) => {
		setError('');
		try {
			await action();
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : t('agentMemory.actionFailed'));
		}
	};

	const proposals = memories.filter((item) => item.status === 'proposed');
	const approved = memories.filter((item) => item.status === 'approved');

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2"><Brain className="size-4" />{t('agentMemory.title', { name: agentName })}</DialogTitle>
					<DialogDescription>{t('agentMemory.description')}</DialogDescription>
				</DialogHeader>
				{error && <p className="text-sm text-destructive">{error}</p>}

				<section className="flex flex-col gap-2">
					<h3 className="text-sm font-medium">{t('agentMemory.proposals', { count: proposals.length })}</h3>
					{proposals.length === 0 ? (
						<p className="text-xs text-muted-foreground">{t('agentMemory.noProposals')}</p>
					) : (
						<ul className="flex flex-col gap-2">
							{proposals.map((item) => (
								<li key={item.id} className="rounded-xl border px-3 py-2 text-xs">
									<Textarea
										rows={2}
										value={drafts[item.id] ?? item.content}
										onChange={(event) => setDrafts((current) => ({ ...current, [item.id]: event.target.value }))}
										aria-label={t('agentMemory.edit')}
									/>
									{item.reason && <p className="mt-1 text-muted-foreground">{t('agentMemory.reason', { reason: item.reason })}</p>}
									<div className="mt-2 flex justify-end gap-2">
										<Button variant="outline" size="xs" onClick={() => void act(() => agentMemoryApi.reject(agentId, item.id))}>
											<X /> {t('agentMemory.reject')}
										</Button>
										<Button
											size="xs"
											onClick={() => void act(() => agentMemoryApi.approve(
												agentId, item.id, drafts[item.id] !== item.content ? drafts[item.id] : undefined,
											))}
										>
											<Check /> {t('agentMemory.approve')}
										</Button>
									</div>
								</li>
							))}
						</ul>
					)}
				</section>

				<section className="flex flex-col gap-2">
					<h3 className="text-sm font-medium">{t('agentMemory.approved', { count: approved.length })}</h3>
					<div className="flex gap-2">
						<Textarea rows={1} value={adding} onChange={(event) => setAdding(event.target.value)} placeholder={t('agentMemory.addPlaceholder')} />
						<Button
							variant="outline"
							size="sm"
							disabled={!adding.trim()}
							onClick={() => void act(async () => {
								await agentMemoryApi.add(agentId, adding.trim());
								setAdding('');
							})}
						>
							<Plus /> {t('agentMemory.add')}
						</Button>
					</div>
					{approved.length === 0 ? (
						<p className="text-xs text-muted-foreground">{t('agentMemory.noApproved')}</p>
					) : (
						<ul className="divide-y rounded-xl border">
							{approved.map((item) => (
								<li key={item.id} className={cn('flex items-start gap-2 px-3 py-2 text-xs', !item.active && 'opacity-60')}>
									<div className="min-w-0 flex-1">
										<p className="break-words">{item.content}</p>
										<div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
											<span className="h-1 w-16 overflow-hidden rounded-full bg-muted" aria-hidden>
												<span className="block h-full bg-primary" style={{ width: `${Math.round(item.priority * 100)}%` }} />
											</span>
											<span>{item.pinned ? t('agentMemory.pinned') : item.active ? t('agentMemory.active') : t('agentMemory.fading')}</span>
										</div>
									</div>
									<Button
										variant="ghost"
										size="icon-sm"
										aria-label={t('agentMemory.confirm')}
										title={t('agentMemory.confirm')}
										onClick={() => void act(() => agentMemoryApi.update(agentId, item.id, { confirm: true }))}
									>
										<RotateCcw />
									</Button>
									<Button
										variant="ghost"
										size="icon-sm"
										aria-label={item.pinned ? t('agentMemory.unpin') : t('agentMemory.pin')}
										title={item.pinned ? t('agentMemory.unpin') : t('agentMemory.pin')}
										onClick={() => void act(() => agentMemoryApi.update(agentId, item.id, { pinned: !item.pinned }))}
									>
										{item.pinned ? <PinOff /> : <Pin />}
									</Button>
									<Button
										variant="ghost"
										size="icon-sm"
										aria-label={t('agentMemory.delete')}
										onClick={() => void act(() => agentMemoryApi.remove(agentId, item.id))}
									>
										<Trash2 />
									</Button>
								</li>
							))}
						</ul>
					)}
				</section>
			</DialogContent>
		</Dialog>
	);
}
