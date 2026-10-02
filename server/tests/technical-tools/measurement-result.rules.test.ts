import { describe, expect, test } from "bun:test";
import type {
  ChecklistItem,
  EvidenceLookup,
  Measurement,
  WorkOrderContext,
} from "../../src/technical-tools";
import { METRICS } from "../../src/technical-tools/reference/metrics";
import { evidenceProblems } from "../../src/technical-tools/tools/evidence-rules";
import {
  measurementProblems,
  validateResult,
} from "../../src/technical-tools/tools/executor-result-rules";
import {
  measuredInFuture,
  normalize,
  qualityFlags,
  technicianMayRecord,
} from "../../src/technical-tools/tools/measurement-rules";
import { NOW, USER } from "./fixtures/world";

/**
 * The decisions the two write tools make, as plain functions: no database, no host, no agent.
 *
 * Each is small enough to be wrong in one line, and the flow tests would only show that a level-1
 * case came out wrong, not which of these made it so.
 */
const minutes = (n: number) => n * 60 * 1000;
const at = (offsetMs: number) => new Date(NOW.getTime() + offsetMs);

describe("converting a value to its metric's unit", () => {
  test.each([
    ["drain_flow", 1.2, "L/min", 1.2, "L/min"],
    ["drain_flow", 1.2, "l/min", 1.2, "L/min"],
    ["condensate_level", 1.24, "cm", 12.4, "mm"],
    ["outlet_temperature", 48, "°C", 48, "C"],
    ["leakage_current", 0.18, "A", 180, "mA"],
    ["leakage_current", 180, "mA", 180, "mA"],
    ["supply_pressure", 250, "kPa", 2.5, "bar"],
    ["surface_moisture", 35, "%", 35, "%"],
  ])("%s %d %s is %d %s", (metric, value, unit, expected, canonical) => {
    expect(normalize(metric, value, unit)).toEqual({
      ok: true,
      value: expected,
      unit: canonical,
    });
  });

  // 250 × 0.01 is 2.5000000000000004 in floating point; a recorded value must not carry that tail.
  test("a conversion comes out as the number a person would write", () => {
    const result = normalize("supply_pressure", 250, "kPa");
    expect(result.ok && result.value).toBe(2.5);
    const amps = normalize("leakage_current", 0.007, "A");
    expect(amps.ok && amps.value).toBe(7);
  });

  test("a unit the metric is not recorded in is refused, on unit", () => {
    const result = normalize("drain_flow", 0.3, "psi");
    expect(result).toMatchObject({ ok: false, field: "unit" });
    expect(!result.ok && result.message).toContain("L/min");
  });

  test("a unit is matched exactly: the case of a symbol can change its meaning", () => {
    // mA and MA are a thousandth and a million amperes.
    expect(normalize("leakage_current", 180, "MA")).toMatchObject({
      ok: false,
      field: "unit",
    });
  });

  // A lookup by `in` would find these on every object; they must not pass for units.
  test.each(["constructor", "toString", "__proto__"])(
    "%s is not a unit",
    (unit) => {
      expect(normalize("drain_flow", 1, unit)).toMatchObject({
        ok: false,
        field: "unit",
      });
    },
  );

  test("a metric the deployment does not record is refused, on metric", () => {
    expect(normalize("vibration", 3, "mm/s")).toMatchObject({
      ok: false,
      field: "metric",
    });
  });

  test("every metric's own unit converts to itself, and its range is the right way round", () => {
    for (const definition of METRICS) {
      expect(definition.units[definition.canonicalUnit]).toBe(1);
      expect(definition.expectedRange.min).toBeLessThan(
        definition.expectedRange.max,
      );
    }
  });
});

describe("when a measurement says it was taken", () => {
  test("a clock a few minutes fast is drift, not the future", () => {
    expect(measuredInFuture(at(minutes(5)), NOW)).toBe(false);
  });

  test("beyond five minutes it is a time the server has not reached", () => {
    expect(measuredInFuture(at(minutes(5) + 1), NOW)).toBe(true);
  });

  test("any time in the past is a time it could have been taken", () => {
    expect(measuredInFuture(at(-minutes(60 * 24 * 30)), NOW)).toBe(false);
  });
});

describe("what is flagged on a value recorded anyway", () => {
  test("an ordinary value is flagged with nothing", () => {
    expect(qualityFlags("drain_flow", 1.2, at(-minutes(12)), NOW)).toEqual([]);
  });

  test.each([
    ["leakage_current", 180],
    ["surface_moisture", 35],
    ["drain_flow", 0.2],
    ["outlet_temperature", 20],
  ])("%s %d is outside what is expected", (metric, value) => {
    expect(qualityFlags(metric, value, NOW, NOW)).toEqual([
      "out_of_expected_range",
    ]);
  });

  test("the bounds of the range are themselves ordinary", () => {
    expect(qualityFlags("leakage_current", 30, NOW, NOW)).toEqual([]);
    expect(qualityFlags("leakage_current", 0, NOW, NOW)).toEqual([]);
  });

  test("written down more than a day after it was taken, it is a late entry", () => {
    const aDay = minutes(60 * 24);
    expect(qualityFlags("drain_flow", 1.2, at(-aDay), NOW)).toEqual([]);
    expect(qualityFlags("drain_flow", 1.2, at(-aDay - 1), NOW)).toEqual([
      "late_entry",
    ]);
  });

  test("both at once are both reported", () => {
    expect(
      qualityFlags("leakage_current", 180, at(-minutes(60 * 48)), NOW),
    ).toEqual(["out_of_expected_range", "late_entry"]);
  });
});

/*
 * general.md §3.1: the agent never creates a measurement. The only name it may record a value under
 * is the name of the person it is acting for, and only on a job that person has taken.
 */
describe("who a technician's measurement may be recorded as", () => {
  const job = (
    assignments: WorkOrderContext["assignments"],
  ): WorkOrderContext => ({
    workOrderId: "wo",
    ticketId: "ticket",
    buildingId: "building",
    status: "in_progress",
    assignments,
  });
  const accepted = (staffUserId: string) => ({
    assignmentId: `a-${staffUserId}`,
    status: "accepted",
    staffUserId,
    acceptedAt: NOW,
  });

  test("the caller, as themselves, on a job they accepted", () => {
    expect(
      technicianMayRecord(
        USER.technician,
        USER.technician,
        job([accepted(USER.technician)]),
      ),
    ).toBe(true);
  });

  test("not as somebody else, even somebody on the same job", () => {
    expect(
      technicianMayRecord(
        USER.technician,
        USER.secondTechnician,
        job([accepted(USER.technician), accepted(USER.secondTechnician)]),
      ),
    ).toBe(false);
  });

  test("not on a job they are not assigned to", () => {
    expect(
      technicianMayRecord(
        USER.technician,
        USER.technician,
        job([accepted(USER.secondTechnician)]),
      ),
    ).toBe(false);
  });

  test.each(["released", "offered", "rejected", "completed", "cancelled"])(
    "not on a job whose assignment is %s",
    (status) => {
      expect(
        technicianMayRecord(
          USER.technician,
          USER.technician,
          job([{ ...accepted(USER.technician), status }]),
        ),
      ).toBe(false);
    },
  );

  test("not by a run that acts for nobody in particular", () => {
    expect(
      technicianMayRecord(
        undefined,
        USER.technician,
        job([accepted(USER.technician)]),
      ),
    ).toBe(false);
  });
});

const TICKET = "ticket-ac";

const evidence = (
  id: string,
  change: Partial<Extract<EvidenceLookup, { kind: "evidence" }>> = {},
): EvidenceLookup => ({
  kind: "evidence",
  id,
  ticketId: TICKET,
  workOrderId: "wo-ac",
  assignmentId: "as-ac",
  purpose: "after",
  status: "active",
  fileStatus: "ready",
  ...change,
});

describe("whether an id offered as evidence is evidence of this ticket", () => {
  test("registered, active, ready and on this ticket: no problem", () => {
    expect(evidenceProblems(["EV-1"], [evidence("EV-1")], TICKET)).toEqual([]);
  });

  test("each kind of problem is named for the id it is about", () => {
    const problems = evidenceProblems(
      ["EV-MISSING", "EV-OTHER", "EV-WITHDRAWN", "FILE-STAGED", "EV-OK"],
      [
        evidence("EV-OTHER", { ticketId: "ticket-leak" }),
        evidence("EV-WITHDRAWN", { status: "withdrawn" }),
        {
          kind: "file",
          id: "FILE-STAGED",
          ticketId: TICKET,
          fileStatus: "staged",
        },
        evidence("EV-OK"),
      ],
      TICKET,
    );
    expect(problems).toEqual([
      "evidence EV-MISSING does not exist",
      "evidence EV-OTHER belongs to another ticket",
      "evidence EV-WITHDRAWN was withdrawn",
      "evidence FILE-STAGED is an upload that has not been registered as evidence (file staged)",
    ]);
  });

  test("an upload on this very ticket is still not evidence until it is registered", () => {
    expect(
      evidenceProblems(
        ["FILE-READY"],
        [
          {
            kind: "file",
            id: "FILE-READY",
            ticketId: TICKET,
            fileStatus: "ready",
          },
        ],
        TICKET,
      ),
    ).toHaveLength(1);
  });

  test("evidence whose file is no longer ready is not usable", () => {
    expect(
      evidenceProblems(
        ["EV-Q"],
        [evidence("EV-Q", { fileStatus: "quarantined" })],
        TICKET,
      ),
    ).toEqual(["evidence EV-Q is not ready (file quarantined)"]);
  });

  test("no ids, no problems", () => {
    expect(evidenceProblems([], [], TICKET)).toEqual([]);
  });
});

const measured = (
  id: string,
  change: Partial<Measurement> = {},
): Measurement => ({
  measurementId: id,
  tenantId: "tenant",
  buildingId: "building",
  workOrderId: "wo-ac",
  assetId: null,
  metric: "drain_flow",
  rawValue: 1.2,
  rawUnit: "L/min",
  normalizedValue: 1.2,
  normalizedUnit: "L/min",
  measuredAt: NOW,
  measuredBy: { kind: "technician", sourceId: USER.technician },
  source: "instrument",
  evidenceIds: [],
  qualityFlags: [],
  createdAt: NOW,
  sourceRunId: "run",
  ...change,
});

describe("whether the measurements a result cites are this job's", () => {
  test("recorded for this work order: no problem", () => {
    expect(measurementProblems(["MS-1"], [measured("MS-1")], "wo-ac")).toEqual(
      [],
    );
  });

  test("unknown, or from another job, is named", () => {
    expect(
      measurementProblems(
        ["MS-GONE", "MS-LEAK"],
        [measured("MS-LEAK", { workOrderId: "wo-leak" })],
        "wo-ac",
      ),
    ).toEqual([
      "measurement MS-GONE does not exist",
      "measurement MS-LEAK was recorded for another work order",
    ]);
  });
});

/*
 * The decision order of tools.md §4.3 as this round reads it: anything a person must weigh first,
 * then anything missing, and ACCEPTED only when there is neither.
 */
describe("the validation status of a submitted result", () => {
  const passed: ChecklistItem[] = [
    { itemCode: "DRAIN_CLEAR", status: "passed" },
  ];
  const base = {
    checklist: passed,
    measurements: [measured("MS-1")],
    evidence: [
      evidence("EV-BEFORE", { purpose: "before" }),
      evidence("EV-AFTER"),
    ],
    completedAt: at(-minutes(5)),
    assignmentAcceptedAt: at(-minutes(90)),
  };

  test("everything in order is ACCEPTED, with nothing to report", () => {
    expect(validateResult(base)).toEqual({
      validationStatus: "ACCEPTED",
      missingEvidence: [],
      conflicts: [],
    });
  });

  test("no photo from after the work is NEEDS_EVIDENCE", () => {
    expect(
      validateResult({
        ...base,
        evidence: [evidence("EV-BEFORE", { purpose: "before" })],
      }),
    ).toEqual({
      validationStatus: "NEEDS_EVIDENCE",
      missingEvidence: ["after_photo"],
      conflicts: [],
    });
  });

  test("no photo at all is NEEDS_EVIDENCE too", () => {
    expect(validateResult({ ...base, evidence: [] }).validationStatus).toBe(
      "NEEDS_EVIDENCE",
    );
  });

  test("a photo of another kind is not a photo from after the work", () => {
    expect(
      validateResult({
        ...base,
        evidence: [evidence("EV-DIAG", { purpose: "diagnostic" })],
      }).missingEvidence,
    ).toEqual(["after_photo"]);
  });

  test("a failed checklist item is HUMAN_REVIEW, and says which", () => {
    const result = validateResult({
      ...base,
      checklist: [...passed, { itemCode: "NO_LEAK_AT_WALL", status: "failed" }],
    });
    expect(result.validationStatus).toBe("HUMAN_REVIEW");
    expect(result.conflicts).toEqual(["checklist item NO_LEAK_AT_WALL failed"]);
  });

  test("not applicable is not a failure", () => {
    expect(
      validateResult({
        ...base,
        checklist: [
          ...passed,
          { itemCode: "GAS_CHECK", status: "not_applicable" },
        ],
      }).validationStatus,
    ).toBe("ACCEPTED");
  });

  test("a cited measurement outside its expected range is HUMAN_REVIEW", () => {
    const result = validateResult({
      ...base,
      measurements: [
        measured("MS-HOT", {
          metric: "leakage_current",
          qualityFlags: ["out_of_expected_range"],
        }),
      ],
    });
    expect(result.validationStatus).toBe("HUMAN_REVIEW");
    expect(result.conflicts).toEqual([
      "measurement MS-HOT is outside the expected range for leakage_current",
    ]);
  });

  test("a late entry alone is not a conflict", () => {
    expect(
      validateResult({
        ...base,
        measurements: [measured("MS-LATE", { qualityFlags: ["late_entry"] })],
      }).validationStatus,
    ).toBe("ACCEPTED");
  });

  test("finished before the job was even accepted is HUMAN_REVIEW", () => {
    const result = validateResult({
      ...base,
      completedAt: at(-minutes(120)),
    });
    expect(result.validationStatus).toBe("HUMAN_REVIEW");
    expect(result.conflicts).toEqual([
      "completed_at is earlier than the time the assignment was accepted",
    ]);
  });

  test("a conflict outranks missing evidence, and both are reported in one answer", () => {
    const result = validateResult({
      ...base,
      checklist: [{ itemCode: "DRAIN_CLEAR", status: "failed" }],
      evidence: [],
    });
    expect(result).toEqual({
      validationStatus: "HUMAN_REVIEW",
      missingEvidence: ["after_photo"],
      conflicts: ["checklist item DRAIN_CLEAR failed"],
    });
  });

  test("every conflict is listed, not only the first", () => {
    const result = validateResult({
      ...base,
      checklist: [
        { itemCode: "A", status: "failed" },
        { itemCode: "B", status: "failed" },
      ],
      measurements: [
        measured("MS-X", { qualityFlags: ["out_of_expected_range"] }),
      ],
      completedAt: at(-minutes(120)),
    });
    expect(result.conflicts).toHaveLength(4);
  });
});
