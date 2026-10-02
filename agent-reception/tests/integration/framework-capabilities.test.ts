import { expect, test } from "bun:test";
import {
  Annotation,
  Command,
  END,
  interrupt,
  START,
  StateGraph,
} from "@langchain/langgraph";
import { HumanMessage } from "@langchain/core/messages";
import {
  createTestDependencies,
  verifiedContextFixture,
} from "../support/fakes";

// Framework conformance spike, not the PD01 business graph or PH03 durability.
test("pinned LangGraph supports injected model/tools, checkpoint, interrupt and resume", async () => {
  const dependencies = createTestDependencies();
  const state = Annotation.Root({ answer: Annotation<string>() });
  let toolCalls = 0;
  const graph = new StateGraph(state)
    .addNode("wait", () => ({
      answer: interrupt<string, string>("test-input"),
    }))
    .addNode("reply", async (input) => {
      const modelMessage = await dependencies.model.invoke([
        new HumanMessage(input.answer),
      ]);
      const result = await dependencies.tools.invoke({
        operation: "echo",
        input: { text: String(modelMessage.content) },
        context: verifiedContextFixture,
        idempotencyKey: "operation-test",
        timeoutMs: 1_000,
      });
      toolCalls++;
      if (result.kind !== "success") throw new Error("Test tool failed");
      return { answer: result.value.text };
    })
    .addEdge(START, "wait")
    .addEdge("wait", "reply")
    .addEdge("reply", END)
    .compile({ checkpointer: dependencies.checkpointer });

  const config = { configurable: { thread_id: "test-thread-a" } };
  await graph.invoke({ answer: "" }, config);
  const waiting = await graph.getState(config);
  expect(waiting.tasks[0]?.interrupts).toHaveLength(1);
  expect(toolCalls).toBe(0);
  const chunks = [];
  for await (const chunk of await graph.stream(
    new Command({ resume: "resident-test-input" }),
    config,
  )) {
    chunks.push(chunk);
  }
  expect(chunks.length).toBeGreaterThan(0);
  const completed = await graph.getState(config);
  expect(completed.values.answer).toBe("model-test-response");
  expect(completed.next).toEqual([]);
  expect(toolCalls).toBe(1);
  const other = await graph.getState({
    configurable: { thread_id: "test-thread-b" },
  });
  expect(other.values).toEqual({});
});
