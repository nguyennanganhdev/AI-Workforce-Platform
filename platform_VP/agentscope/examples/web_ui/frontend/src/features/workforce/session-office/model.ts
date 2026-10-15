/** Presentation contract. Adapters translate mock playback or backend events into this snapshot. */
export interface SessionOfficeSnapshot {
	id: string;
	source: 'mock' | 'preview' | 'live';
	statusLabel?: string;
	/** Demo preserves the original office choreography; events applies backend-derived positions/status later. */
	motion: 'events';
	participants: {
		id: string;
		name: string;
		role: string;
		status: 'idle' | 'working' | 'off';
		message?: string;
	}[];
	phase: 'idle' | 'work' | 'approval' | 'done';
	/** The room is at work: its agents sit round the meeting table, the host at its head. */
	meeting: boolean;
	/** Who leads the room (the session's owner). */
	hostId: string | null;
	activity: { id: string; text: string }[];
}
