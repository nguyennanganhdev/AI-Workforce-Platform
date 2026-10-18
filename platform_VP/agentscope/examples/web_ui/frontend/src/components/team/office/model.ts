export interface OfficeAgent {
	id: string;
	name: string;
	role: string;
	invitable: boolean;
}

/** Presentation contract translated from the active team session. */
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
	/**
	 * The current request, so the office can tell a new one from more of the same.
	 * Changes whenever the customer asks again.
	 */
	turn: string;
	/**
	 * Members the host called onto this request (from its `AgentInvite` calls), in
	 * call order. They meet the host once, then work and report from their desks.
	 */
	called: string[];
	/**
	 * Members who went to another for something this turn (`from` asked `to`), in
	 * order. Each walks to the other's desk and back. Nobody else moves.
	 */
	exchanges: { from: string; to: string }[];
	/** Who leads the room (the session's owner). */
	hostId: string | null;
	activity: { id: string; text: string }[];
}
