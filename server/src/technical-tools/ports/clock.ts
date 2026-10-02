/** Server time, injected so `received_at` and `server_time` are not read from the machine in tests. */
export type Clock = { now(): Date };

export const systemClock: Clock = { now: () => new Date() };
