import { z } from "zod";
import { idempotencyKeySchema } from "./write-common";

/** `maintenance_history.append` (tools.md §4.1). */
export const maintenanceAppendInputSchema = z.strictObject({
  building_id: z.uuid(),
  asset_id: z.string().min(1),
  workorder_id: z.uuid(),
  verified_result_id: z.string().min(1),
  outcome: z.string().min(1).max(4000),
  source_refs: z
    .array(z.string().min(1))
    .min(1)
    .refine((refs) => new Set(refs).size === refs.length, {
      message: "The same reference appears more than once.",
    }),
  occurred_at: z.iso.datetime({ offset: true }).optional(),
  supersedes_event_id: z.string().min(1).optional(),
  idempotency_key: idempotencyKeySchema,
});

export type MaintenanceAppendInput = z.infer<
  typeof maintenanceAppendInputSchema
>;

export const maintenanceAppendOutputSchema = z.strictObject({
  maintenance_event_id: z.string(),
  created_at: z.iso.datetime({ offset: true }),
  revision: z.number().int().min(1),
  supersedes_event_id: z.string().nullable(),
});

export type MaintenanceAppendOutput = z.infer<
  typeof maintenanceAppendOutputSchema
>;
