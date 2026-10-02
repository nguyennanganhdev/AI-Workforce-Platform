import { z } from "zod";
import { CONTACT_CHANNELS, CONTACT_OUTCOMES } from "../domain/unit";
import { QUALIFICATION_STATUSES } from "../domain/vendor";
import { idempotencyKeySchema } from "./write-common";

const unique = <T>(items: T[]) => new Set(items).size === items.length;
const optionalEvidenceSchema = z
  .array(z.string().min(1))
  .refine(unique, { message: "The same id appears more than once." })
  .optional();

/** `apartment_entry.request` (tools.md §6.3). */
export const apartmentEntryInputSchema = z.strictObject({
  building_id: z.uuid(),
  incident_id: z.uuid(),
  unit_id: z.uuid(),
  reason: z.string().min(10).max(2000),
  contact_attempts: z
    .array(
      // Strict, so a message body or a code cannot ride along with an attempt.
      z.strictObject({
        channel: z.enum(CONTACT_CHANNELS),
        attempted_at: z.iso.datetime({ offset: true }),
        outcome: z.enum(CONTACT_OUTCOMES),
        reference_id: z.string().min(1).max(200).optional(),
      }),
    )
    .min(1),
  requested_window: z
    .strictObject({
      from: z.iso.datetime({ offset: true }),
      to: z.iso.datetime({ offset: true }),
    })
    .refine((window) => Date.parse(window.from) < Date.parse(window.to), {
      path: ["to"],
      message: "requested_window.to must be later than requested_window.from.",
    })
    .optional(),
  evidence_ids: optionalEvidenceSchema,
  idempotency_key: idempotencyKeySchema,
});

export type ApartmentEntryInput = z.infer<typeof apartmentEntryInputSchema>;

export const apartmentEntryOutputSchema = z.strictObject({
  request_id: z.string(),
  approval_status: z.literal("PENDING_APPROVAL"),
  required_approvals: z.array(z.string()).min(1),
  created_at: z.iso.datetime({ offset: true }),
});

/** `vendor_dispatch.request` (tools.md §6.4). */
export const vendorDispatchInputSchema = z.strictObject({
  building_id: z.uuid(),
  incident_id: z.uuid(),
  workorder_id: z.uuid().optional(),
  service: z.string().min(2).max(200),
  reason: z.string().min(10).max(2000),
  urgency: z.enum(["routine", "soon", "immediate"]),
  required_specialty_code: z.string().min(1).max(100).optional(),
  evidence_ids: optionalEvidenceSchema,
  idempotency_key: idempotencyKeySchema,
});

export type VendorDispatchInput = z.infer<typeof vendorDispatchInputSchema>;

export const vendorDispatchOutputSchema = z.strictObject({
  request_id: z.string(),
  approval_status: z.literal("PENDING_APPROVAL"),
  eligible_vendors: z.array(
    z.strictObject({
      vendor_id: z.string(),
      display_name: z.string(),
      qualification_status: z.enum(QUALIFICATION_STATUSES),
    }),
  ),
  created_at: z.iso.datetime({ offset: true }),
});
