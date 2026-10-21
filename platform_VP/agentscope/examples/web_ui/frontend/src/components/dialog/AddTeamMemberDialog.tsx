import { LoaderCircle, Plus, Search } from 'lucide-react';
import { useState } from 'react';

import { sessionApi } from '@/api';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	Dialog, DialogContent, DialogDescription,
	DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useAgents } from '@/hooks/useAgents';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

interface Props {
	agentId: string;
	sessionId: string;
	present: string[];
	disabled?: boolean;
	onAdded: () => Promise<void>;
}

const searchText = (value: string) => value.toLocaleLowerCase().normalize('NFD')
	.replace(/\p{Diacritic}/gu, '').replace(/đ/g, 'd');

export function AddTeamMemberDialog({ agentId, sessionId, present, disabled, onAdded }: Props) {
	const { t } = useTranslation();
	const [open, setOpen] = useState(false);
	const [added, setAdded] = useState<string[]>([]);
	const [query, setQuery] = useState('');
	const [adding, setAdding] = useState<string | null>(null);
	const busy = adding !== null;
	const [error, setError] = useState<string | null>(null);
	// Loaded when the dialog opens, not on every Leader session switch.
	const { agents, loading, error: loadError, refetch } = useAgents({ fetchOnMount: false });
	const available = agents.filter((agent) =>
		agent.id !== agentId
		&& agent.source === 'user' && agent.data.system_role === 'business'
		&& agent.data.lifecycle_state === 'published'
		&& agent.data.invite_config.invitable
		&& agent.data.invite_config.invite_description?.trim(),
	);
	const visible = available.filter((agent) => searchText(
		`${agent.data.name} ${agent.data.invite_config.invite_description}`,
	).includes(searchText(query.trim())));

	const changeOpen = (next: boolean) => {
		if (busy) return;
		setOpen(next);
		setAdded([]);
		setQuery('');
		setError(null);
		if (next) void refetch();
	};

	const add = async (memberId: string) => {
		if (busy || present.includes(memberId) || added.includes(memberId)) return;
		setAdding(memberId);
		setError(null);
		try {
			await sessionApi.addTeamMember(sessionId, agentId, memberId);
			setAdded((previous) => [...previous, memberId]);
			await onAdded();
		} catch (e) {
			setError((e as Error).message);
		} finally {
			setAdding(null);
		}
	};

	return (
		<Dialog open={open} onOpenChange={changeOpen}>
			<DialogTrigger asChild>
				<Button variant="outline" size="xs" disabled={disabled}
					className="shrink-0 gap-1 rounded-lg border-border bg-background px-2 text-[11px] text-foreground shadow-none hover:bg-muted"
					aria-label={t('panel.team.addMember')}>
					<Plus className="size-3" />{t('panel.team.addAgents')}
				</Button>
			</DialogTrigger>
			<DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-lg" showCloseButton={!busy}>
				<DialogHeader>
					<DialogTitle>{t('panel.team.addMember')}</DialogTitle>
					<DialogDescription>{t('panel.team.chooseAgentsDescription')}</DialogDescription>
				</DialogHeader>
				<div className="relative">
					<Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
					<Input value={query} onChange={(event) => setQuery(event.target.value)} disabled={busy}
						className="h-10 rounded-xl pl-9" placeholder={t('panel.team.searchAgents')}
						aria-label={t('panel.team.searchAgents')} />
				</div>
				<div className="-mx-1 max-h-80 min-h-0 space-y-2 overflow-y-auto p-1" aria-busy={busy || loading}>
					{loading ? <p className="py-8 text-center text-sm text-muted-foreground">{t('common.loading')}</p>
						: visible.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">
							{t(available.length === 0 ? 'panel.team.noAvailableAgents' : 'panel.team.noSearchResults')}
						</p> : visible.map((agent) => (
							<label key={agent.id} className={cn(
								'flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition-colors hover:bg-muted/50',
								(present.includes(agent.id) || added.includes(agent.id)) ? 'border-primary/30 bg-primary/5' : 'border-border/70',
								busy && 'cursor-wait opacity-60',
							)}>
								<ClayAvatar id={agent.id} label={agent.data.name} size={36} />
								<span className="min-w-0 flex-1">
									<span className="block text-sm font-medium">{agent.data.name}</span>
									<span className="mt-0.5 line-clamp-2 block text-xs leading-5 text-muted-foreground">
										{agent.data.invite_config.invite_description}
									</span>
								</span>
								{adding === agent.id ? <LoaderCircle className="size-4 shrink-0 animate-spin text-primary" /> : (
									<Checkbox checked={present.includes(agent.id) || added.includes(agent.id)}
										disabled={busy || present.includes(agent.id) || added.includes(agent.id)} aria-label={agent.data.name}
										onCheckedChange={(value) => { if (value === true) void add(agent.id); }} />
								)}
							</label>
						))}
				</div>
				<p className="text-xs leading-5 text-muted-foreground">{t('panel.team.manualDescription')}</p>
				{(error || loadError) && <p role="alert" className="text-sm text-destructive">{error || loadError?.message}</p>}
			</DialogContent>
		</Dialog>
	);
}
