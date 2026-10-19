import { ExternalLink, Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useTranslation } from '@/i18n/useI18n';

/** Setup guidance only. Availability is supplied by the existing channel schema API. */
export function TelegramSetup({
	available,
	onConnect,
}: {
	available: boolean;
	onConnect: () => void;
}) {
	const { t } = useTranslation();
	return (
		<section className="telegram-setup mt-5" aria-labelledby="telegram-setup-title">
			<div className="flex flex-wrap items-center justify-between gap-3">
				<div className="flex items-center gap-3">
					<span
						className="grid size-10 place-items-center rounded-xl bg-[#e8f1fd] text-[#225eb8]"
						aria-hidden="true"
					>
						<Send className="size-5" />
					</span>
					<div>
						<h2 id="telegram-setup-title" className="text-sm font-semibold">
							Telegram
						</h2>
						<p className="mt-1 text-xs text-muted-foreground">
							{t(
								available
									? 'channel.telegramSetup.available'
									: 'channel.telegramSetup.unavailable',
							)}
						</p>
					</div>
				</div>
				<Button
					variant="outline"
					onClick={onConnect}
					disabled={!available}
					aria-describedby="telegram-availability"
				>
					{t('channel.telegramSetup.connect')}
				</Button>
			</div>
			<p id="telegram-availability" className="mt-3 text-xs leading-5 text-muted-foreground">
				{t(
					available
						? 'channel.telegramSetup.supportedHint'
						: 'channel.telegramSetup.unsupportedHint',
				)}
			</p>
			<details className="mt-3">
				<summary>{t('channel.telegramSetup.guide')}</summary>
				<ol>
					<li>
						<a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">
							BotFather <ExternalLink className="inline size-3" aria-hidden="true" />
						</a>{' '}
						— {t('channel.telegramSetup.stepBot')}
					</li>
					<li>{t('channel.telegramSetup.stepToken')}</li>
					<li>{t('channel.telegramSetup.stepRouting')}</li>
				</ol>
			</details>
		</section>
	);
}
