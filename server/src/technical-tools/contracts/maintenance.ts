import { z } from "zod";
import { timeRangeSchema } from "./time-range";

/** `maintenance_history.read` (tools.md §3.4). */
export const maintenanceHistoryReadInputSchema = z.strictObject({
  building_id: z.uuid(),
  asset_id: z.string().min(1),
  time_range: timeRangeSchema,
  limit: z.number().int().min(1).max(100).default(20),
});

export type MaintenanceHistoryReadInput = z.infer<
  typeof maintenanceHistoryReadInputSchema
>;

export const maintenanceEventSchema = z.strictObject({
  event_id: z.string(),
  asset_id: z.string(),
  incident_id: z.string().nullable(),
  workorder_id: z.string().nullable(),
  occurred_at: z.iso.datetime({ offset: true }),
  outcome: z.string(),
  source_refs: z.array(z.string()),
});

export const maintenanceHistoryReadOutputSchema = z.strictObject({
  events: z.array(maintenanceEventSchema),
  last_maintenance_at: z.iso.datetime({ offset: true }).nullable(),
  repeat_count: z.number().int().min(0),
});

export type MaintenanceHistoryReadOutput = z.infer<
  typeof maintenanceHistoryReadOutputSchema
>;
