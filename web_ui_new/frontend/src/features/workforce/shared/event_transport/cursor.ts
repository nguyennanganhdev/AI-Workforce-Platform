export interface EventCursorStore {
	get(key: string): string | null;
	set(key: string, eventId: string): void;
	clear(key: string): void;
}

export class MemoryEventCursorStore implements EventCursorStore {
	private readonly cursors = new Map<string, string>();

	get(key: string): string | null {
		return this.cursors.get(key) ?? null;
	}

	set(key: string, eventId: string): void {
		if (eventId.length === 0) throw new Error('eventId must not be empty');
		this.cursors.set(key, eventId);
	}

	clear(key: string): void {
		this.cursors.delete(key);
	}
}

export const conversationCursorKey = (conversationId: string): string => {
	if (conversationId.length === 0) throw new Error('conversationId must not be empty');
	return `workforce:conversation:${conversationId}`;
};
