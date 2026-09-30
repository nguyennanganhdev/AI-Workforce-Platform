import { z } from "zod";
import {
  OFFICIAL_INTERRUPTION_STATUSES,
  UTILITIES,
} from "../domain/interruption";

/** `utility_schedule.read` (tools.md §3.6). */
export const utilityScheduleReadInputSchema = z
  .strictObject({
    building_id: z.uuid(),
    utility_type: z.enum(UTILITIES),
    time_range: z.strictObject({
      from: z.iso.datetime({ offset: true }),
      to: z.iso.datetime({ offset: true }),
    }),
  })
  .refine(
    (input) =>
      Date.parse(input.time_range.from) < Date.parse(input.time_range.to),
    {
      path: ["time_range"],
      message: "time_range.from must be earlier than time_range.to.",
    },
  );

export type UtilityScheduleReadInput = z.infer<
  typeof utilityScheduleReadInputSchema
>;

export const scheduleSchema = z.strictObject({
  schedule_id: z.uuid(),
  utility_type: z.enum(UTILITIES),
  status: z.enum(OFFICIAL_INTERRUPTION_STATUSES),
  planned_start: z.iso.datetime({ offset: true }),
  planned_end: z.iso.datetime({ offset: true }),
  scope_ids: z.array(z.uuid()),
});

export const utilityScheduleReadOutputSchema = z.strictObject({
  schedules: z.array(scheduleSchema),
});

export type UtilityScheduleReadOutput = z.infer<
  typeof utilityScheduleReadOutputSchema
>;
