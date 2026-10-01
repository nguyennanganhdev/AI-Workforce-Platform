import type { BaseChatModel } from "@langchain/core/language_models/chat_models";
import type { BaseCheckpointSaver } from "@langchain/langgraph-checkpoint";

/** Internal proposal, pending PD01/DD01 and C06 review; not a platform DTO. */
export const RECEPTION_CONTRACT_VERSION = "0.1.0-draft.1" as const;
export const RECEPTION_STATE_SCHEMA_VERSION = 1 as const;

/** Supplied only after backend verification in PH02, never from model/browser. */
export type VerifiedReceptionContext = Readonly<{
  principalId: string;
  tenantId: string;
  initiatedBy: string;
  bindingId: string;
  /** Backend-resolved framework keys; internal only, never browser-selected. */
  checkpoint: Readonly<{ threadId: string; namespace: string }>;
  runId: string;
  requestId: string;
  permissions: readonly string[];
}>;

export type ReceptionToolRequest<Operation extends string, Input> = Readonly<{
  operation: Operation;
  input: Input;
  context: VerifiedReceptionContext;
  idempotencyKey: string;
  timeoutMs: number;
  signal?: AbortSignal;
}>;

export type ReceptionToolResult<Output = unknown> =
  | Readonly<{ kind: "success"; value: Output }>
  | Readonly<{ kind: "accepted"; operationId: string }>
  | Readonly<{
      kind: "failure";
      code: string;
      retryable: boolean;
      /** A lost response must not be treated as a confirmed failed mutation. */
      outcome: "not_applied" | "unknown";
    }>;

/** DD01/DD02 bind operation names to their validated input/output types. */
export type ReceptionToolOperations = Record<
  string,
  { input: unknown; output: unknown }
>;

export interface ReceptionToolPort<
  Operations extends ReceptionToolOperations = ReceptionToolOperations,
> {
  invoke<Operation extends keyof Operations & string>(
    request: ReceptionToolRequest<Operation, Operations[Operation]["input"]>,
  ): Promise<ReceptionToolResult<Operations[Operation]["output"]>>;
}

export type ReceptionGraphDependencies<
  Operations extends ReceptionToolOperations = ReceptionToolOperations,
> = Readonly<{
  model: BaseChatModel;
  tools: ReceptionToolPort<Operations>;
  /** Required injection. MemorySaver is permitted only in tests. */
  checkpointer: BaseCheckpointSaver;
}>;

/** PD01 owns the business state; this only defines its version envelope. */
export type ReceptionState = Readonly<{
  schemaVersion: typeof RECEPTION_STATE_SCHEMA_VERSION;
}>;

export type ReceptionRunRequest = Readonly<{
  context: VerifiedReceptionContext;
  /** Stable client operation ID, distinct from runId. Persist/dedup in PH02/03. */
  operationId: string;
  message: Readonly<{ id: string; text: string; fileIds?: readonly string[] }>;
  signal?: AbortSignal;
}>;

export type ReceptionInterrupt = Readonly<{
  id: string;
  reason: "resident_input" | "backend_event" | "human_review";
}>;

export type ReceptionGraphResult<State extends ReceptionState> =
  | Readonly<{ status: "completed"; state: State }>
  | Readonly<{
      status: "interrupted";
      state: State;
      interrupts: readonly ReceptionInterrupt[];
    }>
  | Readonly<{ status: "cancelled" }>
  | Readonly<{ status: "failed"; code: string; retryable: boolean }>;

export type ReceptionGraphEvent<State extends ReceptionState> =
  | Readonly<{ type: "text_delta"; text: string }>
  | Readonly<{ type: "result"; result: ReceptionGraphResult<State> }>;

/** Resident input and backend notifications remain separate resume sources. */
export type ReceptionResumeRequest = Readonly<{
  context: VerifiedReceptionContext;
  operationId: string;
  interruptId: string;
  signal?: AbortSignal;
  source:
    | Readonly<{ kind: "resident"; message: ReceptionRunRequest["message"] }>
    | Readonly<{ kind: "backend"; event: ReceptionResumeEvent }>;
}>;

export interface ReceptionGraph<State extends ReceptionState> {
  readonly stateSchemaVersion: typeof RECEPTION_STATE_SCHEMA_VERSION;
  read(context: VerifiedReceptionContext): Promise<State | undefined>;
  run(request: ReceptionRunRequest): Promise<ReceptionGraphResult<State>>;
  resume(request: ReceptionResumeRequest): Promise<ReceptionGraphResult<State>>;
  /** Exactly one terminal result; consuming stream executes the request once. */
  stream(
    request: ReceptionRunRequest | ReceptionResumeRequest,
  ): AsyncIterable<ReceptionGraphEvent<State>>;
}

export interface ReceptionGraphFactory<
  State extends ReceptionState,
  Operations extends ReceptionToolOperations = ReceptionToolOperations,
> {
  readonly contractVersion: typeof RECEPTION_CONTRACT_VERSION;
  readonly stateSchemaVersion: typeof RECEPTION_STATE_SCHEMA_VERSION;
  create(
    dependencies: ReceptionGraphDependencies<Operations>,
  ): ReceptionGraph<State>;
}

/** PH03 verifies source, binding/interrupt, ticket/generation and event ordering. */
export type ReceptionResumeEvent = Readonly<{
  eventId: string;
  aggregateVersion: number;
  ticketId: string;
  generation: number;
  bindingId: string;
  interruptId: string;
}>;
