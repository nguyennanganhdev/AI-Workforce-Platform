/** How far a reading can be trusted, as the source system reports it. */
export const READING_QUALITIES = [
  "good",
  "uncertain",
  "bad",
  "unknown",
] as const;

export type ReadingQuality = (typeof READING_QUALITIES)[number];

/**
 * A BMS or IoT sensor.
 *
 * `assetId` is null for a sensor that measures a place rather than a machine, such as a moisture
 * probe in a wall. `unit` is what the sensor is declared to report in; each reading carries its own
 * unit as well, because a misconfigured sensor is exactly the one whose readings disagree with it.
 */
export type Sensor = {
  sensorId: string;
  tenantId: string;
  buildingId: string;
  assetId: string | null;
  metric: string;
  unit: string;
};

export type SensorReading = {
  sensorId: string;
  metric: string;
  value: number;
  unit: string;
  /** When the source says it measured this. Not proof of anything by itself (tools.md §1.4). */
  observedAt: Date;
  quality: ReadingQuality;
};
