import { describe, expect, test } from "bun:test";
import {
  describeTechnicalTools,
  responseEnvelopeSchema,
} from "../../src/technical-tools";
import {
  areaRestrictionInputSchema,
  areaRestrictionOutputSchema,
  utilityIsolationInputSchema,
  utilityIsolationOutputSchema,
} from "../../src/technical-tools/contracts/risk-request";
import restrictionGolden from "./golden/area_restriction.request.json";
import isolationGolden from "./golden/utility_isolation.request.json";

/**
 * Whether the two request tools accept and return the shapes docs/teams/quang/tools.md §6.1 and
 * §6.2 specify. The golden files are that document's own worked examples.
 *
 * The part that matters most is what the shapes leave no room for: a status other than
 * PENDING_APPROVAL in an answer, or any field in a request through which the caller could claim an
 * approval.
 */
describe("the specification's own examples", () => {
  test.each([
    [
      "utility_isolation.request",
      utilityIsolationInputSchema,
      utilityIsolationOutputSchema,
      isolationGolden,
    ],
    [
      "area_restriction.request",
      areaRestrictionInputSchema,
      areaRestrictionOutputSchema,
      restrictionGolden,
    ],
  ] as const)("%s", (_name, input, output, golden) => {
    expect(input.safeParse(golden.request).success).toBe(true);
    expect(responseEnvelopeSchema.safeParse(golden.response).success).toBe(
      true,
    );
    expect(output.safeParse(golden.response.data).success).toBe(true);
    expect(golden.response.status).toBe("PENDING_APPROVAL");
  });
});

describe("the JSON Schema a caller is handed", () => {
  const described = (name: string) =>
    describeTechnicalTools().find((tool) => tool.name === name);
  const required = (name: string) => [
    ...((described(name)?.input_schema as { required?: string[] } | undefined)
      ?.required ?? []),
  ];

  test("utility_isolation.request requires what tools.md §6.1 requires", () => {
    expect(required("utility_isolation.request").sort()).toEqual(
      [
        "building_id",
        "incident_id",
        "workorder_id",
        "utility_type",
        "scope_ids",
        "reason",
        "planned_start",
        "planned_end",
        "evidence_ids",
        "idempotency_key",
      ].sort(),
    );
  });

  test("area_restriction.request requires what tools.md §6.2 requires", () => {
    expect(required("area_restriction.request").sort()).toEqual(
      [
        "building_id",
        "incident_id",
        "area",
        "hazard",
        "reason",
        "evidence_ids",
        "idempotency_key",
      ].sort(),
    );
  });

  test("both are requests, and both need a key to be safe to send again", () => {
    for (const name of [
      "utility_isolation.request",
      "area_restriction.request",
    ]) {
      expect(described(name)).toMatchObject({
        side_effect: "request",
        requires_idempotency_key: true,
      });
    }
  });
});

/*
 * There is no field through which the caller could say a request is approved, who approved it, or
 * that the supply should be cut now. A strict schema refuses each of them, so the only way a request
 * becomes an action is through a person elsewhere.
 */
describe("no field claims an approval", () => {
  test.each([
    { status: "approved" },
    { approval_status: "APPROVED" },
    { approved_by: "fixture-manager-vinhomes" },
    { execute_now: true },
    { tenant_id: "x" },
  ])("utility_isolation.request refuses %o", (extra) => {
    expect(
      utilityIsolationInputSchema.safeParse({
        ...isolationGolden.request,
        ...extra,
      }).success,
    ).toBe(false);
  });

  test.each([
    { status: "approved" },
    { approved_by: "fixture-manager-vinhomes" },
    { lock_doors: true },
  ])("area_restriction.request refuses %o", (extra) => {
    expect(
      areaRestrictionInputSchema.safeParse({
        ...restrictionGolden.request,
        ...extra,
      }).success,
    ).toBe(false);
  });

  test("and no answer can carry any status but PENDING_APPROVAL", () => {
    for (const approval_status of ["APPROVED", "ACTIVE", "pending"]) {
      expect(
        utilityIsolationOutputSchema.safeParse({
          ...isolationGolden.response.data,
          approval_status,
        }).success,
      ).toBe(false);
      expect(
        areaRestrictionOutputSchema.safeParse({
          ...restrictionGolden.response.data,
          approval_status,
        }).success,
      ).toBe(false);
    }
  });
});

const isolation = isolationGolden.request;
const restriction = restrictionGolden.request;

const pathsOf = (
  schema:
    | typeof utilityIsolationInputSchema
    | typeof areaRestrictionInputSchema,
  input: unknown,
) => {
  const parsed = schema.safeParse(input);
  return parsed.success
    ? []
    : parsed.error.issues.map((issue) => issue.path.join("."));
};

describe("what utility_isolation.request accepts", () => {
  test("a window that ends after it starts, as time and not as text", () => {
    expect(
      pathsOf(utilityIsolationInputSchema, {
        ...isolation,
        planned_end: isolation.planned_start,
      }),
    ).toEqual(["planned_end"]);
    // 05:30-05:00 is 10:30Z: after the 10:00Z start, though it sorts before it as text.
    expect(
      utilityIsolationInputSchema.safeParse({
        ...isolation,
        planned_end: "2026-09-30T05:30:00-05:00",
      }).success,
    ).toBe(true);
  });

  test("water or power, and nothing else", () => {
    expect(
      pathsOf(utilityIsolationInputSchema, {
        ...isolation,
        utility_type: "gas",
      }),
    ).toEqual(["utility_type"]);
  });

  test("at least one scope and one photo, none twice", () => {
    expect(
      pathsOf(utilityIsolationInputSchema, { ...isolation, scope_ids: [] }),
    ).toEqual(["scope_ids"]);
    expect(
      pathsOf(utilityIsolationInputSchema, { ...isolation, evidence_ids: [] }),
    ).toEqual(["evidence_ids"]);
    const [scope] = isolation.scope_ids;
    expect(
      pathsOf(utilityIsolationInputSchema, {
        ...isolation,
        scope_ids: [scope, scope],
      }),
    ).toEqual(["scope_ids"]);
  });

  test("a reason of at least ten characters", () => {
    expect(
      pathsOf(utilityIsolationInputSchema, { ...isolation, reason: "rò nước" }),
    ).toEqual(["reason"]);
  });
});

describe("what area_restriction.request accepts", () => {
  test("an area, a hazard and a reason with their lengths", () => {
    expect(
      pathsOf(areaRestrictionInputSchema, { ...restriction, area: "A" }),
    ).toEqual(["area"]);
    expect(
      pathsOf(areaRestrictionInputSchema, { ...restriction, hazard: "ok" }),
    ).toEqual(["hazard"]);
  });

  test("at least one photo of the hazard", () => {
    expect(
      pathsOf(areaRestrictionInputSchema, { ...restriction, evidence_ids: [] }),
    ).toEqual(["evidence_ids"]);
  });

  test("the work order is optional, and named by UUID when given", () => {
    expect(
      pathsOf(areaRestrictionInputSchema, {
        ...restriction,
        workorder_id: "WO-4111",
      }),
    ).toEqual(["workorder_id"]);
  });
});
