import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { parseAgentToolCallInput } from "../../src/agents/callback-token";
import {
  createDbInterruptionReadPort,
  findTechnicalTool,
  type InterruptionReadPort,
} from "../../src/technical-tools";
import { LEVEL_CASES, type ToolCall } from "./fixtures/cases";
import { INTERRUPTIONS, idOf } from "./fixtures/interruptions";
import {
  AGENT_VERSION,
  BUILDING,
  CALLER,
  NOW,
  SCOPE,
  SOURCE_RUN_ID,
  TENANT,
  TRACE_ID,
} from "./fixtures/world";
import {
  DATABASE_SETUP_TIMEOUT_MS,
  type TestDatabase,
  technicalToolsTestDatabase,
} from "./support/database";
import { technicalToolHarness } from "./support/harness";

/**
 * The two tools end to end, the way a Bot's call reaches them: through the function
 * `/api/agent-tools/call` is handed, down through the host's checks, into the database adapter and
 * the real schema, and back out as the envelope the agent reads.
 *
 * Nothing between the caller and the tables is faked. The one stand-in is the resolver that says
 * who the caller is, because the runtime gateway that will answer that does not exist yet.
 */
let db: TestDatabase;
let interruptions: InterruptionReadPort;

beforeAll(async () => {
  db = await technicalToolsTestDatabase();
  interruptions = createDbInterruptionReadPort(db.database);
}, DATABASE_SETUP_TIMEOUT_MS);

afterAll(() => db?.close());

/**
 * The name as the route would pass it on: a model is offered `technical__get_active_outage`, and
 * the route rewrites that to a ref before it asks a deployment tool caller.
 */
function refFor(toolName: string) {
  const tool = findTechnicalTool(toolName);
  if (!tool) throw new Error(`${toolName} is not in the catalogue.`);
  const parsed = parseAgentToolCallInput({ name: tool.modelName, args: {} });
  if (!parsed.ok) throw new Error(parsed.error);
  return parsed.value.ref;
}

const OUTAGE = "technical.get_active_outage";
const SCHEDULE = "utility_schedule.read";

const outageArgs = (
  building_id: string,
  service_type = "water",
  occurred_at = "2026-09-30T09:00:00Z",
) => ({ building_id, service_type, occurred_at });

/** The ids a call returned, whichever of the two tools it was. */
function returnedIds(call: ToolCall, data: unknown): string[] {
  if (call.tool === OUTAGE) {
    const { outages } = data as { outages: { outage_id: string }[] };
    return outages.map((outage) => outage.outage_id);
  }
  const { schedules } = data as { schedules: { schedule_id: string }[] };
  return schedules.map((schedule) => schedule.schedule_id);
}

describe.each([3, 2, 1] as const)("level %d incidents", (level) => {
  const cases = LEVEL_CASES.filter((candidate) => candidate.level === level);

  test.each(
    cases.map((levelCase) => [levelCase.id, levelCase.report, levelCase]),
  )("%s: %s", async (_id, _report, levelCase) => {
    const harness = technicalToolHarness({ interruptions });

    for (const call of levelCase.calls) {
      const { envelope, isError } = await harness.call(
        refFor(call.tool),
        call.args,
      );

      expect(envelope.status).toBe("OK");
      expect(isError).toBe(false);
      expect(envelope.errors).toEqual([]);
      expect(returnedIds(call, envelope.data)).toEqual(call.expect.map(idOf));
    }

    // One audit entry per call, each traceable to the run and the agent release that made it.
    expect(harness.auditEntries).toHaveLength(levelCase.calls.length);
    for (const entry of harness.auditEntries) {
      expect(entry).toMatchObject({
        status: "OK",
        trace_id: TRACE_ID,
        agent_version: AGENT_VERSION,
        tenant_id: TENANT.vinhomes,
        source_run_id: SOURCE_RUN_ID,
        bot_id: CALLER.technicalAgent.botId,
        occurred_at: NOW.toISOString(),
      });
    }
  });
});

describe("the cases cover what they claim to", () => {
  test("every level has incidents, and every call names a fixture that exists", () => {
    for (const level of [1, 2, 3]) {
      expect(LEVEL_CASES.some((candidate) => candidate.level === level)).toBe(
        true,
      );
    }
    for (const levelCase of LEVEL_CASES) {
      for (const call of levelCase.calls) call.expect.map(idOf);
    }
  });

  /*
   * A fixture no case ever returns proves nothing, unless it is one of the rows that exist
   * precisely to never be returned.
   */
  test("every official interruption in the agent's buildings is returned by some case", () => {
    const returned = new Set(
      LEVEL_CASES.flatMap((levelCase) =>
        levelCase.calls.flatMap((call) => call.expect),
      ),
    );
    const neverReturned = INTERRUPTIONS.map((fixture) => fixture.key).filter(
      (key) => !returned.has(key),
    );
    // Proposed, cancelled, outside the grant, another tenant, malformed.
    expect(neverReturned).toEqual(["I3", "I4", "I8", "I9", "I10"]);
  });
});

describe("what an answer carries", () => {
  test("an outage past its announced end is still reported, with that end unchanged", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1),
    );

    expect(envelope.data).toEqual({
      outages: [
        {
          outage_id: idOf("I1"),
          service_type: "water",
          status: "active",
          scope_ids: [SCOPE.buildingA1],
          started_at: "2026-09-30T06:05:00.000Z",
          ended_at: null,
          // 08:30 is already half an hour gone at 09:00. The tool does not invent a later one.
          published_eta: "2026-09-30T08:30:00.000Z",
        },
      ],
    });
  });

  test("a finished outage says when it ended", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1, "water", "2026-09-29T15:00:00Z"),
    );
    const { outages } = envelope.data as {
      outages: { status: string; started_at: string; ended_at: string }[];
    };

    expect(outages[0]).toMatchObject({
      status: "restored",
      started_at: "2026-09-29T14:10:00.000Z",
      ended_at: "2026-09-29T15:40:00.000Z",
    });
  });

  test("a schedule covering two buildings is one entry with both scopes", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(refFor(SCHEDULE), {
      building_id: BUILDING.a1,
      utility_type: "power",
      time_range: { from: "2026-10-01T00:00:00Z", to: "2026-10-02T00:00:00Z" },
    });

    expect(envelope.data).toEqual({
      schedules: [
        {
          schedule_id: idOf("I2"),
          utility_type: "power",
          status: "notified",
          planned_start: "2026-10-01T02:00:00.000Z",
          planned_end: "2026-10-01T04:00:00.000Z",
          scope_ids: [SCOPE.buildingA1, SCOPE.buildingA2],
        },
      ],
    });
  });

  test("names the record and revision each result came from", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1),
    );

    expect(envelope.provenance).toHaveLength(1);
    expect(envelope.provenance[0]).toMatchObject({
      source_system: "application_db",
      source_record_id: idOf("I1"),
      retrieved_at: NOW.toISOString(),
    });
    expect(typeof envelope.provenance[0]?.source_version).toBe("string");
  });

  test("an empty answer still says which system it asked", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1, "power", "2026-09-30T07:00:00Z"),
    );

    expect(envelope.data).toEqual({ outages: [] });
    expect(envelope.provenance).toEqual([
      { source_system: "application_db", retrieved_at: NOW.toISOString() },
    ]);
  });

  test("is stamped with the server's time and the run's trace id", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1),
    );

    expect(envelope.trace_id).toBe(TRACE_ID);
    expect(envelope.server_time).toBe(NOW.toISOString());
  });
});

/*
 * A refusal must not answer the question it refuses. If a building outside the grant, a building in
 * another tenant and a building that does not exist were refused differently, the difference would
 * tell a caller which buildings exist.
 */
describe("a building the caller may not ask about", () => {
  async function refusal(buildingId: string) {
    const harness = technicalToolHarness({ interruptions });
    const answer = await harness.call(refFor(OUTAGE), outageArgs(buildingId));
    return { ...answer, auditEntries: harness.auditEntries };
  }

  test.each([
    ["N1: in the same tenant but outside the grant", BUILDING.b1],
    ["N2: in another tenant", BUILDING.x1],
    ["N3: nowhere at all", BUILDING.missing],
  ])("%s", async (_label, buildingId) => {
    const { envelope, isError, text, auditEntries } = await refusal(buildingId);

    expect(envelope.status).toBe("FORBIDDEN");
    expect(isError).toBe(true);
    expect(envelope.data).toBeNull();
    expect(envelope.provenance).toEqual([]);
    // B1 has an active outage (I8) and X1 has one too (I9). Neither may be hinted at.
    expect(text).not.toContain(idOf("I8"));
    expect(text).not.toContain(idOf("I9"));
    expect(auditEntries).toHaveLength(1);
    expect(auditEntries[0]).toMatchObject({
      status: "FORBIDDEN",
      building_id: buildingId,
      result_count: null,
    });
  });

  test("all three are refused in exactly the same words", async () => {
    const [outsideGrant, otherTenant, missing] = await Promise.all(
      [BUILDING.b1, BUILDING.x1, BUILDING.missing].map(refusal),
    );

    expect(otherTenant.envelope).toEqual(outsideGrant.envelope);
    expect(missing.envelope).toEqual(outsideGrant.envelope);
  });

  test("the schedule tool refuses the same building the same way", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(refFor(SCHEDULE), {
      building_id: BUILDING.b1,
      utility_type: "water",
      time_range: { from: "2026-09-30T00:00:00Z", to: "2026-10-01T00:00:00Z" },
    });

    expect(envelope.status).toBe("FORBIDDEN");
    expect(envelope.data).toBeNull();
  });
});

describe("a caller without the right to call", () => {
  test("N4: a Bot never granted interruption:read is refused, for a building it may see", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1),
      CALLER.ungrantedAgent,
    );

    expect(envelope.status).toBe("FORBIDDEN");
    expect(envelope.data).toBeNull();
    expect(harness.auditEntries[0]?.detail).toContain("interruption:read");
  });

  /*
   * Checked before the input is read, so a caller with no grant learns nothing from the shape of
   * the refusal either: a malformed call gets the same answer as a well-formed one.
   */
  test("the capability is checked before the input is", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      { nonsense: true },
      CALLER.ungrantedAgent,
    );

    expect(envelope.status).toBe("FORBIDDEN");
  });

  test("a Bot the deployment has no identity for is refused and still recorded", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1),
      CALLER.unknownAgent,
    );

    expect(envelope.status).toBe("FORBIDDEN");
    expect(harness.auditEntries).toHaveLength(1);
    expect(harness.auditEntries[0]).toMatchObject({
      status: "FORBIDDEN",
      tenant_id: null,
      agent_version: null,
      bot_id: CALLER.unknownAgent.botId,
    });
  });

  test("a resolver that answers with something malformed grants nothing", async () => {
    const harness = technicalToolHarness(
      { interruptions },
      {
        contextResolver: async () =>
          ({
            tenant_id: "not-a-uuid",
            capabilities: ["interruption:read"],
          }) as never,
      },
    );
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1),
    );

    expect(envelope.status).toBe("FORBIDDEN");
  });
});

describe("input the tools will not act on", () => {
  test("N5: a schedule range that runs backwards names the field at fault", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope, isError } = await harness.call(refFor(SCHEDULE), {
      building_id: BUILDING.a1,
      utility_type: "power",
      time_range: { from: "2026-10-02T00:00:00Z", to: "2026-10-01T00:00:00Z" },
    });

    expect(envelope.status).toBe("INVALID_INPUT");
    expect(isError).toBe(true);
    expect(envelope.errors).toEqual([
      {
        code: "INVALID_INPUT",
        message: "time_range.from must be earlier than time_range.to.",
        field: "time_range",
        retryable: false,
      },
    ]);
  });

  test.each([
    ["N6: an unknown utility", { service_type: "gas" }, "service_type"],
    [
      "N6: a building id that is not a UUID",
      { building_id: "A1" },
      "building_id",
    ],
    [
      "N6: a time with no timezone",
      { occurred_at: "2026-09-30T09:00:00" },
      "occurred_at",
    ],
    [
      "N7: a tenant_id of the agent's choosing",
      { tenant_id: TENANT.other },
      "tenant_id",
    ],
  ])("%s", async (_label, change, field) => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(refFor(OUTAGE), {
      ...outageArgs(BUILDING.a1),
      ...change,
    });

    expect(envelope.status).toBe("INVALID_INPUT");
    expect(envelope.data).toBeNull();
    expect(envelope.errors.map((error) => error.field)).toContain(field);
    expect(envelope.errors.every((error) => !error.retryable)).toBe(true);
  });

  /*
   * N7 again, from the other side. Supplying another tenant's id must not merely be rejected as a
   * shape; it must not be able to reach that tenant's outage under any spelling of the call.
   */
  test("no argument reaches another tenant's outage", async () => {
    const harness = technicalToolHarness({ interruptions });
    const { text } = await harness.call(refFor(OUTAGE), {
      ...outageArgs(BUILDING.x1, "power"),
      tenant_id: TENANT.other,
    });

    expect(text).not.toContain(idOf("I9"));
  });
});

/*
 * L1-3. An emergency is exactly when a slow or broken database must not leave the agent waiting:
 * the flow goes on to raise its requests whether or not this lookup answered.
 */
describe("when the data source fails mid-incident", () => {
  const SECRET = "postgres://openbot:s3cret-password@db.internal:5432/openbot";

  test("the agent is told to retry, and told nothing about the database", async () => {
    const failing: InterruptionReadPort = {
      listCovering: async () => {
        throw new Error(`connect ECONNREFUSED ${SECRET}`);
      },
    };
    const harness = technicalToolHarness({ interruptions: failing });
    const { envelope, isError, text } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1, "power"),
    );

    expect(envelope.status).toBe("INTERNAL_ERROR");
    expect(isError).toBe(true);
    expect(envelope.data).toBeNull();
    expect(envelope.errors).toEqual([
      {
        code: "INTERNAL_ERROR",
        message: "The tool could not complete the request.",
        retryable: true,
      },
    ]);
    for (const leaked of [
      "postgres://",
      "s3cret",
      "ECONNREFUSED",
      "db.internal",
    ]) {
      expect(text).not.toContain(leaked);
      expect(JSON.stringify(harness.auditEntries)).not.toContain(leaked);
    }
    expect(harness.auditEntries[0]?.status).toBe("INTERNAL_ERROR");
  });

  test("a data source that never answers is given up on, not waited for", async () => {
    const hanging: InterruptionReadPort = {
      listCovering: () => new Promise(() => {}),
    };
    const harness = technicalToolHarness(
      { interruptions: hanging },
      {
        options: { timeoutMs: 50 },
      },
    );
    const started = performance.now();
    const { envelope } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1, "power"),
    );

    expect(envelope.status).toBe("INTERNAL_ERROR");
    expect(envelope.errors[0]?.retryable).toBe(true);
    expect(performance.now() - started).toBeLessThan(2_000);
    expect(harness.auditEntries[0]?.detail).toContain("timeout");
  });

  /*
   * The gateway these tools sit beside never acts without its audit row. A result handed back
   * while the trail could not be written would be the one call nobody can later account for.
   */
  test("a call that cannot be recorded returns no data", async () => {
    const harness = technicalToolHarness(
      { interruptions },
      {
        audit: {
          record: async () => {
            throw new Error("audit store unavailable");
          },
        },
      },
    );
    const { envelope, text } = await harness.call(
      refFor(OUTAGE),
      outageArgs(BUILDING.a1),
    );

    expect(envelope.status).toBe("INTERNAL_ERROR");
    expect(envelope.data).toBeNull();
    expect(text).not.toContain(idOf("I1"));
  });
});

describe("the door the server opens to these tools", () => {
  test("a name that is not a technical tool is left for the plugin store", async () => {
    const harness = technicalToolHarness({ interruptions });

    expect(
      await harness.caller({
        name: "google_drive/search_files",
        args: {},
        ...CALLER.technicalAgent,
      }),
    ).toBeNull();
    expect(harness.auditEntries).toEqual([]);
  });

  test.each([
    ["the name in tools.md", OUTAGE],
    ["the name a model is offered", "technical__get_active_outage"],
    ["the ref the route derives from it", "technical/get_active_outage"],
  ])("answers to %s", async (_label, name) => {
    const harness = technicalToolHarness({ interruptions });
    const { envelope } = await harness.call(name, outageArgs(BUILDING.a1));

    expect(envelope.status).toBe("OK");
  });

  test("records what started the run, as the audit trail does for every other tool", async () => {
    const harness = technicalToolHarness({ interruptions });
    await harness.call(refFor(OUTAGE), outageArgs(BUILDING.a1), {
      ...CALLER.technicalAgent,
      initiator: { kind: "routine", id: "routine-nightly-check" },
    });

    expect(harness.auditEntries[0]?.initiator).toEqual({
      kind: "routine",
      id: "routine-nightly-check",
    });
  });

  test("records how many records came back, never the records", async () => {
    const harness = technicalToolHarness({ interruptions });
    await harness.call(refFor(OUTAGE), outageArgs(BUILDING.a1));

    expect(harness.auditEntries[0]).toMatchObject({
      tool: OUTAGE,
      tool_version: "1.0.0",
      building_id: BUILDING.a1,
      result_count: 1,
    });
    expect(JSON.stringify(harness.auditEntries)).not.toContain(idOf("I1"));
  });
});
