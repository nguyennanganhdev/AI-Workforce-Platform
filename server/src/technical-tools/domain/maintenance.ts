/**
 * One recorded piece of work on an asset.
 *
 * Append-only, as tools.md §1.4 requires of anything confirmed: a wrong entry is not edited but
 * replaced by a new event naming it in `supersedesEventId`. Reading the history means reading the
 * events nothing has replaced.
 *
 * `incidentId` is what separates a repair from routine upkeep. An event raised by an incident is a
 * fault that happened; one without is maintenance somebody scheduled.
 */
export type MaintenanceEvent = {
  eventId: string;
  tenantId: string;
  buildingId: string;
  assetId: string;
  incidentId: string | null;
  workorderId: string | null;
  occurredAt: Date;
  outcome: string;
  sourceRefs: readonly string[];
  supersedesEventId: string | null;
  /** Who recorded it, when, and in which run. Absent on history imported from elsewhere. */
  recordedBy?: string;
  createdAt?: Date;
  sourceRunId?: string;
};
