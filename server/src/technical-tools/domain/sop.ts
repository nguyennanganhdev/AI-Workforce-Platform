/**
 * One acceptance criterion of a SOP, as something code can check.
 *
 * `sop_kb.retrieve` only hands the agent each criterion's `text`, which is what tools.md §3.1's
 * output schema asks for. The `check` beside it is for `technical.verify_resolution`, which has to
 * decide VERIFIED, NEEDS_EVIDENCE or HUMAN_REVIEW: a criterion written only as a sentence would
 * leave that decision to a model reading prose, and general.md §3.1 forbids the agent inventing
 * measurements or evidence. `manual` is the honest answer for a criterion only a person can settle,
 * and always leads to HUMAN_REVIEW rather than to a guess.
 */
export type AcceptanceCriterion = {
  id: string;
  text: string;
  check:
    | { kind: "checklist"; itemCode: string }
    | { kind: "evidence"; purpose: "before" | "after"; min: number }
    | {
        kind: "measurement";
        metric: string;
        op: "<=" | ">=" | "between";
        value: number | [number, number];
        unit: string;
      }
    | { kind: "manual" };
};

/** A row of `document_acl`, as the eligibility rules read it. */
export type DocumentAclEntry = {
  principalKind: string;
  roleCode: string | null;
  userId: string | null;
  workspaceId: string | null;
  effect: string;
};

/** The active version of a document, where it has one. */
export type DocumentVersionRecord = {
  id: string;
  versionNo: number;
  effectiveFrom: Date;
  effectiveTo: Date | null;
  contentHash: string;
};

/**
 * A knowledge document whose scope covers the building asked about, with everything needed to
 * decide whether it may be used and nothing yet decided.
 *
 * `status`, `language` and the ACL rows are carried as the tables hold them. Whether this document
 * counts as a usable SOP is `sop-rules`' question, in one place, so a second adapter cannot answer
 * it differently.
 */
export type SopDocumentRecord = {
  documentId: string;
  code: string;
  title: string;
  status: string;
  /** `knowledge_bases.status`. A retired collection's documents are not guidance any more. */
  knowledgeBaseStatus: string;
  language: string;
  activeVersion: DocumentVersionRecord | null;
  acl: DocumentAclEntry[];
  updatedAt: Date;
};

/**
 * What a document is about, and what counts as done.
 *
 * Neither is in the schema: `knowledge_documents` has no link to an issue code, and the acceptance
 * criteria live inside the document's file in object storage. Both are recorded as gaps for the
 * schema owner in docs/teams/quang/requests/; until they exist, this profile supplies them, keyed
 * by the document's own code and version so it cannot drift onto a different revision.
 */
export type SopProfile = {
  code: string;
  versionNo: number;
  issueCodes: readonly string[];
  excerpt: string;
  acceptanceCriteria: readonly AcceptanceCriterion[];
};

/** A SOP the caller may use, ready to be reported. */
export type EligibleSop = {
  record: SopDocumentRecord;
  version: DocumentVersionRecord;
  profile: SopProfile;
};
