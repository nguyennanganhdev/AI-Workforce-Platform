import type { Freshness } from "../contracts/sensor";
import type { SensorReading } from "../domain/sensor";
import { unitAccepted } from "../reference/metrics";

/**
 * The most readings one answer carries.
 *
 * Past this the tool asks for a narrower window instead of cutting the list. A list silently cut to
 * its first two hundred rows looks exactly like a complete one, and an agent would reason from half
 * a morning as if it were the whole of it.
 */
export const MAX_READINGS = 200;

/** Readings inside `[from, to)`, earliest first, then by sensor so two sensors interleave stably. */
export function readingsWithin(
  readings: readonly SensorReading[],
  from: Date,
  to: Date,
): SensorReading[] {
  return readings
    .filter(
      (reading) =>
        reading.observedAt.getTime() >= from.getTime() &&
        reading.observedAt.getTime() < to.getTime(),
    )
    .sort(
      (left, right) =>
        left.observedAt.getTime() - right.observedAt.getTime() ||
        left.sensorId.localeCompare(right.sensorId),
    );
}

/**
 * The reading with its quality lowered to `bad` where its unit is wrong for its metric.
 *
 * The value and the unit are left exactly as the source sent them. Converting would be guessing
 * what the sensor meant, and dropping the reading would hide that a sensor is misconfigured. Marked
 * `bad`, it is shown and not relied on, which is what general.md §11 asks of doubtful data.
 */
export function withUnitChecked(reading: SensorReading): SensorReading {
  return unitAccepted(reading.metric, reading.unit) === false
    ? { ...reading, quality: "bad" }
    : reading;
}

/**
 * The moment a reading's age is measured from: the end of the window asked about, or now if that
 * end is still in the future.
 *
 * Measuring always from now would call every reading from yesterday stale, including the ones
 * taken at the very minute the incident being investigated happened. The question is whether the
 * sensor was still reporting at the end of the period, and that is what this measures.
 */
export function freshnessReference(windowEnd: Date, now: Date): Date {
  return windowEnd.getTime() < now.getTime() ? windowEnd : now;
}

/**
 * Whether the newest reading is recent enough to reason from.
 *
 * A reading exactly `maxAgeSeconds` old is still fresh; only one older than that is stale, as
 * tools.md §3.3 words it ("quá max_age_seconds"). No readings at all is `unknown`, which is a
 * different fact from stale: nothing arrived, rather than something old arrived.
 */
export function freshnessOf(
  readings: readonly SensorReading[],
  reference: Date,
  maxAgeSeconds: number,
): Freshness {
  if (readings.length === 0) return "unknown";
  const newest = Math.max(
    ...readings.map((reading) => reading.observedAt.getTime()),
  );
  return reference.getTime() - newest > maxAgeSeconds * 1000
    ? "stale"
    : "fresh";
}
