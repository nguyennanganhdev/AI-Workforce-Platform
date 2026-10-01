import {
  verifyResolutionInputSchema,
  verifyResolutionOutputSchema,
} from "../contracts/verification";
import { defineTool } from "../tool";
import {
  APPLICATION_DB,
  buildingNotFound,
  conflict,
  notFound,
  provenanceOf,
} from "./outcomes";
import { resolveSops } from "./verification-rules";
import {
  aclSubjectOf,
  checksOutput,
  verifyFromSources,
} from "./verification-sources";

const EXECUTOR_RESULT_ADAPTER = "executor_result_adapter";

/**
 * `technical.verify_resolution` (tools.md §5.1).
 *
 * Checks a technician's submitted result against the SOP's acceptance criteria and the evidence as
 * it stands now, and recommends VERIFIED, NEEDS_EVIDENCE or HUMAN_REVIEW. A recommendation only:
 * the work order and the ticket are not touched, and nothing is written to the maintenance
 * history. Accepting the work is a person's decision; this tool tells them whether the records
 * support it.
 */
export const verifyResolutionTool = defineTool({
  name: "technical.verify_resolution",
  version: "1.0.0",
  description:
    "Check a submitted executor result against the acceptance criteria of the SOPs you name " +
    "and the photos and measurements as they stand now, and recommend VERIFIED, NEEDS_EVIDENCE " +
    "or HUMAN_REVIEW with each check and its sources. It never closes the ticket or the work " +
    "order and never writes maintenance history: VERIFIED means hand the case to a person with " +
    "authority to accept it. Without a SOP to check against the answer is HUMAN_REVIEW.",
  effect: "read",
  capability: "resolution:verify",
  timeoutMs: 5_000,
  inputSchema: verifyResolutionInputSchema,
  outputSchema: verifyResolutionOutputSchema,
  async run(context, input, dependencies) {
    const { workOrders, executorResults, sop, sopProfiles, clock } =
      dependencies;

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

    // A result of another work order is answered as if it did not exist, like one in another building.
    const result = await executorResults.findById(
      context.tenant_id,
      input.result_id,
    );
    if (!result || result.workOrderId !== workOrder.workOrderId) {
      return notFound(
        "No submitted result with that id is on this work order.",
        {
          field: "result_id",
        },
      );
    }

    const now = clock.now();
    const requested = input.sop_document_ids ?? [];
    let sops: Awaited<ReturnType<typeof resolveSops>>["sops"] = [];
    if (requested.length > 0) {
      const records = await sop.listForBuilding({
        tenantId: context.tenant_id,
        buildingId: input.building_id,
      });
      if (records === null) return buildingNotFound();
      const resolved = resolveSops(
        requested.map((documentId) => ({ kind: "document", documentId })),
        records,
        (code, versionNo) => sopProfiles.find(code, versionNo),
        now,
        aclSubjectOf(context),
      );
      if (resolved.problems.length > 0) {
        return conflict(resolved.problems, "sop_document_ids");
      }
      sops = resolved.sops;
    }

    const verification = await verifyFromSources(context, dependencies, {
      workOrder,
      result,
      sops,
    });

    const retrievedAt = now.toISOString();
    return {
      status: "OK",
      data: {
        verification_status: verification.status,
        checks: checksOutput(verification),
        required_actions: verification.requiredActions,
        source_refs: verification.sourceRefs,
      },
      provenance: [
        ...provenanceOf(
          [{ id: workOrder.workOrderId }],
          retrievedAt,
          APPLICATION_DB,
        ),
        ...provenanceOf(
          [{ id: result.resultId, version: 1 }],
          retrievedAt,
          EXECUTOR_RESULT_ADAPTER,
        ),
        ...(requested.length > 0
          ? provenanceOf(
              requested.map((documentId, index) => ({
                id: documentId,
                version: sops[index]?.versionNo ?? null,
              })),
              retrievedAt,
              APPLICATION_DB,
            )
          : []),
      ],
      resultCount: verification.checks.length,
    };
  },
});
