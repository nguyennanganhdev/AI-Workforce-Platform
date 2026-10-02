// Compile-time consumer checks. This file is included by tsc, not run by bun test.
import type {
  ReceptionGraph,
  ReceptionGraphDependencies,
  ReceptionGraphFactory,
  ReceptionState,
  ReceptionToolResult,
} from "../../src/contracts";
import { RECEPTION_STATE_SCHEMA_VERSION } from "../../src/contracts";
import {
  createTestDependencies,
  verifiedContextFixture,
  type HarnessTools,
} from "../support/fakes";

async function checkConsumerTypes(
  factory: ReceptionGraphFactory<ReceptionState, HarnessTools>,
) {
  const dependencies = createTestDependencies();
  const graph: ReceptionGraph<ReceptionState> = factory.create(dependencies);
  const request = {
    context: verifiedContextFixture,
    idempotencyKey: "persisted-operation-key",
    timeoutMs: 1_000,
    operation: "echo" as const,
    input: { text: "test" },
  };
  const result: ReceptionToolResult<{ text: string }> =
    await dependencies.tools.invoke(request);
  if (result.kind === "success") result.value.text.toUpperCase();

  // @ts-expect-error Unknown operation is rejected by the consumer's catalog.
  await dependencies.tools.invoke({ ...request, operation: "invented" });
  // @ts-expect-error Input must match the operation; callers cannot choose arbitrary output types.
  await dependencies.tools.invoke({ ...request, input: { text: 42 } });
  // @ts-expect-error A timeout cannot be omitted from tool calls.
  await dependencies.tools.invoke({
    operation: "echo",
    input: request.input,
    context: request.context,
    idempotencyKey: "key",
  });
  const accepted: ReceptionToolResult<string> = {
    kind: "accepted",
    operationId: "pending",
    // @ts-expect-error Accepted only acknowledges the operation, with no completed value.
    value: "done",
  };
  const invalidDependencies: ReceptionGraphDependencies<HarnessTools> = {
    ...dependencies,
    // @ts-expect-error Checkpointer must implement the actual pinned framework API.
    checkpointer: {},
  };
  // @ts-expect-error Schema changes require a contract/version change.
  const invalidState: ReceptionState = { schemaVersion: 2 };
  const state: ReceptionState = {
    schemaVersion: RECEPTION_STATE_SCHEMA_VERSION,
  };
  const run = {
    context: request.context,
    operationId: "run-operation",
    message: { id: "message", text: "test" },
  };
  await graph.read(request.context);
  await graph.run(run);
  await graph.resume({
    ...run,
    interruptId: "interrupt",
    source: { kind: "resident", message: run.message },
  });
  for await (const event of graph.stream(run)) {
    if (event.type === "result" && event.result.status === "completed") {
      const completed: ReceptionState = event.result.state;
      void completed;
    }
  }
  void [result, accepted, invalidDependencies, invalidState, state];
}
void checkConsumerTypes;
