import type { MaintenanceEvent } from "../domain/maintenance";

/**
 * The events nothing has replaced.
 *
 * History is append-only: a wrong entry stays and a correction names it. Reporting both would tell
 * the agent a pump was replaced when the correction says it was only cleaned, and the agent would
 * reason from the mistake.
 */
export function currentEvents(
  events: readonly MaintenanceEvent[],
): MaintenanceEvent[] {
  const replaced = new Set(
    events.flatMap((event) =>
      event.supersedesEventId ? [event.supersedesEventId] : [],
    ),
  );
  return events.filter((event) => !replaced.has(event.eventId));
}

export type MaintenanceSummary = {
  /** Newest first, cut to the page size. */
  events: MaintenanceEvent[];
  lastMaintenanceAt: Date | null;
  repeatCount: number;
};

/**
 * What `maintenance_history.read` reports for one window.
 *
 * `repeatCount` counts only events raised by an incident, over the whole window rather than the
 * page. Scheduled upkeep is not a fault recurring, and a count that included it would make a
 * well-maintained air conditioner look like a failing one. Counting the page instead of the window
 * would make the answer depend on `limit`.
 *
 * `lastMaintenanceAt` is the latest event before the window ends, however long before it starts.
 * Bounded by `from`, a question about the last thirty days would answer `null` for equipment
 * serviced last year, which reads as "never serviced".
 */
export function summarise(
  events: readonly MaintenanceEvent[],
  from: Date,
  to: Date,
  limit: number,
): MaintenanceSummary {
  const current = currentEvents(events).filter(
    (event) => event.occurredAt.getTime() < to.getTime(),
  );
  const newestFirst = [...current].sort(
    (left, right) =>
      right.occurredAt.getTime() - left.occurredAt.getTime() ||
      left.eventId.localeCompare(right.eventId),
  );
  const inWindow = newestFirst.filter(
    (event) => event.occurredAt.getTime() >= from.getTime(),
  );

  return {
    events: inWindow.slice(0, limit),
    lastMaintenanceAt: newestFirst[0]?.occurredAt ?? null,
    repeatCount: inWindow.filter((event) => event.incidentId !== null).length,
  };
}
