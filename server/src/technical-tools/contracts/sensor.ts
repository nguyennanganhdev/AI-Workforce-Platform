import { z } from "zod";
import { READING_QUALITIES } from "../domain/sensor";
import { timeRangeSchema } from "./time-range";

/**
 * `sensor.read` (tools.md §3.3).
 *
 * Exactly one of `sensor_id` or `asset_id`, as the specification's `oneOf` says. Both at once would
 * leave it unclear which one decides, and neither would ask for every sensor in the building.
 */
export const sensorReadInputSchema = z
  .strictObject({
    building_id: z.uuid(),
    sensor_id: z.string().min(1).optional(),
    asset_id: z.string().min(1).optional(),
    metric: z.string().min(1).max(100),
    time_range: timeRangeSchema,
    max_age_seconds: z.number().int().min(1).max(86_400).default(900),
  })
  .refine((input) => Boolean(input.sensor_id) !== Boolean(input.asset_id), {
    path: ["sensor_id"],
    message: "Give exactly one of sensor_id or asset_id.",
  });

export type SensorReadInput = z.infer<typeof sensorReadInputSchema>;

export const FRESHNESS = ["fresh", "stale", "unknown"] as const;

export type Freshness = (typeof FRESHNESS)[number];

export const readingSchema = z.strictObject({
  sensor_id: z.string(),
  asset_id: z.string().nullable(),
  metric: z.string(),
  value: z.number(),
  unit: z.string(),
  observed_at: z.iso.datetime({ offset: true }),
  quality: z.enum(READING_QUALITIES),
});

export const sensorReadOutputSchema = z.strictObject({
  readings: z.array(readingSchema),
  freshness: z.enum(FRESHNESS),
});

export type SensorReadOutput = z.infer<typeof sensorReadOutputSchema>;
