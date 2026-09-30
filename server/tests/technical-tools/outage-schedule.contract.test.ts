import { describe, expect, test } from "bun:test";
import { parseAgentToolCallInput } from "../../src/agents/callback-token";
import {
  describeTechnicalTools,
  findTechnicalTool,
  responseEnvelopeSchema,
  technicalTools,
} from "../../src/technical-tools";
import {
  getActiveOutageInputSchema,
  getActiveOutageOutputSchema,
} from "../../src/technical-tools/contracts/outage";
import {
  utilityScheduleReadInputSchema,
  utilityScheduleReadOutputSchema,
} from "../../src/technical-tools/contracts/schedule";
import { BUILDING, TENANT } from "./fixtures/world";
import outageGolden from "./golden/technical.get_active_outage.json";
import scheduleGolden from "./golden/utility_schedule.read.json";

/**
 * Whether the shapes this module accepts and returns are the shapes docs/teams/quang/tools.md
 * specifies.
 *
 * The golden files are that document's own worked examples, copied rather than paraphrased. A
 * schema that rejects the specification's example of a valid call has drifted from it, however
 * reasonable the schema looks on its own.
 */
describe("the specification's own examples", () => {
  test("tools.md §3.5's example is a valid technical.get_active_outage exchange", () => {
    expect(
      getActiveOutageInputSchema.safeParse(outageGolden.request).success,
    ).toBe(true);
    expect(
      responseEnvelopeSchema.safeParse(outageGolden.response).success,
    ).toBe(true);
    expect(
      getActiveOutageOutputSchema.safeParse(outageGolden.response.data).success,
    ).toBe(true);
  });

  test("tools.md §3.6's example is a valid utility_schedule.read exchange", () => {
    expect(
      utilityScheduleReadInputSchema.safeParse(scheduleGolden.request).success,
    ).toBe(true);
    expect(
      responseEnvelopeSchema.safeParse(scheduleGolden.response).success,
    ).toBe(true);
    expect(
      utilityScheduleReadOutputSchema.safeParse(scheduleGolden.response.data)
        .success,
    ).toBe(true);
  });
});

describe("what technical.get_active_outage refuses as input", () => {
  const valid = {
    building_id: BUILDING.a1,
    service_type: "water",
    occurred_at: "2026-09-30T09:00:00Z",
  };

  test("the valid call it is compared against is accepted", () => {
    expect(getActiveOutageInputSchema.safeParse(valid).success).toBe(true);
  });

  test.each([
    ["a utility that is neither water nor power", { service_type: "gas" }],
    ["a building id that is not a UUID", { building_id: "A1" }],
    ["a time with no timezone", { occurred_at: "2026-09-30T09:00:00" }],
    ["a time that is only a date", { occurred_at: "2026-09-30" }],
  ])("%s", (_label, change) => {
    expect(
      getActiveOutageInputSchema.safeParse({ ...valid, ...change }).success,
    ).toBe(false);
  });

  test.each(["building_id", "service_type", "occurred_at"])(
    "a call missing %s",
    (field) => {
      const { [field]: _removed, ...rest } = valid as Record<string, unknown>;
      expect(getActiveOutageInputSchema.safeParse(rest).success).toBe(false);
    },
  );

  /*
   * The one that matters most. Authority is resolved by the host from the verified caller, and a
   * schema that tolerated a `tenant_id` in the arguments would be one careless line away from a
   * tool that read it.
   */
  test("a tenant_id supplied by the agent is refused, not ignored", () => {
    const result = getActiveOutageInputSchema.safeParse({
      ...valid,
      tenant_id: TENANT.other,
    });
    expect(result.success).toBe(false);
  });

  test("any other property the specification does not name", () => {
    expect(
      getActiveOutageInputSchema.safeParse({ ...valid, role: "admin" }).success,
    ).toBe(false);
  });
});

describe("what utility_schedule.read refuses as input", () => {
  const valid = {
    building_id: BUILDING.a1,
    utility_type: "power",
    time_range: { from: "2026-10-01T00:00:00Z", to: "2026-10-02T00:00:00Z" },
  };

  test("the valid call it is compared against is accepted", () => {
    expect(utilityScheduleReadInputSchema.safeParse(valid).success).toBe(true);
  });

  test("a range that runs backwards, reported on time_range", () => {
    const result = utilityScheduleReadInputSchema.safeParse({
      ...valid,
      time_range: { from: valid.time_range.to, to: valid.time_range.from },
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual(["time_range"]);
  });

  test("a range of no length", () => {
    expect(
      utilityScheduleReadInputSchema.safeParse({
        ...valid,
        time_range: { from: valid.time_range.from, to: valid.time_range.from },
      }).success,
    ).toBe(false);
  });

  test.each([
    ["a utility that is neither water nor power", { utility_type: "gas" }],
    ["a range with no end", { time_range: { from: valid.time_range.from } }],
    [
      "an unknown property inside time_range",
      { time_range: { ...valid.time_range, timezone: "Asia/Ho_Chi_Minh" } },
    ],
    ["a tenant_id supplied by the agent", { tenant_id: TENANT.other }],
  ])("%s", (_label, change) => {
    expect(
      utilityScheduleReadInputSchema.safeParse({ ...valid, ...change }).success,
    ).toBe(false);
  });
});

describe("the catalogue", () => {
  test("lists both tools with what a caller needs to know about each", () => {
    const catalogue = describeTechnicalTools();
    expect(catalogue.map((tool) => tool.name)).toEqual([
      "technical.get_active_outage",
      "utility_schedule.read",
    ]);
    for (const tool of catalogue) {
      expect(tool.side_effect).toBe("read");
      expect(tool.required_capability).toBe("interruption:read");
      expect(tool.requires_idempotency_key).toBe(false);
      expect(tool.timeout_ms).toBeGreaterThan(0);
      // Plain JSON Schema, so a Python runtime reads the contract without Zod.
      expect(tool.input_schema).toMatchObject({
        type: "object",
        additionalProperties: false,
      });
      expect(JSON.parse(JSON.stringify(tool))).toEqual(tool);
    }
  });

  test("offers each tool under a name a model is allowed to call", () => {
    for (const tool of technicalTools) {
      expect(tool.modelName).toMatch(/^[a-zA-Z0-9_-]{1,64}$/);
    }
  });

  /*
   * A model cannot be offered a name with a dot in it, and `/api/agent-tools/call` rewrites the
   * first `__` of whatever name arrives into `/` before asking a deployment tool caller. Using the
   * route's own parser here is what makes this a test of the path a real call takes: if either
   * side changes its spelling, the tool silently stops being found and the call falls through to
   * the plugin store as an unknown MCP tool.
   */
  test("finds each tool by the ref the agent callback route derives from its model name", () => {
    for (const tool of technicalTools) {
      for (const spelling of [
        tool.modelName,
        `mcp__${tool.modelName}`,
        tool.name,
      ]) {
        const parsed = parseAgentToolCallInput({ name: spelling, args: {} });
        if (!parsed.ok) throw new Error(parsed.error);
        expect(findTechnicalTool(parsed.value.ref)?.name).toBe(tool.name);
      }
    }
  });

  test("does not claim a name that belongs to somebody else", () => {
    expect(findTechnicalTool("google_drive/search_files")).toBeUndefined();
    expect(findTechnicalTool("technical.unknown_tool")).toBeUndefined();
  });
});
