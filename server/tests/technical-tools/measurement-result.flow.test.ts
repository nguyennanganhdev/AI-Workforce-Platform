import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  createDbWorkOrderReadPort,
  createInMemoryExecutorResultStore,
  createInMemoryMeasurementStore,
  createInMemorySensorReadPort,
  type ToolCaller,
  type WorkOrderReadPort,
} from "../../src/technical-tools";
import { FORBIDDEN_MESSAGE } from "../../src/technical-tools/tools/outcomes";
import { READINGS, SENSORS } from "./fixtures/sensors";
import {
  EVIDENCE,
  STAGED_UPLOAD,
  WORK,
  type WorkFixture,
} from "./fixtures/work-orders";
import {
  BUILDING,
  CALLER,
  NOW,
  SOURCE_RUN_ID,
  TENANT,
  USER,
} from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";
import { technicalToolHarness } from "./support/harness";

/**
 * `technical.record_measurement` and `technical.submit_executor_result` end to end, the way a Bot's
 * call reaches them: through the function `/api/agent-tools/call` is handed, the host's checks and
 * its guard against writing twice, the work orders, assignments and photos in the real schema, and
 * back out as the envelope the agent reads.
 *
 * Measurements and results go to the in-memory stores, because no table holds them yet. Each test
 * gets empty ones, so what a test counts is what that test wrote.
 */
let db: TestDatabase;
let workOrders: WorkOrderReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  workOrders = createDbWorkOrderReadPort(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

function setUp() {
  const measurements = createInMemoryMeasurementStore();
  const executorResults = createInMemoryExecutorResultStore();
  const harness = technicalToolHarness({
    workOrders,
    sensors: createInMemorySensorReadPort(SENSORS, READINGS),
    measurements,
    executorResults,
  });
  return { ...harness, measurements, executorResults };
}

const MEASURE = "technical/record_measurement";
const SUBMIT = "technical/submit_executor_result";

const job = (key: string) => WORK[key] as WorkFixture;

const measurement = (
  work: WorkFixture,
  metric: string,
  value: number,
  unit: string,
  rest: Record<string, unknown> = {},
) => ({
  building_id: work.buildingId,
  workorder_id: work.workOrderId,
  metric,
  value,
  unit,
  measured_at: "2026-09-30T08:48:00Z",
  measured_by: { kind: "technician", source_id: USER.technician },
  source: "instrument",
  idempotency_key: `measure-${work.key}-${metric}-1`,
  ...rest,
});

const submission = (work: WorkFixture, rest: Record<string, unknown> = {}) => ({
  building_id: work.buildingId,
  workorder_id: work.workOrderId,
  assignment_id: work.assignmentId,
  checklist: [
    { item_code: "DRAIN_CLEAR", status: "passed", note: "Dòng thoát ổn định" },
  ],
  started_at: "2026-09-30T08:20:00Z",
  completed_at: "2026-09-30T08:55:00Z",
  idempotency_key: `executor-${work.key}-v1`,
  ...rest,
});

type Measured = {
  measurement_id: string;
  metric: string;
  normalized_value: number;
  normalized_unit: string;
  created_at: string;
  quality_flags: string[];
};

type Submitted = {
  result_id: string;
  validation_status: string;
  missing_evidence: string[];
  conflicts: string[];
};

const measuredOf = (data: unknown) => data as Measured;
const submittedOf = (data: unknown) => data as Submitted;

/** Records a measurement as a technician would, and hands back its id. */
async function measured(
  harness: ReturnType<typeof setUp>,
  args: Record<string, unknown>,
  as: ToolCaller = CALLER.technicalAgent,
) {
  const { envelope } = await harness.call(MEASURE, args, as);
  if (envelope.status !== "OK") {
    throw new Error(`Setting up a measurement failed: ${envelope.status}`);
  }
  return measuredOf(envelope.data).measurement_id;
}

/*
 * Level 3 is routine: a blocked condensate drain, cleared. The technician measures, photographs,
 * and submits, and nothing about it needs a person to weigh it.
 */
describe("level 3: a routine repair, recorded and submitted", () => {
  test("L3-14: lưu lượng thoát nước sau vệ sinh — recorded as measured, with nothing to flag", async () => {
    const harness = setUp();
    const { envelope, isError } = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min", {
        asset_id: "AC-A1-1205-01",
        evidence_ids: [EVIDENCE.acAfter.evidenceId],
      }),
    );

    expect(isError).toBe(false);
    expect(envelope.status).toBe("OK");
    const data = measuredOf(envelope.data);
    expect(data).toMatchObject({
      metric: "drain_flow",
      normalized_value: 1.2,
      normalized_unit: "L/min",
      created_at: NOW.toISOString(),
      quality_flags: [],
    });
    expect(envelope.provenance).toEqual([
      {
        source_system: "measurement_adapter",
        source_record_id: data.measurement_id,
        source_version: 1,
        retrieved_at: NOW.toISOString(),
      },
    ]);

    const [stored] = harness.measurements.all();
    expect(harness.measurements.all()).toHaveLength(1);
    expect(stored).toMatchObject({
      measurementId: data.measurement_id,
      tenantId: TENANT.vinhomes,
      workOrderId: job("ac").workOrderId,
      assetId: "AC-A1-1205-01",
      measuredBy: { kind: "technician", sourceId: USER.technician },
      evidenceIds: [EVIDENCE.acAfter.evidenceId],
      sourceRunId: SOURCE_RUN_ID,
    });
    // The time the value was taken is the technician's; the time it was recorded is the server's.
    expect(stored?.measuredAt).toEqual(new Date("2026-09-30T08:48:00Z"));
    expect(stored?.createdAt).toEqual(NOW);
  });

  test("L3-15: đơn vị viết thường — converted to the standard spelling, the original kept", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "l/min"),
    );

    expect(measuredOf(envelope.data)).toMatchObject({
      normalized_value: 1.2,
      normalized_unit: "L/min",
    });
    expect(harness.measurements.all()[0]).toMatchObject({
      rawValue: 1.2,
      rawUnit: "l/min",
    });
  });

  test("L3-16: nộp kết quả đầy đủ — ACCEPTED, citing the measurement just recorded", async () => {
    const harness = setUp();
    const flow = await measured(
      harness,
      measurement(job("ac"), "drain_flow", 1.2, "L/min"),
    );

    const { envelope, isError } = await harness.call(
      SUBMIT,
      submission(job("ac"), {
        measurement_ids: [flow],
        parts: [],
        evidence_ids: [
          EVIDENCE.acBefore.evidenceId,
          EVIDENCE.acAfter.evidenceId,
        ],
        diagnosis: "Tắc nhẹ đường nước ngưng",
        repair_notes: "Đã vệ sinh và thử tải",
      }),
    );

    expect(isError).toBe(false);
    expect(envelope.status).toBe("OK");
    const data = submittedOf(envelope.data);
    expect(data).toMatchObject({
      validation_status: "ACCEPTED",
      missing_evidence: [],
      conflicts: [],
    });
    expect(envelope.provenance[0]).toMatchObject({
      source_system: "executor_result_adapter",
      source_record_id: data.result_id,
    });
    expect(harness.executorResults.all()).toEqual([
      expect.objectContaining({
        resultId: data.result_id,
        workOrderId: job("ac").workOrderId,
        assignmentId: job("ac").assignmentId,
        submittedBy: USER.technician,
        measurementIds: [flow],
        diagnosis: "Tắc nhẹ đường nước ngưng",
      }),
    ]);
  });

  /*
   * ACCEPTED says the submission is complete enough to verify. Closing the job is
   * `technical.verify_resolution`'s question and a person's decision, and this tool does not
   * answer it by changing anything.
   */
  test("accepting a result leaves the work order and its assignment exactly as they were", async () => {
    const harness = setUp();
    const before = await workOrders.getWorkOrder({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      workOrderId: job("ac").workOrderId,
    });

    await harness.call(
      SUBMIT,
      submission(job("ac"), { evidence_ids: [EVIDENCE.acAfter.evidenceId] }),
    );

    const after = await workOrders.getWorkOrder({
      tenantId: TENANT.vinhomes,
      buildingId: BUILDING.a1,
      workOrderId: job("ac").workOrderId,
    });
    expect(after).toEqual(before);
    expect(after?.status).toBe("in_progress");
  });

  test("a registered sensor may report a value of its own", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("ac"), "condensate_level", 1.24, "cm", {
        asset_id: "AC-A1-1205-01",
        measured_by: { kind: "device", source_id: "SNS-AC1-COND" },
        source: "bms",
      }),
    );

    expect(envelope.status).toBe("OK");
    expect(measuredOf(envelope.data)).toMatchObject({
      normalized_value: 12.4,
      normalized_unit: "mm",
    });
  });
});

/*
 * Level 2 is a fault that needs a person's judgement before it is closed. The tools record what
 * was found, flag what is unusual, and say what is missing, without deciding any of it.
 */
describe("level 2: a result that needs more, or needs a person", () => {
  test("L2-16: tường thấm, độ ẩm 35% — recorded, and flagged rather than refused", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("leak"), "surface_moisture", 35, "%"),
    );

    expect(envelope.status).toBe("OK");
    expect(measuredOf(envelope.data)).toMatchObject({
      normalized_value: 35,
      quality_flags: ["out_of_expected_range"],
    });
    expect(harness.measurements.all()).toHaveLength(1);
  });

  test("L2-17: chưa có ảnh sau sửa chữa — NEEDS_EVIDENCE, naming the photo", async () => {
    const harness = setUp();
    const { envelope, isError } = await harness.call(
      SUBMIT,
      submission(job("leak"), {
        checklist: [{ item_code: "SEAL_JOINT", status: "passed" }],
        evidence_ids: [EVIDENCE.leakBefore.evidenceId],
      }),
    );

    expect(isError).toBe(false);
    expect(envelope.status).toBe("OK");
    expect(submittedOf(envelope.data)).toMatchObject({
      validation_status: "NEEDS_EVIDENCE",
      missing_evidence: ["after_photo"],
      conflicts: [],
    });
  });

  test("L2-18: một mục checklist không đạt — HUMAN_REVIEW, naming the item", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("leak"), {
        checklist: [
          { item_code: "SEAL_JOINT", status: "passed" },
          { item_code: "WALL_DRY", status: "failed", note: "Tường vẫn ẩm" },
        ],
        evidence_ids: [EVIDENCE.leakBefore.evidenceId],
      }),
    );

    expect(submittedOf(envelope.data)).toMatchObject({
      validation_status: "HUMAN_REVIEW",
      // What is missing is reported too, so the technician learns both in one answer.
      missing_evidence: ["after_photo"],
      conflicts: ["checklist item WALL_DRY failed"],
    });
  });

  test("citing the flagged moisture reading sends the result to a person as well", async () => {
    const harness = setUp();
    const moisture = await measured(
      harness,
      measurement(job("leak"), "surface_moisture", 35, "%"),
    );

    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("leak"), {
        checklist: [{ item_code: "SEAL_JOINT", status: "passed" }],
        measurement_ids: [moisture],
        evidence_ids: [EVIDENCE.leakBefore.evidenceId],
      }),
    );

    expect(submittedOf(envelope.data)).toMatchObject({
      validation_status: "HUMAN_REVIEW",
      conflicts: [
        `measurement ${moisture} is outside the expected range for surface_moisture`,
      ],
    });
  });
});

/*
 * Level 1 is a safety fault: a breaker that sparked. The dangerous number is the one that must be
 * recorded exactly, and the shortcuts an agent might take under pressure are the ones refused.
 */
describe("level 1: a safety fault, where a shortcut is the danger", () => {
  test("L1-16: dòng rò 180 mA — recorded as measured, and flagged for whoever is on duty", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("breaker"), "leakage_current", 180, "mA", {
        measured_by: { kind: "technician", source_id: USER.secondTechnician },
      }),
      CALLER.secondTechnicianAgent,
    );

    expect(envelope.status).toBe("OK");
    expect(measuredOf(envelope.data)).toMatchObject({
      normalized_value: 180,
      normalized_unit: "mA",
      quality_flags: ["out_of_expected_range"],
    });
    expect(harness.measurements.all()[0]).toMatchObject({
      rawValue: 180,
      measuredBy: { kind: "technician", sourceId: USER.secondTechnician },
    });
  });

  test("the same current written in amperes is the same 180 mA", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("breaker"), "leakage_current", 0.18, "A", {
        measured_by: { kind: "technician", source_id: USER.secondTechnician },
      }),
      CALLER.secondTechnicianAgent,
    );
    expect(measuredOf(envelope.data).normalized_value).toBe(180);
  });

  test("L1-17: ảnh còn đang tải — the whole result is refused, and nothing is recorded", async () => {
    const harness = setUp();
    const { envelope, isError } = await harness.call(
      SUBMIT,
      submission(job("breaker"), {
        checklist: [{ item_code: "BREAKER_REPLACED", status: "passed" }],
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId, STAGED_UPLOAD.fileId],
      }),
      CALLER.secondTechnicianAgent,
    );

    expect(isError).toBe(true);
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.data).toBeNull();
    expect(envelope.errors).toEqual([
      {
        code: "CONFLICT",
        message: `evidence ${STAGED_UPLOAD.fileId} is an upload that has not been registered as evidence (file staged)`,
        field: "evidence_ids",
        retryable: false,
      },
    ]);
    expect(harness.executorResults.all()).toEqual([]);
  });

  test("once the photo is ready, the same key carries the corrected submission", async () => {
    const harness = setUp();
    const args = submission(job("breaker"), {
      checklist: [{ item_code: "BREAKER_REPLACED", status: "passed" }],
      evidence_ids: [EVIDENCE.breakerAfter.evidenceId, STAGED_UPLOAD.fileId],
    });
    await harness.call(SUBMIT, args, CALLER.secondTechnicianAgent);

    const { envelope } = await harness.call(
      SUBMIT,
      { ...args, evidence_ids: [EVIDENCE.breakerAfter.evidenceId] },
      CALLER.secondTechnicianAgent,
    );

    expect(submittedOf(envelope.data).validation_status).toBe("ACCEPTED");
    expect(harness.executorResults.all()).toHaveLength(1);
  });

  test("a measurement cannot cite the photo still uploading either", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("breaker"), "leakage_current", 180, "mA", {
        measured_by: { kind: "technician", source_id: USER.secondTechnician },
        evidence_ids: [STAGED_UPLOAD.fileId],
      }),
      CALLER.secondTechnicianAgent,
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(harness.measurements.all()).toEqual([]);
  });

  /*
   * general.md §3.1. The agent acts for one technician. Recording a value under another's name is
   * the agent creating a measurement and attributing it to somebody who never took it.
   */
  test("L1-18: ghi số đo nhân danh kỹ thuật viên khác — FORBIDDEN, and nothing recorded", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("breaker"), "leakage_current", 12, "mA", {
        measured_by: { kind: "technician", source_id: USER.secondTechnician },
      }),
      CALLER.technicalAgent,
    );

    expect(envelope.status).toBe("FORBIDDEN");
    // The same words as every other refusal, so it says nothing about who is on the job.
    expect(envelope.errors[0]?.message).toBe(FORBIDDEN_MESSAGE);
    expect(harness.measurements.all()).toEqual([]);
  });

  test("nor under the caller's own name, on a job somebody else holds", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("breaker"), "leakage_current", 12, "mA"),
    );
    expect(envelope.status).toBe("FORBIDDEN");
  });

  test.each([
    [
      "a sensor that does not exist",
      "SNS-FAKE-001",
      "leakage_current",
      "bms",
      {},
    ],
    [
      "a real sensor in another building",
      "SNS-B1-COND",
      "condensate_level",
      "bms",
      {},
    ],
    [
      "a real sensor, for a metric it does not measure",
      "SNS-AC1-COND",
      "leakage_current",
      "bms",
      {},
    ],
    [
      "a real sensor, on another machine than the one named",
      "SNS-BP12-CUR",
      "leakage_current",
      "bms",
      { asset_id: "BP-A1-1205-01" },
    ],
    [
      "a real sensor, said to have been typed in by hand",
      "SNS-BP1-CUR-A",
      "leakage_current",
      "manual_entry",
      {},
    ],
  ])(
    "L1-19: thiết bị không hợp lệ (%s) — FORBIDDEN",
    async (_label, sensorId, metric, source, extra) => {
      const harness = setUp();
      const { envelope } = await harness.call(
        MEASURE,
        measurement(
          job("breaker"),
          metric,
          12,
          metric === "leakage_current" ? "mA" : "mm",
          {
            measured_by: { kind: "device", source_id: sensorId },
            source,
            ...extra,
          },
        ),
      );
      expect(envelope.status).toBe("FORBIDDEN");
      expect(harness.measurements.all()).toEqual([]);
    },
  );

  test("the breaker's own sensor, reporting as a device, is recorded", async () => {
    // The positive control for L1-19: the refusals above are about the claims, not about devices.
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("breaker"), "leakage_current", 12, "mA", {
        asset_id: "BP-A1-1205-01",
        measured_by: { kind: "device", source_id: "SNS-BP1-CUR-A" },
        source: "iot",
      }),
    );
    expect(envelope.status).toBe("OK");
  });
});

/*
 * The same cases as `idempotency.test.ts`, on the real tools: what the agent sees when the network
 * drops an answer and it sends the call again.
 */
describe("sending a call again", () => {
  test("I-1: the same measurement twice is one measurement, with one id", async () => {
    const harness = setUp();
    const args = measurement(job("ac"), "drain_flow", 1.2, "L/min");
    const first = await harness.call(MEASURE, args);
    const again = await harness.call(MEASURE, args);

    expect(measuredOf(again.envelope.data).measurement_id).toBe(
      measuredOf(first.envelope.data).measurement_id,
    );
    expect(harness.measurements.all()).toHaveLength(1);
    expect(harness.auditEntries[1]?.idempotent_replay).toBe(true);
  });

  test("I-2: the same key with another value is a conflict, and the first value stands", async () => {
    const harness = setUp();
    await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min"),
    );
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.3, "L/min"),
    );

    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.field).toBe("idempotency_key");
    expect(harness.measurements.all().map((m) => m.rawValue)).toEqual([1.2]);
  });

  test("I-4: refused for the wrong name, then sent correctly under the same key", async () => {
    const harness = setUp();
    const wrong = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min", {
        measured_by: { kind: "technician", source_id: USER.secondTechnician },
      }),
    );
    const right = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min"),
    );

    expect(wrong.envelope.status).toBe("FORBIDDEN");
    expect(right.envelope.status).toBe("OK");
    expect(harness.measurements.all()).toHaveLength(1);
  });

  test("a submission sent twice is one result", async () => {
    const harness = setUp();
    const args = submission(job("ac"), {
      evidence_ids: [EVIDENCE.acAfter.evidenceId],
    });
    const first = await harness.call(SUBMIT, args);
    const again = await harness.call(SUBMIT, args);

    expect(submittedOf(again.envelope.data).result_id).toBe(
      submittedOf(first.envelope.data).result_id,
    );
    expect(harness.executorResults.all()).toHaveLength(1);
  });
});

describe("which work order, and whose", () => {
  test("a work order in another building, and one that does not exist, get the same answer", async () => {
    const harness = setUp();
    const elsewhere = await harness.call(
      MEASURE,
      measurement(job("b1"), "drain_flow", 1.2, "L/min", {
        building_id: BUILDING.a1,
      }),
    );
    const nowhere = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min", {
        workorder_id: "54000000-0000-4000-8000-000000000099",
      }),
    );

    expect(elsewhere.envelope.status).toBe("NOT_FOUND");
    expect(nowhere.envelope.errors).toEqual(elsewhere.envelope.errors);
    expect(elsewhere.envelope.errors[0]?.field).toBe("workorder_id");
  });

  test("a building outside the agent's grant is refused before any work order is looked up", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(SUBMIT, submission(job("b1")));
    expect(envelope.status).toBe("FORBIDDEN");
    expect(harness.auditEntries[0]?.detail).toContain(
      "outside the caller's grant",
    );
  });

  test("a technician released from a job can no longer record against it", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("old"), "door_gap", 2, "mm"),
    );
    expect(envelope.status).toBe("FORBIDDEN");
  });

  test("nor submit a result for it: the assignment is no longer accepted", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(SUBMIT, submission(job("old")));
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors).toEqual([
      expect.objectContaining({
        field: "assignment_id",
        message: `assignment ${job("old").assignmentId} is released, not accepted`,
      }),
    ]);
  });

  test("an assignment from another job is not this job's", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("leak"), { assignment_id: job("ac").assignmentId }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toContain(
      "is not an assignment of this work order",
    );
  });

  test("another technician cannot submit a result for a job that is not theirs", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("ac"), { evidence_ids: [EVIDENCE.acAfter.evidenceId] }),
      CALLER.secondTechnicianAgent,
    );
    expect(envelope.status).toBe("FORBIDDEN");
    expect(harness.executorResults.all()).toEqual([]);
  });

  test("the building manager may submit for the technician, and is recorded as the one who did", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("ac"), { evidence_ids: [EVIDENCE.acAfter.evidenceId] }),
      CALLER.managementAgent,
    );
    expect(envelope.status).toBe("OK");
    expect(harness.executorResults.all()[0]?.submittedBy).toBe(USER.manager);
  });

  test("an agent without the write capability is refused, and nothing is written", async () => {
    const harness = setUp();
    const measure = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min"),
      CALLER.ungrantedAgent,
    );
    const submit = await harness.call(
      SUBMIT,
      submission(job("ac")),
      CALLER.ungrantedAgent,
    );

    expect([measure.envelope.status, submit.envelope.status]).toEqual([
      "FORBIDDEN",
      "FORBIDDEN",
    ]);
    expect(harness.auditEntries.map((entry) => entry.detail)).toEqual([
      "The caller does not hold measurement:write.",
      "The caller does not hold executor_result:submit.",
    ]);
    expect(harness.measurements.all()).toEqual([]);
    expect(harness.executorResults.all()).toEqual([]);
  });
});

describe("what a result's evidence and measurements must be", () => {
  test("a withdrawn photo and another ticket's photo are both reported, in one answer", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("ac"), {
        evidence_ids: [
          EVIDENCE.acAfter.evidenceId,
          EVIDENCE.acWithdrawn.evidenceId,
          EVIDENCE.leakBefore.evidenceId,
        ],
      }),
    );

    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors.map((error) => error.message)).toEqual([
      `evidence ${EVIDENCE.acWithdrawn.evidenceId} was withdrawn`,
      `evidence ${EVIDENCE.leakBefore.evidenceId} belongs to another ticket`,
    ]);
  });

  test("an id the agent made up is reported as not existing", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("ac"), { evidence_ids: ["EV-22"] }),
    );
    expect(envelope.errors[0]?.message).toBe("evidence EV-22 does not exist");
  });

  test("a measurement from another job cannot be cited", async () => {
    const harness = setUp();
    const moisture = await measured(
      harness,
      measurement(job("leak"), "surface_moisture", 12, "%"),
    );
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("ac"), {
        measurement_ids: [moisture],
        evidence_ids: [EVIDENCE.acAfter.evidenceId],
      }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]).toMatchObject({
      field: "measurement_ids",
      message: `measurement ${moisture} was recorded for another work order`,
    });
  });

  test("a job finished before it was accepted goes to a person", async () => {
    const harness = setUp();
    // WO-AC was accepted at 07:30.
    const { envelope } = await harness.call(
      SUBMIT,
      submission(job("ac"), {
        started_at: "2026-09-30T06:00:00Z",
        completed_at: "2026-09-30T07:00:00Z",
        evidence_ids: [EVIDENCE.acAfter.evidenceId],
      }),
    );
    expect(submittedOf(envelope.data)).toMatchObject({
      validation_status: "HUMAN_REVIEW",
      conflicts: [
        "completed_at is earlier than the time the assignment was accepted",
      ],
    });
  });
});

describe("what a measurement must be", () => {
  test("a time the server has not reached is refused", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min", {
        measured_at: "2026-09-30T09:30:00Z",
      }),
    );
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.errors[0]?.field).toBe("measured_at");
  });

  test("a value written down two days late is recorded, and flagged as late", async () => {
    const harness = setUp();
    const { envelope } = await harness.call(
      MEASURE,
      measurement(job("ac"), "drain_flow", 1.2, "L/min", {
        measured_at: "2026-09-28T08:00:00Z",
      }),
    );
    expect(measuredOf(envelope.data).quality_flags).toEqual(["late_entry"]);
  });

  test.each([
    ["a unit the metric is not recorded in", "drain_flow", "psi", "unit"],
    ["a metric the deployment does not record", "vibration", "mm/s", "metric"],
  ])(
    "%s is refused, and nothing recorded",
    async (_label, metric, unit, field) => {
      const harness = setUp();
      const { envelope } = await harness.call(
        MEASURE,
        measurement(job("ac"), metric, 0.3, unit),
      );
      expect(envelope.status).toBe("INVALID_INPUT");
      expect(envelope.errors[0]?.field).toBe(field);
      expect(harness.measurements.all()).toEqual([]);
    },
  );
});

describe("what the audit trail keeps", () => {
  /*
   * Who wrote what, and how it ended. Not the values: those are in the record, and an audit trail
   * that copied them would be a second, unguarded copy of every reading and note.
   */
  test("every write, with its outcome, and none of the values or notes", async () => {
    const harness = setUp();
    const flow = await measured(
      harness,
      measurement(job("ac"), "drain_flow", 1.234567, "L/min"),
    );
    await harness.call(
      SUBMIT,
      submission(job("ac"), {
        measurement_ids: [flow],
        evidence_ids: [EVIDENCE.acAfter.evidenceId],
        diagnosis: "DIAGNOSIS-MARKER",
        repair_notes: "NOTES-MARKER",
      }),
    );

    expect(harness.auditEntries).toEqual([
      expect.objectContaining({
        tool: "technical.record_measurement",
        status: "OK",
        building_id: BUILDING.a1,
        actor_id: USER.technician,
        result_count: 1,
      }),
      expect.objectContaining({
        tool: "technical.submit_executor_result",
        status: "OK",
        result_count: 1,
      }),
    ]);
    const trail = JSON.stringify(harness.auditEntries);
    expect(trail).not.toContain("1.234567");
    expect(trail).not.toContain("DIAGNOSIS-MARKER");
    expect(trail).not.toContain("NOTES-MARKER");
    expect(trail).not.toContain("measure-WO-AC");
  });
});
