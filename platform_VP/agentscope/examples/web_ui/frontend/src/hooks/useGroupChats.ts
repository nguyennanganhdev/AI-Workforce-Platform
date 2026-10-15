import { useEffect, useState } from 'react';

import { type GroupChat, listGroupChats, onGroupChatsChange } from '@/lib/group-chats';

/** The group chats this browser knows about, kept current as they change. */
export function useGroupChats(): GroupChat[] {
	const [groups, setGroups] = useState(listGroupChats);
	useEffect(() => onGroupChatsChange(() => setGroups(listGroupChats())), []);
	return groups;
}
