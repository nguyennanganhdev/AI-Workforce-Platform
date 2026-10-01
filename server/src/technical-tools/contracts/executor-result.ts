import { z } from "zod";
import { VALIDATION_STATUSES } from "../domain/executor-result";
import { idempotencyKeySchema, uniqueIdsSchema } from "./write-common";

/** `technical.submit_executor_result` (tools.md §4.3). */
export const submitExecutorResultInputSchema = z
  .strictObject({
    building_id: z.uuid(),
    workorder_id: z.uuid(),
    assignment_id: z.uuid(),
    checklist: z
      .array(
        z.strictObject({
          item_code: z.string().min(1),
          status: z.enum(["passed", "failed", "not_applicable"]),
          note: z.string().optional(),
        }),
      )
      .min(1),
    measurement_ids: uniqueIdsSchema.optional(),
    parts: z
      .array(
        z.strictObject({
          name: z.string().min(1),
          quantity: z.number().positive(),
          unit: z.string().optional(),
        }),
      )
      .optional(),
    evidence_ids: uniqueIdsSchema.optional(),
    diagnosis: z.string().max(4000).optional(),
    repair_notes: z.string().max(8000).optional(),
    started_at: z.iso.datetime({ offset: true }),
    completed_at: z.iso.datetime({ offset: true }),
    idempotency_key: idempotencyKeySchema,
  })
  // tools.md §8 case 9: a result whose timestamps run backwards is refused.
  .refine(
    (input) => Date.parse(input.started_at) < Date.parse(input.completed_at),
    {
      path: ["completed_at"],
      message: "completed_at must be later than started_at.",
    },
  );

export type SubmitExecutorResultInput = z.infer<
  typeof submitExecutorResultInputSchema
>;

export const submitExecutorResultOutputSchema = z.strictObject({
  result_id: z.string(),
  validation_status: z.enum(VALIDATION_STATUSES),
  created_at: z.iso.datetime({ offset: true }),
  missing_evidence: z.array(z.string()),
  conflicts: z.array(z.string()),
});

export type SubmitExecutorResultOutput = z.infer<
  typeof submitExecutorResultOutputSchema
>;
