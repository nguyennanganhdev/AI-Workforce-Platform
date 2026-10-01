import type { WorkOrderContext } from "../domain/work-order";
import { metricDefinition } from "../reference/metrics";

/** How far ahead of the server a measurement may claim to have been taken: a clock drifting. */
export const FUTURE_TOLERANCE_MS = 5 * 60 * 1000;

/** How long after the fact a measurement may be written down before it is flagged as late. */
export const LATE_ENTRY_MS = 24 * 60 * 60 * 1000;

export type Normalized =
  | { ok: true; value: number; unit: string }
  | { ok: false; field: "metric" | "unit"; message: string };

/**
 * The value in its metric's canonical unit, or why it cannot be recorded.
 *
 * Refused outright where reading would only flag it. A reading is shown and not relied on; a
 * recorded measurement becomes evidence a repair met its criteria, and a number nobody can put in
 * a known unit must not become that. `toPrecision` keeps a conversion such as 250 kPa to bar from
 * arriving as 2.5000000000000004.
 */
export function normalize(
  metric: string,
  value: number,
  unit: string,
): Normalized {
  const definition = metricDefinition(metric);
  if (!definition) {
    return {
      ok: false,
      field: "metric",
      message: `${metric} is not a metric this deployment records. Use one of its listed metrics.`,
    };
  }
  // Own keys only: `constructor` is on every object, and is not a unit.
  const factor = Object.hasOwn(definition.units, unit)
    ? definition.units[unit]
    : undefined;
  if (factor === undefined) {
    return {
      ok: false,
      field: "unit",
      message: `${unit} is not a unit ${metric} is recorded in. Accepted: ${Object.keys(definition.units).join(", ")}.`,
    };
  }
  return {
    ok: true,
    value: Number((value * factor).toPrecision(12)),
    unit: definition.canonicalUnit,
  };
}

/** Whether the source claims a time the server has not reached yet, beyond clock drift. */
export function measuredInFuture(measuredAt: Date, now: Date): boolean {
  return measuredAt.getTime() > now.getTime() + FUTURE_TOLERANCE_MS;
}

/**
 * What a person on duty should notice about a measurement that is recorded anyway.
 *
 * Flags, not refusals. A leakage current of 180 mA is the measurement that matters most, and a
 * tool that refused it for being unusual would lose exactly the data a safety decision needs.
 */
export function qualityFlags(
  metric: string,
  normalizedValue: number,
  measuredAt: Date,
  now: Date,
): string[] {
  const flags: string[] = [];
  const range = metricDefinition(metric)?.expectedRange;
  if (range && (normalizedValue < range.min || normalizedValue > range.max)) {
    flags.push("out_of_expected_range");
  }
  if (now.getTime() - measuredAt.getTime() > LATE_ENTRY_MS) {
    flags.push("late_entry");
  }
  return flags;
}

/**
 * Whether the person the run acts for may put their name to this measurement (general.md §3.1:
 * the agent must never create a measurement).
 *
 * Only as themselves, and only on a work order they have accepted. An agent that could record a
 * value "measured by" another technician could invent any number and attribute it to somebody who
 * was never asked.
 */
export function technicianMayRecord(
  callerUserId: string | undefined,
  claimedSourceId: string,
  workOrder: WorkOrderContext,
): boolean {
  if (!callerUserId || callerUserId !== claimedSourceId) return false;
  return workOrder.assignments.some(
    (assignment) =>
      assignment.status === "accepted" &&
      assignment.staffUserId === callerUserId,
  );
}

/** The sources a device can report through. A device does not type numbers in by hand. */
export const DEVICE_SOURCES: ReadonlySet<string> = new Set([
  "bms",
  "iot",
  "instrument",
]);
