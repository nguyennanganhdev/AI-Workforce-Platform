import { AssistantMsg, UserMsg, type Msg } from '@agentscope-ai/agentscope/message';
import { useEffect, useState } from 'react';

import { client } from '@/api/client';
import { useCurrentUser } from '@/context/CurrentUserContext';

interface GroupEvent {
	id: string; revision: number; task_id: string; kind: string; content: string;
	source_agent_id: string | null; source_session_id: string | null;
	source_message_id: string | null; recipient_session_ids: string[];
	created_at: string; report_type: 'verified' | 'analysis';
}
interface Page { events: GroupEvent[]; has_more: boolean; before_revision: number | null }

/** Durable event ids/revisions make poll/reconnect and older pages idempotent. */
export function useGroupConversation(sessionId: string | null, agentId: string | null, roster: { agent_id: string; session_id: string; name: string }[]) {
	const user = useCurrentUser();
	const [state, setState] = useState<{ key: string; events: GroupEvent[]; hasMore: boolean; error: boolean }>({ key: '', events: [], hasMore: false, error: false });
	const key = `${user?.id}:${sessionId}:${agentId}`;
	const path = `/sessions/personal/groups/${sessionId}/messages`;
	useEffect(() => {
		if (!sessionId || !agentId) return;
		let active = true;
		const load = async () => {
			try {
				const page = await client.get<Page>(path, { agent_id: agentId });
				if (!active) return;
				setState(previous => {
					const map = new Map((previous.key === key ? previous.events : []).map(e => [e.id, e]));
					for (const e of page.events) map.set(e.id, e);
					return { key, events: [...map.values()].sort((a, b) => a.revision - b.revision), hasMore: previous.key === key && previous.events.length ? previous.hasMore : page.has_more, error: false };
				});
			} catch { if (active) setState(previous => ({ key, events: previous.key === key ? previous.events : [], hasMore: previous.key === key && previous.hasMore, error: true })); }
		};
		void load();
		const timer = window.setInterval(() => void load(), 2000);
		return () => { active = false; window.clearInterval(timer); };
	}, [sessionId, agentId, key, path]);
	const current = state.key === key ? state : { events: [], hasMore: false, error: false };
	const messages = current.events.filter(e => e.kind !== 'external_event').map(e => {
		const member = roster.find(m => m.agent_id === e.source_agent_id);
		const recipients = e.recipient_session_ids.map(id => roster.find(m => m.session_id === id)?.name).filter(Boolean).join(', ');
		const name = e.kind === 'customer_message' ? 'Bạn' : member?.name ?? 'Context';
		const msg = (e.kind === 'customer_message' ? UserMsg : AssistantMsg)({ name, content: e.content });
		return { ...msg, id: e.source_message_id ?? `group:${e.id}`, created_at: e.created_at, finished_at: e.created_at, metadata: { ...msg.metadata, group_event: true, group_kind: e.kind, group_to: recipients, group_to_ids: roster.filter(m => e.recipient_session_ids.includes(m.session_id)).map(m => m.agent_id), group_analysis: e.report_type === 'analysis', office_agent_id: e.source_agent_id, group_revision: e.revision } } as Msg;
	});
	const loadOlder = async () => {
		if (!agentId || !current.events.length) return;
		const page = await client.get<Page>(path, { agent_id: agentId, before_revision: String(current.events[0].revision) });
		setState(previous => {
			if (previous.key !== key) return previous;
			const map = new Map([...page.events, ...previous.events].map(e => [e.id, e]));
			return { ...previous, events: [...map.values()].sort((a, b) => a.revision - b.revision), hasMore: page.has_more };
		});
	};
	return { messages, hasMore: current.hasMore, error: current.error, loadOlder };
}
