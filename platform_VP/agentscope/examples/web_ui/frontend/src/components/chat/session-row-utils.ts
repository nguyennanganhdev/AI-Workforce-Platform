import { format, isToday } from 'date-fns';

import type { SessionView } from '@/api';
import { useTranslation } from '@/i18n/useI18n';

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

/** Keep stored titles; use existing conversation/team data for unnamed sessions. */
export function sessionDisplayTitle(view: SessionView, fallback: string): string {
	return sessionTitle(view.session.config.name)
		|| view.preview?.trim()
		|| sessionTitle(view.team?.team.data.name)
		|| `${fallback} · ${format(new Date(view.session.created_at), 'dd/MM HH:mm')}`;
}

/** Status takes priority; otherwise show team context instead of repeating the title. */
export function useSessionPreview() {
	const { t } = useTranslation();
	return (view: SessionView, agentName: string) => {
		if (view.status === 'running') return t('chat.session.previewRunning');
		if (view.status === 'awaiting_permission') return t('chat.session.previewAwaiting');
		if (view.status === 'awaiting_external_result') return t('chat.session.previewExternal');
		if (view.team) {
			const name = sessionTitle(view.team.team.data.name);
			const members = view.team.members.map((member) => member.agent.data.name).join(', ');
			return [name || t('chat.session.previewTeam'), members].filter(Boolean).join(' · ');
		}
		if (view.session.origin.type === 'channel' && view.session.origin.chat_name) {
			return view.session.origin.chat_name;
		}
		return t('chat.session.previewAgent', { name: agentName });
	};
}
