import { describe, expect, test } from "bun:test";
import type {
  EvidenceLookup,
  ExecutorResult,
  Measurement,
  SopBasis,
  SopDocumentRecord,
  SopProfile,
} from "../../src/technical-tools";
import {
  HAND_OVER,
  resolveSops,
  sopReferences,
  type VerificationInput,
  verify,
} from "../../src/technical-tools/tools/verification-rules";
import { sopByKey } from "./fixtures/sop";
import { NOW, USER } from "./fixtures/world";

/**
 * The decision `technical.verify_resolution` and `maintenance_history.append` share, as a plain
 * function: no database, no store, no host.
 *
 * The SOPs are the sample estate's own: SOP-HVAC-012 (a checklist item and a photo after),
 * SOP-ELEC-001 (a leakage current threshold as well), SOP-PLUMB-020 (a moisture threshold and a
 * criterion only an engineer can sign off).
 */
const TICKET = "ticket-ac";

const basis = (key: string): SopBasis => {
  const sop = sopByKey(key);
  return {
    code: sop.code,
    versionNo: sop.version?.versionNo ?? 0,
    criteria: sop.acceptanceCriteria,
  };
};
const HVAC = basis("S2");
const ELEC = basis("S1");
const PLUMB = basis("S3");

const photo = (
  id: string,
  purpose: string,
  change: Partial<Extract<EvidenceLookup, { kind: "evidence" }>> = {},
): EvidenceLookup => ({
  kind: "evidence",
  id,
  ticketId: TICKET,
  workOrderId: "wo",
  assignmentId: "as",
  purpose,
  status: "active",
  fileStatus: "ready",
  ...change,
});

const measured = (
  id: string,
  metric: string,
  value: number,
  change: Partial<Measurement> = {},
): Measurement => ({
  measurementId: id,
  tenantId: "tenant",
  buildingId: "building",
  workOrderId: "wo",
  assetId: null,
  metric,
  rawValue: value,
  rawUnit: "",
  normalizedValue: value,
  normalizedUnit: "",
  measuredAt: new Date("2026-09-30T08:48:00Z"),
  measuredBy: { kind: "technician", sourceId: USER.technician },
  source: "instrument",
  evidenceIds: [],
  qualityFlags: [],
  createdAt: NOW,
  sourceRunId: "run",
  ...change,
});

const submitted = (change: Partial<ExecutorResult> = {}): ExecutorResult => ({
  resultId: "ER-1",
  tenantId: "tenant",
  buildingId: "building",
  workOrderId: "wo",
  assignmentId: "as",
  submittedBy: USER.technician,
  checklist: [{ itemCode: "DRAIN_CLEAR", status: "passed" }],
  measurementIds: [],
  parts: [],
  evidenceIds: ["EV-BEFORE", "EV-AFTER"],
  diagnosis: null,
  repairNotes: null,
  startedAt: new Date("2026-09-30T08:20:00Z"),
  completedAt: new Date("2026-09-30T08:55:00Z"),
  validationStatus: "ACCEPTED",
  missingEvidence: [],
  conflicts: [],
  createdAt: NOW,
  sourceRunId: "run",
  ...change,
});

/** The air conditioner job, complete, checked against SOP-HVAC-012. */
const complete = (
  change: Partial<VerificationInput> = {},
): VerificationInput => ({
  result: submitted(),
  evidence: [photo("EV-BEFORE", "before"), photo("EV-AFTER", "after")],
  measurements: [],
  ticketId: TICKET,
  assignmentAcceptedAt: new Date("2026-09-30T07:30:00Z"),
  sops: [HVAC],
  ...change,
});

const statusOf = (input: VerificationInput) => verify(input).status;
const checkNamed = (input: VerificationInput, fragment: string) =>
  verify(input).checks.find((item) => item.criterion.includes(fragment));

describe("everything in order", () => {
  test("is VERIFIED, and the only action is handing it to a person", () => {
    const verification = verify(complete());
    expect(verification.status).toBe("VERIFIED");
    expect(verification.requiredActions).toEqual([HAND_OVER]);
    expect(verification.checks.every((item) => item.status === "passed")).toBe(
      true,
    );
  });

  test("names the result and the SOP version it was checked against", () => {
    expect(verify(complete()).sourceRefs).toEqual([
      "result:ER-1",
      "doc:SOP-HVAC-012:v3",
    ]);
  });

  test("each SOP criterion is a check of its own, pinned to the SOP version", () => {
    const check = checkNamed(complete(), "Không còn rò");
    expect(check).toMatchObject({
      criterion: "SOP-HVAC-012 v3: Không còn rò tại thời điểm kiểm tra",
      status: "passed",
      sourceRefs: ["doc:SOP-HVAC-012:v3", "result:ER-1"],
    });
  });

  test("a photo criterion cites the photos that satisfied it", () => {
    expect(checkNamed(complete(), "Có ảnh trước và sau")?.sourceRefs).toEqual([
      "doc:SOP-HVAC-012:v3",
      "evidence:EV-AFTER",
    ]);
  });
});

/*
 * Things the technician can still supply. Nothing is wrong with the work; the record of it is
 * incomplete.
 */
describe("NEEDS_EVIDENCE: something the technician can still supply", () => {
  test("no photo from after the work", () => {
    const input = complete({
      result: submitted({ evidenceIds: ["EV-BEFORE"] }),
      evidence: [photo("EV-BEFORE", "before")],
    });
    expect(statusOf(input)).toBe("NEEDS_EVIDENCE");
    expect(checkNamed(input, "Có ảnh sau khi sửa chữa")?.status).toBe(
      "unknown",
    );
    expect(verify(input).requiredActions).toContain(
      "Bổ sung bằng chứng: Có ảnh sau khi sửa chữa",
    );
  });

  test("a checklist item the SOP requires and the result does not report", () => {
    const input = complete({
      result: submitted({
        checklist: [{ itemCode: "PIPE_SLOPE", status: "passed" }],
      }),
    });
    expect(statusOf(input)).toBe("NEEDS_EVIDENCE");
    expect(checkNamed(input, "Không còn rò")?.status).toBe("unknown");
  });

  test("a required item marked not applicable is still not done", () => {
    expect(
      statusOf(
        complete({
          result: submitted({
            checklist: [{ itemCode: "DRAIN_CLEAR", status: "not_applicable" }],
          }),
        }),
      ),
    ).toBe("NEEDS_EVIDENCE");
  });

  test("a measurement the SOP requires and nobody took", () => {
    const input = complete({
      sops: [ELEC],
      result: submitted({
        checklist: [{ itemCode: "BREAKER_HOLDS_LOAD", status: "passed" }],
      }),
    });
    expect(statusOf(input)).toBe("NEEDS_EVIDENCE");
    expect(checkNamed(input, "Dòng rò")?.status).toBe("unknown");
  });

  /*
   * The trap of trusting the past: when the result was submitted, the photo was there and the
   * result was ACCEPTED. It has since been withdrawn. The stored status says ACCEPTED; the records
   * say otherwise, and the records decide.
   */
  test("a photo withdrawn after the result was submitted no longer counts", () => {
    const input = complete({
      result: submitted({ validationStatus: "ACCEPTED" }),
      evidence: [
        photo("EV-BEFORE", "before"),
        photo("EV-AFTER", "after", { status: "withdrawn" }),
      ],
    });
    expect(statusOf(input)).toBe("NEEDS_EVIDENCE");
    expect(checkNamed(input, "vẫn còn hiệu lực")).toMatchObject({
      status: "unknown",
      sourceRefs: ["evidence:EV-AFTER"],
    });
  });

  test("so does a photo that has disappeared, or now belongs to another ticket", () => {
    expect(
      statusOf(complete({ evidence: [photo("EV-BEFORE", "before")] })),
    ).toBe("NEEDS_EVIDENCE");
    expect(
      statusOf(
        complete({
          evidence: [
            photo("EV-BEFORE", "before"),
            photo("EV-AFTER", "after", { ticketId: "ticket-leak" }),
          ],
        }),
      ),
    ).toBe("NEEDS_EVIDENCE");
  });

  test("a photo the result never cited does not count for it", () => {
    expect(
      statusOf(
        complete({
          result: submitted({ evidenceIds: ["EV-BEFORE"] }),
          evidence: [photo("EV-BEFORE", "before"), photo("EV-OTHER", "after")],
        }),
      ),
    ).toBe("NEEDS_EVIDENCE");
  });
});

/*
 * Things only a person can settle: the work may have failed, the sources disagree, or the SOP
 * itself says a person must sign it off.
 */
describe("HUMAN_REVIEW: something only a person can settle", () => {
  test("a failed checklist item", () => {
    const input = complete({
      result: submitted({
        checklist: [{ itemCode: "DRAIN_CLEAR", status: "failed" }],
      }),
    });
    expect(statusOf(input)).toBe("HUMAN_REVIEW");
    expect(checkNamed(input, "Không còn rò")?.status).toBe("failed");
    expect(checkNamed(input, "Không có mục checklist")?.status).toBe("failed");
  });

  test("a measurement over the SOP's threshold, which is also out of the expected range", () => {
    const input = complete({
      sops: [ELEC],
      result: submitted({
        checklist: [{ itemCode: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurementIds: ["MS-180"],
      }),
      measurements: [
        measured("MS-180", "leakage_current", 180, {
          qualityFlags: ["out_of_expected_range"],
        }),
      ],
    });
    expect(statusOf(input)).toBe("HUMAN_REVIEW");
    expect(checkNamed(input, "Dòng rò")).toMatchObject({
      status: "failed",
      sourceRefs: ["doc:SOP-ELEC-001:v3", "measurement:MS-180"],
    });
    expect(checkNamed(input, "khoảng thường gặp")?.status).toBe("conflict");
  });

  test("a SOP threshold is its own test, apart from the metric's expected range", () => {
    // 25 mA is under SOP-ELEC-001's 30 mA.
    const passes = complete({
      sops: [ELEC],
      result: submitted({
        checklist: [{ itemCode: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurementIds: ["MS-25"],
      }),
      measurements: [measured("MS-25", "leakage_current", 25)],
    });
    expect(statusOf(passes)).toBe("VERIFIED");
    // 18.5 % is inside surface moisture's ordinary range and over SOP-PLUMB-020's 18 %.
    const fails = complete({
      sops: [PLUMB],
      measurements: [measured("MS-M", "surface_moisture", 18.5)],
      result: submitted({ measurementIds: ["MS-M"] }),
    });
    expect(checkNamed(fails, "Độ ẩm")?.status).toBe("failed");
  });

  test("the latest measurement of a metric is the one judged", () => {
    const input = complete({
      sops: [ELEC],
      result: submitted({
        checklist: [{ itemCode: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurementIds: ["MS-BEFORE", "MS-AFTER"],
      }),
      measurements: [
        measured("MS-AFTER", "leakage_current", 12, {
          measuredAt: new Date("2026-09-30T08:50:00Z"),
        }),
        measured("MS-BEFORE", "leakage_current", 28, {
          measuredAt: new Date("2026-09-30T08:10:00Z"),
        }),
      ],
    });
    expect(checkNamed(input, "Dòng rò")?.sourceRefs).toContain(
      "measurement:MS-AFTER",
    );
  });

  test("a criterion the SOP leaves to a person is never settled by the records", () => {
    const input = complete({
      sops: [PLUMB],
      measurements: [measured("MS-M", "surface_moisture", 12)],
      result: submitted({ measurementIds: ["MS-M"] }),
    });
    expect(statusOf(input)).toBe("HUMAN_REVIEW");
    expect(checkNamed(input, "Kỹ sư cấp nước")).toMatchObject({
      status: "unknown",
    });
    expect(verify(input).requiredActions).toContain(
      "Chuyển người có thẩm quyền xem xét: SOP-PLUMB-020 v2: Kỹ sư cấp nước xác nhận đã thay đoạn ống bị rò",
    );
  });

  test("with no SOP to check against, the records alone are not enough", () => {
    const input = complete({ sops: [] });
    expect(statusOf(input)).toBe("HUMAN_REVIEW");
    expect(checkNamed(input, "Có SOP")?.status).toBe("unknown");
    expect(verify(input).sourceRefs).toEqual(["result:ER-1"]);
  });

  test("finished before the job was accepted", () => {
    const input = complete({
      result: submitted({ completedAt: new Date("2026-09-30T07:00:00Z") }),
    });
    expect(statusOf(input)).toBe("HUMAN_REVIEW");
    expect(checkNamed(input, "Hoàn tất sau")?.status).toBe("conflict");
  });

  test("a person's judgement outranks missing evidence, and both are listed", () => {
    const verification = verify(
      complete({
        result: submitted({
          checklist: [{ itemCode: "DRAIN_CLEAR", status: "failed" }],
          evidenceIds: [],
        }),
        evidence: [],
      }),
    );
    expect(verification.status).toBe("HUMAN_REVIEW");
    expect(
      verification.requiredActions.some((a) => a.startsWith("Bổ sung")),
    ).toBe(true);
    expect(verification.requiredActions).not.toContain(HAND_OVER);
  });

  test("a SOP threshold in a unit its metric is not recorded in is a contradiction", () => {
    const odd: SopBasis = {
      code: "SOP-ODD",
      versionNo: 1,
      criteria: [
        {
          id: "odd-1",
          text: "Dòng rò dưới 0.03 psi",
          check: {
            kind: "measurement",
            metric: "leakage_current",
            op: "<=",
            value: 0.03,
            unit: "psi",
          },
        },
      ],
    };
    const input = complete({
      sops: [odd],
      measurements: [measured("MS-1", "leakage_current", 12)],
      result: submitted({ measurementIds: ["MS-1"] }),
    });
    expect(checkNamed(input, "psi")?.status).toBe("conflict");
    expect(statusOf(input)).toBe("HUMAN_REVIEW");
  });

  test("a SOP threshold is compared in the metric's canonical unit", () => {
    const amps: SopBasis = {
      code: "SOP-AMPS",
      versionNo: 1,
      criteria: [
        {
          id: "amps-1",
          text: "Dòng rò dưới 0.03 A",
          check: {
            kind: "measurement",
            metric: "leakage_current",
            op: "<=",
            value: 0.03,
            unit: "A",
          },
        },
      ],
    };
    const at = (value: number) =>
      checkNamed(
        complete({
          sops: [amps],
          measurements: [measured("MS-1", "leakage_current", value)],
          result: submitted({ measurementIds: ["MS-1"] }),
        }),
        "0.03 A",
      )?.status;
    expect(at(30)).toBe("passed");
    expect(at(31)).toBe("failed");
  });
});

describe("which SOP references a result's source_refs cite", () => {
  test("doc:<code>:v<n>, and nothing else", () => {
    expect(
      sopReferences([
        "result:ER-1",
        "doc:SOP-HVAC-012:v3",
        "evidence:EV-22",
        "doc:SOP-ELEC-001:vthree",
        "doc:SOP-ELEC-001:v12",
      ]),
    ).toEqual([
      { kind: "reference", code: "SOP-HVAC-012", versionNo: 3 },
      { kind: "reference", code: "SOP-ELEC-001", versionNo: 12 },
    ]);
  });
});

describe("which SOPs may be verified against", () => {
  const record = (key: string): SopDocumentRecord => {
    const sop = sopByKey(key);
    return {
      documentId: sop.documentId,
      code: sop.code,
      title: sop.title,
      status: sop.status,
      knowledgeBaseStatus: "active",
      language: sop.language,
      activeVersion: sop.version
        ? { id: `v-${key}`, contentHash: "h", ...sop.version }
        : null,
      acl: sop.acl.map((entry) => ({
        principalKind: entry.principalKind,
        roleCode: entry.roleCode ?? null,
        userId: entry.userId ?? null,
        workspaceId: entry.workspaceId ?? null,
        effect: entry.effect,
      })),
      updatedAt: NOW,
    };
  };
  const records = ["S1", "S2", "S5", "S6", "S8"].map(record);
  const profiles: SopProfile[] = ["S1", "S2", "S5", "S6", "S8"].map((key) => {
    const sop = sopByKey(key);
    return {
      code: sop.code,
      versionNo: sop.version?.versionNo ?? 0,
      issueCodes: sop.issueCodes,
      excerpt: sop.excerpt,
      acceptanceCriteria: sop.acceptanceCriteria,
    };
  });
  const resolve = (...requests: Parameters<typeof resolveSops>[0]) =>
    resolveSops(
      requests,
      records,
      (code, versionNo) =>
        profiles.find((p) => p.code === code && p.versionNo === versionNo),
      NOW,
      { roleCode: "staff" },
    );
  const byId = (key: string) => ({
    kind: "document" as const,
    documentId: sopByKey(key).documentId,
  });

  test("a published SOP in force, readable by the caller, with its criteria", () => {
    expect(resolve(byId("S2"))).toEqual({ sops: [HVAC], problems: [] });
  });

  test.each([
    ["S5", "expired on 01/09/2026", "is not a published SOP in force"],
    ["S6", "still a draft", "is not a published SOP in force"],
    ["S8", "granted to nobody", "may not be read by the caller"],
  ])("%s, %s, is refused", (key, _why, message) => {
    const { sops, problems } = resolve(byId(key));
    expect(sops).toEqual([]);
    expect(problems).toEqual([
      `document ${sopByKey(key).documentId} ${message}`,
    ]);
  });

  test("a document not in this building is refused", () => {
    expect(
      resolve({
        kind: "document",
        documentId: "82000000-0000-4000-8000-000000000099",
      }).problems,
    ).toHaveLength(1);
  });

  test("a reference to a version other than the one in force is refused", () => {
    expect(
      resolve({ kind: "reference", code: "SOP-HVAC-012", versionNo: 2 })
        .problems,
    ).toEqual(["doc:SOP-HVAC-012:v2 is not the version in force (v3)"]);
    expect(
      resolve({ kind: "reference", code: "SOP-HVAC-012", versionNo: 3 }).sops,
    ).toEqual([HVAC]);
  });

  test("every problem is reported in one answer", () => {
    const { problems } = resolve(byId("S2"), byId("S5"), byId("S6"));
    expect(problems).toHaveLength(2);
  });
});
