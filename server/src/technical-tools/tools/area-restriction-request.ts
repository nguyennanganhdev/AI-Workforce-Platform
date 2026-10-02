import { randomUUID } from "node:crypto";
import {
  areaRestrictionInputSchema,
  areaRestrictionOutputSchema,
} from "../contracts/risk-request";
import { payloadHash } from "../idempotency";
import { defineTool } from "../tool";
import { evidenceProblems } from "./evidence-rules";
import { conflict, invalidInput, notFound, provenanceOf } from "./outcomes";
import { restrictionUntilProblem, sameArea } from "./request-rules";

const APPROVAL_ADAPTER = "approval_adapter";

/** Who decides on a restriction in a building: its management, not the technician who saw it. */
export const RESTRICTION_APPROVER = "building_management";

/**
 * `area_restriction.request` (tools.md §6.2).
 *
 * Asks for an area with a hazard in it to be cordoned off. It asks only: no door locks, no lift
 * stops, no sign goes up because of it. The answer is always PENDING_APPROVAL, and the building's
 * management decides.
 *
 * A request for an area that already has one waiting on the same incident is refused with the
 * earlier request's id, so the people deciding see one request per hazard rather than one per
 * agent turn.
 */
export const areaRestrictionRequestTool = defineTool({
  name: "area_restriction.request",
  version: "1.0.0",
  description:
    "Ask building management to cordon off an area with a hazard in it, for an incident, with " +
    "photo evidence. This only creates a request: the answer is always PENDING_APPROVAL, and " +
    "nothing is locked, stopped or signposted because of it. Tell people to keep clear only as " +
    "advice, never as an enforced restriction, until management approves. requested_until may " +
    "be at most 7 days away.",
  effect: "request",
  capability: "area_restriction:request",
  timeoutMs: 5_000,
  inputSchema: areaRestrictionInputSchema,
  outputSchema: areaRestrictionOutputSchema,
  async run(context, input, { workOrders, approvalRequests, clock }) {
    const now = clock.now();
    if (input.requested_until) {
      const problem = restrictionUntilProblem(
        new Date(input.requested_until),
        now,
      );
      if (problem) return invalidInput(problem, "requested_until");
    }

    const ticket = await workOrders.getTicket({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      ticketId: input.incident_id,
    });
    if (!ticket) {
      return notFound("No incident with that id is in this building.", {
        field: "incident_id",
      });
    }

    if (input.workorder_id) {
      const workOrder = await workOrders.getWorkOrder({
        tenantId: context.tenant_id,
        buildingId: input.building_id,
        workOrderId: input.workorder_id,
      });
      if (workOrder?.ticketId !== ticket.ticketId) {
        return conflict(
          [
            `work order ${input.workorder_id} does not belong to incident ${input.incident_id}`,
          ],
          "workorder_id",
        );
      }
    }

    const wrongEvidence = evidenceProblems(
      input.evidence_ids,
      await workOrders.findEvidence({
        tenantId: context.tenant_id,
        ids: input.evidence_ids,
      }),
      ticket.ticketId,
    );
    if (wrongEvidence.length > 0)
      return conflict(wrongEvidence, "evidence_ids");

    const waiting = (
      await approvalRequests.listOpen({
        tenantId: context.tenant_id,
        kind: "area_restriction",
        incidentId: ticket.ticketId,
      })
    ).filter((request) => sameArea(String(request.detail.area), input.area));
    if (waiting.length > 0) {
      return conflict(
        waiting.map(
          (request) =>
            `a restriction of this area is already waiting for approval: request ${request.requestId}`,
        ),
        "area",
      );
    }

    const requestId = randomUUID();
    await approvalRequests.create({
      requestId,
      kind: "area_restriction",
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      incidentId: ticket.ticketId,
      workOrderId: input.workorder_id ?? null,
      status: "pending",
      requiredApproverScope: RESTRICTION_APPROVER,
      detail: {
        area: input.area,
        hazard: input.hazard,
        reason: input.reason,
        evidence_ids: input.evidence_ids,
        requested_until: input.requested_until ?? null,
      },
      requestHash: payloadHash(input),
      requestedBy: context.user_id ?? context.principal_id,
      sourceRunId: context.source_run_id,
      createdAt: now,
    });

    return {
      status: "PENDING_APPROVAL",
      data: {
        request_id: requestId,
        approval_status: "PENDING_APPROVAL" as const,
        required_approver_scope: RESTRICTION_APPROVER,
        created_at: now.toISOString(),
      },
      provenance: provenanceOf(
        [{ id: requestId, version: 1 }],
        now.toISOString(),
        APPROVAL_ADAPTER,
      ),
      resultCount: 1,
    };
  },
});
