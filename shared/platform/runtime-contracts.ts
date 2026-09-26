import type { DomainSubjectRef, JsonValue, RequestContext } from './context.js';

/** Draft transport DTOs. Keep the Python TypedDict definitions aligned. */
export interface RuntimePlan {
  readonly context: RequestContext;
  readonly subject: DomainSubjectRef;
  readonly agentVersionId: string;
  readonly input: Readonly<Record<string, JsonValue>>;
}

export interface RuntimeSessionRef {
  readonly tenantId: string;
  readonly sessionId: string;
}

export interface RuntimeStep {
  readonly session: RuntimeSessionRef;
  readonly stepId: string;
  readonly input: Readonly<Record<string, JsonValue>>;
}

export interface RuntimeCheckpoint {
  readonly session: RuntimeSessionRef;
  readonly checkpointId: string;
}

export interface RuntimeEvent {
  readonly session: RuntimeSessionRef;
  readonly eventId: string;
  readonly correlationId: string;
  readonly type: 'RUN_STARTED' | 'STEP_COMPLETED' | 'RUN_COMPLETED' | 'RUN_FAILED' | 'RUN_CANCELLED';
  readonly occurredAt: string;
  readonly payload: Readonly<Record<string, JsonValue>>;
}
