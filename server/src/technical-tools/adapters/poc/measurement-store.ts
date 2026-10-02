import type { Measurement } from "../../domain/measurement";
import type { MeasurementStore } from "../../ports/measurement-store";

/**
 * Measurements held in memory, until a table exists.
 *
 * Everything recorded here is lost when the process stops. That is acceptable for the POC and for
 * tests, and it is the reason this is not the production store: a measurement a technician took
 * must outlive a restart.
 *
 * `all()` is for tests, which need to count what was written. It is not part of the port.
 */
export function createInMemoryMeasurementStore(): MeasurementStore & {
  all(): readonly Measurement[];
} {
  const measurements: Measurement[] = [];
  return {
    append: async (measurement) => {
      measurements.push(measurement);
    },
    findByIds: async (tenantId, ids) => {
      const wanted = new Set(ids);
      return measurements.filter(
        (measurement) =>
          measurement.tenantId === tenantId &&
          wanted.has(measurement.measurementId),
      );
    },
    all: () => [...measurements],
  };
}
