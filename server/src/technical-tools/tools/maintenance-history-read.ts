import {
  maintenanceHistoryReadInputSchema,
  maintenanceHistoryReadOutputSchema,
} from "../contracts/maintenance";
import { defineTool } from "../tool";
import { summarise } from "./maintenance-rules";
import { notFound, provenanceOf } from "./outcomes";

/** The POC adapter names itself, so provenance does not imply the data came from the database. */
const MAINTENANCE_ADAPTER = "maintenance_adapter";

/**
 * `maintenance_history.read` (tools.md §3.4).
 *
 * Whether this fault has happened before on this equipment. It reports history as history: a note
 * from July that the drain was cleaned says what was done in July, not what is wrong today, and the
 * description says so where the model will read it.
 */
export const maintenanceHistoryReadTool = defineTool({
  name: "maintenance_history.read",
  version: "1.0.0",
  description:
    "Read the recorded maintenance and repairs of one asset over a time range, newest first, with " +
    "how many were raised by an incident (repeat_count) and when it was last serviced. Use it to " +
    "tell a first fault from a recurring one. Past notes are history, not a diagnosis of the " +
    "current fault: never repeat an old outcome as today's cause. last_maintenance_at may fall " +
    "before the range asked about.",
  effect: "read",
  capability: "maintenance:read",
  timeoutMs: 5_000,
  inputSchema: maintenanceHistoryReadInputSchema,
  outputSchema: maintenanceHistoryReadOutputSchema,
  async run(context, input, { assets, maintenance, clock }) {
    /*
     * The asset is looked up first so an unknown one is NOT_FOUND rather than an empty history.
     * The two would otherwise read the same, and "no repairs on record" for a machine that does
     * not exist is an answer an agent would repeat to a resident.
     */
    const [asset] = await assets.find({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      assetId: input.asset_id,
    });
    if (!asset) {
      return notFound(
        "No asset with that id is in this building. Look it up with asset.read first.",
        { field: "asset_id" },
      );
    }

    const from = new Date(input.time_range.from);
    const to = new Date(input.time_range.to);
    const events = await maintenance.listForAsset({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      assetId: input.asset_id,
      until: to,
    });
    const summary = summarise(events, from, to, input.limit);

    return {
      status: "OK",
      data: {
        events: summary.events.map((event) => ({
          event_id: event.eventId,
          asset_id: event.assetId,
          incident_id: event.incidentId,
          workorder_id: event.workorderId,
          occurred_at: event.occurredAt.toISOString(),
          outcome: event.outcome,
          source_refs: [...event.sourceRefs],
        })),
        last_maintenance_at: summary.lastMaintenanceAt?.toISOString() ?? null,
        repeat_count: summary.repeatCount,
      },
      provenance: provenanceOf(
        [{ id: asset.assetId, version: summary.events[0]?.eventId ?? null }],
        clock.now().toISOString(),
        MAINTENANCE_ADAPTER,
      ),
      resultCount: summary.events.length,
    };
  },
});
