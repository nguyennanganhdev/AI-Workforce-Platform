import { createContext, useContext } from 'react';

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
