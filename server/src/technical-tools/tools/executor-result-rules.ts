import type {
  ChecklistItem,
  ValidationStatus,
} from "../domain/executor-result";
import type { Measurement } from "../domain/measurement";
import type { EvidenceLookup } from "../domain/work-order";

export type ValidationInput = {
  checklist: readonly ChecklistItem[];
  measurements: readonly Measurement[];
  /** The evidence already confirmed usable. */
  evidence: readonly EvidenceLookup[];
  completedAt: Date;
  assignmentAcceptedAt: Date | null;
};

export type Validation = {
  validationStatus: ValidationStatus;
  missingEvidence: string[];
  conflicts: string[];
};

/**
 * The first check of a submitted result: complete enough to verify, or not yet.
 *
 * Decided by rules in a fixed order, never by a model reading the notes. Anything a person must
 * weigh comes first: a failed checklist item, a measurement flagged as out of range, a finish time
 * before the technician even accepted the job. Then what is missing: without a photo taken after
 * the work there is nothing to verify the repair against. Only a result with neither is ACCEPTED.
 *
 * Missing evidence is reported even when a conflict already decides the status, so the technician
 * learns everything that needs fixing in one answer rather than one problem per round trip.
 */
export function validateResult(input: ValidationInput): Validation {
  const conflicts = [
    ...input.checklist
      .filter((item) => item.status === "failed")
      .map((item) => `checklist item ${item.itemCode} failed`),
    ...input.measurements
      .filter((measurement) =>
        measurement.qualityFlags.includes("out_of_expected_range"),
      )
      .map(
        (measurement) =>
          `measurement ${measurement.measurementId} is outside the expected range for ${measurement.metric}`,
      ),
    ...(input.assignmentAcceptedAt &&
    input.completedAt.getTime() < input.assignmentAcceptedAt.getTime()
      ? ["completed_at is earlier than the time the assignment was accepted"]
      : []),
  ];

  const hasAfterPhoto = input.evidence.some(
    (lookup) => lookup.kind === "evidence" && lookup.purpose === "after",
  );
  const missingEvidence = hasAfterPhoto ? [] : ["after_photo"];

  return {
    validationStatus:
      conflicts.length > 0
        ? "HUMAN_REVIEW"
        : missingEvidence.length > 0
          ? "NEEDS_EVIDENCE"
          : "ACCEPTED",
    missingEvidence,
    conflicts,
  };
}

/** Measurement ids that are unknown, or recorded against another work order. */
export function measurementProblems(
  requested: readonly string[],
  found: readonly Measurement[],
  workOrderId: string,
): string[] {
  const byId = new Map(found.map((m) => [m.measurementId, m]));
  return requested.flatMap((id) => {
    const measurement = byId.get(id);
    if (!measurement) return [`measurement ${id} does not exist`];
    if (measurement.workOrderId !== workOrderId) {
      return [`measurement ${id} was recorded for another work order`];
    }
    return [];
  });
}
