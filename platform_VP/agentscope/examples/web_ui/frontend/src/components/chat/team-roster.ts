import { createContext, useContext, useEffect, useState } from 'react';

import { workforceApi } from '@/api';
import type { RoomEntry, RoomView } from '@/api';

/**
 * The open session's agents by lower-cased display name, so a room card can
 * show an agent's own portrait (the one the team panel and the map use).
 */
export const TeamRosterContext = createContext<ReadonlyMap<string, string>>(new Map());

/** The agent id behind a display name, or the name itself when unknown. */
export function useAgentId(name: string): string {
	return useContext(TeamRosterContext).get(name.toLocaleLowerCase()) ?? name;
}

/** Whether the open session is a partner ticket of the Leader page. */
export const TicketViewContext = createContext(false);

const ROOM_REFRESH_MS = 5000;

/** A team session's room (who said what, the members' tool calls, cost), polled. */
export function useRoom(sessionId: string | null): RoomView | null {
	const [room, setRoom] = useState<RoomView | null>(null);
	useEffect(() => {
		setRoom(null);
		if (!sessionId) return;
		let active = true;
		const load = () =>
			workforceApi
				.room(sessionId)
				.then((value) => active && setRoom(value))
				.catch(() => active && setRoom(null));
		load();
		const timer = setInterval(load, ROOM_REFRESH_MS);
		return () => {
			active = false;
			clearInterval(timer);
		};
	}, [sessionId]);
	return room;
}

/** The open session's room, shared by the chat cards and the team panel. */
export const RoomContext = createContext<RoomView | null>(null);

/** A server time in ms; one written without a zone is UTC (the message log's). */
function toMs(at: string): number {
	return Date.parse(/(Z|[+-]\d{2}:?\d{2})$/.test(at) ? at : `${at}Z`);
}

/** Kinds that close a member's piece of work in the room log. */
const REPORTS = new Set(['result', 'answer', 'question', 'error', 'conflict', 'review']);

/**
 * The tool calls behind the report `member` delivered at `at`. A report can
 * reach the Leader later than it was written, so the report is the member's
 * latest one written by then, and its calls are those since the one before.
 */
export function memberToolCalls(entries: RoomEntry[], member: string, at: string | undefined): RoomEntry[] {
	if (!at) return [];
	const name = member.toLocaleLowerCase();
	const delivered = toMs(at) + 2000;
	const mine = entries.filter((entry) => entry.sender.toLocaleLowerCase() === name);
	const reports = mine
		.filter((entry) => REPORTS.has(entry.kind))
		.map((entry) => toMs(entry.at))
		.filter((time) => time <= delivered)
		.sort((a, b) => a - b);
	if (reports.length === 0) return [];
	const report = reports[reports.length - 1];
	const since = reports.length > 1 ? reports[reports.length - 2] : 0;
	return mine.filter((entry) => {
		const time = toMs(entry.at);
		return entry.kind === 'tool' && time > since && time <= report;
	});
}
