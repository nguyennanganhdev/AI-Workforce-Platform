import type { MaintenanceEvent } from "../domain/maintenance";

export type AppendOutcome =
  | { state: "appended" }
  /** Another event already replaces the one this event would replace. Nothing was written. */
  | { state: "already_superseded"; byEventId: string };

/**
 * Where maintenance events are written. Append-only (tools.md §1.4): a wrong entry is corrected by
 * a new event naming it, and the wrong one stays on the record.
 *
 * `append` must refuse, in the same step as the write, an event replacing one that something else
 * already replaces. Checked beforehand and written after, two corrections of one entry sent at the
 * same moment would both land and split the history in two. A table enforces this with a unique
 * index on `supersedes_event_id`.
 */
export type MaintenanceStore = {
  findEvent(
    tenantId: string,
    eventId: string,
  ): Promise<MaintenanceEvent | null>;
  /** The event that replaces this one, if any. */
  supersededBy(tenantId: string, eventId: string): Promise<string | null>;
  append(event: MaintenanceEvent): Promise<AppendOutcome>;
};
