import {
  type InterruptionRecord,
  OFFICIAL_INTERRUPTION_STATUSES,
  type OfficialInterruptionStatus,
} from "../domain/interruption";

export type OfficialInterruption = InterruptionRecord & {
  status: OfficialInterruptionStatus;
};

function isOfficial(
  record: InterruptionRecord,
): record is OfficialInterruption {
  return (OFFICIAL_INTERRUPTION_STATUSES as readonly string[]).includes(
    record.status,
  );
}

/**
 * Whether a row's own times make sense.
 *
 * The data dictionary says `planned_end` comes after `planned_start`, but the table carries no CHECK
 * for it, so a row can exist that ends before it begins. Such a row overlaps every window a naive
 * comparison is asked about, and would be reported as a schedule on any day somebody looked.
 */
export function isWellFormed(record: InterruptionRecord): boolean {
  if (record.plannedEnd.getTime() <= record.plannedStart.getTime()) {
    return false;
  }
  if (
    record.actualStart &&
    record.actualEnd &&
    record.actualEnd.getTime() < record.actualStart.getTime()
  ) {
    return false;
  }
  return true;
}

/** When the interruption began: what actually happened where it is known, the plan where it is not. */
export function startedAt(record: InterruptionRecord): Date {
  return record.actualStart ?? record.plannedStart;
}

/**
 * Whether the utility was cut at `instant`, going by what the row says happened.
 *
 * An `active` row counts from its start until somebody records the restoration, however far past
 * `planned_end` that runs: an outage nobody has ended is still an outage. `approved` and `notified`
 * rows have not started yet as far as the record knows, so only their planned window can place them.
 */
export function affectsAt(
  record: OfficialInterruption,
  instant: Date,
): boolean {
  const at = instant.getTime();
  switch (record.status) {
    case "active":
      return (
        startedAt(record).getTime() <= at &&
        (record.actualEnd === null || at < record.actualEnd.getTime())
      );
    case "restored":
      return (
        startedAt(record).getTime() <= at &&
        at < (record.actualEnd ?? record.plannedEnd).getTime()
      );
    case "approved":
    case "notified":
      return (
        record.plannedStart.getTime() <= at && at < record.plannedEnd.getTime()
      );
  }
}

/** Whether the planned window `[planned_start, planned_end)` overlaps `[from, to)`. */
export function overlapsPlannedWindow(
  record: InterruptionRecord,
  from: Date,
  to: Date,
): boolean {
  return (
    record.plannedStart.getTime() < to.getTime() &&
    record.plannedEnd.getTime() > from.getTime()
  );
}

function byTimeThenId(time: (record: OfficialInterruption) => Date) {
  return (left: OfficialInterruption, right: OfficialInterruption) =>
    time(left).getTime() - time(right).getTime() ||
    left.id.localeCompare(right.id);
}

/** The interruptions `technical.get_active_outage` reports for one instant, earliest first. */
export function selectOutagesAt(
  records: InterruptionRecord[],
  instant: Date,
): OfficialInterruption[] {
  return records
    .filter(isOfficial)
    .filter(isWellFormed)
    .filter((record) => affectsAt(record, instant))
    .sort(byTimeThenId(startedAt));
}

/** The interruptions `utility_schedule.read` reports for one window, earliest first. */
export function selectSchedulesWithin(
  records: InterruptionRecord[],
  from: Date,
  to: Date,
): OfficialInterruption[] {
  return records
    .filter(isOfficial)
    .filter(isWellFormed)
    .filter((record) => overlapsPlannedWindow(record, from, to))
    .sort(byTimeThenId((record) => record.plannedStart));
}
