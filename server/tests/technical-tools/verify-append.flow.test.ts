import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import {
  createDbSopReadPort,
  createDbWorkOrderReadPort,
  createInMemoryAssetReadPort,
  createInMemoryExecutorResultStore,
  createInMemoryMaintenanceStore,
  createInMemoryMeasurementStore,
  createInMemorySensorReadPort,
  createInMemorySopProfilePort,
  type ExecutorResult,
  type SopReadPort,
  type ToolCaller,
  type WorkOrderReadPort,
} from "../../src/technical-tools";
import { HAND_OVER } from "../../src/technical-tools/tools/verification-rules";
import { ASSETS } from "./fixtures/assets";
import { MAINTENANCE_EVENTS } from "./fixtures/maintenance";
import { READINGS, SENSORS } from "./fixtures/sensors";
import { SOP_PROFILES, sopByKey } from "./fixtures/sop";
import { EVIDENCE, WORK, type WorkFixture } from "./fixtures/work-orders";
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
 * `technical.verify_resolution` and `maintenance_history.append` end to end, the way a Bot's call
 * reaches them, at the end of the chain the earlier tools start: a technician measures, submits,
 * the agent verifies, and only then is the work recorded in the asset's history.
 *
 * Work orders, assignments, photos and SOPs are the real schema's. Measurements, results and the
 * maintenance history are the in-memory stores, fresh for every test, the history starting from
 * the sample estate's.
 *
 * The cases are grouped by how much a wrong answer would cost, and each level-1 case is a way an
 * agent could get an unverified repair into the record that sounds reasonable at the time.
 */
let db: TestDatabase;
let workOrders: WorkOrderReadPort;
let sop: SopReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  workOrders = createDbWorkOrderReadPort(db.database);
  sop = createDbSopReadPort(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

function setUp() {
  const measurements = createInMemoryMeasurementStore();
  const executorResults = createInMemoryExecutorResultStore();
  const history = createInMemoryMaintenanceStore(MAINTENANCE_EVENTS);
  const harness = technicalToolHarness({
    workOrders,
    sop,
    sopProfiles: createInMemorySopProfilePort(SOP_PROFILES),
    assets: createInMemoryAssetReadPort(ASSETS),
    sensors: createInMemorySensorReadPort(SENSORS, READINGS),
    measurements,
    executorResults,
    maintenance: history,
    maintenanceStore: history,
  });
  return { ...harness, measurements, executorResults, history };
}

type Harness = ReturnType<typeof setUp>;

const MEASURE = "technical/record_measurement";
const SUBMIT = "technical/submit_executor_result";
const VERIFY = "technical/verify_resolution";
const APPEND = "maintenance_history/append";
const HISTORY = "maintenance_history/read";

const job = (key: string) => WORK[key] as WorkFixture;
const docOf = (key: string) => sopByKey(key).documentId;
const refOf = (key: string) => {
  const found = sopByKey(key);
  return `doc:${found.code}:v${found.version?.versionNo}`;
};

const HVAC = "S2"; // SOP-HVAC-012 v3: DRAIN_CLEAR, a photo after
const ELEC = "S1"; // SOP-ELEC-001 v3: leakage ≤ 30 mA, BREAKER_HOLDS_LOAD, a photo after
const PLUMB_MANUAL = "S3"; // SOP-PLUMB-020 v2: moisture ≤ 18 %, an engineer's sign-off
const CEILING = "S4"; // SOP-PLUMB-021 v1: CEILING_STAIN_STABLE
const LAPSED = "S5"; // SOP-ARCH-005: in force until 01/09/2026
const DRAFT = "S6"; // SOP-ELEC-009: a draft

const AC_ASSET = "AC-A1-1205-01";
const BREAKER_ASSET = "BP-A1-1205-01";

async function okData<T>(
  harness: Harness,
  name: string,
  args: Record<string, unknown>,
  as: ToolCaller = CALLER.technicalAgent,
): Promise<T> {
  const { envelope } = await harness.call(name, args, as);
  if (envelope.status !== "OK") {
    throw new Error(
      `${name} was expected to succeed: ${envelope.status} ${JSON.stringify(envelope.errors)}`,
    );
  }
  return envelope.data as T;
}

/** A technician records a measurement through the real tool, and its id comes back. */
const measure = async (
  harness: Harness,
  work: WorkFixture,
  metric: string,
  value: number,
  unit: string,
  as: ToolCaller = CALLER.technicalAgent,
) =>
  (
    await okData<{ measurement_id: string }>(
      harness,
      MEASURE,
      {
        building_id: work.buildingId,
        workorder_id: work.workOrderId,
        metric,
        value,
        unit,
        measured_at: "2026-09-30T08:48:00Z",
        measured_by: { kind: "technician", source_id: as.actorId },
        source: "instrument",
        idempotency_key: `measure-${work.key}-${metric}-${value}`,
      },
      as,
    )
  ).measurement_id;

let submissions = 0;

/** A technician submits a result through the real tool, and its id comes back. */
const submit = async (
  harness: Harness,
  work: WorkFixture,
  rest: Record<string, unknown>,
  as: ToolCaller = CALLER.technicalAgent,
) =>
  (
    await okData<{ result_id: string }>(
      harness,
      SUBMIT,
      {
        building_id: work.buildingId,
        workorder_id: work.workOrderId,
        assignment_id: work.assignmentId,
        started_at: "2026-09-30T08:20:00Z",
        completed_at: "2026-09-30T08:55:00Z",
        idempotency_key: `executor-${work.key}-${++submissions}`,
        ...rest,
      },
      as,
    )
  ).result_id;

/** The air conditioner job, done properly. */
const submitAcJob = (harness: Harness) =>
  submit(harness, job("ac"), {
    checklist: [{ item_code: "DRAIN_CLEAR", status: "passed" }],
    evidence_ids: [EVIDENCE.acBefore.evidenceId, EVIDENCE.acAfter.evidenceId],
  });

const verifyArgs = (
  work: WorkFixture,
  resultId: string,
  sopKeys: string[] = [HVAC],
  rest: Record<string, unknown> = {},
) => ({
  building_id: work.buildingId,
  incident_id: work.ticketId,
  workorder_id: work.workOrderId,
  result_id: resultId,
  ...(sopKeys.length > 0 ? { sop_document_ids: sopKeys.map(docOf) } : {}),
  ...rest,
});

const appendArgs = (
  work: WorkFixture,
  resultId: string,
  rest: Record<string, unknown> = {},
) => ({
  building_id: work.buildingId,
  asset_id: AC_ASSET,
  workorder_id: work.workOrderId,
  verified_result_id: resultId,
  outcome: "Đã vệ sinh đường thoát nước ngưng và kiểm tra không còn rò.",
  source_refs: [`result:${resultId}`, refOf(HVAC)],
  occurred_at: "2026-09-30T08:55:00Z",
  idempotency_key: `mh-${work.key}-${resultId.slice(0, 8)}`,
  ...rest,
});

type Verified = {
  verification_status: string;
  checks: { criterion: string; status: string; source_refs: string[] }[];
  required_actions: string[];
  source_refs: string[];
};

type Appended = {
  maintenance_event_id: string;
  created_at: string;
  revision: number;
  supersedes_event_id: string | null;
};

type History = {
  events: { event_id: string; outcome: string }[];
  repeat_count: number;
};

const readHistory = (harness: Harness, assetId = AC_ASSET) =>
  okData<History>(harness, HISTORY, {
    building_id: BUILDING.a1,
    asset_id: assetId,
    time_range: { from: "2026-01-01T00:00:00Z", to: NOW.toISOString() },
  });

const checkNamed = (data: Verified, fragment: string) =>
  data.checks.find((item) => item.criterion.includes(fragment));

/** A result written straight into the store, as it stood when it was submitted. */
function storedResult(
  harness: Harness,
  work: WorkFixture,
  change: Partial<ExecutorResult>,
): ExecutorResult {
  const result: ExecutorResult = {
    resultId: `ER-STORED-${work.key}`,
    tenantId: TENANT.vinhomes,
    buildingId: work.buildingId,
    workOrderId: work.workOrderId,
    assignmentId: work.assignmentId,
    submittedBy: USER.technician,
    checklist: [{ itemCode: "DRAIN_CLEAR", status: "passed" }],
    measurementIds: [],
    parts: [],
    evidenceIds: [],
    diagnosis: null,
    repairNotes: null,
    startedAt: new Date("2026-09-30T08:20:00Z"),
    completedAt: new Date("2026-09-30T08:55:00Z"),
    validationStatus: "ACCEPTED",
    missingEvidence: [],
    conflicts: [],
    createdAt: new Date("2026-09-30T08:56:00Z"),
    sourceRunId: SOURCE_RUN_ID,
    ...change,
  };
  void harness.executorResults.append(result);
  return result;
}

/*
 * Level 3 is routine: the air conditioner's drain, cleared and photographed. The trap here is
 * small but real: a tool that verifies must not also close anything.
 */
describe("level 3: a routine repair, verified and recorded", () => {
  test("L3-17: điều hòa chảy nước, đủ hồ sơ — VERIFIED, handed to a person to accept", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);

    const { envelope, isError } = await harness.call(
      VERIFY,
      verifyArgs(job("ac"), resultId),
    );

    expect(isError).toBe(false);
    const data = envelope.data as Verified;
    expect(data.verification_status).toBe("VERIFIED");
    expect(data.required_actions).toEqual([HAND_OVER]);
    expect(data.source_refs).toEqual([`result:${resultId}`, refOf(HVAC)]);
    expect(checkNamed(data, "Không còn rò")).toMatchObject({
      status: "passed",
      source_refs: [refOf(HVAC), `result:${resultId}`],
    });
    expect(envelope.provenance.map((p) => p.source_system)).toEqual([
      "application_db",
      "executor_result_adapter",
      "application_db",
    ]);
  });

  test("L3-18: ghi lịch sử bảo trì — revision 1, and the history reads it back at once", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const before = await readHistory(harness);

    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId),
    );

    expect(envelope.status).toBe("OK");
    const data = envelope.data as Appended;
    expect(data).toMatchObject({
      created_at: NOW.toISOString(),
      revision: 1,
      supersedes_event_id: null,
    });
    expect(envelope.provenance[0]).toMatchObject({
      source_system: "maintenance_adapter",
      source_record_id: data.maintenance_event_id,
    });

    const after = await readHistory(harness);
    expect(after.events[0]?.event_id).toBe(data.maintenance_event_id);
    // Raised by the ticket the work order serves, so it counts as the fault happening again.
    expect(after.repeat_count).toBe(before.repeat_count + 1);
    expect(
      harness.history
        .all()
        .find((e) => e.eventId === data.maintenance_event_id),
    ).toMatchObject({
      incidentId: job("ac").ticketId,
      workorderId: job("ac").workOrderId,
      recordedBy: USER.technician,
      sourceRunId: SOURCE_RUN_ID,
    });
  });

  test("L3-19: gọi lại sau khi mất mạng — the same verdict, and still one event", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);

    const first = await harness.call(VERIFY, verifyArgs(job("ac"), resultId));
    const again = await harness.call(VERIFY, verifyArgs(job("ac"), resultId));
    expect(again.envelope.data).toEqual(first.envelope.data);

    const count = harness.history.all().length;
    const written = await harness.call(APPEND, appendArgs(job("ac"), resultId));
    const retried = await harness.call(APPEND, appendArgs(job("ac"), resultId));
    expect((retried.envelope.data as Appended).maintenance_event_id).toBe(
      (written.envelope.data as Appended).maintenance_event_id,
    );
    expect(harness.history.all()).toHaveLength(count + 1);
  });

  test("bẫy: verifying and recording leave the work order exactly as they found it", async () => {
    const harness = setUp();
    const at = () =>
      workOrders.getWorkOrder({
        tenantId: TENANT.vinhomes,
        buildingId: BUILDING.a1,
        workOrderId: job("ac").workOrderId,
      });
    const before = await at();
    const resultId = await submitAcJob(harness);

    await harness.call(VERIFY, verifyArgs(job("ac"), resultId));
    await harness.call(APPEND, appendArgs(job("ac"), resultId));

    expect(await at()).toEqual(before);
    expect((await at())?.status).toBe("in_progress");
  });
});

/*
 * Level 2 is incomplete or contested work. The tools say exactly what is missing or what a person
 * has to look at, and the history refuses what is not yet verified.
 */
describe("level 2: what is missing, and what needs a person", () => {
  test("L2-19: rò âm tường, chỉ có ảnh trước — NEEDS_EVIDENCE, naming the photo", async () => {
    const harness = setUp();
    const resultId = await submit(harness, job("leak"), {
      checklist: [{ item_code: "CEILING_STAIN_STABLE", status: "passed" }],
      evidence_ids: [EVIDENCE.leakBefore.evidenceId],
    });

    const data = await okData<Verified>(
      harness,
      VERIFY,
      verifyArgs(job("leak"), resultId, [CEILING]),
    );

    expect(data.verification_status).toBe("NEEDS_EVIDENCE");
    expect(checkNamed(data, "Có ảnh sau khi sửa chữa")?.status).toBe("unknown");
    expect(data.required_actions).toEqual([
      "Bổ sung bằng chứng: Có ảnh sau khi sửa chữa",
    ]);
  });

  test("L2-20: một mục checklist không đạt — HUMAN_REVIEW, the item failed", async () => {
    const harness = setUp();
    const resultId = await submit(harness, job("leak"), {
      checklist: [{ item_code: "CEILING_STAIN_STABLE", status: "failed" }],
      evidence_ids: [EVIDENCE.leakBefore.evidenceId],
    });

    const data = await okData<Verified>(
      harness,
      VERIFY,
      verifyArgs(job("leak"), resultId, [CEILING]),
    );

    expect(data.verification_status).toBe("HUMAN_REVIEW");
    expect(checkNamed(data, "Vết thấm trần")?.status).toBe("failed");
  });

  test("L2-21: SOP đòi kỹ sư xác nhận — HUMAN_REVIEW, however good the numbers are", async () => {
    const harness = setUp();
    const moisture = await measure(
      harness,
      job("leak"),
      "surface_moisture",
      12,
      "%",
    );
    const resultId = await submit(harness, job("leak"), {
      checklist: [{ item_code: "SEAL_JOINT", status: "passed" }],
      measurement_ids: [moisture],
      evidence_ids: [EVIDENCE.leakBefore.evidenceId],
    });

    const data = await okData<Verified>(
      harness,
      VERIFY,
      verifyArgs(job("leak"), resultId, [PLUMB_MANUAL]),
    );

    expect(data.verification_status).toBe("HUMAN_REVIEW");
    expect(checkNamed(data, "Độ ẩm")?.status).toBe("passed");
    expect(checkNamed(data, "Kỹ sư cấp nước")?.status).toBe("unknown");
  });

  test("L2-22: ghi lịch sử từ kết quả còn thiếu ảnh — CONFLICT, and no event", async () => {
    const harness = setUp();
    const resultId = await submit(harness, job("leak"), {
      checklist: [{ item_code: "CEILING_STAIN_STABLE", status: "passed" }],
      evidence_ids: [EVIDENCE.leakBefore.evidenceId],
    });
    const count = harness.history.all().length;

    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("leak"), resultId, {
        source_refs: [`result:${resultId}`, refOf(CEILING)],
      }),
    );

    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]).toMatchObject({
      field: "verified_result_id",
      message: `result ${resultId} is NEEDS_EVIDENCE, not VERIFIED; nothing was recorded`,
    });
    expect(envelope.errors.map((e) => e.message)).toContain(
      "Bổ sung bằng chứng: Có ảnh sau khi sửa chữa",
    );
    expect(harness.history.all()).toHaveLength(count);
  });

  test("L2-23: sửa bản ghi sai — revision 2, only the correction is read, counted once", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const wrong = await okData<Appended>(
      harness,
      APPEND,
      appendArgs(job("ac"), resultId, { outcome: "Đã thay bơm thoát nước." }),
    );
    const countWithWrong = (await readHistory(harness)).repeat_count;

    const corrected = await okData<Appended>(
      harness,
      APPEND,
      appendArgs(job("ac"), resultId, {
        outcome: "Chỉ vệ sinh đường thoát nước ngưng, không thay bơm.",
        supersedes_event_id: wrong.maintenance_event_id,
        idempotency_key: "mh-WO-AC-correction-1",
      }),
    );

    expect(corrected).toMatchObject({
      revision: 2,
      supersedes_event_id: wrong.maintenance_event_id,
    });
    const after = await readHistory(harness);
    const ids = after.events.map((e) => e.event_id);
    expect(ids).toContain(corrected.maintenance_event_id);
    expect(ids).not.toContain(wrong.maintenance_event_id);
    expect(after.repeat_count).toBe(countWithWrong);
  });

  test("a correction of the sample history's own correction is revision 3", async () => {
    // ME-104 already corrects ME-103, so a correction of ME-104 is the third version.
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const data = await okData<Appended>(
      harness,
      APPEND,
      appendArgs(job("ac"), resultId, { supersedes_event_id: "ME-104" }),
    );
    expect(data.revision).toBe(3);
  });

  /*
   * The trap of trusting the past. The result was ACCEPTED when it was submitted. Its photo from
   * after the work has since been withdrawn: the wrong unit was photographed. The stored status
   * still says ACCEPTED, and a tool that read it would verify a repair with no photo of it.
   */
  test("bẫy: ảnh bị rút sau khi nộp — NEEDS_EVIDENCE now, whatever the result said then", async () => {
    const harness = setUp();
    const stored = storedResult(harness, job("ac"), {
      evidenceIds: [
        EVIDENCE.acBefore.evidenceId,
        EVIDENCE.acWithdrawn.evidenceId,
      ],
      validationStatus: "ACCEPTED",
    });

    const data = await okData<Verified>(
      harness,
      VERIFY,
      verifyArgs(job("ac"), stored.resultId),
    );
    expect(data.verification_status).toBe("NEEDS_EVIDENCE");
    expect(checkNamed(data, "vẫn còn hiệu lực")).toMatchObject({
      status: "unknown",
      source_refs: [`evidence:${EVIDENCE.acWithdrawn.evidenceId}`],
    });

    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), stored.resultId),
    );
    expect(envelope.status).toBe("CONFLICT");
  });
});

/*
 * Level 1 is a safety fault, and every case is a way to get an unverified repair into an asset's
 * history that would read as reasonable to whoever let it through: an id that exists, a claim in
 * the notes, a SOP left out, an old version cited.
 */
describe("level 1: every way round the verification is closed", () => {
  test("L1-20: cầu dao, dòng rò 180 mA — HUMAN_REVIEW, naming the measurement", async () => {
    const harness = setUp();
    const current = await measure(
      harness,
      job("breaker"),
      "leakage_current",
      180,
      "mA",
      CALLER.secondTechnicianAgent,
    );
    const resultId = await submit(
      harness,
      job("breaker"),
      {
        checklist: [{ item_code: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurement_ids: [current],
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
      },
      CALLER.secondTechnicianAgent,
    );

    const data = await okData<Verified>(
      harness,
      VERIFY,
      verifyArgs(job("breaker"), resultId, [ELEC]),
      CALLER.secondTechnicianAgent,
    );

    expect(data.verification_status).toBe("HUMAN_REVIEW");
    expect(checkNamed(data, "Dòng rò")).toMatchObject({
      status: "failed",
      source_refs: [refOf(ELEC), `measurement:${current}`],
    });
    expect(checkNamed(data, "khoảng thường gặp")?.status).toBe("conflict");
    expect(data.required_actions).not.toContain(HAND_OVER);
  });

  test("and the same job at 12 mA is VERIFIED: the refusal is about the number", async () => {
    const harness = setUp();
    const current = await measure(
      harness,
      job("breaker"),
      "leakage_current",
      12,
      "mA",
      CALLER.secondTechnicianAgent,
    );
    const resultId = await submit(
      harness,
      job("breaker"),
      {
        checklist: [{ item_code: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurement_ids: [current],
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
      },
      CALLER.secondTechnicianAgent,
    );
    const data = await okData<Verified>(
      harness,
      VERIFY,
      verifyArgs(job("breaker"), resultId, [ELEC]),
    );
    expect(data.verification_status).toBe("VERIFIED");
  });

  test.each([
    ["đã hết hiệu lực", LAPSED],
    ["còn là bản nháp", DRAFT],
  ])("L1-21: SOP %s — CONFLICT, never used as the basis", async (_why, key) => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      VERIFY,
      verifyArgs(job("ac"), resultId, [HVAC, key]),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors).toEqual([
      expect.objectContaining({
        field: "sop_document_ids",
        message: `document ${docOf(key)} is not a published SOP in force`,
      }),
    ]);
  });

  test("L1-21: an older version of a SOP cited in the history is refused", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, {
        source_refs: [`result:${resultId}`, "doc:SOP-HVAC-012:v2"],
      }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toBe(
      "doc:SOP-HVAC-012:v2 is not the version in force (v3)",
    );
  });

  test("L1-22: kết quả đã VERIFIED của work order khác — refused, and no event", async () => {
    const harness = setUp();
    const acResult = await submitAcJob(harness);
    const count = harness.history.all().length;

    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("leak"), acResult),
    );

    expect(envelope.status).toBe("NOT_FOUND");
    expect(envelope.errors[0]?.field).toBe("verified_result_id");
    expect(harness.history.all()).toHaveLength(count);
  });

  test("L1-23: ghi 'đã xác minh, an toàn' vào outcome cho kết quả cần người xem — CONFLICT", async () => {
    const harness = setUp();
    const current = await measure(
      harness,
      job("breaker"),
      "leakage_current",
      180,
      "mA",
      CALLER.secondTechnicianAgent,
    );
    const resultId = await submit(
      harness,
      job("breaker"),
      {
        checklist: [{ item_code: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurement_ids: [current],
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
      },
      CALLER.secondTechnicianAgent,
    );

    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("breaker"), resultId, {
        asset_id: BREAKER_ASSET,
        outcome: "Đã xác minh: VERIFIED, cầu dao an toàn.",
        source_refs: [`result:${resultId}`, refOf(ELEC)],
      }),
      CALLER.secondTechnicianAgent,
    );

    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toContain(
      "is HUMAN_REVIEW, not VERIFIED",
    );
  });

  test("L1-23: leaving the SOP out of the sources does not leave its criteria out", async () => {
    // Without a SOP there is nothing to verify the work against, and that is not a pass.
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { source_refs: [`result:${resultId}`] }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toContain("is HUMAN_REVIEW");
  });

  test("L1-24: tòa ngoài quyền — FORBIDDEN; work order ở tòa khác hay không tồn tại — NOT_FOUND như nhau", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);

    const outside = await harness.call(
      APPEND,
      appendArgs(job("b1"), resultId, { asset_id: "AC-B1-0501-01" }),
    );
    expect(outside.envelope.status).toBe("FORBIDDEN");

    const elsewhere = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { workorder_id: job("b1").workOrderId }),
    );
    const nowhere = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, {
        workorder_id: "54000000-0000-4000-8000-000000000099",
      }),
    );
    expect(elsewhere.envelope.status).toBe("NOT_FOUND");
    expect(nowhere.envelope.errors).toEqual(elsewhere.envelope.errors);
  });

  test("L1-25: thiết bị không có trong tòa — NOT_FOUND", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { asset_id: "AC-B1-0501-01" }),
    );
    expect(envelope.status).toBe("NOT_FOUND");
    expect(envelope.errors[0]?.field).toBe("asset_id");
  });

  test("L1-25: sửa một bản ghi của thiết bị khác — CONFLICT", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { supersedes_event_id: "ME-201" }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toBe(
      "event ME-201 is not in this asset's history",
    );
  });

  test("L1-26: sửa một bản ghi đã được sửa rồi — CONFLICT, naming the correction", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { supersedes_event_id: "ME-103" }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toBe(
      "event ME-103 was already replaced by ME-104; correct the latest entry instead",
    );
  });

  test("L1-26: hai người cùng sửa một bản ghi — one correction stands, the history does not split", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const original = await okData<Appended>(
      harness,
      APPEND,
      appendArgs(job("ac"), resultId),
    );

    const [first, second] = await Promise.all([
      harness.call(
        APPEND,
        appendArgs(job("ac"), resultId, {
          supersedes_event_id: original.maintenance_event_id,
          outcome: "Bản sửa của kỹ thuật viên.",
          idempotency_key: "mh-WO-AC-fix-technician",
        }),
      ),
      harness.call(
        APPEND,
        appendArgs(job("ac"), resultId, {
          supersedes_event_id: original.maintenance_event_id,
          outcome: "Bản sửa thứ hai, gửi cùng lúc.",
          idempotency_key: "mh-WO-AC-fix-second",
        }),
      ),
    ]);

    const statuses = [first.envelope.status, second.envelope.status].sort();
    expect(statuses).toEqual(["CONFLICT", "OK"]);
    const refused = [first, second].find(
      (c) => c.envelope.status === "CONFLICT",
    );
    expect(refused?.envelope.errors[0]?.field).toBe("supersedes_event_id");
    const replacing = harness.history
      .all()
      .filter((e) => e.supersedesEventId === original.maintenance_event_id);
    expect(replacing).toHaveLength(1);
  });

  test("L1-27: incident_id không phải ticket của work order — CONFLICT", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      VERIFY,
      verifyArgs(job("ac"), resultId, [HVAC], {
        incident_id: job("leak").ticketId,
      }),
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.field).toBe("incident_id");
  });

  test("L1-28: kỹ thuật viên khác ghi lịch sử cho việc không phải của mình — FORBIDDEN", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const count = harness.history.all().length;
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId),
      CALLER.secondTechnicianAgent,
    );
    expect(envelope.status).toBe("FORBIDDEN");
    expect(harness.history.all()).toHaveLength(count);
  });

  test("L1-28: nor the other way round, on the breaker job the second technician holds", async () => {
    const harness = setUp();
    const current = await measure(
      harness,
      job("breaker"),
      "leakage_current",
      12,
      "mA",
      CALLER.secondTechnicianAgent,
    );
    const resultId = await submit(
      harness,
      job("breaker"),
      {
        checklist: [{ item_code: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurement_ids: [current],
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
      },
      CALLER.secondTechnicianAgent,
    );
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("breaker"), resultId, {
        asset_id: BREAKER_ASSET,
        source_refs: [`result:${resultId}`, refOf(ELEC)],
      }),
      CALLER.technicalAgent,
    );
    expect(envelope.status).toBe("FORBIDDEN");
  });

  test("the building manager may record it, and is recorded as the one who did", async () => {
    // SOP-ELEC-001 is granted to management as well as staff.
    const harness = setUp();
    const current = await measure(
      harness,
      job("breaker"),
      "leakage_current",
      12,
      "mA",
      CALLER.secondTechnicianAgent,
    );
    const resultId = await submit(
      harness,
      job("breaker"),
      {
        checklist: [{ item_code: "BREAKER_HOLDS_LOAD", status: "passed" }],
        measurement_ids: [current],
        evidence_ids: [EVIDENCE.breakerAfter.evidenceId],
      },
      CALLER.secondTechnicianAgent,
    );
    const data = await okData<Appended>(
      harness,
      APPEND,
      appendArgs(job("breaker"), resultId, {
        asset_id: BREAKER_ASSET,
        source_refs: [`result:${resultId}`, refOf(ELEC)],
      }),
      CALLER.managementAgent,
    );
    expect(
      harness.history.all().find((e) => e.eventId === data.maintenance_event_id)
        ?.recordedBy,
    ).toBe(USER.manager);
  });

  /*
   * SOP-HVAC-012 is granted to staff only. Verifying against a document the caller may not read
   * would let a role reach guidance its access list withholds, by way of a verdict.
   */
  test("but not against a SOP the manager's role may not read", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId),
      CALLER.managementAgent,
    );
    expect(envelope.status).toBe("CONFLICT");
    expect(envelope.errors[0]?.message).toBe(
      `${refOf(HVAC)} may not be read by the caller`,
    );
  });
});

describe("what the two tools refuse before deciding anything", () => {
  test("a result of another work order is not found by verify either", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      VERIFY,
      verifyArgs(job("leak"), resultId, [CEILING]),
    );
    expect(envelope.status).toBe("NOT_FOUND");
    expect(envelope.errors[0]?.field).toBe("result_id");
  });

  test("an event must name the result it records among its sources", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { source_refs: [refOf(HVAC)] }),
    );
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.errors[0]?.field).toBe("source_refs");
  });

  test("an event cannot be dated after the server's clock", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const { envelope } = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { occurred_at: "2026-10-01T09:00:00Z" }),
    );
    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.errors[0]?.field).toBe("occurred_at");
  });

  test("an agent without the capabilities is refused, and nothing is written", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    const count = harness.history.all().length;
    const verify = await harness.call(
      VERIFY,
      verifyArgs(job("ac"), resultId),
      CALLER.ungrantedAgent,
    );
    const append = await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId),
      CALLER.ungrantedAgent,
    );
    expect([verify.envelope.status, append.envelope.status]).toEqual([
      "FORBIDDEN",
      "FORBIDDEN",
    ]);
    expect(harness.auditEntries.slice(-2).map((entry) => entry.detail)).toEqual(
      [
        "The caller does not hold resolution:verify.",
        "The caller does not hold maintenance:append.",
      ],
    );
    expect(harness.history.all()).toHaveLength(count);
  });

  test("the audit trail records the calls and keeps none of the outcome's words", async () => {
    const harness = setUp();
    const resultId = await submitAcJob(harness);
    await harness.call(VERIFY, verifyArgs(job("ac"), resultId));
    await harness.call(
      APPEND,
      appendArgs(job("ac"), resultId, { outcome: "OUTCOME-MARKER" }),
    );
    const trail = harness.auditEntries.slice(-2);
    expect(trail.map((entry) => [entry.tool, entry.status])).toEqual([
      ["technical.verify_resolution", "OK"],
      ["maintenance_history.append", "OK"],
    ]);
    expect(JSON.stringify(trail)).not.toContain("OUTCOME-MARKER");
  });
});
