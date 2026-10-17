import { format, isToday } from 'date-fns';

import type { SessionView } from '@/api';
import { useTranslation } from '@/i18n/useI18n';

/** Today's timestamps show the time; older ones the day. */
export function sessionTime(at: string): string {
	const date = new Date(at);
	return format(date, isToday(date) ? 'HH:mm' : 'dd/MM');
}

/**
 * A session's title, or `null` while it still carries the timestamp it was
 * created with — the first reply replaces that with a real one, and a date
 * reads worse than no title at all.
 */
export function sessionTitle(name: string | null | undefined): string | null {
	if (!name || /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?/.test(name)) return null;
	return name;
}

/**
 * The second line of a session row: what the session is waiting on when it
 * is waiting on something, otherwise which agent it belongs to.
 */
export function useSessionPreview() {
	const { t } = useTranslation();
	return (view: SessionView, agentName: string) => {
		if (view.status === 'running') return t('chat.session.previewRunning');
		if (view.status === 'awaiting_permission') return t('chat.session.previewAwaiting');
		return (
			sessionTitle(view.session.config.name) ||
			t('chat.session.previewAgent', { name: agentName })
		);
	};
}
