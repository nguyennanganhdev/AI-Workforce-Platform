import { z } from "zod";
import {
  OFFICIAL_INTERRUPTION_STATUSES,
  UTILITIES,
} from "../domain/interruption";

/** `technical.get_active_outage` (tools.md §3.5). */
export const getActiveOutageInputSchema = z.strictObject({
  building_id: z.uuid(),
  service_type: z.enum(UTILITIES),
  occurred_at: z.iso.datetime({ offset: true }),
});

export type GetActiveOutageInput = z.infer<typeof getActiveOutageInputSchema>;

export const outageSchema = z.strictObject({
  outage_id: z.uuid(),
  service_type: z.enum(UTILITIES),
  status: z.enum(OFFICIAL_INTERRUPTION_STATUSES),
  scope_ids: z.array(z.uuid()),
  started_at: z.iso.datetime({ offset: true }),
  ended_at: z.iso.datetime({ offset: true }).nullable(),
  published_eta: z.iso.datetime({ offset: true }).nullable(),
});

export const getActiveOutageOutputSchema = z.strictObject({
  outages: z.array(outageSchema),
});

export type GetActiveOutageOutput = z.infer<typeof getActiveOutageOutputSchema>;
