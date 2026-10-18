import { Sparkles } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
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
import { cn } from '@/lib/utils';

/** Starting points that fill the description in one tap. Text lives in i18n. */
const PRESETS = ['reception', 'technician', 'cleaning', 'report'] as const;

/**
 * The fast way to make an agent: say what it is for and hand it to the Agent
 * Builder, which drafts the prompt, tools and knowledge — or a small team when
 * the work splits — for review and publication there.
 */
export function QuickAgentDialog({
	open,
	onOpenChange,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const { t } = useTranslation();
	const navigate = useNavigate();
	const [description, setDescription] = useState('');
	const [preset, setPreset] = useState<(typeof PRESETS)[number] | null>(null);

	useEffect(() => {
		if (open) return;
		setDescription('');
		setPreset(null);
	}, [open]);

	const trimmed = description.trim();

	const handleSubmit = (event: FormEvent) => {
		event.preventDefault();
		if (!trimmed) return;
		onOpenChange(false);
		navigate('/workforce/builder', { state: { draft: trimmed } });
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
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
							onChange={(e) => {
								setDescription(e.target.value);
								setPreset(null);
							}}
							placeholder={t('quickAgent.rolePlaceholder')}
							className="min-h-32 rounded-xl px-3 py-2.5 text-[15px]/[22px] md:text-[15px]"
						/>
					</label>


					<DialogFooter className="items-center sm:justify-between">
						<Button
							type="button"
							variant="link"
							className="px-0 text-muted-foreground"
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
							>
								{t('common.cancel')}
							</Button>
							<Button type="submit" size="lg" className="min-w-20" disabled={!trimmed}>
								{t('quickAgent.create')}
							</Button>
						</div>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
