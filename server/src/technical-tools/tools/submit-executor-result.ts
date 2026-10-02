import { randomUUID } from "node:crypto";
import {
  submitExecutorResultInputSchema,
  submitExecutorResultOutputSchema,
} from "../contracts/executor-result";
import type { ExecutorResult } from "../domain/executor-result";
import { defineTool } from "../tool";
import { evidenceProblems } from "./evidence-rules";
import { measurementProblems, validateResult } from "./executor-result-rules";
import { conflict, forbidden, notFound, provenanceOf } from "./outcomes";

/** The POC store names itself, so provenance does not imply the result is in the database. */
const EXECUTOR_RESULT_ADAPTER = "executor_result_adapter";

/**
 * `technical.submit_executor_result` (tools.md §4.3).
 *
 * Takes what a technician reports at the end of a job: the checklist, the measurements, the parts
 * and the photos. It records the submission and says whether it is complete enough to verify. It
 * does not complete anything: the work order and the ticket keep whatever state they had, because
 * a technician saying the job is done is not the job being accepted as done.
 *
 * Everything a result points at is checked before it is written. A photo still uploading, a
 * measurement from another job, an assignment the technician has already been released from: each
 * refuses the whole submission, since a result recorded with any of them silently dropped would be
 * judged against evidence the technician never meant to leave out.
 */
export const submitExecutorResultTool = defineTool({
  name: "technical.submit_executor_result",
  version: "1.0.0",
  description:
    "Submit a technician's result for a work order: checklist, measurement ids, parts, photo " +
    "evidence ids, diagnosis and notes. Returns ACCEPTED, NEEDS_EVIDENCE or HUMAN_REVIEW, which " +
    "says whether the submission can be verified; it never means the job is closed, and it does " +
    "not change the work order. Only submit what the technician reported. A photo that is still " +
    "uploading is refused: wait for it, then submit again with the same idempotency_key.",
  effect: "write",
  capability: "executor_result:submit",
  timeoutMs: 5_000,
  inputSchema: submitExecutorResultInputSchema,
  outputSchema: submitExecutorResultOutputSchema,
  async run(
    context,
    input,
    { workOrders, measurements, executorResults, clock },
  ) {
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

    const assignment = workOrder.assignments.find(
      (candidate) => candidate.assignmentId === input.assignment_id,
    );
    if (assignment?.status !== "accepted") {
      return conflict(
        [
          assignment
            ? `assignment ${input.assignment_id} is ${assignment.status}, not accepted`
            : `assignment ${input.assignment_id} is not an assignment of this work order`,
        ],
        "assignment_id",
      );
    }

    // The technician on the assignment, or management answering for the work in their scope.
    if (
      context.user_id !== assignment.staffUserId &&
      context.role_code !== "management"
    ) {
      return forbidden();
    }

    const measurementIds = input.measurement_ids ?? [];
    const found =
      measurementIds.length > 0
        ? await measurements.findByIds(context.tenant_id, measurementIds)
        : [];
    const wrongMeasurements = measurementProblems(
      measurementIds,
      found,
      workOrder.workOrderId,
    );
    if (wrongMeasurements.length > 0) {
      return conflict(wrongMeasurements, "measurement_ids");
    }

    const evidenceIds = input.evidence_ids ?? [];
    const evidence =
      evidenceIds.length > 0
        ? await workOrders.findEvidence({
            tenantId: context.tenant_id,
            ids: evidenceIds,
          })
        : [];
    const wrongEvidence = evidenceProblems(
      evidenceIds,
      evidence,
      workOrder.ticketId,
    );
    if (wrongEvidence.length > 0)
      return conflict(wrongEvidence, "evidence_ids");

    const completedAt = new Date(input.completed_at);
    const checklist = input.checklist.map((item) => ({
      itemCode: item.item_code,
      status: item.status,
      ...(item.note ? { note: item.note } : {}),
    }));
    const validation = validateResult({
      checklist,
      measurements: found,
      evidence,
      completedAt,
      assignmentAcceptedAt: assignment.acceptedAt,
    });

    const now = clock.now();
    const result: ExecutorResult = {
      resultId: randomUUID(),
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      workOrderId: workOrder.workOrderId,
      assignmentId: assignment.assignmentId,
      submittedBy: context.user_id ?? context.principal_id,
      checklist,
      measurementIds,
      parts: input.parts ?? [],
      evidenceIds,
      diagnosis: input.diagnosis ?? null,
      repairNotes: input.repair_notes ?? null,
      startedAt: new Date(input.started_at),
      completedAt,
      ...validation,
      createdAt: now,
      sourceRunId: context.source_run_id,
    };
    await executorResults.append(result);

    return {
      status: "OK",
      data: {
        result_id: result.resultId,
        validation_status: result.validationStatus,
        created_at: result.createdAt.toISOString(),
        missing_evidence: [...result.missingEvidence],
        conflicts: [...result.conflicts],
      },
      provenance: provenanceOf(
        [{ id: result.resultId, version: 1 }],
        now.toISOString(),
        EXECUTOR_RESULT_ADAPTER,
      ),
      resultCount: 1,
    };
  },
});
