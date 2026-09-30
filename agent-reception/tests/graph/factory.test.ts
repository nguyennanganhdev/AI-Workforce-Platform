import { expect, test } from "bun:test";
import { FakeListChatModel } from "@langchain/core/utils/testing";
import { MemorySaver } from "@langchain/langgraph-checkpoint";
import type {
  ReceptionGraphResult,
  ReceptionResumeRequest,
  ReceptionRunRequest,
  ReceptionToolPort,
  ReceptionToolRequest,
  ReceptionToolResult,
  VerifiedReceptionContext,
} from "../../src/contracts";
import {
  createReceptionGraphFactory,
  type ReceptionBusinessState,
  type ToolBinding,
} from "../../src/graph";

type TestOperations = {
  verify_unit: {
    input: { unitId: string };
    output: { verifiedUnit: string };
  };
};
type Output = TestOperations["verify_unit"]["output"];
type Call = ReceptionToolRequest<
  "verify_unit",
  TestOperations["verify_unit"]["input"]
>;

const context: VerifiedReceptionContext = {
  principalId: "service-synthetic",
  tenantId: "tenant-synthetic",
  initiatedBy: "resident-synthetic",
  bindingId: "binding-synthetic",
  runId: "run-synthetic",
  requestId: "request-synthetic",
  permissions: ["unit:read"],
  checkpoint: {
    threadId: "thread-synthetic",
    namespace: "reception-synthetic",
  },
};
const request: ReceptionRunRequest = {
  context,
  operationId: "message-operation-1",
  message: { id: "message-1", text: "Tôi cần hỗ trợ." },
};
const complete = JSON.stringify({
  action: "complete",
  text: "Đã xác minh thông tin.",
});
const tool = JSON.stringify({
  action: "tool",
  operation: "verify_unit",
  input: { unitId: "unit-synthetic" },
  inferences: [{ name: "cause", value: "có thể rò nước" }],
});

function harness(
  responses: string[],
  options: {
    invoke?: (request: Call) => Promise<ReceptionToolResult<Output>>;
    reconcile?: ToolBinding<
      TestOperations["verify_unit"]["input"],
      Output
    >["reconcile"];
    saver?: MemorySaver;
    maxSteps?: number;
    maxClarifications?: number;
  } = {},
) {
  const calls: Call[] = [];
  const saver = options.saver ?? new MemorySaver();
  const port: ReceptionToolPort<TestOperations> = {
    async invoke(call) {
      calls.push(call);
      return options.invoke
        ? options.invoke(call)
        : { kind: "success", value: { verifiedUnit: call.input.unitId } };
    },
  };
  const binding: ToolBinding<TestOperations["verify_unit"]["input"], Output> = {
    description: "Test only: verify unit through an authorized backend.",
    inputSchema: {
      type: "object",
      properties: { unitId: { type: "string" } },
      required: ["unitId"],
      additionalProperties: false,
    },
    parseInput(value) {
      const input = value as { unitId?: unknown };
      if (!input || typeof input.unitId !== "string" || !input.unitId)
        throw new Error("Test invalid input");
      return { unitId: input.unitId };
    },
    parseOutput(value) {
      const output = value as { verifiedUnit?: unknown };
      if (!output || typeof output.verifiedUnit !== "string")
        throw new Error("Test invalid output");
      return { verifiedUnit: output.verifiedUnit };
    },
    confirmedFacts: (output) => [{ name: "unit", value: output.verifiedUnit }],
    ticket: () => ({
      id: "ticket-synthetic",
      generation: 1,
      aggregateVersion: 3,
    }),
    reconcile: options.reconcile,
  };
  const factory = createReceptionGraphFactory<TestOperations>({
    bindings: { verify_unit: binding },
    maxSteps: options.maxSteps,
    maxClarifications: options.maxClarifications,
  });
  return {
    calls,
    saver,
    factory,
    dependencies: {
      model: new FakeListChatModel({ responses }),
      tools: port,
      checkpointer: saver,
    },
    graph: factory.create({
      model: new FakeListChatModel({ responses }),
      tools: port,
      checkpointer: saver,
    }),
  };
}

function interrupted(result: ReceptionGraphResult<ReceptionBusinessState>) {
  if (result.status !== "interrupted")
    throw new Error(`Expected interrupt, got ${JSON.stringify(result)}`);
  return result;
}

function resume(
  result: ReceptionGraphResult<ReceptionBusinessState>,
  kind: "resident" | "backend",
): ReceptionResumeRequest {
  const waiting = interrupted(result);
  const interruptId = waiting.interrupts[0].id;
  return {
    context,
    operationId: "resume-operation-2",
    interruptId,
    source:
      kind === "resident"
        ? { kind, message: { id: "message-2", text: "Tôi chọn căn hộ này." } }
        : {
            kind,
            event: {
              eventId: "event-synthetic",
              bindingId: context.bindingId,
              interruptId,
              ticketId: "ticket-synthetic",
              generation: 1,
              aggregateVersion: 4,
            },
          },
  };
}

test("draft PH01 factory conforms and empty read does not create a session", async () => {
  const { factory, graph, calls } = harness([complete]);
  expect(factory.contractVersion).toBe("0.1.0-draft.1");
  expect(graph.stateSchemaVersion).toBe(1);
  expect(await graph.read(context)).toBeUndefined();
  expect(calls).toHaveLength(0);
});

test("intake completes a conversation turn without closing a ticket", async () => {
  const { graph, calls } = harness([complete]);
  const result = await graph.run(request);
  expect(result.status).toBe("completed");
  const state = await graph.read(context);
  expect(state?.phase).toBe("completion");
  expect(state?.reported).toEqual([request.message]);
  expect(state?.ticket).toBeNull();
  expect(state?.confirmed).toEqual([]);
  expect(calls).toHaveLength(0);
});

test.each(["clarify", "await_resident"])(
  "%s persists a resident wait and resumes without network",
  async (action) => {
    const { graph, calls } = harness([
      JSON.stringify({ action, text: "Bạn cần hỗ trợ việc gì?" }),
      complete,
    ]);
    const waiting = interrupted(await graph.run(request));
    expect(waiting.state.phase).toBe(
      action === "clarify" ? "clarify" : "awaiting_resident",
    );
    expect(waiting.interrupts[0].reason).toBe("resident_input");
    expect(await graph.run(request)).toMatchObject({
      status: "failed",
      code: "RESUME_REQUIRED",
    });
    const done = await graph.resume(resume(waiting, "resident"));
    expect(done.status).toBe("completed");
    expect((await graph.read(context))?.reported).toHaveLength(2);
    expect(calls).toHaveLength(0);
  },
);

test("tool plan/key are checkpointed before invoke; reported and inferred facts remain unconfirmed", async () => {
  const saver = new MemorySaver();
  let savedPending: unknown;
  const { graph, calls } = harness([tool, complete], {
    saver,
    invoke: async (call) => {
      const saved = await saver.getTuple({
        configurable: {
          thread_id: JSON.stringify([
            context.checkpoint.namespace,
            context.checkpoint.threadId,
          ]),
          checkpoint_ns: "",
        },
      });
      if (!saved)
        throw new Error("Tool plan must be checkpointed before invoke");
      savedPending = (
        saved.checkpoint.channel_values.data as ReceptionBusinessState
      ).pendingTool;
      return { kind: "success", value: { verifiedUnit: call.input.unitId } };
    },
  });
  const done = await graph.run(request);
  expect(done.status).toBe("completed");
  expect(calls).toHaveLength(1);
  expect(calls[0].context).toEqual(context);
  expect(calls[0].timeoutMs).toBe(10_000);
  expect(savedPending).toMatchObject({
    operation: "verify_unit",
    idempotencyKey: calls[0].idempotencyKey,
  });
  const state = await graph.read(context);
  expect(state?.confirmed).toEqual([
    {
      name: "unit",
      value: "unit-synthetic",
      source: {
        operation: "verify_unit",
        idempotencyKey: calls[0].idempotencyKey,
      },
    },
  ]);
  expect(state?.inferences).toEqual([
    { name: "cause", value: "có thể rò nước" },
  ]);
  expect(state?.ticket?.id).toBe("ticket-synthetic");
});

test("accepted waits for backend reconciliation, retaining key across graph recreation and new runId", async () => {
  const reconciled: string[] = [];
  const h = harness([tool, complete], {
    invoke: async () => ({
      kind: "accepted",
      operationId: "backend-operation-synthetic",
    }),
    reconcile: async (call) => {
      reconciled.push(call.idempotencyKey);
      return { kind: "success", value: { verifiedUnit: "unit-synthetic" } };
    },
  });
  const waiting = interrupted(await h.graph.run(request));
  expect(waiting.state.phase).toBe("awaiting_tool");
  expect(waiting.state.confirmed).toEqual([]);
  expect(waiting.interrupts[0].reason).toBe("backend_event");
  const recreated = h.factory.create({
    ...h.dependencies,
    model: new FakeListChatModel({ responses: [complete] }),
  });
  const input = resume(waiting, "backend");
  const done = await recreated.resume({
    ...input,
    context: { ...context, runId: "run-new" },
  });
  expect(done.status).toBe("completed");
  expect(reconciled).toEqual([h.calls[0].idempotencyKey]);
  expect(h.calls).toHaveLength(1);
  expect(await recreated.resume(input)).toMatchObject({
    status: "failed",
    code: "INTERRUPT_MISMATCH",
  });
});

test("accepted/unknown without reconciliation preserves pending interrupt and reports dependency", async () => {
  const { graph, calls } = harness([tool], {
    invoke: async () => ({
      kind: "failure",
      code: "timeout",
      outcome: "unknown",
      retryable: true,
    }),
  });
  const waiting = interrupted(await graph.run(request));
  expect(waiting.state.phase).toBe("awaiting_tool");
  expect(await graph.resume(resume(waiting, "backend"))).toMatchObject({
    status: "failed",
    code: "RECONCILIATION_UNAVAILABLE",
  });
  expect((await graph.read(context))?.pendingTool?.idempotencyKey).toBe(
    calls[0].idempotencyKey,
  );
  expect(calls).toHaveLength(1);
});

test("thrown tool errors do not leak messages or claim mutation failed", async () => {
  const { graph } = harness([tool], {
    invoke: async () => {
      throw new Error("secret-token-and-PII");
    },
  });
  const waiting = interrupted(await graph.run(request));
  expect(waiting.state.lastToolResult).toEqual({
    kind: "failure",
    code: "TOOL_RESPONSE_LOST",
    retryable: false,
    outcome: "unknown",
  });
  expect(JSON.stringify(waiting)).not.toContain("secret-token");
});

test("response schema failure keeps outcome unknown and never confirms facts", async () => {
  const { graph } = harness([tool], {
    invoke: async () => ({
      kind: "success",
      value: { verifiedUnit: 42 } as unknown as Output,
    }),
  });
  const waiting = interrupted(await graph.run(request));
  expect(waiting.state.confirmed).toEqual([]);
  expect(waiting.state.pendingTool).not.toBeNull();
  expect(waiting.state.lastToolResult).toMatchObject({
    kind: "failure",
    outcome: "unknown",
    code: "INVALID_TOOL_OUTPUT",
  });
});

test("403/not-applied produces human handoff and no blind retries", async () => {
  const { graph, calls } = harness([tool], {
    invoke: async () => ({
      kind: "failure",
      code: "forbidden",
      outcome: "not_applied",
      retryable: false,
    }),
  });
  const waiting = interrupted(await graph.run(request));
  expect(waiting.state.phase).toBe("handoff");
  expect(waiting.state.pendingTool).toBeNull();
  expect(waiting.interrupts[0].reason).toBe("human_review");
  expect(calls).toHaveLength(1);
});

test("model handoff awaits human review; backend notification alone does not close a ticket", async () => {
  const { graph, calls } = harness([
    JSON.stringify({ action: "handoff", text: "Yêu cầu cần người xem xét." }),
    complete,
  ]);
  const waiting = interrupted(await graph.run(request));
  expect(waiting.state.phase).toBe("handoff");
  expect(waiting.interrupts[0].reason).toBe("human_review");
  expect((await graph.resume(resume(waiting, "backend"))).status).toBe(
    "completed",
  );
  expect((await graph.read(context))?.ticket).toBeNull();
  expect(calls).toHaveLength(0);
});

test.each(["clarify", "await_resident"])(
  "bounded %s questions escalate instead of looping",
  async (action) => {
    const { graph } = harness(
      [JSON.stringify({ action, text: "Bạn mô tả thêm?" })],
      { maxClarifications: 1 },
    );
    const first = await graph.run(request);
    const second = interrupted(await graph.resume(resume(first, "resident")));
    expect(second.state.phase).toBe("handoff");
    expect(second.state.clarifications).toBe(1);
  },
);

test("bounded model/tool loop escalates after the configured decision budget", async () => {
  const { graph, calls } = harness([tool], { maxSteps: 2 });
  const waiting = interrupted(await graph.run(request));
  expect(waiting.state.phase).toBe("handoff");
  expect(calls).toHaveLength(2);
  expect(calls[0].idempotencyKey).not.toBe(calls[1].idempotencyKey);
});

test.each([
  "not JSON",
  JSON.stringify({
    action: "complete",
    text: "done",
    confirmed: [{ name: "unit", value: "forged" }],
  }),
  JSON.stringify({ action: "tool", operation: "drop_database", input: {} }),
  JSON.stringify({ action: "tool", operation: "verify_unit", input: {} }),
])(
  "invalid/unallowlisted model decision fails without a tool side effect: %s",
  async (response) => {
    const { graph, calls } = harness([response]);
    expect((await graph.run(request)).status).toBe("failed");
    expect(calls).toHaveLength(0);
    expect((await graph.read(context))?.confirmed).toEqual([]);
  },
);

test("wrong interrupt/source/binding cannot consume a resident wait", async () => {
  const { graph } = harness([
    JSON.stringify({ action: "clarify", text: "Cần thông tin gì?" }),
    complete,
  ]);
  const waiting = await graph.run(request);
  const valid = resume(waiting, "resident");
  expect(await graph.resume({ ...valid, interruptId: "forged" })).toMatchObject(
    { status: "failed", code: "INTERRUPT_MISMATCH" },
  );
  expect(await graph.resume(resume(waiting, "backend"))).toMatchObject({
    status: "failed",
    code: "RESUME_SOURCE_MISMATCH",
  });
  expect(
    await graph.resume({
      ...valid,
      context: { ...context, initiatedBy: "other-resident" },
    }),
  ).toMatchObject({ status: "failed", code: "CONTEXT_MISMATCH" });
  expect((await graph.resume(valid)).status).toBe("completed");
});

test("backend events for wrong ticket/generation/stale version are rejected", async () => {
  const { graph } = harness([
    tool,
    JSON.stringify({ action: "handoff", text: "Chờ người xem xét." }),
    complete,
  ]);
  const waiting = await graph.run(request);
  const valid = resume(waiting, "backend");
  if (valid.source.kind !== "backend")
    throw new Error("Expected backend fixture");
  for (const patch of [
    { ticketId: "other-ticket" },
    { generation: 0 },
    { aggregateVersion: 3 },
    { bindingId: "other-binding" },
  ]) {
    const changed = {
      ...valid,
      source: {
        kind: "backend" as const,
        event: { ...valid.source.event, ...patch },
      },
    };
    expect((await graph.resume(changed)).status).toBe("failed");
  }
  expect((await graph.resume(valid)).status).toBe("completed");
});

test("thread + namespace isolate two residents without mutable factory state", async () => {
  const { graph } = harness([complete]);
  const otherContext = {
    ...context,
    initiatedBy: "resident-B",
    bindingId: "binding-B",
    checkpoint: { ...context.checkpoint, namespace: "other-namespace" },
  };
  const results = await Promise.all([
    graph.run(request),
    graph.run({
      ...request,
      context: otherContext,
      message: { id: "message-B", text: "Yêu cầu khác." },
    }),
  ]);
  expect(results.map((result) => result.status)).toEqual([
    "completed",
    "completed",
  ]);
  expect((await graph.read(context))?.reported[0].text).toBe(
    request.message.text,
  );
  expect((await graph.read(otherContext))?.reported[0].text).toBe(
    "Yêu cầu khác.",
  );
});

test("same key under another tenant is rejected before reading state", async () => {
  const { graph } = harness([complete]);
  await graph.run(request);
  await expect(
    graph.read({ ...context, tenantId: "other-tenant" }),
  ).rejects.toMatchObject({ code: "CONTEXT_MISMATCH" });
});

test("unknown checkpoint state version is rejected without resetting the session", async () => {
  const h = harness([complete]);
  await h.graph.run(request);
  const config = {
    configurable: {
      thread_id: JSON.stringify([
        context.checkpoint.namespace,
        context.checkpoint.threadId,
      ]),
      checkpoint_ns: "",
    },
  };
  const saved = await h.saver.getTuple(config);
  if (!saved) throw new Error("Expected checkpoint");
  const stored = saved.checkpoint.channel_values.data as ReceptionBusinessState;
  await h.saver.put(
    config,
    {
      ...saved.checkpoint,
      channel_values: {
        ...saved.checkpoint.channel_values,
        data: { ...stored, schemaVersion: 999 },
      },
    },
    saved.metadata!,
  );
  expect(await h.graph.run(request)).toMatchObject({
    status: "failed",
    code: "STATE_VERSION_UNSUPPORTED",
  });
  await expect(h.graph.read(context)).rejects.toMatchObject({
    code: "STATE_VERSION_UNSUPPORTED",
  });
});

test("stream executes once and emits exactly one terminal result", async () => {
  const { graph, calls } = harness([tool, complete]);
  const events = [];
  for await (const event of graph.stream(request)) events.push(event);
  expect(events.map((event) => event.type)).toEqual(["text_delta", "result"]);
  expect(calls).toHaveLength(1);
});

test("stream resumes a resident interrupt once", async () => {
  const { graph } = harness([
    JSON.stringify({ action: "await_resident", text: "Vui lòng xác nhận." }),
    complete,
  ]);
  const waiting = await graph.run(request);
  const events = [];
  for await (const event of graph.stream(resume(waiting, "resident")))
    events.push(event);
  expect(events.filter((event) => event.type === "result")).toHaveLength(1);
  expect(events.at(-1)).toMatchObject({
    type: "result",
    result: { status: "completed" },
  });
});

test("pre-aborted run produces cancelled without tools or checkpoint", async () => {
  const { graph, calls } = harness([tool]);
  expect(await graph.run({ ...request, signal: AbortSignal.abort() })).toEqual({
    status: "cancelled",
  });
  expect(await graph.read(context)).toBeUndefined();
  expect(calls).toHaveLength(0);
});

test("abort during a tool call returns cancelled but preserves the operation key for PH03 recovery", async () => {
  const controller = new AbortController();
  const { graph, calls } = harness([tool], {
    invoke: async (call) => {
      expect(call.signal?.aborted).toBe(false);
      controller.abort();
      call.signal?.throwIfAborted();
      return { kind: "success", value: { verifiedUnit: "unreachable" } };
    },
  });
  expect(await graph.run({ ...request, signal: controller.signal })).toEqual({
    status: "cancelled",
  });
  expect((await graph.read(context))?.pendingTool?.idempotencyKey).toBe(
    calls[0].idempotencyKey,
  );
  expect((await graph.read(context))?.confirmed).toEqual([]);
});

test("reconciliation that is still accepted creates another wait, never completes or retries mutation", async () => {
  let reconciliations = 0;
  const { graph, calls } = harness([tool], {
    invoke: async () => ({
      kind: "accepted",
      operationId: "backend-operation",
    }),
    reconcile: async () => {
      reconciliations++;
      return { kind: "accepted", operationId: "backend-operation" };
    },
  });
  const first = await graph.run(request);
  const second = interrupted(await graph.resume(resume(first, "backend")));
  expect(second.state.phase).toBe("awaiting_tool");
  expect(second.state.confirmed).toEqual([]);
  expect(calls).toHaveLength(1);
  expect(reconciliations).toBe(1);
});

test("one resident can have two ticket threads without overwriting their messages", async () => {
  const { graph } = harness([complete]);
  const secondContext = {
    ...context,
    bindingId: "binding-second-ticket",
    checkpoint: { ...context.checkpoint, threadId: "thread-second-ticket" },
  };
  await graph.run(request);
  await graph.run({
    ...request,
    context: secondContext,
    message: { id: "message-second-ticket", text: "Ticket thứ hai." },
  });
  expect((await graph.read(context))?.reported[0].text).toBe(
    request.message.text,
  );
  expect((await graph.read(secondContext))?.reported[0].text).toBe(
    "Ticket thứ hai.",
  );
});

test("failed stream has one terminal result and does not expose raw model errors", async () => {
  const { graph } = harness(["secret-and-invalid-output"]);
  const events = [];
  for await (const event of graph.stream(request)) events.push(event);
  expect(events).toEqual([
    {
      type: "result",
      result: { status: "failed", code: "INVALID_DECISION", retryable: false },
    },
  ]);
});

test("factory requires valid limits and has no implicit model/tool/checkpointer", () => {
  expect(() =>
    createReceptionGraphFactory<TestOperations>({
      bindings: {} as never,
      timeoutMs: 0,
    }),
  ).toThrow();
  expect(() =>
    createReceptionGraphFactory<TestOperations>({
      bindings: {} as never,
      maxSteps: -1,
    }),
  ).toThrow();
});
