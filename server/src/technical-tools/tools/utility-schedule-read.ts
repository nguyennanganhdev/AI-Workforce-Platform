import {
  utilityScheduleReadInputSchema,
  utilityScheduleReadOutputSchema,
} from "../contracts/schedule";
import { defineTool } from "../tool";
import { selectSchedulesWithin } from "./interruption-rules";
import {
  buildingNotFound,
  interruptionProvenance,
} from "./interruption-shared";

/**
 * `utility_schedule.read` (tools.md §3.6).
 *
 * The planned side of the same table `technical.get_active_outage` reads: which cuts have been
 * approved or announced for a window of time. It goes by the planned times only, so an outage that
 * has overrun its plan appears here under the window it was planned for, not under today.
 */
export const utilityScheduleReadTool = defineTool({
  name: "utility_schedule.read",
  version: "1.0.0",
  description:
    "Read the approved or announced water or power cut schedule for a building within a time " +
    "range. Use it before booking a repair, or when a resident asks about upcoming cuts. A " +
    "proposal that nobody has approved is not a schedule and is never returned, and neither is a " +
    "cancelled one.",
  effect: "read",
  capability: "interruption:read",
  timeoutMs: 5_000,
  inputSchema: utilityScheduleReadInputSchema,
  outputSchema: utilityScheduleReadOutputSchema,
  async run(context, input, { interruptions, clock }) {
    const from = new Date(input.time_range.from);
    const to = new Date(input.time_range.to);
    const records = await interruptions.listCovering({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      utility: input.utility_type,
      window: { from, to },
    });
    if (records === null) return buildingNotFound();

    const schedules = selectSchedulesWithin(records, from, to);
    return {
      status: "OK",
      data: {
        schedules: schedules.map((record) => ({
          schedule_id: record.id,
          utility_type: record.utility,
          status: record.status,
          planned_start: record.plannedStart.toISOString(),
          planned_end: record.plannedEnd.toISOString(),
          scope_ids: record.scopeIds,
        })),
      },
      provenance: interruptionProvenance(schedules, clock.now().toISOString()),
      resultCount: schedules.length,
    };
  },
});
