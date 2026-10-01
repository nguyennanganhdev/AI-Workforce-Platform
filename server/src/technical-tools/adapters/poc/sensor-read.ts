import type { Sensor, SensorReading } from "../../domain/sensor";
import type { SensorReadPort } from "../../ports/sensor-read";

/**
 * A sensor source held in memory, for use until a BMS or IoT feed is connected.
 *
 * Given nothing, it has no sensors, and `sensor.read` answers NOT_FOUND. That is the point: a
 * deployment shipped with invented readings would tell an agent a leakage current it never
 * measured, and the agent might call a live circuit safe on the strength of it. The catalogue and
 * the readings are passed in by whoever stands the deployment up, or by a test.
 */
export function createInMemorySensorReadPort(
  sensors: readonly Sensor[] = [],
  readings: readonly SensorReading[] = [],
): SensorReadPort {
  return {
    find: async ({ tenantId, buildingId, sensorId, assetId, metric }) => {
      const matched = sensors.filter(
        (sensor) =>
          sensor.tenantId === tenantId &&
          sensor.buildingId === buildingId &&
          sensor.metric === metric &&
          (sensorId === undefined || sensor.sensorId === sensorId) &&
          (assetId === undefined || sensor.assetId === assetId),
      );
      const ids = new Set(matched.map((sensor) => sensor.sensorId));
      return {
        sensors: matched,
        // Every reading of the matched sensors: the rules keep the window, not the adapter.
        readings: readings.filter(
          (reading) => ids.has(reading.sensorId) && reading.metric === metric,
        ),
      };
    },
  };
}
