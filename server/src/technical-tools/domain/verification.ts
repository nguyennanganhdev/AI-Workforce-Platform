import type { AcceptanceCriterion } from "./sop";

export const VERIFICATION_STATUSES = [
  "VERIFIED",
  "NEEDS_EVIDENCE",
  "HUMAN_REVIEW",
] as const;

export type VerificationStatus = (typeof VERIFICATION_STATUSES)[number];

export const CHECK_STATUSES = [
  "passed",
  "failed",
  "unknown",
  "conflict",
] as const;

export type CheckStatus = (typeof CHECK_STATUSES)[number];

/**
 * One criterion a result was checked against, and what it came to.
 *
 * `settledBy` says who can close a check that is still `unknown`: more evidence from the
 * technician, or a person's judgement. A SOP criterion only a person can assess, or the absence of
 * any SOP to check against, is `unknown` in the same way a missing photo is, and the difference
 * between them is what separates NEEDS_EVIDENCE from HUMAN_REVIEW. It is not reported.
 */
export type Check = {
  criterion: string;
  status: CheckStatus;
  sourceRefs: string[];
  settledBy: "evidence" | "person" | null;
};

/** What a result was verified against: one SOP, at the version in force. */
export type SopBasis = {
  code: string;
  versionNo: number;
  criteria: readonly AcceptanceCriterion[];
};

/**
 * A recommendation on a submitted result, computed afresh from the records each time it is asked.
 *
 * VERIFIED recommends acceptance to a person with the authority to give it. Nothing about the work
 * order, the ticket or the maintenance history changes because of it.
 */
export type Verification = {
  status: VerificationStatus;
  checks: Check[];
  requiredActions: string[];
  sourceRefs: string[];
};
