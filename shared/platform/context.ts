export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface ActorRef {
  readonly kind: "user" | "service" | "agent";
  readonly id: string;
}

/** Constructed by authenticated server middleware, never trusted from a request body. */
export interface RequestContext {
  readonly tenantId: string;
  readonly actor: ActorRef;
  readonly correlationId: string;
  readonly traceId: string;
}

export interface DomainSubjectRef {
  readonly namespace: string;
  readonly subjectType: string;
  readonly subjectId: string;
}

/** Effective scope is resolved by the domain from membership and authorization. */
export interface DomainScope {
  readonly namespace: string;
  readonly tenantId: string;
  readonly subjects: readonly DomainSubjectRef[];
}
