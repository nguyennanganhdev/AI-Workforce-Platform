import { describe, expect, test } from "bun:test";
import {
  describeTechnicalTools,
  responseEnvelopeSchema,
} from "../../src/technical-tools";
import {
  submitExecutorResultInputSchema,
  submitExecutorResultOutputSchema,
} from "../../src/technical-tools/contracts/executor-result";
import {
  recordMeasurementInputSchema,
  recordMeasurementOutputSchema,
} from "../../src/technical-tools/contracts/measurement";
import measurementGolden from "./golden/technical.record_measurement.json";
import resultGolden from "./golden/technical.submit_executor_result.json";

/**
 * Whether the two write tools accept and return the shapes docs/teams/quang/tools.md §4.2 and §4.3
 * specify. The golden files are that document's own worked examples, copied rather than
 * paraphrased.
 *
 * Only shape is asked here. Whether an id names something real, or a technician may put their name
 * to a value, is the rules' and the flow tests' question.
 */
describe("the specification's own examples", () => {
  test("tools.md §4.2's example is a valid technical.record_measurement exchange", () => {
    expect(
      recordMeasurementInputSchema.safeParse(measurementGolden.request).success,
    ).toBe(true);
    expect(
      responseEnvelopeSchema.safeParse(measurementGolden.response).success,
    ).toBe(true);
    expect(
      recordMeasurementOutputSchema.safeParse(measurementGolden.response.data)
        .success,
    ).toBe(true);
  });

  test("tools.md §4.3's example is a valid technical.submit_executor_result exchange", () => {
    expect(
      submitExecutorResultInputSchema.safeParse(resultGolden.request).success,
    ).toBe(true);
    expect(
      responseEnvelopeSchema.safeParse(resultGolden.response).success,
    ).toBe(true);
    expect(
      submitExecutorResultOutputSchema.safeParse(resultGolden.response.data)
        .success,
    ).toBe(true);
  });
});

/*
 * The published JSON Schema is what the Python coordination runtime validates against, so the
 * fields it requires must be the specification's, no more and no fewer.
 */
describe("the JSON Schema a caller is handed", () => {
  const schemaOf = (name: string) =>
    describeTechnicalTools().find((tool) => tool.name === name)
      ?.input_schema as { required: string[] };

  test("record_measurement requires what tools.md §4.2 requires", () => {
    expect(schemaOf("technical.record_measurement").required.sort()).toEqual(
      [
        "building_id",
        "workorder_id",
        "metric",
        "value",
        "unit",
        "measured_at",
        "measured_by",
        "source",
        "idempotency_key",
      ].sort(),
    );
  });

  test("submit_executor_result requires what tools.md §4.3 requires", () => {
    expect(
      schemaOf("technical.submit_executor_result").required.sort(),
    ).toEqual(
      [
        "building_id",
        "workorder_id",
        "assignment_id",
        "checklist",
        "started_at",
        "completed_at",
        "idempotency_key",
      ].sort(),
    );
  });
});

const measurement = measurementGolden.request;
const result = resultGolden.request;

const issuesOf = (
  schema:
    | typeof recordMeasurementInputSchema
    | typeof submitExecutorResultInputSchema,
  input: unknown,
) => {
  const parsed = schema.safeParse(input);
  return parsed.success
    ? []
    : parsed.error.issues.map((issue) => issue.path.join("."));
};

describe("the key every write carries", () => {
  test.each([
    ["record_measurement", recordMeasurementInputSchema, measurement],
    ["submit_executor_result", submitExecutorResultInputSchema, result],
  ] as const)(
    "%s: missing, too short or too long is refused",
    (_name, schema, golden) => {
      const { idempotency_key: _key, ...withoutKey } = golden;
      expect(issuesOf(schema, withoutKey)).toEqual(["idempotency_key"]);
      expect(
        issuesOf(schema, { ...golden, idempotency_key: "1234567" }),
      ).toEqual(["idempotency_key"]);
      expect(
        issuesOf(schema, { ...golden, idempotency_key: "12345678" }),
      ).toEqual([]);
      expect(
        issuesOf(schema, { ...golden, idempotency_key: "k".repeat(129) }),
      ).toEqual(["idempotency_key"]);
    },
  );

  /*
   * The tenant comes from the verified identity, never from the arguments. A field the model could
   * fill in would be a field it could fill in wrongly.
   */
  test.each([
    ["record_measurement", recordMeasurementInputSchema, measurement],
    ["submit_executor_result", submitExecutorResultInputSchema, result],
  ] as const)(
    "%s: a tenant_id the caller adds is refused",
    (_name, schema, golden) => {
      expect(schema.safeParse({ ...golden, tenant_id: "x" }).success).toBe(
        false,
      );
    },
  );
});

describe("what technical.record_measurement accepts", () => {
  test("a value is a number, not text that looks like one", () => {
    expect(
      issuesOf(recordMeasurementInputSchema, { ...measurement, value: "1.2" }),
    ).toEqual(["value"]);
  });

  test("measured_by is a technician or a device, and nothing else", () => {
    expect(
      issuesOf(recordMeasurementInputSchema, {
        ...measurement,
        measured_by: { kind: "agent", source_id: "technical-agent-a2" },
      }),
    ).toEqual(["measured_by.kind"]);
    expect(
      recordMeasurementInputSchema.safeParse({
        ...measurement,
        measured_by: { ...measurement.measured_by, confidence: 0.9 },
      }).success,
    ).toBe(false);
  });

  test("source is one of the four kinds a measurement comes from; an estimate is not one", () => {
    expect(
      issuesOf(recordMeasurementInputSchema, {
        ...measurement,
        source: "estimate",
      }),
    ).toEqual(["source"]);
    for (const source of ["manual_entry", "instrument", "bms", "iot"]) {
      expect(
        recordMeasurementInputSchema.safeParse({ ...measurement, source })
          .success,
      ).toBe(true);
    }
  });

  test("measured_at is an instant with its offset", () => {
    expect(
      issuesOf(recordMeasurementInputSchema, {
        ...measurement,
        measured_at: "2026-09-30 08:48",
      }),
    ).toEqual(["measured_at"]);
    expect(
      recordMeasurementInputSchema.safeParse({
        ...measurement,
        measured_at: "2026-09-30T15:48:00+07:00",
      }).success,
    ).toBe(true);
  });

  test("the same photo cannot be offered twice", () => {
    expect(
      issuesOf(recordMeasurementInputSchema, {
        ...measurement,
        evidence_ids: ["EV-22", "EV-22"],
      }),
    ).toEqual(["evidence_ids"]);
  });

  test("the work order is named by its id, which is a UUID", () => {
    expect(
      issuesOf(recordMeasurementInputSchema, {
        ...measurement,
        workorder_id: "WO-4111",
      }),
    ).toEqual(["workorder_id"]);
  });
});

describe("what technical.submit_executor_result accepts", () => {
  test("a job that finished before it started is refused, on completed_at", () => {
    const backwards = {
      ...result,
      started_at: "2026-09-30T08:55:00Z",
      completed_at: "2026-09-30T08:20:00Z",
    };
    const parsed = submitExecutorResultInputSchema.safeParse(backwards);
    expect(parsed.success).toBe(false);
    expect(parsed.error?.issues[0]).toMatchObject({
      path: ["completed_at"],
      message: "completed_at must be later than started_at.",
    });
  });

  test("and so is one that took no time at all", () => {
    expect(
      issuesOf(submitExecutorResultInputSchema, {
        ...result,
        completed_at: result.started_at,
      }),
    ).toEqual(["completed_at"]);
  });

  test("the order of the two instants is compared as time, not as text", () => {
    // 15:50+07:00 is 08:50Z: later than 08:20Z, though it sorts earlier as a string.
    expect(
      submitExecutorResultInputSchema.safeParse({
        ...result,
        completed_at: "2026-09-30T15:50:00+07:00",
      }).success,
    ).toBe(true);
  });

  test("a checklist has at least one item, each passed, failed or not applicable", () => {
    expect(
      issuesOf(submitExecutorResultInputSchema, { ...result, checklist: [] }),
    ).toEqual(["checklist"]);
    expect(
      issuesOf(submitExecutorResultInputSchema, {
        ...result,
        checklist: [{ item_code: "DRAIN_CLEAR", status: "done" }],
      }),
    ).toEqual(["checklist.0.status"]);
  });

  test("a part is used in a positive quantity", () => {
    for (const quantity of [0, -1]) {
      expect(
        issuesOf(submitExecutorResultInputSchema, {
          ...result,
          parts: [{ name: "Ống thoát nước", quantity }],
        }),
      ).toEqual(["parts.0.quantity"]);
    }
    expect(
      submitExecutorResultInputSchema.safeParse({
        ...result,
        parts: [{ name: "Ống thoát nước", quantity: 0.5, unit: "m" }],
      }).success,
    ).toBe(true);
  });

  test("the same measurement or photo cannot be listed twice", () => {
    expect(
      issuesOf(submitExecutorResultInputSchema, {
        ...result,
        measurement_ids: ["MS-701", "MS-701"],
      }),
    ).toEqual(["measurement_ids"]);
    expect(
      issuesOf(submitExecutorResultInputSchema, {
        ...result,
        evidence_ids: ["EV-21", "EV-21"],
      }),
    ).toEqual(["evidence_ids"]);
  });

  test("diagnosis and notes have the specification's limits", () => {
    expect(
      issuesOf(submitExecutorResultInputSchema, {
        ...result,
        diagnosis: "x".repeat(4001),
      }),
    ).toEqual(["diagnosis"]);
    expect(
      issuesOf(submitExecutorResultInputSchema, {
        ...result,
        repair_notes: "x".repeat(8001),
      }),
    ).toEqual(["repair_notes"]);
  });
});

describe("what the two tools return", () => {
  test("a validation status is one of the three; none of them means closed", () => {
    const data = resultGolden.response.data;
    for (const status of ["ACCEPTED", "NEEDS_EVIDENCE", "HUMAN_REVIEW"]) {
      expect(
        submitExecutorResultOutputSchema.safeParse({
          ...data,
          validation_status: status,
        }).success,
      ).toBe(true);
    }
    for (const status of ["CLOSED", "COMPLETED", "VERIFIED"]) {
      expect(
        submitExecutorResultOutputSchema.safeParse({
          ...data,
          validation_status: status,
        }).success,
      ).toBe(false);
    }
  });

  test("a normalised value is a number, and a created_at an instant", () => {
    const data = measurementGolden.response.data;
    expect(
      recordMeasurementOutputSchema.safeParse({
        ...data,
        normalized_value: "1.2",
      }).success,
    ).toBe(false);
    expect(
      recordMeasurementOutputSchema.safeParse({ ...data, created_at: "today" })
        .success,
    ).toBe(false);
  });
});
