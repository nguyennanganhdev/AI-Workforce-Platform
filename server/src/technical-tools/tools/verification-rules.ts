import type { ExecutorResult } from "../domain/executor-result";
import type { Measurement } from "../domain/measurement";
import type {
  AcceptanceCriterion,
  SopDocumentRecord,
  SopProfile,
} from "../domain/sop";
import type {
  Check,
  SopBasis,
  Verification,
  VerificationStatus,
} from "../domain/verification";
import type { EvidenceLookup } from "../domain/work-order";
import { evidenceProblems } from "./evidence-rules";
import { normalize } from "./measurement-rules";
import { type AclSubject, aclDecision, isUsable } from "./sop-rules";

/** The one thing a recommendation always asks for: a person with authority to accept it. */
export const HAND_OVER = "Chuyển người có thẩm quyền xác nhận hoàn tất";

export type VerificationInput = {
  result: ExecutorResult;
  /** What each of the result's evidence ids is now, looked up at the time of verifying. */
  evidence: readonly EvidenceLookup[];
  /** The measurements the result cites. Append-only, so what was cited is what is there. */
  measurements: readonly Measurement[];
  ticketId: string;
  assignmentAcceptedAt: Date | null;
  sops: readonly SopBasis[];
};

const resultRef = (result: ExecutorResult) => `result:${result.resultId}`;
const docRef = (sop: SopBasis) => `doc:${sop.code}:v${sop.versionNo}`;

const check = (
  criterion: string,
  status: Check["status"],
  sourceRefs: string[],
  settledBy: Check["settledBy"] = null,
): Check => ({ criterion, status, sourceRefs, settledBy });

function compare(
  value: number,
  op: "<=" | ">=" | "between",
  bound: number | [number, number],
): boolean {
  if (op === "between") {
    const [low, high] = Array.isArray(bound) ? bound : [bound, bound];
    return value >= low && value <= high;
  }
  const limit = Array.isArray(bound) ? bound[0] : bound;
  return op === "<=" ? value <= limit : value >= limit;
}

/**
 * A SOP's threshold in its metric's canonical unit, so it compares with a normalised measurement.
 * `null` when the SOP names a unit the metric is not recorded in, which only a person can resolve.
 */
function canonicalBound(
  criterion: Extract<AcceptanceCriterion["check"], { kind: "measurement" }>,
): number | [number, number] | null {
  const convert = (value: number) => {
    const converted = normalize(criterion.metric, value, criterion.unit);
    return converted.ok ? converted.value : null;
  };
  if (Array.isArray(criterion.value)) {
    const [low, high] = criterion.value.map(convert);
    return low === null ||
      high === null ||
      low === undefined ||
      high === undefined
      ? null
      : [low, high];
  }
  return convert(criterion.value);
}

function criterionCheck(
  sop: SopBasis,
  criterion: AcceptanceCriterion,
  input: VerificationInput,
  usableEvidence: readonly Extract<EvidenceLookup, { kind: "evidence" }>[],
): Check {
  const label = `${sop.code} v${sop.versionNo}: ${criterion.text}`;
  const ref = docRef(sop);
  const rule = criterion.check;

  switch (rule.kind) {
    case "checklist": {
      const item = input.result.checklist.find(
        (candidate) => candidate.itemCode === rule.itemCode,
      );
      if (item?.status === "passed") {
        return check(label, "passed", [ref, resultRef(input.result)]);
      }
      if (item?.status === "failed") {
        return check(label, "failed", [ref, resultRef(input.result)]);
      }
      // Not reported, or marked not applicable when the SOP requires it.
      return check(label, "unknown", [ref], "evidence");
    }
    case "evidence": {
      const photos = usableEvidence.filter(
        (photo) => photo.purpose === rule.purpose,
      );
      return photos.length >= rule.min
        ? check(label, "passed", [
            ref,
            ...photos.map((photo) => `evidence:${photo.id}`),
          ])
        : check(label, "unknown", [ref], "evidence");
    }
    case "measurement": {
      const latest = [...input.measurements]
        .filter((measurement) => measurement.metric === rule.metric)
        .sort((a, b) => b.measuredAt.getTime() - a.measuredAt.getTime())[0];
      if (!latest) return check(label, "unknown", [ref], "evidence");
      const bound = canonicalBound(rule);
      const refs = [ref, `measurement:${latest.measurementId}`];
      if (bound === null) return check(label, "conflict", refs, "person");
      return compare(latest.normalizedValue, rule.op, bound)
        ? check(label, "passed", refs)
        : check(label, "failed", refs);
    }
    case "manual":
      // A person's judgement, which no record here can stand in for.
      return check(label, "unknown", [ref], "person");
  }
}

/**
 * The recommendation on a result, by rules in a fixed order and never by a model reading notes.
 *
 * Recomputed from the records as they are now, not read off the status stored when the result was
 * submitted. A photo can be withdrawn after the fact and a SOP can lapse; a recommendation that
 * trusted the earlier status would accept work against evidence that no longer exists.
 *
 * - HUMAN_REVIEW: anything failed or contradictory, or anything only a person can settle,
 *   including there being no SOP to check against at all.
 * - NEEDS_EVIDENCE: otherwise, anything the technician could still supply.
 * - VERIFIED: every check passed.
 */
export function verify(input: VerificationInput): Verification {
  const { result } = input;
  const cited = new Set(result.evidenceIds);
  const lookups = input.evidence.filter((lookup) => cited.has(lookup.id));
  const usableEvidence = lookups.filter(
    (lookup): lookup is Extract<EvidenceLookup, { kind: "evidence" }> =>
      lookup.kind === "evidence" &&
      evidenceProblems([lookup.id], [lookup], input.ticketId).length === 0,
  );

  const checks: Check[] = [];

  const failedItems = result.checklist.filter(
    (item) => item.status === "failed",
  );
  checks.push(
    check(
      "Không có mục checklist nào không đạt",
      failedItems.length > 0 ? "failed" : "passed",
      [resultRef(result)],
    ),
  );

  if (input.measurements.length > 0) {
    const unusual = input.measurements.filter((measurement) =>
      measurement.qualityFlags.includes("out_of_expected_range"),
    );
    checks.push(
      check(
        "Số đo nằm trong khoảng thường gặp",
        unusual.length > 0 ? "conflict" : "passed",
        (unusual.length > 0 ? unusual : input.measurements).map(
          (measurement) => `measurement:${measurement.measurementId}`,
        ),
        unusual.length > 0 ? "person" : null,
      ),
    );
  }

  const finishedTooEarly =
    input.assignmentAcceptedAt !== null &&
    result.completedAt.getTime() < input.assignmentAcceptedAt.getTime();
  checks.push(
    check(
      "Hoàn tất sau thời điểm nhận việc",
      finishedTooEarly ? "conflict" : "passed",
      [resultRef(result)],
      finishedTooEarly ? "person" : null,
    ),
  );

  if (result.evidenceIds.length > 0) {
    const lapsed = result.evidenceIds.filter(
      (id) => !usableEvidence.some((photo) => photo.id === id),
    );
    checks.push(
      lapsed.length > 0
        ? check(
            "Bằng chứng đã nộp vẫn còn hiệu lực",
            "unknown",
            lapsed.map((id) => `evidence:${id}`),
            "evidence",
          )
        : check(
            "Bằng chứng đã nộp vẫn còn hiệu lực",
            "passed",
            result.evidenceIds.map((id) => `evidence:${id}`),
          ),
    );
  }

  const afterPhotos = usableEvidence.filter(
    (photo) => photo.purpose === "after",
  );
  checks.push(
    afterPhotos.length > 0
      ? check(
          "Có ảnh sau khi sửa chữa",
          "passed",
          afterPhotos.map((photo) => `evidence:${photo.id}`),
        )
      : check("Có ảnh sau khi sửa chữa", "unknown", [], "evidence"),
  );

  if (input.sops.length === 0) {
    checks.push(
      check("Có SOP được duyệt để đối chiếu", "unknown", [], "person"),
    );
  }
  for (const sop of input.sops) {
    for (const criterion of sop.criteria) {
      checks.push(criterionCheck(sop, criterion, input, usableEvidence));
    }
  }

  const needsPerson = checks.filter(
    (item) =>
      item.status === "failed" ||
      item.status === "conflict" ||
      (item.status === "unknown" && item.settledBy === "person"),
  );
  const needsEvidence = checks.filter(
    (item) => item.status === "unknown" && item.settledBy === "evidence",
  );

  const status: VerificationStatus =
    needsPerson.length > 0
      ? "HUMAN_REVIEW"
      : needsEvidence.length > 0
        ? "NEEDS_EVIDENCE"
        : "VERIFIED";

  const requiredActions =
    status === "VERIFIED"
      ? [HAND_OVER]
      : [
          ...needsPerson.map(
            (item) => `Chuyển người có thẩm quyền xem xét: ${item.criterion}`,
          ),
          ...needsEvidence.map(
            (item) => `Bổ sung bằng chứng: ${item.criterion}`,
          ),
        ];

  return {
    status,
    checks,
    requiredActions,
    sourceRefs: [resultRef(result), ...input.sops.map(docRef)],
  };
}

/** A SOP a caller names, by document id or by the `doc:<code>:v<n>` reference a result cites. */
export type SopRequest =
  | { kind: "document"; documentId: string }
  | { kind: "reference"; code: string; versionNo: number };

const DOC_REF = /^doc:(.+):v(\d+)$/;

/** The SOPs a list of source references cites. Other references are not SOPs and are ignored. */
export function sopReferences(sourceRefs: readonly string[]): SopRequest[] {
  return sourceRefs.flatMap((ref) => {
    const match = DOC_REF.exec(ref);
    return match?.[1] && match[2]
      ? [
          {
            kind: "reference" as const,
            code: match[1],
            versionNo: Number(match[2]),
          },
        ]
      : [];
  });
}

/**
 * The SOPs to verify against, or why some cannot be used.
 *
 * The same test `sop_kb.retrieve` applies: published, in its knowledge base's active collection, a
 * version in force now, and readable by the caller. A reference to a version other than the one in
 * force is refused too: verifying against a replaced version would accept work by criteria that
 * no longer apply.
 */
export function resolveSops(
  requests: readonly SopRequest[],
  records: readonly SopDocumentRecord[],
  profile: (code: string, versionNo: number) => SopProfile | undefined,
  at: Date,
  subject: AclSubject,
): { sops: SopBasis[]; problems: string[] } {
  const sops: SopBasis[] = [];
  const problems: string[] = [];

  for (const request of requests) {
    const name =
      request.kind === "document"
        ? `document ${request.documentId}`
        : `doc:${request.code}:v${request.versionNo}`;
    const record = records.find((candidate) =>
      request.kind === "document"
        ? candidate.documentId === request.documentId
        : candidate.code === request.code,
    );
    if (!record) {
      problems.push(`${name} is not a SOP in this building`);
      continue;
    }
    if (!isUsable(record, at, record.language) || !record.activeVersion) {
      problems.push(`${name} is not a published SOP in force`);
      continue;
    }
    if (
      request.kind === "reference" &&
      record.activeVersion.versionNo !== request.versionNo
    ) {
      problems.push(
        `${name} is not the version in force (v${record.activeVersion.versionNo})`,
      );
      continue;
    }
    if (aclDecision(record.acl, subject) !== "allow") {
      problems.push(`${name} may not be read by the caller`);
      continue;
    }
    const found = profile(record.code, record.activeVersion.versionNo);
    if (!found) {
      problems.push(`${name} has no acceptance criteria on record`);
      continue;
    }
    sops.push({
      code: record.code,
      versionNo: record.activeVersion.versionNo,
      criteria: found.acceptanceCriteria,
    });
  }

  return { sops, problems };
}
