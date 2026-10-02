import type {
  ActionProposal,
  ActionValidation,
  DomainActionReceipt,
} from "./action-contracts.js";
import type {
  DomainScope,
  DomainSubjectRef,
  JsonValue,
  RequestContext,
} from "./context.js";

export interface DomainContext {
  readonly subject: DomainSubjectRef;
  readonly data: Readonly<Record<string, JsonValue>>;
}

export interface DomainCapability {
  readonly key: string;
  readonly description: string;
  readonly effect: "READ" | "ANALYZE" | "PROPOSE";
}

export interface EvidenceDescriptor {
  readonly id: string;
  readonly subject: DomainSubjectRef;
  readonly mediaType: string;
  readonly fileObjectId: string;
}

/** All methods enforce tenant, membership and subject access in the domain. */
export interface DomainAdapter {
  readonly namespace: string;
  resolveSubject(
    context: RequestContext,
    ref: DomainSubjectRef,
  ): Promise<DomainContext>;
  validateAction(
    context: RequestContext,
    proposal: ActionProposal,
  ): Promise<ActionValidation>;
  submitAction(
    context: RequestContext,
    proposal: ActionProposal,
  ): Promise<DomainActionReceipt>;
  listCapabilities(
    context: RequestContext,
    scope: DomainScope,
  ): Promise<readonly DomainCapability[]>;
  resolveActorScope(context: RequestContext): Promise<DomainScope>;
  getEvidence(
    context: RequestContext,
    refs: readonly string[],
  ): Promise<readonly EvidenceDescriptor[]>;
}
