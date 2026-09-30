import {
  getActiveOutageInputSchema,
  getActiveOutageOutputSchema,
} from "../contracts/outage";
import { defineTool } from "../tool";
import { selectOutagesAt, startedAt } from "./interruption-rules";
import { APPLICATION_DB, buildingNotFound, provenanceOf } from "./outcomes";

/**
 * `technical.get_active_outage` (tools.md §3.5).
 *
 * Answers one question: at the moment the incident happened, was this building's water or power
 * already cut? It reports what the record says and nothing more. `published_eta` is the planned end
 * that was announced, left as it is even once that time has passed, because a restoration time this
 * tool worked out for itself would be a guess presented as a fact.
 */
export const getActiveOutageTool = defineTool({
  name: "technical.get_active_outage",
  version: "1.0.0",
  description:
    "Find water or power interruptions affecting a building at the time an incident occurred. " +
    "Use it to tell a fault in one apartment from a building-wide cut. Returns only approved, " +
    "notified, active or restored interruptions; a proposed or cancelled one is never reported. " +
    "An empty list means no recorded interruption, not that the utility is confirmed working. " +
    "Do not use it to estimate when service will be restored.",
  effect: "read",
  capability: "interruption:read",
  timeoutMs: 5_000,
  inputSchema: getActiveOutageInputSchema,
  outputSchema: getActiveOutageOutputSchema,
  async run(context, input, { interruptions, clock }) {
    const occurredAt = new Date(input.occurred_at);
    const records = await interruptions.listCovering({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      utility: input.service_type,
      window: { from: occurredAt, to: occurredAt },
    });
    if (records === null) return buildingNotFound();

    const outages = selectOutagesAt(records, occurredAt);
    return {
      status: "OK",
      data: {
        outages: outages.map((record) => ({
          outage_id: record.id,
          service_type: record.utility,
          status: record.status,
          scope_ids: record.scopeIds,
          started_at: startedAt(record).toISOString(),
          ended_at: record.actualEnd?.toISOString() ?? null,
          published_eta: record.plannedEnd.toISOString(),
        })),
      },
      provenance: provenanceOf(
        outages.map((record) => ({
          id: record.id,
          version: record.updatedAt.toISOString(),
        })),
        clock.now().toISOString(),
        APPLICATION_DB,
      ),
      resultCount: outages.length,
    };
  },
});
