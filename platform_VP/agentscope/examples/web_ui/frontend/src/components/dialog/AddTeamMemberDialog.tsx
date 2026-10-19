import { Plus } from 'lucide-react';
import { useState } from 'react';

import { isInvitableMember } from './team-members';
import { sessionApi } from '@/api';
import { Button } from '@/components/ui/button';
import {
	Dialog, DialogContent, DialogDescription, DialogFooter,
	DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog';
import {
	Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { useAgents } from '@/hooks/useAgents';
import { useTranslation } from '@/i18n/useI18n';


interface Props {
	agentId: string;
	sessionId: string;
	present: string[];
	disabled?: boolean;
	onAdded: () => Promise<void>;
}

export function AddTeamMemberDialog({ agentId, sessionId, present, disabled, onAdded }: Props) {
	const { t } = useTranslation();
	const [open, setOpen] = useState(false);
	const [selected, setSelected] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	// Loaded when the dialog opens, not on every Leader session switch.
	const { agents, loading, error: loadError, refetch } = useAgents({ fetchOnMount: false });
	const available = agents.filter((agent) =>
		agent.id !== agentId && !present.includes(agent.id) && isInvitableMember(agent),
	);
	const selectedAgent = available.find((agent) => agent.id === selected);

	const changeOpen = (next: boolean) => {
		if (busy) return;
		setOpen(next);
		setSelected('');
		setError(null);
		if (next) void refetch();
	};

	const add = async () => {
		if (!selectedAgent) return;
		setBusy(true);
		setError(null);
		try {
			await sessionApi.addTeamMember(sessionId, agentId, selectedAgent.id);
			await onAdded();
			setOpen(false);
			setSelected('');
		} catch (e) {
			setError((e as Error).message);
		} finally {
			setBusy(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={changeOpen}>
			<DialogTrigger asChild>
				<Button variant="ghost" size="icon-sm" disabled={disabled}
					aria-label={t('panel.team.addMember')} title={t('panel.team.addMember')}>
					<Plus className="size-4" />
				</Button>
			</DialogTrigger>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{t('panel.team.addMember')}</DialogTitle>
					<DialogDescription>{t('panel.team.manualDescription')}</DialogDescription>
				</DialogHeader>
				{loading ? <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
					: available.length === 0 ? <p className="text-sm text-muted-foreground">{t('panel.team.noAvailableAgents')}</p>
						: <Select value={selected} onValueChange={setSelected} disabled={busy}>
							<SelectTrigger className="w-full" aria-label={t('panel.team.selectAgent')}>
								<SelectValue placeholder={t('panel.team.selectAgent')} />
							</SelectTrigger>
							<SelectContent>
								{available.map((agent) => <SelectItem key={agent.id} value={agent.id}>{agent.data.name}</SelectItem>)}
							</SelectContent>
							</Select>}
				{selectedAgent && <p className="text-sm text-muted-foreground">{selectedAgent.data.invite_config.invite_description}</p>}
				{(error || loadError) && <p role="alert" className="text-sm text-destructive">{error || loadError?.message}</p>}
				<DialogFooter>
					<Button variant="outline" disabled={busy} onClick={() => changeOpen(false)}>{t('common.cancel')}</Button>
					<Button disabled={busy || loading || !!loadError || !selectedAgent} onClick={add}>
						{busy ? t('common.loading') : t('panel.team.addMember')}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
