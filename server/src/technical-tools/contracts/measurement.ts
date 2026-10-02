import { z } from "zod";
import { MEASUREMENT_SOURCES } from "../domain/measurement";
import { idempotencyKeySchema, uniqueIdsSchema } from "./write-common";

/** `technical.record_measurement` (tools.md §4.2). */
export const recordMeasurementInputSchema = z.strictObject({
  building_id: z.uuid(),
  workorder_id: z.uuid(),
  asset_id: z.string().min(1).optional(),
  metric: z.string().min(1).max(100),
  value: z.number(),
  unit: z.string().min(1).max(32),
  measured_at: z.iso.datetime({ offset: true }),
  measured_by: z.strictObject({
    kind: z.enum(["technician", "device"]),
    source_id: z.string().min(1),
  }),
  source: z.enum(MEASUREMENT_SOURCES),
  evidence_ids: uniqueIdsSchema.optional(),
  idempotency_key: idempotencyKeySchema,
});

export type RecordMeasurementInput = z.infer<
  typeof recordMeasurementInputSchema
>;

export const recordMeasurementOutputSchema = z.strictObject({
  measurement_id: z.string(),
  metric: z.string(),
  normalized_value: z.number(),
  normalized_unit: z.string(),
  created_at: z.iso.datetime({ offset: true }),
  quality_flags: z.array(z.string()),
});

export type RecordMeasurementOutput = z.infer<
  typeof recordMeasurementOutputSchema
>;
