import type {
  DocumentAclEntry,
  EligibleSop,
  SopDocumentRecord,
  SopProfile,
} from "../domain/sop";
import { normalizeText, termMatchCount } from "./text";

/** Who is asking, as `document_acl` describes principals. */
export type AclSubject = {
  roleCode?: string;
  userId?: string;
  workspaceId?: string;
};

export type AclDecision = "allow" | "deny" | "unset";

function matchesSubject(entry: DocumentAclEntry, subject: AclSubject): boolean {
  switch (entry.principalKind) {
    case "role":
      return Boolean(entry.roleCode) && entry.roleCode === subject.roleCode;
    case "user":
      return Boolean(entry.userId) && entry.userId === subject.userId;
    case "workspace":
      return (
        Boolean(entry.workspaceId) && entry.workspaceId === subject.workspaceId
      );
    default:
      // A principal kind the table does not define matches nobody.
      return false;
  }
}

/**
 * What the document's access list says about this caller.
 *
 * Deny beats allow, and a document with no row for the caller is refused rather than shared: the
 * data dictionary's rule for `document_acl` is that absence of a grant is a refusal. `unset` is
 * kept apart from `deny` because they are different facts about the configuration, even though
 * both end in the caller not reading the document.
 */
export function aclDecision(
  acl: readonly DocumentAclEntry[],
  subject: AclSubject,
): AclDecision {
  const matching = acl.filter((entry) => matchesSubject(entry, subject));
  if (matching.some((entry) => entry.effect === "deny")) return "deny";
  if (matching.some((entry) => entry.effect === "allow")) return "allow";
  return "unset";
}

/** Whether the version was in force at `at`, over `[effective_from, effective_to)`. */
export function isInForce(
  version: { effectiveFrom: Date; effectiveTo: Date | null },
  at: Date,
): boolean {
  if (at.getTime() < version.effectiveFrom.getTime()) return false;
  return (
    version.effectiveTo === null || at.getTime() < version.effectiveTo.getTime()
  );
}

/**
 * Whether this document is a SOP the agent may be guided by at all.
 *
 * `published` with a version in force, and nothing else: tools.md §3.1 forbids falling back to a
 * draft, an archived document or a lapsed version. A draft is somebody's work in progress, and a
 * lapsed version is guidance that has been replaced — following either on site is the failure this
 * rule exists to prevent.
 */
export function isUsable(
  record: SopDocumentRecord,
  at: Date,
  language: string,
): boolean {
  if (record.status !== "published") return false;
  if (record.knowledgeBaseStatus !== "active") return false;
  if (record.language !== language) return false;
  if (!record.activeVersion) return false;
  return isInForce(record.activeVersion, at);
}

export type SopSelection =
  | { outcome: "found"; documents: EligibleSop[] }
  /** No document in scope covers this issue code, or none of them is usable. */
  | { outcome: "none" }
  /** Usable documents exist here, and the caller may read none of them. */
  | { outcome: "forbidden" };

export type SopSelectionInput = {
  records: readonly SopDocumentRecord[];
  profile(code: string, versionNo: number): SopProfile | undefined;
  issueCode: string;
  at: Date;
  language: string;
  subject: AclSubject;
  terms: readonly string[];
  limit: number;
};

/**
 * The SOPs to report, in the order to report them.
 *
 * The issue code decides which documents are candidates; the query only orders them. A document
 * whose wording shares nothing with the query is still returned, last: the agent already knows
 * which fault it has, and dropping the one approved SOP for that fault because a technician
 * phrased the question differently would leave it with no guidance at all.
 *
 * Ranking is by how many of the query's words the document mentions, then by code, so the same
 * question always gets the same order. It is not a relevance model, and nothing here decides
 * anything a person is accountable for.
 */
export function selectSops(input: SopSelectionInput): SopSelection {
  const candidates = input.records.flatMap((record) => {
    if (!record.activeVersion) return [];
    const profile = input.profile(record.code, record.activeVersion.versionNo);
    if (!profile?.issueCodes.includes(input.issueCode)) return [];
    return [{ record, version: record.activeVersion, profile }];
  });
  if (candidates.length === 0) return { outcome: "none" };

  const usable = candidates.filter(({ record }) =>
    isUsable(record, input.at, input.language),
  );
  if (usable.length === 0) return { outcome: "none" };

  const permitted = usable.filter(
    ({ record }) => aclDecision(record.acl, input.subject) === "allow",
  );
  if (permitted.length === 0) return { outcome: "forbidden" };

  const ranked = permitted
    .map((sop) => ({
      sop,
      score: termMatchCount(
        normalizeText(
          [
            sop.record.title,
            sop.record.code,
            sop.profile.excerpt,
            ...sop.profile.acceptanceCriteria.map(
              (criterion) => criterion.text,
            ),
          ].join(" "),
        ),
        input.terms,
      ),
    }))
    .sort(
      (left, right) =>
        right.score - left.score ||
        left.sop.record.code.localeCompare(right.sop.record.code),
    );

  return {
    outcome: "found",
    documents: ranked.slice(0, input.limit).map(({ sop }) => sop),
  };
}
