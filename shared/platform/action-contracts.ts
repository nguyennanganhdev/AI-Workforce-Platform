import type { DomainSubjectRef, JsonValue } from './context.js';

/** A proposal is not an approval or permission to execute a WRITE tool. */
export interface ActionProposal {
  readonly proposalId: string;
  readonly subject: DomainSubjectRef;
  readonly actionType: string;
  readonly producerType: 'AGENT' | 'USER' | 'SYSTEM';
  readonly producerId: string;
  readonly producerVersion: string | null;
  readonly payload: Readonly<Record<string, JsonValue>>;
  readonly idempotencyKey: string;
}

export type ActionValidation =
  | { readonly valid: true }
  | { readonly valid: false; readonly reasons: readonly string[] };

/** Confirms domain intake only; business execution has its own lifecycle. */
export interface DomainActionReceipt {
  readonly actionRequestId: string;
  readonly subject: DomainSubjectRef;
}
