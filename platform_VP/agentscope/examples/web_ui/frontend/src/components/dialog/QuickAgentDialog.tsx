import { CircleAlert, Loader2 } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';

import type { ContextConfig, InviteConfig, ReActConfig } from '@/api';
import { defaultAgentFormValues } from '@/components/form/AgentFormFields';
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
import { useAgents } from '@/hooks/useAgents';
import { useAgentSchema } from '@/hooks/useAgentSchema';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';
import { cn } from '@/lib/utils';

/** Starting points that fill both fields in one tap. Text lives in i18n. */
const PRESETS = ['assistant', 'reception', 'technician', 'planner'] as const;

/**
 * The fast way to make an agent: a name and, optionally, what it is for.
 * Everything the full form exposes (context, ReAct, invites) takes the
 * schema's defaults, so creating one is two fields and a button. The
 * avatar follows the name as it is typed.
 *
 * "Advanced settings" hands off to the full form for anyone who wants it.
 */
export function QuickAgentDialog({
	open,
	onOpenChange,
	onCreated,
	onAdvanced,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Called with the new agent's id once it exists. */
	onCreated: (agentId: string) => void | Promise<void>;
	/** Opens the full agent form instead. */
	onAdvanced?: () => void;
}) {
	const { t } = useTranslation();
	const { create } = useAgents();
	const { schema } = useAgentSchema();
	const [name, setName] = useState('');
	const [prompt, setPrompt] = useState('');
	const [preset, setPreset] = useState<(typeof PRESETS)[number] | null>(null);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState('');

	useEffect(() => {
		if (open) return;
		setName('');
		setPrompt('');
		setPreset(null);
		setError('');
	}, [open]);

	const applyPreset = (key: (typeof PRESETS)[number]) => {
		setPreset(key);
		setName(t(`quickAgent.presets.${key}.name`));
		setPrompt(t(`quickAgent.presets.${key}.prompt`));
	};

	const trimmed = name.trim();

	const handleSubmit = async (event: FormEvent) => {
		event.preventDefault();
		if (!trimmed || !schema || submitting) return;
		setSubmitting(true);
		setError('');
		try {
			const defaults = defaultAgentFormValues(schema);
			const res = await create(
				{
					name: trimmed,
					system_prompt:
						prompt.trim() ||
						(defaults.identity.system_prompt as string | undefined) ||
						undefined,
					context_config: defaults.context_config as unknown as ContextConfig,
					react_config: defaults.react_config as unknown as ReActConfig,
					invite_config: defaults.invite_config as unknown as InviteConfig,
				},
				{ silent: true },
			);
			await onCreated(res.agent_id);
			onOpenChange(false);
		} catch (e) {
			setError(formatApiErrorForAlert(e));
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="!w-[576px] !max-w-[calc(100%-2rem)]">
				<form onSubmit={handleSubmit} className="flex flex-col gap-5">
					<DialogHeader className="flex-row items-center gap-3 pr-10">
						<ClayAvatar
							id={trimmed || 'new-agent'}
							label={trimmed || undefined}
							size={52}
						/>
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
									onClick={() => applyPreset(key)}
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
							{t('quickAgent.name')}
						</span>
						<Input
							autoFocus
							value={name}
							onChange={(e) => {
								setName(e.target.value);
								setPreset(null);
							}}
							placeholder={t('quickAgent.namePlaceholder')}
							className="h-10 text-[15px] md:text-[15px]"
							maxLength={64}
						/>
					</label>

					<label className="flex flex-col gap-2">
						<span className="text-[13px]/[18px] text-muted-foreground">
							{t('quickAgent.role')}
						</span>
						<Textarea
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							placeholder={t('quickAgent.rolePlaceholder')}
							className="min-h-32 rounded-xl px-3 py-2.5 text-[15px]/[22px] md:text-[15px]"
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
						{onAdvanced ? (
							<Button
								type="button"
								variant="link"
								className="px-0 text-muted-foreground"
								onClick={() => {
									onOpenChange(false);
									onAdvanced();
								}}
							>
								{t('quickAgent.advanced')}
							</Button>
						) : (
							<span />
						)}
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
								disabled={!trimmed || !schema || submitting}
							>
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
