import { z } from "zod";
import { CHECK_STATUSES, VERIFICATION_STATUSES } from "../domain/verification";

/** `technical.verify_resolution` (tools.md §5.1). */
export const verifyResolutionInputSchema = z.strictObject({
  building_id: z.uuid(),
  incident_id: z.uuid(),
  workorder_id: z.uuid(),
  result_id: z.string().min(1),
  sop_document_ids: z
    .array(z.uuid())
    .refine((ids) => new Set(ids).size === ids.length, {
      message: "The same id appears more than once.",
    })
    .optional(),
});

export type VerifyResolutionInput = z.infer<typeof verifyResolutionInputSchema>;

export const verifyResolutionOutputSchema = z.strictObject({
  verification_status: z.enum(VERIFICATION_STATUSES),
  checks: z.array(
    z.strictObject({
      criterion: z.string(),
      status: z.enum(CHECK_STATUSES),
      source_refs: z.array(z.string()),
    }),
  ),
  required_actions: z.array(z.string()),
  source_refs: z.array(z.string()).min(1),
});

export type VerifyResolutionOutput = z.infer<
  typeof verifyResolutionOutputSchema
>;
