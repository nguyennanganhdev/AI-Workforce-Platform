import { describe, expect, test } from "bun:test";
import { z } from "zod";
import {
  createInMemoryAssetReadPort,
  createInMemoryExecutorResultStore,
  createInMemoryIdempotencyStore,
  createInMemoryMaintenanceReadPort,
  createInMemoryMeasurementStore,
  createInMemorySensorReadPort,
  createInMemorySopProfilePort,
  createTechnicalToolHost,
  defineTool,
  type ToolStatus,
} from "../../src/technical-tools";
import { BUILDING, CALLER } from "./fixtures/world";
import {
  fixedClock,
  fixtureContextResolver,
  recordingAudit,
} from "./support/harness";

/**
 * The host's check on what a tool hands back, tried with a tool built to break it.
 *
 * A real tool cannot be made to return malformed data on demand, which is the point of the check:
 * it guards against the mistake nobody has made yet. So a stand-in tool is defined here and handed
 * to the host directly, the way the catalogue's own tools are.
 */
const unused = () => {
  throw new Error("This test's tool does not read data.");
};

function hostWith(audit = recordingAudit()) {
  return {
    audit,
    host: createTechnicalToolHost({
      interruptions: { listCovering: unused },
      sop: { listForBuilding: unused },
      sopProfiles: createInMemorySopProfilePort(),
      assets: createInMemoryAssetReadPort(),
      sensors: createInMemorySensorReadPort(),
      maintenance: createInMemoryMaintenanceReadPort(),
      workOrders: { getWorkOrder: unused, findEvidence: unused },
      measurements: createInMemoryMeasurementStore(),
      executorResults: createInMemoryExecutorResultStore(),
      idempotency: createInMemoryIdempotencyStore(),
      clock: fixedClock,
      contextResolver: fixtureContextResolver,
      audit: audit.sink,
    }),
  };
}

/** A tool that answers `status` with whatever `data` it is told to. */
function toolAnswering(status: ToolStatus, data: unknown) {
  return defineTool({
    name: "test.answers",
    version: "1.0.0",
    description: "A stand-in tool whose answer the test decides.",
    effect: "read",
    capability: "sensor:read",
    timeoutMs: 1_000,
    inputSchema: z.strictObject({ building_id: z.uuid() }),
    outputSchema: z.strictObject({ readings: z.array(z.number()) }),
    run: async () => ({ status, data: data as { readings: number[] } }),
  });
}

describe("what the host checks before an answer leaves", () => {
  test("well-formed data passes, whatever the status", async () => {
    for (const status of ["OK", "STALE_DATA", "NEEDS_INPUT"] as const) {
      const { host } = hostWith();
      const envelope = await host.call(
        CALLER.technicalAgent,
        toolAnswering(status, { readings: [1, 2] }),
        { building_id: BUILDING.a1 },
      );
      expect(envelope.status).toBe(status);
      expect(envelope.data).toEqual({ readings: [1, 2] });
    }
  });

  /*
   * Until this round only OK answers were checked. NEEDS_INPUT carries candidates and STALE_DATA
   * carries old readings, and an agent reads those as closely as a result, so a malformed one is
   * just as misleading.
   */
  test.each(["OK", "STALE_DATA", "NEEDS_INPUT"] as const)(
    "malformed data under %s becomes an INTERNAL_ERROR",
    async (status) => {
      const { host, audit } = hostWith();
      const envelope = await host.call(
        CALLER.technicalAgent,
        toolAnswering(status, { readings: ["MALFORMED-MARKER"] }),
        { building_id: BUILDING.a1 },
      );

      expect(envelope.status).toBe("INTERNAL_ERROR");
      expect(envelope.data).toBeNull();
      // None of the malformed data reaches the agent.
      expect(JSON.stringify(envelope)).not.toContain("MALFORMED-MARKER");
      expect(audit.entries[0]?.detail).toContain("output schema");
    },
  );

  test("an answer with no data is not checked, because there is nothing to check", async () => {
    const { host } = hostWith();
    const envelope = await host.call(
      CALLER.technicalAgent,
      toolAnswering("NOT_FOUND", null),
      { building_id: BUILDING.a1 },
    );

    expect(envelope.status).toBe("NOT_FOUND");
  });
});
