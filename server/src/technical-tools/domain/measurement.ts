export const MEASUREMENT_SOURCES = [
  "manual_entry",
  "instrument",
  "bms",
  "iot",
] as const;

export type MeasurementSource = (typeof MEASUREMENT_SOURCES)[number];

export type MeasuredBy = { kind: "technician" | "device"; sourceId: string };

/**
 * A measurement as recorded: append-only, as tools.md §1.4 requires of anything confirmed.
 *
 * The raw value and unit are kept beside the normalised ones, as tools.md §4.2 asks, so a
 * conversion can be checked afterwards against what the technician actually wrote down.
 */
export type Measurement = {
  measurementId: string;
  tenantId: string;
  buildingId: string;
  workOrderId: string;
  assetId: string | null;
  metric: string;
  rawValue: number;
  rawUnit: string;
  normalizedValue: number;
  normalizedUnit: string;
  measuredAt: Date;
  measuredBy: MeasuredBy;
  source: MeasurementSource;
  evidenceIds: readonly string[];
  qualityFlags: readonly string[];
  /** Server time, never the source's. */
  createdAt: Date;
  sourceRunId: string;
};
