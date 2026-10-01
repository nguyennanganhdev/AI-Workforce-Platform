export type ChecklistItem = {
  itemCode: string;
  status: "passed" | "failed" | "not_applicable";
  note?: string;
};

export type Part = { name: string; quantity: number; unit?: string };

export const VALIDATION_STATUSES = [
  "ACCEPTED",
  "NEEDS_EVIDENCE",
  "HUMAN_REVIEW",
] as const;

export type ValidationStatus = (typeof VALIDATION_STATUSES)[number];

/**
 * What a technician submitted for a work order, with the first check of it.
 *
 * `validationStatus` says whether the submission is complete enough to be verified, not whether the
 * work is done. Accepting a result changes nothing about the work order or the ticket; closing
 * either is for `technical.verify_resolution` and a person with the authority to do it.
 */
export type ExecutorResult = {
  resultId: string;
  tenantId: string;
  buildingId: string;
  workOrderId: string;
  assignmentId: string;
  /** The user the run acted for when this was submitted. */
  submittedBy: string;
  checklist: readonly ChecklistItem[];
  measurementIds: readonly string[];
  parts: readonly Part[];
  evidenceIds: readonly string[];
  diagnosis: string | null;
  repairNotes: string | null;
  startedAt: Date;
  completedAt: Date;
  validationStatus: ValidationStatus;
  missingEvidence: readonly string[];
  conflicts: readonly string[];
  createdAt: Date;
  sourceRunId: string;
};
