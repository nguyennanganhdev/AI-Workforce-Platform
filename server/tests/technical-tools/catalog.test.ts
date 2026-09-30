import { describe, expect, test } from "bun:test";
import { parseAgentToolCallInput } from "../../src/agents/callback-token";
import {
  describeTechnicalTools,
  findTechnicalTool,
  ISSUE_CODES,
  technicalTools,
} from "../../src/technical-tools";

/**
 * The tool catalogue (task Q01): what exists, what each one may do, and whether the server can
 * still find it by the name a call arrives under.
 *
 * Written over whatever the catalogue holds rather than over a list repeated here, so adding the
 * next tool does not mean editing an assertion, and so a tool that forgets to declare a capability
 * or a timeout fails on the day it is added.
 */
const CATALOGUE = describeTechnicalTools();

describe("what the catalogue says about every tool", () => {
  test("names the six built so far: every lookup tool in tools.md", () => {
    expect(CATALOGUE.map((tool) => tool.name)).toEqual([
      "technical.get_active_outage",
      "utility_schedule.read",
      "sop_kb.retrieve",
      "asset.read",
      "sensor.read",
      "maintenance_history.read",
    ]);
  });

  test.each(CATALOGUE.map((tool) => [tool.name, tool] as const))(
    "%s declares everything a caller needs",
    (_name, tool) => {
      expect(tool.version).toMatch(/^\d+\.\d+\.\d+$/);
      expect(tool.description.length).toBeGreaterThan(80);
      expect(["read", "write", "request"]).toContain(tool.side_effect);
      expect(tool.required_capability).toMatch(/^[a-z_]+:[a-z_]+$/);
      expect(tool.timeout_ms).toBeGreaterThan(0);
      // A read changes nothing, so it needs no key to be safe to repeat.
      expect(tool.requires_idempotency_key).toBe(tool.side_effect !== "read");
      // Plain JSON Schema, so the Python coordination runtime reads the contract without Zod.
      expect(tool.input_schema).toMatchObject({
        type: "object",
        additionalProperties: false,
      });
      expect(tool.output_schema).toMatchObject({ type: "object" });
      expect(JSON.parse(JSON.stringify(tool))).toEqual(tool);
    },
  );

  test("every tool takes a building, because every check is scoped to one", () => {
    for (const tool of CATALOGUE) {
      expect(
        (tool.input_schema as { properties?: Record<string, unknown> })
          .properties,
      ).toHaveProperty("building_id");
    }
  });

  /*
   * The description is what a model chooses by. These two tools are close enough in subject that a
   * model handed only their names would pick between them by coin toss, so each has to say which
   * question it answers.
   */
  test("the two interruption tools say apart what they are for", () => {
    const outage = CATALOGUE.find(
      (tool) => tool.name === "technical.get_active_outage",
    );
    const schedule = CATALOGUE.find(
      (tool) => tool.name === "utility_schedule.read",
    );
    expect(outage?.description).toContain("at the time an incident occurred");
    expect(schedule?.description).toContain("within a time range");
  });

  test("a tool that refuses to guess says so where the model will read it", () => {
    const asset = CATALOGUE.find((tool) => tool.name === "asset.read");
    expect(asset?.description).toContain("NEEDS_INPUT");
    const sop = CATALOGUE.find((tool) => tool.name === "sop_kb.retrieve");
    expect(sop?.description).toContain("NOT_FOUND");
    const sensor = CATALOGUE.find((tool) => tool.name === "sensor.read");
    expect(sensor?.description).toContain("never conclude");
    const history = CATALOGUE.find(
      (tool) => tool.name === "maintenance_history.read",
    );
    expect(history?.description).toContain("not a diagnosis");
  });
});

describe("finding a tool by the name a call arrives under", () => {
  test("every tool is offered under a name a model is allowed to call", () => {
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
  test("each tool answers to the ref the agent callback route derives from its model name", () => {
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

  test("no two tools answer to the same name", () => {
    const names = technicalTools.flatMap((tool) => [tool.name, tool.modelName]);
    expect(new Set(names).size).toBe(names.length);
  });

  test("a name that belongs to somebody else is not claimed", () => {
    expect(findTechnicalTool("google_drive/search_files")).toBeUndefined();
    expect(findTechnicalTool("technical.unknown_tool")).toBeUndefined();
  });
});

/*
 * The issue codes are reference data the tools share: `sop_kb.retrieve` matches documents to one,
 * and the classification and verification tools will read the levels. general.md §12.2 requires all
 * sixteen to be classified correctly, so a code quietly dropped here would take a requirement with
 * it.
 */
describe("the issue codes of general.md §4", () => {
  test("all sixteen are present, once each", () => {
    expect(ISSUE_CODES).toHaveLength(16);
    expect(new Set(ISSUE_CODES.map((code) => code.code)).size).toBe(16);
  });

  test.each(ISSUE_CODES.map((code) => [code.code, code] as const))(
    "%s carries a level and what raises it",
    (_code, code) => {
      expect(code.code).toMatch(/^TECH\.[A-Z]+\.[A-Z0-9_]+$/);
      expect(code.code.split(".")[1]).toBe(code.group);
      // No code defaults to level 1: that is a judgement about the signals, not about the fault.
      expect([2, 3]).toContain(code.defaultLevel);
      expect(code.escalatesToLevel1.length).toBeGreaterThan(5);
      expect(code.name.length).toBeGreaterThan(5);
    },
  );
});
