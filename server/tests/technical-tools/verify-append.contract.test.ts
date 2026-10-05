import { describe, expect, test } from "bun:test";
import {
  describeTechnicalTools,
  responseEnvelopeSchema,
} from "../../src/technical-tools";
import {
  maintenanceAppendInputSchema,
  maintenanceAppendOutputSchema,
} from "../../src/technical-tools/contracts/maintenance-append";
import {
  verifyResolutionInputSchema,
  verifyResolutionOutputSchema,
} from "../../src/technical-tools/contracts/verification";
import appendGolden from "./golden/maintenance_history.append.json";
import verifyGolden from "./golden/technical.verify_resolution.json";

/**
 * Whether the two tools accept and return the shapes docs/teams/quang/tools.md §4.1 and §5.1
 * specify. The golden files are that document's own worked examples, copied rather than
 * paraphrased. Only shape is asked here.
 */
describe("the specification's own examples", () => {
  test("tools.md §5.1's example is a valid technical.verify_resolution exchange", () => {
    expect(
      verifyResolutionInputSchema.safeParse(verifyGolden.request).success,
    ).toBe(true);
    expect(
      responseEnvelopeSchema.safeParse(verifyGolden.response).success,
    ).toBe(true);
    expect(
      verifyResolutionOutputSchema.safeParse(verifyGolden.response.data)
        .success,
    ).toBe(true);
  });

  test("tools.md §4.1's example is a valid maintenance_history.append exchange", () => {
    expect(
      maintenanceAppendInputSchema.safeParse(appendGolden.request).success,
    ).toBe(true);
    expect(
      responseEnvelopeSchema.safeParse(appendGolden.response).success,
    ).toBe(true);
    expect(
      maintenanceAppendOutputSchema.safeParse(appendGolden.response.data)
        .success,
    ).toBe(true);
  });
});

describe("the JSON Schema a caller is handed", () => {
  const described = (name: string) =>
    describeTechnicalTools().find((tool) => tool.name === name);
  const required = (name: string) =>
    [
      ...((described(name)?.input_schema as { required?: string[] } | undefined)
        ?.required ?? []),
    ].sort();

  test("verify_resolution requires what tools.md §5.1 requires, and no key: it writes nothing", () => {
    expect(required("technical.verify_resolution")).toEqual(
      ["building_id", "incident_id", "workorder_id", "result_id"].sort(),
    );
    expect(described("technical.verify_resolution")).toMatchObject({
      side_effect: "read",
      requires_idempotency_key: false,
    });
  });

  test("maintenance_history.append requires what tools.md §4.1 requires", () => {
    expect(required("maintenance_history.append")).toEqual(
      [
        "building_id",
        "asset_id",
        "workorder_id",
        "verified_result_id",
        "outcome",
        "source_refs",
        "idempotency_key",
      ].sort(),
    );
    expect(described("maintenance_history.append")).toMatchObject({
      side_effect: "write",
      requires_idempotency_key: true,
    });
  });
});

const verifyRequest = verifyGolden.request;
const appendRequest = appendGolden.request;

const pathsOf = (
  schema:
    | typeof verifyResolutionInputSchema
    | typeof maintenanceAppendInputSchema,
  input: unknown,
) => {
  const parsed = schema.safeParse(input);
  return parsed.success
    ? []
    : parsed.error.issues.map((issue) => issue.path.join("."));
};

describe("what technical.verify_resolution accepts", () => {
  test("the incident and the work order are named by UUID", () => {
    expect(
      pathsOf(verifyResolutionInputSchema, {
        ...verifyRequest,
        incident_id: "INC-31",
      }),
    ).toEqual(["incident_id"]);
  });

  test("SOPs are named by document id, once each", () => {
    expect(
      pathsOf(verifyResolutionInputSchema, {
        ...verifyRequest,
        sop_document_ids: ["SOP-HVAC-012"],
      }),
    ).toEqual(["sop_document_ids.0"]);
    const id = verifyRequest.sop_document_ids[0];
    expect(
      pathsOf(verifyResolutionInputSchema, {
        ...verifyRequest,
        sop_document_ids: [id, id],
      }),
    ).toEqual(["sop_document_ids"]);
  });

  test("the caller cannot hand in a verdict, a tenant or a status of its own", () => {
    for (const extra of [
      { verification_status: "VERIFIED" },
      { tenant_id: "x" },
      { close_ticket: true },
    ]) {
      expect(
        verifyResolutionInputSchema.safeParse({ ...verifyRequest, ...extra })
          .success,
      ).toBe(false);
    }
  });
});

describe("what technical.verify_resolution returns", () => {
  const data = verifyGolden.response.data;

  test("exactly the three recommendations; none of them is closed", () => {
    for (const status of ["VERIFIED", "NEEDS_EVIDENCE", "HUMAN_REVIEW"]) {
      expect(
        verifyResolutionOutputSchema.safeParse({
          ...data,
          verification_status: status,
        }).success,
      ).toBe(true);
    }
    for (const status of ["CLOSED", "COMPLETED", "ACCEPTED"]) {
      expect(
        verifyResolutionOutputSchema.safeParse({
          ...data,
          verification_status: status,
        }).success,
      ).toBe(false);
    }
  });

  test("a check is passed, failed, unknown or conflict", () => {
    expect(
      verifyResolutionOutputSchema.safeParse({
        ...data,
        checks: [{ criterion: "x", status: "maybe", source_refs: [] }],
      }).success,
    ).toBe(false);
  });

  test("an answer always says what it was based on", () => {
    expect(
      verifyResolutionOutputSchema.safeParse({ ...data, source_refs: [] })
        .success,
    ).toBe(false);
  });
});

describe("what maintenance_history.append accepts", () => {
  test("at least one source, none twice", () => {
    expect(
      pathsOf(maintenanceAppendInputSchema, {
        ...appendRequest,
        source_refs: [],
      }),
    ).toEqual(["source_refs"]);
    expect(
      pathsOf(maintenanceAppendInputSchema, {
        ...appendRequest,
        source_refs: ["result:ER-9001", "result:ER-9001"],
      }),
    ).toEqual(["source_refs"]);
  });

  test("an outcome of one to four thousand characters", () => {
    expect(
      pathsOf(maintenanceAppendInputSchema, { ...appendRequest, outcome: "" }),
    ).toEqual(["outcome"]);
    expect(
      pathsOf(maintenanceAppendInputSchema, {
        ...appendRequest,
        outcome: "x".repeat(4001),
      }),
    ).toEqual(["outcome"]);
  });

  test("the key that makes a retry safe, as every write carries", () => {
    const { idempotency_key: _key, ...withoutKey } = appendRequest;
    expect(pathsOf(maintenanceAppendInputSchema, withoutKey)).toEqual([
      "idempotency_key",
    ]);
  });

  test("no revision, incident or recorder of the caller's own: the server decides those", () => {
    for (const extra of [
      { revision: 1 },
      { incident_id: "x" },
      { recorded_by: "x" },
    ]) {
      expect(
        maintenanceAppendInputSchema.safeParse({ ...appendRequest, ...extra })
          .success,
      ).toBe(false);
    }
  });

  test("occurred_at, where given, is an instant with its offset", () => {
    expect(
      pathsOf(maintenanceAppendInputSchema, {
        ...appendRequest,
        occurred_at: "30/09/2026",
      }),
    ).toEqual(["occurred_at"]);
  });
});

describe("what maintenance_history.append returns", () => {
  const data = appendGolden.response.data;

  test("a revision counts from one", () => {
    expect(
      maintenanceAppendOutputSchema.safeParse({ ...data, revision: 0 }).success,
    ).toBe(false);
    expect(
      maintenanceAppendOutputSchema.safeParse({ ...data, revision: 1.5 })
        .success,
    ).toBe(false);
  });

  test("supersedes_event_id is present, as null when nothing was replaced", () => {
    const { supersedes_event_id: _replaced, ...without } = data;
    expect(maintenanceAppendOutputSchema.safeParse(without).success).toBe(
      false,
    );
    expect(
      maintenanceAppendOutputSchema.safeParse({
        ...data,
        supersedes_event_id: "ME-103",
      }).success,
    ).toBe(true);
  });
});
