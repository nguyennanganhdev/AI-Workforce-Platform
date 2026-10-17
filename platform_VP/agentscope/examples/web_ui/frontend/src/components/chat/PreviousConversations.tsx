import { useInfiniteQuery } from '@tanstack/react-query';
import { History } from 'lucide-react';
import { useState } from 'react';

import { sessionApi, type SessionRecord } from '@/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { useTranslation } from '@/i18n/useI18n';

/** Preserve access to old transcripts without re-entering the Leader workflow. */
export function PreviousConversations({ sessions, agentId }: { sessions: SessionRecord[]; agentId: string }) {
	const { t } = useTranslation();
	const user = useCurrentUser();
	const [open, setOpen] = useState(false);
	const [selected, setSelected] = useState(sessions[0]?.id ?? '');
	const { data, isPending, isError, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } = useInfiniteQuery({
		queryKey: ['previous-conversations', user?.id, agentId, selected],
		queryFn: ({ pageParam }) => sessionApi.messages(selected, agentId, { limit: 100, ...(pageParam ? { before: pageParam } : {}) }),
		initialPageParam: undefined as string | undefined,
		getNextPageParam: page => page.has_more ? page.messages[0]?.id : undefined,
		enabled: open && !!selected,
	});
	return <Dialog open={open} onOpenChange={setOpen}>
		<DialogTrigger asChild><Button variant="ghost" className="w-full justify-start text-muted-foreground"><History />{t('personal.previous')}</Button></DialogTrigger>
		<DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-3xl">
			<DialogHeader><DialogTitle>{t('personal.previous')}</DialogTitle><DialogDescription>{t('personal.previousDescription')}</DialogDescription></DialogHeader>
			<label className="flex flex-col gap-2 text-sm">{t('personal.chooseConversation')}<select className="h-11 rounded-md border bg-background px-3" value={selected} onChange={event => setSelected(event.target.value)}>{sessions.map(session => <option key={session.id} value={session.id}>{session.config.name}</option>)}</select></label>
			<div className="min-h-0 space-y-4 overflow-y-auto rounded-lg border p-4">
				{isPending && <p role="status">{t('common.loading')}</p>}
				{isError && <Button variant="outline" onClick={() => void refetch()}>{t('personal.retryContext')}</Button>}
				{hasNextPage && <Button variant="outline" disabled={isFetchingNextPage} onClick={() => void fetchNextPage()}>{t('personal.older')}</Button>}
				{[...(data?.pages ?? [])].reverse().flatMap(page => page.messages).map(message => <article key={message.id} className="space-y-1"><p className="text-xs font-medium text-muted-foreground">{message.role === 'user' ? t('personal.you') : message.name}</p><p className="whitespace-pre-wrap break-words text-sm">{message.content.filter(block => block.type === 'text').map(block => block.text).join('\n')}</p></article>)}
			</div>
		</DialogContent>
	</Dialog>;
}
