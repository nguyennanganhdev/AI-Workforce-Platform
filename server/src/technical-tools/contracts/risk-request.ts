import { z } from "zod";
import { UTILITIES } from "../domain/interruption";
import { idempotencyKeySchema } from "./write-common";

const unique = <T>(items: T[]) => new Set(items).size === items.length;
const uniqueMessage = { message: "The same id appears more than once." };

/** Ids of evidence a request rests on: at least one, none twice. */
const requiredEvidenceSchema = z
  .array(z.string().min(1))
  .min(1)
  .refine(unique, uniqueMessage);

/** `utility_isolation.request` (tools.md §6.1). */
export const utilityIsolationInputSchema = z
  .strictObject({
    building_id: z.uuid(),
    incident_id: z.uuid(),
    workorder_id: z.uuid(),
    utility_type: z.enum(UTILITIES),
    scope_ids: z.array(z.uuid()).min(1).refine(unique, uniqueMessage),
    reason: z.string().min(10).max(2000),
    planned_start: z.iso.datetime({ offset: true }),
    planned_end: z.iso.datetime({ offset: true }),
    evidence_ids: requiredEvidenceSchema,
    idempotency_key: idempotencyKeySchema,
  })
  .refine(
    (input) => Date.parse(input.planned_start) < Date.parse(input.planned_end),
    {
      path: ["planned_end"],
      message: "planned_end must be later than planned_start.",
    },
  );

export type UtilityIsolationInput = z.infer<typeof utilityIsolationInputSchema>;

export const utilityIsolationOutputSchema = z.strictObject({
  request_id: z.uuid(),
  interruption_id: z.uuid(),
  approval_status: z.literal("PENDING_APPROVAL"),
  required_scope_id: z.uuid(),
  created_at: z.iso.datetime({ offset: true }),
});

/** `area_restriction.request` (tools.md §6.2). */
export const areaRestrictionInputSchema = z.strictObject({
  building_id: z.uuid(),
  incident_id: z.uuid(),
  workorder_id: z.uuid().optional(),
  area: z.string().min(2).max(500),
  hazard: z.string().min(3).max(1000),
  reason: z.string().min(10).max(2000),
  requested_until: z.iso.datetime({ offset: true }).optional(),
  evidence_ids: requiredEvidenceSchema,
  idempotency_key: idempotencyKeySchema,
});

export type AreaRestrictionInput = z.infer<typeof areaRestrictionInputSchema>;

export const areaRestrictionOutputSchema = z.strictObject({
  request_id: z.string(),
  approval_status: z.literal("PENDING_APPROVAL"),
  required_approver_scope: z.string(),
  created_at: z.iso.datetime({ offset: true }),
});
