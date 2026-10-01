import { randomUUID } from "node:crypto";
import {
  apartmentEntryInputSchema,
  apartmentEntryOutputSchema,
} from "../contracts/entry-vendor";
import type { ContactAttempt } from "../domain/unit";
import { payloadHash } from "../idempotency";
import { defineTool } from "../tool";
import {
  contactIsSufficient,
  entryWindowProblem,
  hasCurrentResident,
  looksLikeCredential,
  requiredApprovals,
} from "./entry-rules";
import { evidenceProblems } from "./evidence-rules";
import { measuredInFuture } from "./measurement-rules";
import {
  conflict,
  forbidden,
  invalidInput,
  needsInput,
  notFound,
  provenanceOf,
} from "./outcomes";
import { worksOnIncident } from "./request-rules";

const APPROVAL_ADAPTER = "approval_adapter";

/**
 * `apartment_entry.request` (tools.md §6.3).
 *
 * Asks for permission to enter an apartment whose resident cannot be reached. It asks only: no
 * door is opened, and no code, PIN or password is taken in or handed out. A request that looks
 * like it carries one is refused without being stored, because a code written into a request is a
 * code every approver can read.
 *
 * The tool decides who must approve, from what the record says about the resident and what they
 * answered; the agent cannot choose an easier approver. And it will not ask at all until the
 * resident has been tried properly: one unanswered ring a minute ago is not "could not be reached".
 */
export const apartmentEntryRequestTool = defineTool({
  name: "apartment_entry.request",
  version: "1.0.0",
  description:
    "Ask for permission to enter an apartment whose resident cannot be reached, for an incident, " +
    "with the record of attempts to contact them. This only creates a request: the answer is " +
    "always PENDING_APPROVAL with who must approve, and nobody may enter until they do. Never " +
    "send or repeat a door code, PIN or password: a request carrying one is refused. Try the " +
    "resident twice, 15 minutes apart, within the last day (once for an emergency ticket) before " +
    "asking; otherwise the answer is NEEDS_INPUT.",
  effect: "request",
  capability: "apartment_entry:request",
  timeoutMs: 5_000,
  inputSchema: apartmentEntryInputSchema,
  outputSchema: apartmentEntryOutputSchema,
  async run(context, input, { workOrders, units, approvalRequests, clock }) {
    const now = clock.now();

    if (
      looksLikeCredential(input.reason) ||
      input.contact_attempts.some(
        (attempt) =>
          attempt.reference_id && looksLikeCredential(attempt.reference_id),
      )
    ) {
      // The message does not repeat the text: it would hand the code straight back.
      return invalidInput(
        "The request appears to contain a door code, PIN or password. Remove it: entry requests never carry credentials.",
        "reason",
      );
    }

    const attempts: ContactAttempt[] = input.contact_attempts.map(
      (attempt) => ({
        channel: attempt.channel,
        attemptedAt: new Date(attempt.attempted_at),
        outcome: attempt.outcome,
        ...(attempt.reference_id ? { referenceId: attempt.reference_id } : {}),
      }),
    );
    if (
      attempts.some((attempt) => measuredInFuture(attempt.attemptedAt, now))
    ) {
      return invalidInput(
        "A contact attempt is dated later than the server's clock. Report only attempts that were made.",
        "contact_attempts",
      );
    }
    if (input.requested_window) {
      const problem = entryWindowProblem(
        {
          from: new Date(input.requested_window.from),
          to: new Date(input.requested_window.to),
        },
        now,
      );
      if (problem) return invalidInput(problem, "requested_window");
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

    // tools.md §6.3: a unit outside this building is refused, not reported missing.
    const unit = await units.findUnit({
      tenantId: context.tenant_id,
      unitId: input.unit_id,
    });
    if (!unit || unit.buildingId !== input.building_id) return forbidden();

    const onTheJob = worksOnIncident(
      context.user_id,
      await workOrders.listWorkOrders({
        tenantId: context.tenant_id,
        buildingId: input.building_id,
        ticketId: ticket.ticketId,
      }),
    );
    if (!onTheJob && context.role_code !== "management") return forbidden();

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

    const waiting = (
      await approvalRequests.listOpen({
        tenantId: context.tenant_id,
        kind: "apartment_entry",
        incidentId: ticket.ticketId,
      })
    ).filter((request) => request.detail.unit_id === unit.unitId);
    if (waiting.length > 0) {
      return conflict(
        waiting.map(
          (request) =>
            `a request to enter ${unit.code} is already waiting for approval: request ${request.requestId}`,
        ),
        "unit_id",
      );
    }

    if (!contactIsSufficient(attempts, now, ticket.isEmergency)) {
      return needsInput(
        "The resident has not been tried enough to ask to enter without them. Try again: two attempts at least 15 minutes apart within the last day, or one for an emergency ticket.",
        ["contact_attempts"],
        { field: "contact_attempts" },
      );
    }

    const approvals = requiredApprovals(
      attempts,
      hasCurrentResident(
        await units.residents({
          tenantId: context.tenant_id,
          unitId: unit.unitId,
        }),
        now,
      ),
    );

    const requestId = randomUUID();
    await approvalRequests.create({
      requestId,
      kind: "apartment_entry",
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      incidentId: ticket.ticketId,
      workOrderId: null,
      status: "pending",
      requiredApproverScope: approvals.join(","),
      detail: {
        unit_id: unit.unitId,
        unit_code: unit.code,
        reason: input.reason,
        // How, when and how it went: never what was said.
        contact_attempts: input.contact_attempts.map((attempt) => ({
          channel: attempt.channel,
          attempted_at: attempt.attempted_at,
          outcome: attempt.outcome,
          reference_id: attempt.reference_id ?? null,
        })),
        requested_window: input.requested_window ?? null,
        evidence_ids: evidenceIds,
        required_approvals: approvals,
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
        required_approvals: approvals,
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
