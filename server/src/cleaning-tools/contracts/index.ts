import { z } from "zod";
import {
  sopRetrieveInputSchema,
  sopRetrieveOutputSchema,
} from "../../technical-tools/contracts/sop";
const id = z.uuid();
const version = z.number().int().nonnegative();
const time = z.iso.datetime({ offset: true });
const key = z.string().min(8).max(128);
const page = {
  limit: z.number().int().min(1).max(100).default(20),
  offset: z.number().int().min(0).max(100000).default(0),
};
export const retrieveSopInput = sopRetrieveInputSchema.extend({
  issue_code: z.string().regex(/^CLEAN\.[A-Z]+\.[A-Z0-9_]+$/),
});
export const retrieveSopOutput = sopRetrieveOutputSchema;
export const listStaffInput = z.strictObject({
  building_id: id,
  work_order_id: id.optional(),
  ...page,
});
export const staffSchema = z.strictObject({
  staff_id: id,
  name: z.string().optional(),
  employee_code: z.string(),
  management_unit_id: id,
  active_jobs: z.number().int().nonnegative(),
  max_concurrent_jobs: z.number().int().nonnegative(),
});
export const listStaffOutput = z.strictObject({
  staff: z.array(staffSchema),
  next_offset: version.nullable(),
});
export const readWorkInput = z
  .strictObject({
    building_id: id,
    work_order_id: id.optional(),
    ticket_id: id.optional(),
    include_history: z.boolean().default(false),
    ...page,
  })
  .refine(
    (v) => Boolean(v.work_order_id) !== Boolean(v.ticket_id),
    "Supply exactly one work_order_id or ticket_id",
  );
export const assignmentSchema = z.strictObject({
  assignment_id: id,
  staff_id: id,
  status: z.string(),
  eta_at: time.nullable(),
  accepted_at: time.nullable(),
});
export const workSchema = z.strictObject({
  work_order_id: id,
  ticket_id: id,
  category_id: id,
  status: z.string(),
  version,
  description: z.string(),
  assignments: z.array(assignmentSchema),
});
export const readWorkOutput = z.strictObject({
  ticket_id: id,
  ticket_version: version,
  work_orders: z.array(workSchema),
  next_offset: version.nullable(),
  history: z.array(
    z.strictObject({
      id,
      event_type: z.string(),
      occurred_at: time,
      from_status: z.string().nullable(),
      to_status: z.string().nullable(),
    }),
  ),
});
export const createWorkInput = z.strictObject({
  building_id: id,
  ticket_id: id,
  ticket_version: version,
  description: z.string().min(1).max(5000),
  required_specialty_id: id,
  idempotency_key: key,
});
export const createWorkOutput = z.strictObject({
  work_order_id: id,
  ticket_id: id,
  status: z.string(),
  version,
});
export const dispatchInput = z.strictObject({
  building_id: id,
  work_order_id: id,
  staff_id: id,
  expected_version: version,
  offer_expires_at: time,
  idempotency_key: key,
});
export const dispatchOutput = z.strictObject({
  work_order_id: id,
  assignment_id: id,
  staff_id: id,
  assignment_status: z.literal("offered"),
  work_order_status: z.literal("offered"),
  version,
});
export const updateStatusInput = z.strictObject({
  building_id: id,
  work_order_id: id,
  assignment_id: id,
  expected_version: version,
  status: z.enum([
    "en_route",
    "arrived",
    "awaiting_approval",
    "in_progress",
    "completed",
  ]),
  note: z.string().min(1).max(2000),
  idempotency_key: key,
});
export const updateStatusOutput = z.strictObject({
  work_order_id: id,
  assignment_id: id,
  staff_id: id,
  status: z.string(),
  version,
});
// Identical result/verification contracts to technical tools; no extra version or SOP gate.
export {
  submitExecutorResultInputSchema as submitResultInput,
  submitExecutorResultOutputSchema as submitResultOutput,
} from "../../technical-tools/contracts/executor-result";
export {
  verifyResolutionInputSchema as verifyInput,
  verifyResolutionOutputSchema as verifyOutput,
} from "../../technical-tools/contracts/verification";
