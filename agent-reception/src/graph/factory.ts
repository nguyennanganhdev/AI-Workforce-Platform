import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import type { RunnableConfig } from "@langchain/core/runnables";
import {
  Command,
  END,
  interrupt,
  START,
  StateGraph,
} from "@langchain/langgraph";
import {
  RECEPTION_CONTRACT_VERSION,
  RECEPTION_STATE_SCHEMA_VERSION,
  type ReceptionGraph,
  type ReceptionGraphDependencies,
  type ReceptionGraphFactory,
  type ReceptionGraphResult,
  type ReceptionResumeRequest,
  type ReceptionRunRequest,
  type ReceptionToolOperations,
  type ReceptionToolRequest,
  type ReceptionToolResult,
  type VerifiedReceptionContext,
} from "../contracts";
import { PD01_SYSTEM_PROMPT } from "../prompts/pd01";
import { facts, GraphFault, jsonValue, parseDecision } from "./decision";
import {
  belongsTo,
  type Fact,
  initialState,
  type JsonValue,
  type PendingTool,
  ReceptionAnnotation,
  type ReceptionBusinessState,
} from "./state";

/** Composition supplies real DD01 validators/decoders; no built-in operations. */
export type ToolBinding<Input, Output> = Readonly<{
  description: string;
  inputSchema: JsonValue;
  parseInput(value: unknown): Input;
  parseOutput(value: unknown): Output;
  /** Only verified fields returned by the authorized backend may be projected. */
  confirmedFacts?(output: Output): readonly Fact[];
  ticket?(output: Output): ReceptionBusinessState["ticket"];
  /** Required to resume accepted/unknown calls; read/reconcile, never blind retry. */
  reconcile?(
    request: ReceptionToolRequest<string, Input>,
  ): Promise<ReceptionToolResult<Output>>;
}>;

export type ReceptionFactoryOptions<
  Operations extends ReceptionToolOperations,
> = Readonly<{
  bindings: {
    [Operation in keyof Operations]: ToolBinding<
      Operations[Operation]["input"],
      Operations[Operation]["output"]
    >;
  };
  timeoutMs?: number;
  maxSteps?: number;
  maxClarifications?: number;
}>;

type Request = ReceptionRunRequest | ReceptionResumeRequest;
type StateResult = ReceptionGraphResult<ReceptionBusinessState>;

function positive(value: number, name: string): number {
  if (!Number.isSafeInteger(value) || value <= 0)
    throw new GraphFault(`INVALID_${name}`);
  return value;
}

function contextOf(config: RunnableConfig): VerifiedReceptionContext {
  return config.configurable?.receptionContext as VerifiedReceptionContext;
}

function checkedState(
  value: unknown,
  context: VerifiedReceptionContext,
): ReceptionBusinessState | undefined {
  if (value === undefined) return undefined;
  const state = value as ReceptionBusinessState;
  if (state?.schemaVersion !== RECEPTION_STATE_SCHEMA_VERSION)
    throw new GraphFault("STATE_VERSION_UNSUPPORTED");
  if (!state.owner || !belongsTo(state, context))
    throw new GraphFault("CONTEXT_MISMATCH");
  // No migration/reset fallback. Detailed persisted-shape migration belongs to PH03.
  if (
    !Array.isArray(state.reported) ||
    !Array.isArray(state.confirmed) ||
    !Array.isArray(state.inferences) ||
    !state.message ||
    ![
      "intake",
      "clarify",
      "awaiting_tool",
      "awaiting_resident",
      "handoff",
      "completion",
    ].includes(state.phase) ||
    !Number.isSafeInteger(state.toolSequence) ||
    state.toolSequence < 0
  ) {
    throw new GraphFault("STATE_INVALID");
  }
  return state;
}

export function createReceptionGraphFactory<
  Operations extends ReceptionToolOperations,
>(
  options: ReceptionFactoryOptions<Operations>,
): ReceptionGraphFactory<ReceptionBusinessState, Operations> {
  const timeoutMs = positive(options.timeoutMs ?? 10_000, "TIMEOUT");
  const maxSteps = positive(options.maxSteps ?? 8, "STEP_LIMIT");
  const maxClarifications = positive(
    options.maxClarifications ?? 3,
    "CLARIFICATION_LIMIT",
  );
  const bindingFor = (operation: string): ToolBinding<unknown, unknown> => {
    if (!Object.hasOwn(options.bindings, operation))
      throw new GraphFault("TOOL_NOT_ALLOWED");
    return options.bindings[operation] as ToolBinding<unknown, unknown>;
  };

  function create(
    dependencies: ReceptionGraphDependencies<Operations>,
  ): ReceptionGraph<ReceptionBusinessState> {
    const compiled = new StateGraph(ReceptionAnnotation)
      .addNode("decide", async ({ data }, config) => {
        config.signal?.throwIfAborted();
        if (data.steps >= maxSteps) {
          return {
            data: {
              ...data,
              phase: "handoff" as const,
              reply: "Yêu cầu cần người có thẩm quyền xem xét để tiếp tục.",
            },
          };
        }
        const response = await dependencies.model.invoke(
          [
            new SystemMessage(PD01_SYSTEM_PROMPT),
            new HumanMessage(
              JSON.stringify({
                catalog: Object.entries(options.bindings).map(
                  ([operation, binding]) => ({
                    operation,
                    description: binding.description,
                    inputSchema: binding.inputSchema,
                  }),
                ),
                reported: data.reported,
                confirmed: data.confirmed,
                inferences: data.inferences,
                lastToolResult: data.lastToolResult,
                pendingTool: data.pendingTool,
              }),
            ),
          ],
          { signal: config.signal },
        );
        if (typeof response.content !== "string")
          throw new GraphFault("INVALID_DECISION");
        const decision = parseDecision(response.content);
        const next = {
          ...data,
          decision,
          steps: data.steps + 1,
          inferences: [...data.inferences, ...decision.inferences].slice(-64),
        };
        if (decision.action === "tool") {
          if (data.pendingTool) throw new GraphFault("TOOL_OUTCOME_UNRESOLVED");
          const binding = bindingFor(decision.operation);
          const input = jsonValue(binding.parseInput(decision.input));
          const toolSequence = data.toolSequence + 1;
          // JSON tuple is unambiguous, independent of model/runId; PH03 persists it.
          const idempotencyKey = JSON.stringify([
            data.owner.bindingId,
            data.operationId,
            toolSequence,
          ]);
          return {
            data: {
              ...next,
              phase: "awaiting_tool" as const,
              toolSequence,
              pendingTool: {
                operation: decision.operation,
                input,
                idempotencyKey,
                timeoutMs,
              },
              reply: "",
            },
          };
        }
        if (decision.action === "complete" && data.pendingTool)
          throw new GraphFault("TOOL_OUTCOME_UNRESOLVED");
        if (
          ["clarify", "await_resident"].includes(decision.action) &&
          data.clarifications >= maxClarifications
        ) {
          return {
            data: {
              ...next,
              phase: "handoff" as const,
              reply:
                "Chưa đủ dữ kiện sau các lần làm rõ; yêu cầu cần người xem xét.",
            },
          };
        }
        const phase =
          decision.action === "complete"
            ? "completion"
            : decision.action === "await_resident"
              ? "awaiting_resident"
              : decision.action;
        return {
          data: {
            ...next,
            phase,
            reply: decision.text,
            clarifications:
              data.clarifications +
              (["clarify", "await_resident"].includes(decision.action) ? 1 : 0),
          },
        };
      })
      .addNode("tool", async ({ data }, config) => {
        if (!data.pendingTool) throw new GraphFault("STATE_INVALID");
        const request = toolRequest(data.pendingTool, config);
        let result: ReceptionToolResult<unknown>;
        try {
          result = await dependencies.tools.invoke({
            ...request,
            operation: request.operation as keyof Operations & string,
            input: request.input as Operations[keyof Operations &
              string]["input"],
          });
        } catch {
          // Exception/lost response does not prove the side effect was rolled back.
          result = {
            kind: "failure",
            code: "TOOL_RESPONSE_LOST",
            retryable: false,
            outcome: "unknown",
          };
        }
        return { data: applyResult(data, result) };
      })
      .addNode("resident_wait", ({ data }) => {
        const source = interrupt<
          ReceptionResumeRequest["source"],
          ReceptionResumeRequest["source"]
        >({ kind: "resident", message: data.message });
        if (source.kind !== "resident")
          throw new GraphFault("RESUME_SOURCE_MISMATCH");
        return {
          data: {
            ...data,
            phase: "intake" as const,
            message: source.message,
            reported: [...data.reported, source.message].slice(-64),
            steps: 0,
            reply: "",
          },
        };
      })
      .addNode("backend_wait", async ({ data }, config) => {
        interrupt({ reason: "backend_event" });
        if (!data.pendingTool) throw new GraphFault("STATE_INVALID");
        const reconcile = bindingFor(data.pendingTool.operation).reconcile;
        if (!reconcile) throw new GraphFault("RECONCILIATION_UNAVAILABLE");
        let result: ReceptionToolResult<unknown>;
        try {
          result = await reconcile(toolRequest(data.pendingTool, config));
        } catch {
          result = {
            kind: "failure",
            code: "TOOL_RESPONSE_LOST",
            retryable: false,
            outcome: "unknown",
          };
        }
        return { data: applyResult(data, result) };
      })
      .addNode("handoff_wait", ({ data }) => {
        interrupt({ reason: "human_review" });
        // Event is a notification, not proof of completion or verified new facts.
        return {
          data: { ...data, phase: "intake" as const, steps: 0, reply: "" },
        };
      })
      .addEdge(START, "decide")
      .addConditionalEdges(
        "decide",
        ({ data }) => {
          if (data.phase === "awaiting_tool") return "tool";
          if (data.phase === "completion") return END;
          return data.phase === "handoff" ? "handoff_wait" : "resident_wait";
        },
        ["tool", "resident_wait", "handoff_wait", END],
      )
      .addConditionalEdges("tool", afterTool, [
        "decide",
        "backend_wait",
        "handoff_wait",
      ])
      .addEdge("resident_wait", "decide")
      .addConditionalEdges("backend_wait", afterTool, [
        "decide",
        "backend_wait",
        "handoff_wait",
      ])
      .addEdge("handoff_wait", "decide")
      .compile({ checkpointer: dependencies.checkpointer });

    function afterTool({ data }: { data: ReceptionBusinessState }) {
      return data.phase === "handoff"
        ? "handoff_wait"
        : data.pendingTool
          ? "backend_wait"
          : "decide";
    }

    function toolRequest(
      pending: PendingTool,
      config: RunnableConfig,
    ): ReceptionToolRequest<string, unknown> {
      config.signal?.throwIfAborted();
      return { ...pending, context: contextOf(config), signal: config.signal };
    }

    function applyResult(
      data: ReceptionBusinessState,
      raw: ReceptionToolResult<unknown>,
    ): ReceptionBusinessState {
      const pending = data.pendingTool;
      if (!pending) throw new GraphFault("STATE_INVALID");
      if (raw.kind === "success") {
        const binding = bindingFor(pending.operation);
        let output: unknown;
        try {
          output = binding.parseOutput(raw.value);
        } catch {
          return {
            ...data,
            phase: "awaiting_tool",
            lastToolResult: {
              kind: "failure",
              code: "INVALID_TOOL_OUTPUT",
              retryable: false,
              outcome: "unknown",
            },
          };
        }
        const confirmed = facts(binding.confirmedFacts?.(output) ?? []).map(
          (fact) => ({
            ...fact,
            source: {
              operation: pending.operation,
              idempotencyKey: pending.idempotencyKey,
            },
          }),
        );
        const ticket = binding.ticket?.(output) ?? data.ticket;
        if (
          ticket &&
          (!ticket.id ||
            !Number.isSafeInteger(ticket.generation) ||
            ticket.generation < 0 ||
            !Number.isSafeInteger(ticket.aggregateVersion) ||
            ticket.aggregateVersion < 0)
        )
          throw new GraphFault("INVALID_TOOL_OUTPUT");
        return {
          ...data,
          phase: "intake",
          confirmed: [...data.confirmed, ...confirmed].slice(-64),
          ticket,
          pendingTool: null,
          lastToolResult: { kind: "success", value: jsonValue(output) },
        };
      }
      if (
        raw.kind === "accepted" &&
        typeof raw.operationId === "string" &&
        raw.operationId
      ) {
        return {
          ...data,
          phase: "awaiting_tool",
          lastToolResult: raw,
          reply: "Hệ thống đã tiếp nhận yêu cầu; đang chờ xác nhận kết quả.",
        };
      }
      if (
        raw.kind === "failure" &&
        typeof raw.code === "string" &&
        typeof raw.retryable === "boolean" &&
        ["unknown", "not_applied"].includes(raw.outcome)
      ) {
        return {
          ...data,
          phase: raw.outcome === "unknown" ? "awaiting_tool" : "handoff",
          pendingTool: raw.outcome === "unknown" ? pending : null,
          lastToolResult: raw,
          reply:
            raw.outcome === "unknown"
              ? "Chưa xác định kết quả; cần kiểm tra lại với hệ thống."
              : "Yêu cầu chưa được thực hiện; cần người có thẩm quyền xem xét.",
        };
      }
      return {
        ...data,
        phase: "awaiting_tool",
        lastToolResult: {
          kind: "failure",
          code: "INVALID_TOOL_RESULT",
          retryable: false,
          outcome: "unknown",
        },
        reply: "Chưa xác định kết quả; cần kiểm tra lại với hệ thống.",
      };
    }

    function configFor(
      context: VerifiedReceptionContext,
      signal?: AbortSignal,
    ): RunnableConfig {
      // LangGraph 1.4.10 resets checkpoint_ns for root graphs. Encode both
      // backend-resolved keys into an unambiguous thread key, use root namespace.
      return {
        configurable: {
          thread_id: JSON.stringify([
            context.checkpoint.namespace,
            context.checkpoint.threadId,
          ]),
          checkpoint_ns: "",
          receptionContext: context,
        },
        signal,
        recursionLimit: maxSteps * 4 + 16,
      };
    }

    async function snapshot(context: VerifiedReceptionContext) {
      const state = await compiled.getState(configFor(context));
      return {
        snapshot: state,
        data: checkedState(state.values.data, context),
      };
    }

    async function execute(request: Request): Promise<StateResult> {
      try {
        if (request.signal?.aborted) return { status: "cancelled" };
        if (
          !request.operationId ||
          ("message" in request && !request.message.id)
        )
          throw new GraphFault("INVALID_REQUEST");
        const current = await snapshot(request.context);
        let input: Parameters<typeof compiled.invoke>[0];
        const waiting = current.snapshot.tasks.flatMap(
          (task) => task.interrupts ?? [],
        );
        if ("source" in request) {
          if (
            !current.data ||
            waiting.length !== 1 ||
            waiting[0].id !== request.interruptId
          )
            throw new GraphFault("INTERRUPT_MISMATCH");
          const residentExpected = ["clarify", "awaiting_resident"].includes(
            current.data.phase,
          );
          if (residentExpected !== (request.source.kind === "resident"))
            throw new GraphFault("RESUME_SOURCE_MISMATCH");
          if (request.source.kind === "backend") {
            const event = request.source.event;
            if (
              !event.eventId ||
              !event.ticketId ||
              !Number.isSafeInteger(event.generation) ||
              event.generation < 0 ||
              !Number.isSafeInteger(event.aggregateVersion) ||
              event.aggregateVersion < 0
            )
              throw new GraphFault("EVENT_INVALID");
            if (
              event.bindingId !== request.context.bindingId ||
              event.interruptId !== request.interruptId
            )
              throw new GraphFault("EVENT_CONTEXT_MISMATCH");
            const ticket = current.data.ticket;
            if (
              ticket &&
              (event.ticketId !== ticket.id ||
                event.generation !== ticket.generation ||
                event.aggregateVersion <= ticket.aggregateVersion)
            )
              throw new GraphFault("EVENT_STALE_OR_MISMATCH");
            if (
              current.data.pendingTool &&
              !bindingFor(current.data.pendingTool.operation).reconcile
            )
              throw new GraphFault("RECONCILIATION_UNAVAILABLE");
          }
          input = new Command({ resume: request.source });
        } else {
          if (waiting.length || current.snapshot.next.length)
            throw new GraphFault("RESUME_REQUIRED");
          if (current.data?.pendingTool)
            throw new GraphFault("TOOL_OUTCOME_UNRESOLVED");
          const data = current.data
            ? {
                ...current.data,
                phase: "intake" as const,
                operationId: request.operationId,
                message: request.message,
                reported: [...current.data.reported, request.message].slice(
                  -64,
                ),
                decision: null,
                steps: 0,
                reply: "",
              }
            : initialState(request);
          input = { data };
        }
        await compiled.invoke(input, {
          ...configFor(request.context, request.signal),
          durability: "sync",
        });
        const final = await snapshot(request.context);
        if (!final.data) throw new GraphFault("STATE_INVALID");
        const interrupts = final.snapshot.tasks.flatMap(
          (task) => task.interrupts ?? [],
        );
        if (interrupts.length)
          return {
            status: "interrupted",
            state: final.data,
            interrupts: interrupts.map((item) => ({
              id: item.id ?? "",
              reason: ["clarify", "awaiting_resident"].includes(
                final.data?.phase ?? "",
              )
                ? "resident_input"
                : final.data?.phase === "handoff"
                  ? "human_review"
                  : "backend_event",
            })),
          };
        return { status: "completed", state: final.data };
      } catch (error) {
        if (request.signal?.aborted) return { status: "cancelled" };
        return {
          status: "failed",
          code:
            error instanceof GraphFault ? error.code : "GRAPH_EXECUTION_FAILED",
          retryable: error instanceof GraphFault ? error.retryable : false,
        };
      }
    }

    return {
      stateSchemaVersion: RECEPTION_STATE_SCHEMA_VERSION,
      async read(context) {
        return (await snapshot(context)).data;
      },
      run: execute,
      resume: execute,
      async *stream(request) {
        const result = await execute(request);
        if (
          (result.status === "completed" || result.status === "interrupted") &&
          result.state.reply
        ) {
          yield { type: "text_delta" as const, text: result.state.reply };
        }
        yield { type: "result" as const, result };
      },
    };
  }

  return {
    contractVersion: RECEPTION_CONTRACT_VERSION,
    stateSchemaVersion: RECEPTION_STATE_SCHEMA_VERSION,
    create,
  };
}
