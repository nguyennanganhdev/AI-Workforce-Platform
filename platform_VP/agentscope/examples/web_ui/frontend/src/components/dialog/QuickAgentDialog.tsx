import { CircleAlert, Loader2, Sparkles } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { studioApi } from '@/api';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';
import { cn } from '@/lib/utils';

/** Starting points that fill the description in one tap. Text lives in i18n. */
const PRESETS = ['reception', 'technician', 'cleaning', 'report'] as const;

/**
 * The fast way to make an agent: say what it is for and let the Agent
 * Builder draft it — prompt, tools, knowledge and test cases, or a small team
 * when the work splits. The draft opens in agent management, where it is
 * configured, tested and published like any other agent.
 */
export function QuickAgentDialog({
	open,
	onOpenChange,
	onCreated,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Called with the first drafted agent's id once the Builder is done. */
	onCreated?: (agentId: string) => void | Promise<void>;
}) {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const [description, setDescription] = useState('');
	const [preset, setPreset] = useState<(typeof PRESETS)[number] | null>(null);
	const [allowTeam, setAllowTeam] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState('');

	useEffect(() => {
		if (open) return;
		setDescription('');
		setPreset(null);
		setAllowTeam(false);
		setError('');
	}, [open]);

	const trimmed = description.trim();

	const handleSubmit = async (event: FormEvent) => {
		event.preventDefault();
		if (!trimmed || submitting) return;
		setSubmitting(true);
		setError('');
		try {
			const result = await studioApi.compose(trimmed, undefined, { allowTeam });
			const first = result.agents[0]?.agent_id;
			if (!first) throw new Error(t('quickAgent.nothing'));
			await onCreated?.(first);
			onOpenChange(false);
			navigate(`/workforce/agents/${first}`);
		} catch (e) {
			setError(formatApiErrorForAlert(e));
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={(next) => !submitting && onOpenChange(next)}>
			<DialogContent className="!w-[576px] !max-w-[calc(100%-2rem)]">
				<form onSubmit={handleSubmit} className="flex flex-col gap-5">
					<DialogHeader className="flex-row items-center gap-3 pr-10">
						<span className="flex size-[52px] shrink-0 items-center justify-center rounded-2xl bg-foreground text-background">
							<Sparkles className="size-6" />
						</span>
						<div className="flex min-w-0 flex-col gap-1">
							<DialogTitle>{t('quickAgent.title')}</DialogTitle>
							<DialogDescription className="text-[13px]/[18px]">
								{t('quickAgent.description')}
							</DialogDescription>
						</div>
					</DialogHeader>

					<div className="flex flex-col gap-2">
						<span className="text-[13px]/[18px] text-muted-foreground">
							{t('quickAgent.templates')}
						</span>
						<div className="flex flex-wrap gap-2">
							{PRESETS.map((key) => (
								<button
									key={key}
									type="button"
									disabled={submitting}
									onClick={() => {
										setPreset(key);
										setDescription(t(`quickAgent.presets.${key}.prompt`));
									}}
									aria-pressed={preset === key}
									className={cn(
										'h-8 rounded-full border border-[var(--cue-border,var(--border))] px-3 text-[13px] transition-colors hover:bg-[var(--cue-bg-hover,var(--accent))]',
										preset === key &&
											'border-foreground bg-foreground text-background hover:bg-foreground',
									)}
								>
									{t(`quickAgent.presets.${key}.name`)}
								</button>
							))}
						</div>
					</div>

					<label className="flex flex-col gap-2">
						<span className="text-[13px]/[18px] text-muted-foreground">
							{t('quickAgent.role')}
						</span>
						<Textarea
							autoFocus
							value={description}
							disabled={submitting}
							onChange={(e) => {
								setDescription(e.target.value);
								setPreset(null);
							}}
							placeholder={t('quickAgent.rolePlaceholder')}
							className="min-h-32 rounded-xl px-3 py-2.5 text-[15px]/[22px] md:text-[15px]"
						/>
					</label>

					<label className="flex items-start gap-2 text-[13px]/[18px]">
						<Checkbox
							checked={allowTeam}
							disabled={submitting}
							onCheckedChange={(value) => setAllowTeam(value === true)}
							className="mt-0.5"
						/>
						<span>
							{t('quickAgent.team')}
							<span className="block text-muted-foreground">{t('quickAgent.teamHint')}</span>
						</span>
					</label>

					{submitting && (
						<p className="text-[13px]/[18px] text-muted-foreground">{t('quickAgent.waiting')}</p>
					)}
					{error && (
						<Alert variant="destructive">
							<CircleAlert />
							<AlertDescription className="whitespace-pre-wrap">{error}</AlertDescription>
						</Alert>
					)}

					<DialogFooter className="items-center sm:justify-between">
						<Button
							type="button"
							variant="link"
							className="px-0 text-muted-foreground"
							disabled={submitting}
							onClick={() => {
								onOpenChange(false);
								navigate('/workforce/builder');
							}}
						>
							{t('quickAgent.advanced')}
						</Button>
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
							<Button type="submit" size="lg" className="min-w-20" disabled={!trimmed || submitting}>
								{submitting && <Loader2 className="animate-spin" />}
								{submitting ? t('quickAgent.creating') : t('quickAgent.create')}
							</Button>
						</div>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
