import { randomUUID } from "node:crypto";
import {
  utilityIsolationInputSchema,
  utilityIsolationOutputSchema,
} from "../contracts/risk-request";
import type { OpenIsolation } from "../domain/approval-request";
import { payloadHash } from "../idempotency";
import { defineTool } from "../tool";
import { evidenceProblems } from "./evidence-rules";
import {
  APPLICATION_DB,
  buildingNotFound,
  conflict,
  forbidden,
  invalidInput,
  notFound,
  provenanceOf,
} from "./outcomes";
import {
  overlappingIsolations,
  scopeProblems,
  widestScope,
} from "./request-rules";

const APPROVAL_ADAPTER = "approval_adapter";

/**
 * `utility_isolation.request` (tools.md §6.1).
 *
 * Asks for water or power to be shut off across a stated area for a stated time. It asks and does
 * nothing else: no valve closes and no breaker opens because of it. The answer is always
 * PENDING_APPROVAL, and the interruption it proposes stays `proposed`, which every read tool here
 * declines to report as an outage, until a person with authority over the whole area approves it
 * somewhere these tools cannot reach.
 *
 * Water goes to the deployment's own tables, approval and interruption in one transaction. Power
 * goes to the shared approval adapter, because the database has no approval kind for it and an
 * interruption there must point at an approval: borrowing `customer_repair` would route a request
 * to cut a building's power to a resident.
 */
export const utilityIsolationRequestTool = defineTool({
  name: "utility_isolation.request",
  version: "1.0.0",
  description:
    "Ask for water or power to be isolated across given scopes for a planned window, for a work " +
    "order, with photo evidence. This only creates a request: the answer is always " +
    "PENDING_APPROVAL and nothing is shut off until a person with authority approves it. Never " +
    "tell anyone the supply is off, or ask them to act as if it were, because of this call. " +
    "Scopes must be the building, its zone or its site. A request overlapping one already open " +
    "on the same work order is refused with its id.",
  effect: "request",
  capability: "utility_isolation:request",
  timeoutMs: 5_000,
  inputSchema: utilityIsolationInputSchema,
  outputSchema: utilityIsolationOutputSchema,
  async run(context, input, dependencies) {
    const { workOrders, scopes, isolations, approvalRequests, clock } =
      dependencies;
    const now = clock.now();
    const plannedStart = new Date(input.planned_start);
    const plannedEnd = new Date(input.planned_end);

    if (plannedEnd.getTime() <= now.getTime()) {
      return invalidInput(
        "planned_end has already passed. Ask for the window the isolation is still needed in.",
        "planned_end",
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
    if (workOrder.ticketId !== input.incident_id) {
      return conflict(
        [
          `work order ${input.workorder_id} does not belong to incident ${input.incident_id}`,
        ],
        "incident_id",
      );
    }

    // The technician working on the job, or management answering for the building.
    const onTheJob = workOrder.assignments.some(
      (assignment) =>
        assignment.status === "accepted" &&
        assignment.staffUserId === context.user_id,
    );
    if (!onTheJob && context.role_code !== "management") return forbidden();

    const building = await scopes.placement({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
    });
    if (!building) return buildingNotFound();
    const found = await scopes.findScopes({
      tenantId: context.tenant_id,
      ids: input.scope_ids,
    });
    const wrongScopes = scopeProblems(input.scope_ids, found, building);
    if (wrongScopes.length > 0) return conflict(wrongScopes, "scope_ids");

    const wrongEvidence = evidenceProblems(
      input.evidence_ids,
      await workOrders.findEvidence({
        tenantId: context.tenant_id,
        ids: input.evidence_ids,
      }),
      workOrder.ticketId,
    );
    if (wrongEvidence.length > 0)
      return conflict(wrongEvidence, "evidence_ids");

    const open: OpenIsolation[] =
      input.utility_type === "water"
        ? await isolations.findOpen({
            tenantId: context.tenant_id,
            workOrderId: workOrder.workOrderId,
            utility: "water",
          })
        : (
            await approvalRequests.listOpen({
              tenantId: context.tenant_id,
              kind: "power_isolation",
              incidentId: workOrder.ticketId,
            })
          ).flatMap((request) =>
            request.interruption &&
            request.workOrderId === workOrder.workOrderId
              ? [
                  {
                    requestId: request.requestId,
                    interruptionId: request.interruption.interruptionId,
                    status: request.interruption.status,
                    plannedStart: request.interruption.plannedStart,
                    plannedEnd: request.interruption.plannedEnd,
                  },
                ]
              : [],
          );
    const overlapping = overlappingIsolations(open, {
      from: plannedStart,
      to: plannedEnd,
    });
    if (overlapping.length > 0) {
      return conflict(
        overlapping.map(
          (isolation) =>
            `a ${input.utility_type} isolation for this work order is already ${isolation.status} for an overlapping window: request ${isolation.requestId}`,
        ),
        "planned_start",
      );
    }

    const requiredScope = widestScope(
      found.filter((scope) => input.scope_ids.includes(scope.id)),
    );
    const requestId = randomUUID();
    const interruptionId = randomUUID();
    const requestedBy = context.user_id ?? context.principal_id;
    const detail = {
      utility: input.utility_type,
      reason: input.reason,
      scope_ids: input.scope_ids,
      evidence_ids: input.evidence_ids,
      planned_start: plannedStart.toISOString(),
      planned_end: plannedEnd.toISOString(),
      incident_id: workOrder.ticketId,
      requested_by: requestedBy,
      source_run_id: context.source_run_id,
    };
    const requestHash = payloadHash(input);

    if (input.utility_type === "water") {
      await isolations.createWaterIsolation({
        tenantId: context.tenant_id,
        workOrderId: workOrder.workOrderId,
        approvalId: requestId,
        interruptionId,
        requiredScopeId: requiredScope.id,
        scopeIds: input.scope_ids,
        reason: input.reason,
        plannedStart,
        plannedEnd,
        requestDetail: detail,
        requestHash,
      });
    } else {
      await approvalRequests.create({
        requestId,
        kind: "power_isolation",
        tenantId: context.tenant_id,
        buildingId: input.building_id,
        incidentId: workOrder.ticketId,
        workOrderId: workOrder.workOrderId,
        status: "pending",
        requiredApproverScope: requiredScope.id,
        detail,
        requestHash,
        requestedBy,
        sourceRunId: context.source_run_id,
        createdAt: now,
        interruption: {
          interruptionId,
          utility: "power",
          status: "proposed",
          scopeIds: [...input.scope_ids],
          plannedStart,
          plannedEnd,
        },
      });
    }

    return {
      status: "PENDING_APPROVAL",
      data: {
        request_id: requestId,
        interruption_id: interruptionId,
        approval_status: "PENDING_APPROVAL" as const,
        required_scope_id: requiredScope.id,
        created_at: now.toISOString(),
      },
      provenance: provenanceOf(
        [{ id: requestId, version: 1 }],
        now.toISOString(),
        input.utility_type === "water" ? APPLICATION_DB : APPROVAL_ADAPTER,
      ),
      resultCount: 1,
    };
  },
});
