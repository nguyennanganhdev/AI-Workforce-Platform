/**
 * Group chats the user started from the "+" menu.
 *
 * The backend has no "group chat" object: a team only exists once a
 * session's agent calls `TeamCreate` and pulls members in with
 * `AgentInvite`. So a group chat is a session on the leader agent, plus
 * this note of who was meant to be in it — kept in the browser so the
 * sidebar can show the group as one row (name, stacked avatars) before
 * the leader has formed the team, and after.
 *
 * `kickoff` is the instruction the leader is sent when the chat first
 * opens; it is cleared once sent, so it goes out exactly once.
 */
export interface GroupChat {
	sessionId: string;
	/** The leader: the agent the session belongs to. */
	agentId: string;
	name: string;
	/** Everyone else, in the order they were picked. */
	memberIds: string[];
	createdAt: string;
	kickoff?: string;
}

const KEY = 'chat_group_chats';

function read(): GroupChat[] {
	try {
		const raw = localStorage.getItem(KEY);
		return raw ? (JSON.parse(raw) as GroupChat[]) : [];
	} catch {
		return [];
	}
}

function write(groups: GroupChat[]) {
	try {
		localStorage.setItem(KEY, JSON.stringify(groups));
	} catch {
		// Storage off (private window): the group still works as a session.
	}
	window.dispatchEvent(new Event(KEY));
}

export function listGroupChats(): GroupChat[] {
	return read();
}

export function addGroupChat(group: GroupChat) {
	write([group, ...read().filter((g) => g.sessionId !== group.sessionId)]);
}

export function removeGroupChat(sessionId: string) {
	write(read().filter((g) => g.sessionId !== sessionId));
}

/** The leader's first instruction for `sessionId`, if not yet sent. Consumes it. */
export function takeGroupKickoff(sessionId: string): string | null {
	const groups = read();
	const group = groups.find((g) => g.sessionId === sessionId);
	if (!group?.kickoff) return null;
	const { kickoff } = group;
	write(groups.map((g) => (g.sessionId === sessionId ? { ...g, kickoff: undefined } : g)));
	return kickoff;
}

/** Subscribe to changes, from this tab or another. Returns the unsubscribe. */
export function onGroupChatsChange(listener: () => void): () => void {
	const onStorage = (event: StorageEvent) => event.key === KEY && listener();
	window.addEventListener(KEY, listener);
	window.addEventListener('storage', onStorage);
	return () => {
		window.removeEventListener(KEY, listener);
		window.removeEventListener('storage', onStorage);
	};
}

/**
 * How `AgentInvite` and `TeamSay` name an agent: its name, then the first
 * eight characters of its id (`Mia@9f3c1a20`). Matches the backend's
 * `_display_name`, so the leader can pass it straight through.
 */
export function agentHandle(name: string, id: string): string {
	return `${name}@${id.slice(0, 8)}`;
}
