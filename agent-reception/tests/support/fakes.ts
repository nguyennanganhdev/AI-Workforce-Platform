import { FakeListChatModel } from "@langchain/core/utils/testing";
import { MemorySaver } from "@langchain/langgraph-checkpoint";
import type {
  ReceptionGraphDependencies,
  VerifiedReceptionContext,
} from "../../src/contracts";

/** Synthetic identities and tools only. Never import this module from src/. */
export const verifiedContextFixture: VerifiedReceptionContext = {
  principalId: "service-test",
  tenantId: "tenant-test",
  initiatedBy: "resident-test",
  bindingId: "binding-test",
  runId: "run-test",
  requestId: "request-test",
  checkpoint: {
    threadId: "framework-thread-test",
    namespace: "reception-test",
  },
  permissions: ["test:echo"],
};

export type HarnessTools = {
  echo: { input: { text: string }; output: { text: string } };
};

export function createTestDependencies(): ReceptionGraphDependencies<HarnessTools> {
  return {
    model: new FakeListChatModel({ responses: ["model-test-response"] }),
    checkpointer: new MemorySaver(),
    tools: {
      async invoke(request) {
        request.signal?.throwIfAborted();
        return { kind: "success", value: { text: request.input.text } };
      },
    },
  };
}
