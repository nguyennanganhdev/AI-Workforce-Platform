import { format, isToday } from 'date-fns';

import type { SessionView } from '@/api';

/** Today's timestamps show the time; older ones the day. */
export function sessionTime(at: string): string {
	const date = new Date(at);
	return format(date, isToday(date) ? 'HH:mm' : 'dd/MM');
}

/**
 * Hide placeholder names until the first reply gives the session a title.
 */
export function sessionTitle(name: string | null | undefined): string | null {
	if (!name?.trim() || /^(Mới|Phiên mới|Nhóm mới|New session|New group|Phiếu đối tác|Ticket mới|Partner ticket)$/i.test(name.trim())
		|| /^team:[a-f0-9-]+$/i.test(name.trim())
		|| /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?/.test(name)) return null;
	return name.trim();
}

/** Match group labels to the team panel; keep conversation titles for other sessions. */
export function sessionDisplayTitle(view: SessionView, fallback: string): string {
	return sessionTitle(view.team?.team.data.name)
		|| sessionTitle(view.session.config.name)
		|| view.preview?.trim()
		|| `${fallback} · ${format(new Date(view.session.created_at), 'dd/MM HH:mm')}`;
}
