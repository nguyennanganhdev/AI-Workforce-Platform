import { describe, expect, test } from "bun:test";
import { z } from "zod";
import {
  type ContextResolver,
  createInMemoryApprovalRequestStore,
  createInMemoryAssetReadPort,
  createInMemoryExecutorResultStore,
  createInMemoryIdempotencyStore,
  createInMemoryMaintenanceReadPort,
  createInMemoryMaintenanceStore,
  createInMemoryMeasurementStore,
  createInMemorySensorReadPort,
  createInMemorySopProfilePort,
  createTechnicalToolHost,
  defineTool,
  type HostOptions,
  type IdempotencyStore,
  type ToolOutcome,
} from "../../src/technical-tools";
import { payloadHash } from "../../src/technical-tools/idempotency";
import { BUILDING, CALLER, TENANT } from "./fixtures/world";
import {
  fixedClock,
  fixtureContextResolver,
  recordingAudit,
} from "./support/harness";

/**
 * The host's guard against a write happening twice (tools.md §1.4), tried with stand-in write tools
 * whose behaviour each test decides: answer at once, refuse, fail, or wait until told to finish.
 *
 * The real tools are tried the same way in `measurement-result.flow.test.ts`. Here the question is
 * only the host's: given a key, does a write run at most once, and does a call that wrote nothing
 * leave the key free to be used again?
 */
const unused = () => {
  throw new Error("The stand-in tools read no data.");
};

function hostWith(
  overrides: {
    idempotency?: IdempotencyStore;
    contextResolver?: ContextResolver;
    options?: HostOptions;
  } = {},
) {
  const audit = recordingAudit();
  const host = createTechnicalToolHost(
    {
      interruptions: { listCovering: unused },
      sop: { listForBuilding: unused },
      sopProfiles: createInMemorySopProfilePort(),
      assets: createInMemoryAssetReadPort(),
      sensors: createInMemorySensorReadPort(),
      maintenance: createInMemoryMaintenanceReadPort(),
      maintenanceStore: createInMemoryMaintenanceStore(),
      scopes: { placement: unused, findScopes: unused },
      isolations: { findOpen: unused, createWaterIsolation: unused },
      approvalRequests: createInMemoryApprovalRequestStore(),
      workOrders: {
        getWorkOrder: unused,
        getTicket: unused,
        findEvidence: unused,
      },
      measurements: createInMemoryMeasurementStore(),
      executorResults: createInMemoryExecutorResultStore(),
      idempotency: overrides.idempotency ?? createInMemoryIdempotencyStore(),
      clock: fixedClock,
      contextResolver: overrides.contextResolver ?? fixtureContextResolver,
      audit: audit.sink,
    },
    overrides.options,
  );
  return { host, audit: audit.entries };
}

type Written = { record_id: string };

/**
 * A write tool whose every run is counted, and whose answer `behave` decides.
 *
 * The run number is the record id, so a test can tell the first run's answer from a second run's:
 * a replay must hand back `record-1` however many times it is asked.
 */
function writeTool(
  behave: (run: number) => Promise<ToolOutcome<Written>> = async (run) => ({
    status: "OK",
    data: { record_id: `record-${run}` },
  }),
  name = "test.write",
) {
  const runs: number[] = [];
  const tool = defineTool({
    name,
    version: "1.0.0",
    description: "A stand-in write tool whose answer the test decides.",
    effect: "write",
    capability: "measurement:write",
    timeoutMs: 1_000,
    inputSchema: z.strictObject({
      building_id: z.uuid(),
      value: z.number(),
      note: z.strictObject({ a: z.string(), b: z.string() }).optional(),
      idempotency_key: z.string().min(8),
    }),
    outputSchema: z.strictObject({ record_id: z.string() }),
    run: async () => {
      runs.push(runs.length + 1);
      return behave(runs.length);
    },
  });
  return { tool, runs };
}

/** A promise a test opens when it chooses, to hold a run in flight. */
function latch() {
  let open: () => void = () => {};
  const opened = new Promise<void>((resolve) => {
    open = resolve;
  });
  return { open, opened };
}

const KEY = "measure-WO-AC-flow-1";
const args = (value = 1.2, key = KEY) => ({
  building_id: BUILDING.a1,
  value,
  idempotency_key: key,
});

describe("I-1: the same request twice", () => {
  test("runs once and hands back the first answer both times", async () => {
    const { host } = hostWith();
    const { tool, runs } = writeTool();

    const first = await host.call(CALLER.technicalAgent, tool, args());
    const second = await host.call(CALLER.technicalAgent, tool, args());

    expect(first.status).toBe("OK");
    expect(second.status).toBe("OK");
    expect(second.data).toEqual({ record_id: "record-1" });
    expect(second.data).toEqual(first.data);
    expect(runs).toEqual([1]);
  });

  test("the audit trail tells the replay apart from the write", async () => {
    const { host, audit } = hostWith();
    const { tool } = writeTool();

    await host.call(CALLER.technicalAgent, tool, args());
    await host.call(CALLER.technicalAgent, tool, args());

    expect(audit[0]?.idempotent_replay).toBeUndefined();
    expect(audit[1]?.idempotent_replay).toBe(true);
    expect(audit[1]?.status).toBe("OK");
    expect(audit[1]?.detail).toContain("earlier call");
  });

  /*
   * An agent framework may serialise the same arguments in a different order on a retry. Taking
   * that for a different request would refuse the very retry the key exists to allow.
   */
  test("a retry with its properties in another order is the same request", async () => {
    const { host } = hostWith();
    const { tool, runs } = writeTool();

    await host.call(CALLER.technicalAgent, tool, {
      building_id: BUILDING.a1,
      value: 1.2,
      note: { a: "x", b: "y" },
      idempotency_key: KEY,
    });
    const again = await host.call(CALLER.technicalAgent, tool, {
      idempotency_key: KEY,
      note: { b: "y", a: "x" },
      value: 1.2,
      building_id: BUILDING.a1,
    });

    expect(again.status).toBe("OK");
    expect(runs).toEqual([1]);
  });
});

describe("what the request's fingerprint covers", () => {
  test("not the order of its properties, at any depth", () => {
    expect(payloadHash({ a: 1, b: { c: 2, d: [3, { e: 4, f: 5 }] } })).toBe(
      payloadHash({ b: { d: [3, { f: 5, e: 4 }], c: 2 }, a: 1 }),
    );
  });

  test("not the key itself, which is the name of the request and not part of it", () => {
    expect(payloadHash({ value: 1, idempotency_key: "first-key" })).toBe(
      payloadHash({ value: 1, idempotency_key: "second-key" }),
    );
  });

  test("every value, and the order of a list", () => {
    expect(payloadHash({ value: 1.2 })).not.toBe(payloadHash({ value: 1.3 }));
    expect(payloadHash({ ids: ["a", "b"] })).not.toBe(
      payloadHash({ ids: ["b", "a"] }),
    );
    expect(payloadHash({ value: 1 })).not.toBe(
      payloadHash({ value: 1, extra: null }),
    );
  });
});

describe("I-2: the same key for a different request", () => {
  test("is a conflict, and the first record stands", async () => {
    const { host, audit } = hostWith();
    const { tool, runs } = writeTool();

    await host.call(CALLER.technicalAgent, tool, args(1.2));
    const changed = await host.call(CALLER.technicalAgent, tool, args(1.3));

    expect(changed.status).toBe("CONFLICT");
    expect(changed.data).toBeNull();
    expect(changed.errors).toEqual([
      expect.objectContaining({
        code: "CONFLICT",
        field: "idempotency_key",
        retryable: false,
      }),
    ]);
    expect(runs).toEqual([1]);
    expect(audit[1]?.detail).toContain("different payload");

    // The original is still what the key answers with.
    const original = await host.call(CALLER.technicalAgent, tool, args(1.2));
    expect(original.data).toEqual({ record_id: "record-1" });
  });

  test("a new key for the new request is written as usual", async () => {
    const { host } = hostWith();
    const { tool, runs } = writeTool();

    await host.call(CALLER.technicalAgent, tool, args(1.2));
    const next = await host.call(
      CALLER.technicalAgent,
      tool,
      args(1.3, "measure-WO-AC-flow-2"),
    );

    expect(next.data).toEqual({ record_id: "record-2" });
    expect(runs).toEqual([1, 2]);
  });
});

describe("I-3: two calls with one key at the same time", () => {
  test("only one writes; the other is told to retry", async () => {
    const { host } = hostWith();
    const started = latch();
    const finish = latch();
    const { tool, runs } = writeTool(async (run) => {
      started.open();
      await finish.opened;
      return { status: "OK", data: { record_id: `record-${run}` } };
    });

    const first = host.call(CALLER.technicalAgent, tool, args());
    await started.opened;
    const second = await host.call(CALLER.technicalAgent, tool, args());

    expect(second.status).toBe("CONFLICT");
    expect(second.errors[0]).toMatchObject({
      field: "idempotency_key",
      retryable: true,
    });

    finish.open();
    expect((await first).status).toBe("OK");
    expect(runs).toEqual([1]);

    // Retrying as told now gets the first call's answer.
    const retried = await host.call(CALLER.technicalAgent, tool, args());
    expect(retried.data).toEqual({ record_id: "record-1" });
    expect(runs).toEqual([1]);
  });

  test("a different request under the running key is refused outright, not deferred", async () => {
    const { host } = hostWith();
    const started = latch();
    const finish = latch();
    const { tool } = writeTool(async (run) => {
      started.open();
      await finish.opened;
      return { status: "OK", data: { record_id: `record-${run}` } };
    });

    const first = host.call(CALLER.technicalAgent, tool, args(1.2));
    await started.opened;
    const other = await host.call(CALLER.technicalAgent, tool, args(9.9));
    finish.open();
    await first;

    expect(other.status).toBe("CONFLICT");
    expect(other.errors[0]?.retryable).toBe(false);
  });
});

/*
 * A refused call wrote nothing. Holding its key would make the agent invent a new key just to send
 * the corrected request, which is what a retry with the same key is supposed to make unnecessary.
 */
describe("I-4: a call the tool refused", () => {
  test.each(["FORBIDDEN", "INVALID_INPUT", "NOT_FOUND", "CONFLICT"] as const)(
    "%s leaves the key free for the corrected request",
    async (status) => {
      const { host } = hostWith();
      const { tool, runs } = writeTool(async (run) =>
        run === 1
          ? {
              status,
              data: null,
              errors: [{ code: status, message: "refused", retryable: false }],
            }
          : { status: "OK", data: { record_id: `record-${run}` } },
      );

      const refused = await host.call(CALLER.technicalAgent, tool, args(1.2));
      const corrected = await host.call(CALLER.technicalAgent, tool, args(1.3));

      expect(refused.status).toBe(status);
      expect(corrected.status).toBe("OK");
      expect(corrected.data).toEqual({ record_id: "record-2" });
      expect(runs).toEqual([1, 2]);
    },
  );

  test("and the same request sent again is decided afresh, not replayed as a refusal", async () => {
    const { host, audit } = hostWith();
    const { tool, runs } = writeTool(async () => ({
      status: "FORBIDDEN",
      data: null,
      errors: [{ code: "FORBIDDEN", message: "refused", retryable: false }],
    }));

    await host.call(CALLER.technicalAgent, tool, args());
    await host.call(CALLER.technicalAgent, tool, args());

    expect(runs).toEqual([1, 2]);
    expect(audit.some((entry) => entry.idempotent_replay)).toBe(false);
  });

  test("a call the host refused never reaches the store at all", async () => {
    const { host } = hostWith();
    const { tool, runs } = writeTool();

    const outside = await host.call(CALLER.technicalAgent, tool, {
      ...args(),
      building_id: BUILDING.b1,
    });
    const ungranted = await host.call(CALLER.ungrantedAgent, tool, args());
    const malformed = await host.call(CALLER.technicalAgent, tool, {
      ...args(),
      value: "1.2",
    });
    const fine = await host.call(CALLER.technicalAgent, tool, args(4.5));

    expect([outside.status, ungranted.status, malformed.status]).toEqual([
      "FORBIDDEN",
      "FORBIDDEN",
      "INVALID_INPUT",
    ]);
    expect(fine.status).toBe("OK");
    expect(runs).toEqual([1]);
  });

  test("an answer that is a write, waiting on approval, is kept like any other write", async () => {
    const { host } = hostWith();
    const { tool, runs } = writeTool(async () => ({
      status: "PENDING_APPROVAL",
      data: null,
    }));

    await host.call(CALLER.technicalAgent, tool, args());
    const again = await host.call(CALLER.technicalAgent, tool, args());

    expect(again.status).toBe("PENDING_APPROVAL");
    expect(runs).toEqual([1]);
  });
});

describe("I-5: a run that failed part way", () => {
  test("releases the key, so the retry writes once", async () => {
    const { host } = hostWith();
    const { tool, runs } = writeTool(async (run) => {
      if (run === 1) throw new Error("The store went away.");
      return { status: "OK", data: { record_id: `record-${run}` } };
    });

    const failed = await host.call(CALLER.technicalAgent, tool, args());
    const retried = await host.call(CALLER.technicalAgent, tool, args());

    expect(failed.status).toBe("INTERNAL_ERROR");
    // A write may have landed before it failed, so the agent is told to reconcile, not to repeat.
    expect(failed.errors[0]?.retryable).toBe(false);
    expect(retried.status).toBe("OK");
    expect(retried.data).toEqual({ record_id: "record-2" });
    expect(runs).toEqual([1, 2]);
  });

  test("a key store that cannot be reached stops the write before it starts", async () => {
    const broken: IdempotencyStore = {
      reserve: async () => {
        throw new Error("unreachable");
      },
      complete: async () => {},
      release: async () => {},
    };
    const { host, audit } = hostWith({ idempotency: broken });
    const { tool, runs } = writeTool();

    const envelope = await host.call(CALLER.technicalAgent, tool, args());

    expect(envelope.status).toBe("INTERNAL_ERROR");
    expect(runs).toEqual([]);
    expect(audit[0]?.detail).toContain("idempotency store");
  });
});

/*
 * The caller gives up at the timeout, but the run does not stop: the write may land a moment later.
 * If the key were released when the caller gave up, the agent's retry would write it again.
 */
describe("a run still going when the caller stops waiting", () => {
  test("keeps its key until it ends, then the retry gets its answer", async () => {
    const { host } = hostWith({ options: { timeoutMs: 20 } });
    const finish = latch();
    const { tool, runs } = writeTool(async (run) => {
      await finish.opened;
      return { status: "OK", data: { record_id: `record-${run}` } };
    });

    const timedOut = await host.call(CALLER.technicalAgent, tool, args());
    expect(timedOut.status).toBe("INTERNAL_ERROR");

    const tooSoon = await host.call(CALLER.technicalAgent, tool, args());
    expect(tooSoon.status).toBe("CONFLICT");
    expect(tooSoon.errors[0]?.retryable).toBe(true);

    finish.open();
    await Bun.sleep(10);

    const later = await host.call(CALLER.technicalAgent, tool, args());
    expect(later.status).toBe("OK");
    expect(later.data).toEqual({ record_id: "record-1" });
    expect(runs).toEqual([1]);
  });

  test("and releases it if the run then fails, so the retry can write", async () => {
    const { host } = hostWith({ options: { timeoutMs: 20 } });
    const finish = latch();
    const { tool, runs } = writeTool(async (run) => {
      if (run === 1) {
        await finish.opened;
        throw new Error("failed after the caller left");
      }
      return { status: "OK", data: { record_id: `record-${run}` } };
    });

    await host.call(CALLER.technicalAgent, tool, args());
    finish.open();
    await Bun.sleep(10);

    const retried = await host.call(CALLER.technicalAgent, tool, args());
    expect(retried.data).toEqual({ record_id: "record-2" });
    expect(runs).toEqual([1, 2]);
  });
});

describe("I-6: what a key is scoped to", () => {
  test("another tenant using the same key is a different request", async () => {
    const store = createInMemoryIdempotencyStore();
    const asOther: ContextResolver = async (caller) => {
      const identity = await fixtureContextResolver(caller);
      return identity && { ...identity, tenant_id: TENANT.other };
    };
    const { tool, runs } = writeTool();

    const ours = await hostWith({ idempotency: store }).host.call(
      CALLER.technicalAgent,
      tool,
      args(1.2),
    );
    const theirs = await hostWith({
      idempotency: store,
      contextResolver: asOther,
    }).host.call(CALLER.technicalAgent, tool, args(7.7));

    expect(ours.status).toBe("OK");
    expect(theirs.status).toBe("OK");
    expect(theirs.data).toEqual({ record_id: "record-2" });
    expect(runs).toEqual([1, 2]);
  });

  test("another tool using the same key is a different request", async () => {
    const { host } = hostWith();
    const measure = writeTool(undefined, "test.measure");
    const submit = writeTool(undefined, "test.submit");

    await host.call(CALLER.technicalAgent, measure.tool, args(1.2));
    const other = await host.call(
      CALLER.technicalAgent,
      submit.tool,
      args(7.7),
    );

    expect(other.status).toBe("OK");
    expect(submit.runs).toEqual([1]);
  });
});

describe("what the host does not guard", () => {
  test("a read never touches the key store", async () => {
    const tripwire: IdempotencyStore = {
      reserve: async () => {
        throw new Error("A read reserved a key.");
      },
      complete: async () => {},
      release: async () => {},
    };
    const { host } = hostWith({ idempotency: tripwire });
    const read = defineTool({
      name: "test.read",
      version: "1.0.0",
      description: "A stand-in read tool.",
      effect: "read",
      capability: "sensor:read",
      timeoutMs: 1_000,
      inputSchema: z.strictObject({ building_id: z.uuid() }),
      outputSchema: z.strictObject({ ok: z.boolean() }),
      run: async () => ({ status: "OK", data: { ok: true } }),
    });

    const envelope = await host.call(CALLER.technicalAgent, read, {
      building_id: BUILDING.a1,
    });
    expect(envelope.status).toBe("OK");
  });

  test("a write tool cannot be defined without demanding a key", () => {
    expect(() =>
      defineTool({
        name: "test.unguarded",
        version: "1.0.0",
        description: "A write tool that forgot its key.",
        effect: "write",
        capability: "measurement:write",
        timeoutMs: 1_000,
        inputSchema: z.strictObject({ building_id: z.uuid() }),
        outputSchema: z.strictObject({ ok: z.boolean() }),
        run: async () => ({ status: "OK", data: { ok: true } }),
      }),
    ).toThrow(/idempotency_key/);
  });
});
