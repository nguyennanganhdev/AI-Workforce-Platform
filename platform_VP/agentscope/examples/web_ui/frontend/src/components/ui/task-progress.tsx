import { Clock3 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Spinner } from './spinner';
import { useTranslation } from '@/i18n/useI18n';

/** Elapsed wall time, without inventing model stages or a completion percentage. */
export function TaskProgress({ label, startedAt }: { label: string; startedAt: number }) {
	const { t } = useTranslation();
	const [now, setNow] = useState(() => Date.now());
	useEffect(() => {
		const timer = window.setInterval(() => setNow(Date.now()), 1000);
		return () => window.clearInterval(timer);
	}, []);
	return (
		<div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/50 px-3 py-2 text-sm" role="status">
			<Spinner /> <span>{label}</span>
			<span className="ml-auto inline-flex items-center gap-1 text-xs tabular-nums text-muted-foreground" aria-live="off">
				<Clock3 className="size-3" />{' '}
				{t('common.secondsElapsed', { count: Math.max(0, Math.floor((now - startedAt) / 1000)) })}
			</span>
		</div>
	);
}
