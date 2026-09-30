import { Annotation } from "@langchain/langgraph";
import type {
  ReceptionRunRequest,
  ReceptionState,
  ReceptionToolResult,
  VerifiedReceptionContext,
} from "../contracts";

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export type ReceptionPhase =
  | "intake"
  | "clarify"
  | "awaiting_tool"
  | "awaiting_resident"
  | "handoff"
  | "completion";

export type Fact = Readonly<{ name: string; value: JsonValue }>;
export type ConfirmedFact = Fact &
  Readonly<{
    source: { operation: string; idempotencyKey: string };
  }>;

export type Decision =
  | Readonly<{
      action: "clarify" | "await_resident" | "handoff" | "complete";
      text: string;
      inferences: readonly Fact[];
    }>
  | Readonly<{
      action: "tool";
      operation: string;
      input: JsonValue;
      inferences: readonly Fact[];
    }>;

/** Stored before calling a tool. Reconciliation must keep this exact key/input. */
export type PendingTool = Readonly<{
  operation: string;
  input: JsonValue;
  idempotencyKey: string;
  timeoutMs: number;
}>;

export type ReceptionBusinessState = ReceptionState &
  Readonly<{
    owner: Pick<
      VerifiedReceptionContext,
      "tenantId" | "principalId" | "initiatedBy" | "bindingId"
    >;
    phase: ReceptionPhase;
    operationId: string;
    message: ReceptionRunRequest["message"];
    /** Resident statements are reports, not backend-verified facts. */
    reported: readonly ReceptionRunRequest["message"][];
    confirmed: readonly ConfirmedFact[];
    inferences: readonly Fact[];
    decision: Decision | null;
    pendingTool: PendingTool | null;
    lastToolResult: ReceptionToolResult<JsonValue> | null;
    ticket: Readonly<{
      id: string;
      generation: number;
      aggregateVersion: number;
    }> | null;
    reply: string;
    clarifications: number;
    steps: number;
    toolSequence: number;
  }>;

// One channel replaces an entire immutable snapshot; it never merges user fields
// into authority fields. No credentials, model instances or abort signals here.
export const ReceptionAnnotation = Annotation.Root({
  data: Annotation<ReceptionBusinessState>(),
});

export function belongsTo(
  state: ReceptionBusinessState,
  context: VerifiedReceptionContext,
): boolean {
  return (
    state.owner.tenantId === context.tenantId &&
    state.owner.principalId === context.principalId &&
    state.owner.initiatedBy === context.initiatedBy &&
    state.owner.bindingId === context.bindingId
  );
}

export function initialState(
  request: ReceptionRunRequest,
): ReceptionBusinessState {
  const { tenantId, principalId, initiatedBy, bindingId } = request.context;
  return {
    schemaVersion: 1,
    owner: { tenantId, principalId, initiatedBy, bindingId },
    phase: "intake",
    operationId: request.operationId,
    message: request.message,
    reported: [request.message],
    confirmed: [],
    inferences: [],
    decision: null,
    pendingTool: null,
    lastToolResult: null,
    ticket: null,
    reply: "",
    clarifications: 0,
    steps: 0,
    toolSequence: 0,
  };
}
