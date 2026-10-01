import { randomUUID } from "node:crypto";
import {
  maintenanceAppendInputSchema,
  maintenanceAppendOutputSchema,
} from "../contracts/maintenance-append";
import type { MaintenanceEvent } from "../domain/maintenance";
import type { MaintenanceStore } from "../ports/maintenance-store";
import { defineTool } from "../tool";
import { measuredInFuture } from "./measurement-rules";
import {
  buildingNotFound,
  conflict,
  forbidden,
  invalidInput,
  notFound,
  provenanceOf,
} from "./outcomes";
import { resolveSops, sopReferences } from "./verification-rules";
import { aclSubjectOf, verifyFromSources } from "./verification-sources";

const MAINTENANCE_ADAPTER = "maintenance_adapter";

/** How many events stand before this one in its chain of corrections, plus one. */
async function revisionOf(
  store: MaintenanceStore,
  tenantId: string,
  replaced: MaintenanceEvent | null,
): Promise<number> {
  let revision = 1;
  let current = replaced;
  const seen = new Set<string>();
  while (current && !seen.has(current.eventId)) {
    seen.add(current.eventId);
    revision += 1;
    current = current.supersedesEventId
      ? await store.findEvent(tenantId, current.supersedesEventId)
      : null;
  }
  return revision;
}

/**
 * `maintenance_history.append` (tools.md §4.1).
 *
 * Records a repair in an asset's history, once the result behind it is verified. It does not take
 * the agent's word for that: the result is verified again here, against the SOPs the event cites,
 * the same way `technical.verify_resolution` does, and anything short of VERIFIED is refused. An id
 * is something the agent can supply; that the work passed is not.
 *
 * Append-only. A wrong entry is corrected by a new one naming it, and an entry already corrected
 * cannot be corrected a second time, so the history never splits into two versions of the truth.
 */
export const appendMaintenanceHistoryTool = defineTool({
  name: "maintenance_history.append",
  version: "1.0.0",
  description:
    "Record verified work in an asset's maintenance history. Only after " +
    "technical.verify_resolution has answered VERIFIED: the result is verified again here " +
    "against the SOPs cited in source_refs (doc:<code>:v<n>), and anything else is refused " +
    "with CONFLICT. source_refs must include result:<verified_result_id>. To correct an entry, " +
    "append a new one with supersedes_event_id; entries are never edited.",
  effect: "write",
  capability: "maintenance:append",
  timeoutMs: 5_000,
  inputSchema: maintenanceAppendInputSchema,
  outputSchema: maintenanceAppendOutputSchema,
  async run(context, input, dependencies) {
    const {
      workOrders,
      assets,
      executorResults,
      maintenanceStore,
      sop,
      sopProfiles,
      clock,
    } = dependencies;
    const now = clock.now();

    if (!input.source_refs.includes(`result:${input.verified_result_id}`)) {
      return invalidInput(
        `source_refs must include result:${input.verified_result_id}, the result this event records.`,
        "source_refs",
      );
    }
    const occurredAt = input.occurred_at ? new Date(input.occurred_at) : now;
    if (measuredInFuture(occurredAt, now)) {
      return invalidInput(
        "occurred_at is later than the server's clock. Record when the work was done.",
        "occurred_at",
      );
    }

    const workOrder = await workOrders.getWorkOrder({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      workOrderId: input.workorder_id,
    });
    if (!workOrder) {
      return notFound("No work order with that id is in this building.", {
        field: "workorder_id",
      });
    }

    const asset = await assets.find({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      assetId: input.asset_id,
    });
    if (asset.length === 0) {
      return notFound("No asset with that id is in this building.", {
        field: "asset_id",
      });
    }

    const result = await executorResults.findById(
      context.tenant_id,
      input.verified_result_id,
    );
    if (!result || result.workOrderId !== workOrder.workOrderId) {
      return notFound(
        "No submitted result with that id is on this work order.",
        {
          field: "verified_result_id",
        },
      );
    }

    // The technician who did the work, or management answering for work in their scope.
    const assignment = workOrder.assignments.find(
      (candidate) => candidate.assignmentId === result.assignmentId,
    );
    if (
      context.user_id !== assignment?.staffUserId &&
      context.role_code !== "management"
    ) {
      return forbidden();
    }

    const records = await sop.listForBuilding({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
    });
    if (records === null) return buildingNotFound();
    const resolved = resolveSops(
      sopReferences(input.source_refs),
      records,
      (code, versionNo) => sopProfiles.find(code, versionNo),
      now,
      aclSubjectOf(context),
    );
    if (resolved.problems.length > 0) {
      return conflict(resolved.problems, "source_refs");
    }

    const verification = await verifyFromSources(context, dependencies, {
      workOrder,
      result,
      sops: resolved.sops,
    });
    if (verification.status !== "VERIFIED") {
      return conflict(
        [
          `result ${result.resultId} is ${verification.status}, not VERIFIED; nothing was recorded`,
          ...verification.requiredActions,
        ],
        "verified_result_id",
      );
    }

    let replaced: MaintenanceEvent | null = null;
    if (input.supersedes_event_id) {
      replaced = await maintenanceStore.findEvent(
        context.tenant_id,
        input.supersedes_event_id,
      );
      if (
        !replaced ||
        replaced.buildingId !== input.building_id ||
        replaced.assetId !== input.asset_id
      ) {
        return conflict(
          [`event ${input.supersedes_event_id} is not in this asset's history`],
          "supersedes_event_id",
        );
      }
      const already = await maintenanceStore.supersededBy(
        context.tenant_id,
        replaced.eventId,
      );
      if (already) {
        return conflict(
          [
            `event ${replaced.eventId} was already replaced by ${already}; correct the latest entry instead`,
          ],
          "supersedes_event_id",
        );
      }
    }

    const event: MaintenanceEvent = {
      eventId: randomUUID(),
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      assetId: input.asset_id,
      // The ticket the work order serves, so the repeat count sees this as a fault that happened.
      incidentId: workOrder.ticketId,
      workorderId: workOrder.workOrderId,
      occurredAt,
      outcome: input.outcome,
      sourceRefs: [...input.source_refs],
      supersedesEventId: replaced?.eventId ?? null,
      recordedBy: context.user_id ?? context.principal_id,
      createdAt: now,
      sourceRunId: context.source_run_id,
    };
    const revision = await revisionOf(
      maintenanceStore,
      context.tenant_id,
      replaced,
    );
    const appended = await maintenanceStore.append(event);
    if (appended.state === "already_superseded") {
      return conflict(
        [
          `event ${replaced?.eventId} was already replaced by ${appended.byEventId}; correct the latest entry instead`,
        ],
        "supersedes_event_id",
      );
    }

    return {
      status: "OK",
      data: {
        maintenance_event_id: event.eventId,
        created_at: now.toISOString(),
        revision,
        supersedes_event_id: event.supersedesEventId,
      },
      provenance: provenanceOf(
        [{ id: event.eventId, version: revision }],
        now.toISOString(),
        MAINTENANCE_ADAPTER,
      ),
      resultCount: 1,
    };
  },
});
