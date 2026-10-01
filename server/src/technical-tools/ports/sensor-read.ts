import type { Sensor, SensorReading } from "../domain/sensor";

export type SensorQuery = {
  tenantId: string;
  buildingId: string;
  sensorId?: string;
  assetId?: string;
  metric: string;
  window: { from: Date; to: Date };
};

export type SensorReadPort = {
  /**
   * The sensors in the building that match, and their readings around the window.
   *
   * The sensors come back even when they have no readings, because "no sensor measures that" and
   * "the sensor sent nothing in that hour" are different answers, and only the second is a reason
   * to go and look at the sensor.
   *
   * Readings may be a superset of the window. `sensor-rules` keeps those inside it, so a second
   * adapter cannot disagree with the first about where a window ends.
   */
  find(
    query: SensorQuery,
  ): Promise<{ sensors: Sensor[]; readings: SensorReading[] }>;
};
