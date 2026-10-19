import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Brain, Loader2, LockKeyhole } from 'lucide-react';
import { useState } from 'react';

import { personalChatApi } from '@/api/personal-chat';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';

/** Shows stored sources and measured context cost, never fabricated progress. */
export function PersonalContextPanel({ agentId, sessionId, agentName, busy }: {
	agentId: string; sessionId: string; agentName?: string; busy: boolean;
}) {
	const { t } = useTranslation();
	const user = useCurrentUser();
	const cache = useQueryClient();
	const [open, setOpen] = useState(false);
	const [note, setNote] = useState('');
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState('');
	const { data, isPending, isError, refetch } = useQuery({
		queryKey: ['personal-context', user?.id, agentId, sessionId],
		queryFn: () => personalChatApi.context(sessionId, agentId),
		enabled: open,
		refetchInterval: open ? 5000 : false,
	});
	const save = async (body: { note?: string; context_mode?: 'shared' | 'isolated' }) => {
		setSaving(true); setError('');
		try {
			await personalChatApi.updateContext(sessionId, agentId, body);
			if (body.note) setNote('');
			await Promise.all([refetch(), cache.invalidateQueries({ queryKey: ['sessions'] })]);
		} catch (e) { setError(formatApiErrorForAlert(e)); }
		finally { setSaving(false); }
	};
	return <Sheet open={open} onOpenChange={setOpen}>
		<SheetTrigger asChild><Button variant="ghost" size="sm" aria-label={t('personal.context')} title={t('personal.context')}><Brain className="size-4" /><span className="hidden sm:inline">{t('personal.context')}</span></Button></SheetTrigger>
		<SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-lg">
			<SheetHeader className="border-b">
				<SheetTitle>{t('personal.context')}</SheetTitle>
				<SheetDescription>{agentName} · {t('personal.independent')}</SheetDescription>
			</SheetHeader>
			<div className="space-y-6 p-5">
				{isPending && <p role="status" className="flex gap-2 text-sm"><Loader2 className="size-4 animate-spin" />{t('common.loading')}</p>}
				{isError && <Button variant="outline" onClick={() => void refetch()}>{t('personal.retryContext')}</Button>}
				{data && <>
					<section className="space-y-2">
						<h3 className="flex items-center gap-2 text-sm font-semibold"><LockKeyhole className="size-4" />{t('personal.privateContext')}</h3>
						<p className="text-sm text-muted-foreground">{t('personal.privateDescription')}</p>
						<details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm">{t('personal.privateSummary')}</summary><p className="mt-3 whitespace-pre-wrap break-words text-sm text-muted-foreground">{data.private_summary || t('personal.noSummary')}</p></details>
					</section>
					{data.kind === 'group' && <>
						<section className="space-y-3 border-t pt-5">
							<h3 className="text-sm font-semibold">{t('personal.sharedContext')}</h3>
							{data.goal && <p className="whitespace-pre-wrap break-words text-sm">{data.goal}</p>}
							{!data.collaborative && <label className="flex items-center justify-between gap-4 text-sm"><span>{t('personal.shareTurns')}</span><Switch checked={data.context_mode === 'shared'} disabled={saving || busy} onCheckedChange={checked => void save({ context_mode: checked ? 'shared' : 'isolated' })} /></label>}
							<p className="text-xs leading-relaxed text-muted-foreground">{t(data.collaborative ? 'personal.teamSharing' : 'personal.shareImpact')}</p>
							<dl className="grid grid-cols-2 gap-3 text-sm"><div><dt className="text-muted-foreground">{t('personal.revision')}</dt><dd className="mt-1 font-medium tabular-nums">{data.revision}</dd></div><div><dt className="text-muted-foreground">{t('personal.packetTokens')}</dt><dd className="mt-1 font-medium tabular-nums">{data.metrics.last_packet_tokens || t('personal.notMeasured')}</dd></div></dl>
							{Number(data.metrics.compactions) > 0 && <p className="text-xs text-muted-foreground">{t('personal.compactionImpact')}: {data.metrics.last_summary_input_tokens} → {data.metrics.last_summary_output_tokens} tokens · {t('personal.compactionCount', { count: Number(data.metrics.compactions) })}</p>}
							<details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm">{t('personal.sharedSummary')}</summary><p className="mt-3 whitespace-pre-wrap break-words text-sm text-muted-foreground">{data.summary?.text || t('personal.noSummary')}</p>{data.summary && <p className="mt-2 text-xs text-muted-foreground">{t('personal.summarySources', { count: data.summary.source_event_ids.length })}</p>}</details>
						</section>
						<form className="space-y-3" onSubmit={event => { event.preventDefault(); if (note.trim()) void save({ note: note.trim() }); }}>
							<label className="block space-y-2 text-sm font-medium"><span>{t('personal.shareNote')}</span><Textarea value={note} onChange={event => setNote(event.target.value)} maxLength={4000} disabled={saving || busy} placeholder={t('personal.notePlaceholder')} /></label>
							<Button type="submit" disabled={saving || busy || !note.trim()}>{saving && <Loader2 className="animate-spin" />}{t('personal.saveNote')}</Button>
						</form>
						<section className="space-y-3 border-t pt-5"><h3 className="text-sm font-semibold">{t('personal.sharedHistory')}</h3><p className="text-xs text-muted-foreground">{t('personal.historyLimit')}</p>
							{data.events.length === 0 && <p className="text-sm text-muted-foreground">{t('personal.noSharedHistory')}</p>}
							{[...data.events].reverse().map(event => <article key={event.id} className="border-l-2 pl-3"><time className="text-xs text-muted-foreground">{new Date(event.created_at).toLocaleString()}</time><p className="mt-1 whitespace-pre-wrap break-words text-sm">{event.content}</p></article>)}
						</section>
					</>}
				</>}
				{error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
			</div>
		</SheetContent>
	</Sheet>;
}
