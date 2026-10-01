import { randomUUID } from "node:crypto";
import {
  vendorDispatchInputSchema,
  vendorDispatchOutputSchema,
} from "../contracts/entry-vendor";
import { payloadHash } from "../idempotency";
import { defineTool } from "../tool";
import { evidenceProblems } from "./evidence-rules";
import {
  buildingNotFound,
  conflict,
  forbidden,
  notFound,
  provenanceOf,
} from "./outcomes";
import { worksOnIncident } from "./request-rules";
import { normalizeText } from "./text";
import { candidates } from "./vendor-rules";

const VENDOR_ADAPTER = "vendor_adapter";

/** What makes two dispatch requests the same: the specialty if named, the service otherwise. */
const needOf = (specialty: string | null | undefined, service: string) =>
  specialty
    ? `specialty:${specialty}`
    : `service:${normalizeText(service).trim()}`;

/**
 * `vendor_dispatch.request` (tools.md §6.4).
 *
 * Asks for an outside contractor with a specialty the team does not have, and lists the vendors who
 * could be engaged. It asks only: nobody is called, nothing is booked, no contract or cost is
 * committed. The candidate list is matching, not a choice; a person picks, and procurement engages.
 *
 * `urgency` is recorded with the request and changes nothing else. An agent saying "immediate"
 * does not make the ticket critical: priority belongs to triage, and a contractor request is not a
 * way round it.
 */
export const vendorDispatchRequestTool = defineTool({
  name: "vendor_dispatch.request",
  version: "1.0.0",
  description:
    "Ask for an outside contractor for an incident, and get the vendors in the catalogue " +
    "qualified for the specialty here. This only creates a request: the answer is always " +
    "PENDING_APPROVAL. Nobody is contacted, booked or paid, and no cost may be promised. urgency " +
    "is recorded and does not change the ticket's priority. Without required_specialty_code no " +
    "vendors are listed: the specialty is not guessed from the service text.",
  effect: "request",
  capability: "vendor_dispatch:request",
  timeoutMs: 5_000,
  inputSchema: vendorDispatchInputSchema,
  outputSchema: vendorDispatchOutputSchema,
  async run(
    context,
    input,
    { workOrders, scopes, vendors, approvalRequests, clock },
  ) {
    const now = clock.now();

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

    const raised = await workOrders.listWorkOrders({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      ticketId: ticket.ticketId,
    });
    if (
      input.workorder_id &&
      !raised.some((workOrder) => workOrder.workOrderId === input.workorder_id)
    ) {
      return conflict(
        [
          `work order ${input.workorder_id} does not belong to incident ${input.incident_id}`,
        ],
        "workorder_id",
      );
    }
    if (
      !worksOnIncident(context.user_id, raised) &&
      context.role_code !== "management"
    ) {
      return forbidden();
    }

    const evidenceIds = input.evidence_ids ?? [];
    if (evidenceIds.length > 0) {
      const wrong = evidenceProblems(
        evidenceIds,
        await workOrders.findEvidence({
          tenantId: context.tenant_id,
          ids: evidenceIds,
        }),
        ticket.ticketId,
      );
      if (wrong.length > 0) return conflict(wrong, "evidence_ids");
    }

    const need = needOf(input.required_specialty_code, input.service);
    const waiting = (
      await approvalRequests.listOpen({
        tenantId: context.tenant_id,
        kind: "vendor_dispatch",
        incidentId: ticket.ticketId,
      })
    ).filter(
      (request) =>
        needOf(
          request.detail.required_specialty_code as string | null,
          String(request.detail.service),
        ) === need,
    );
    if (waiting.length > 0) {
      return conflict(
        waiting.map(
          (request) =>
            `a contractor request for this need is already waiting for approval: request ${request.requestId}`,
        ),
        input.required_specialty_code ? "required_specialty_code" : "service",
      );
    }

    const building = await scopes.placement({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
    });
    if (!building) return buildingNotFound();
    const listed = input.required_specialty_code
      ? candidates(
          await vendors.findBySpecialty({
            tenantId: context.tenant_id,
            specialtyCode: input.required_specialty_code,
          }),
          building.siteId,
          now,
        )
      : [];

    const requestId = randomUUID();
    await approvalRequests.create({
      requestId,
      kind: "vendor_dispatch",
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      incidentId: ticket.ticketId,
      workOrderId: input.workorder_id ?? null,
      status: "pending",
      requiredApproverScope: "building_management",
      detail: {
        service: input.service,
        reason: input.reason,
        urgency: input.urgency,
        required_specialty_code: input.required_specialty_code ?? null,
        evidence_ids: evidenceIds,
        candidate_vendor_ids: listed.map((vendor) => vendor.vendorId),
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
        eligible_vendors: listed.map((vendor) => ({
          vendor_id: vendor.vendorId,
          display_name: vendor.displayName,
          qualification_status: vendor.qualificationStatus,
        })),
        created_at: now.toISOString(),
      },
      provenance: provenanceOf(
        [{ id: requestId, version: 1 }],
        now.toISOString(),
        VENDOR_ADAPTER,
      ),
      resultCount: listed.length,
    };
  },
});
