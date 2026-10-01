import type { ToolOutcome } from "../tool";

/** One key: an agent's `idempotency_key`, for one tool, in one tenant. */
export type IdempotencyScope = {
  tenantId: string;
  tool: string;
  key: string;
};

/** What a completed call left behind, to hand back to the next call that repeats it. */
export type StoredOutcome = {
  payloadHash: string;
  outcome: ToolOutcome<unknown>;
};

export type Reservation =
  /** Nobody has used the key: the caller now holds it and must complete or release it. */
  | { state: "reserved" }
  /** A call with this key already wrote something. */
  | { state: "completed"; stored: StoredOutcome }
  /** A call with this key is running now. */
  | { state: "in_progress"; payloadHash: string };

/**
 * Where write tools remember which requests they have already carried out (tools.md §1.4).
 *
 * `reserve` must claim the key and report what was there in one step. A store that looked and then
 * claimed in two would let two concurrent retries both see "nobody" and both write, which is the
 * exact failure the key exists to prevent.
 *
 * In production the key belongs in the same transaction as the record it guards. Stored apart, a
 * crash between writing the record and completing the key leaves a write the next retry repeats.
 */
export type IdempotencyStore = {
  reserve(scope: IdempotencyScope, payloadHash: string): Promise<Reservation>;
  complete(scope: IdempotencyScope, stored: StoredOutcome): Promise<void>;
  release(scope: IdempotencyScope): Promise<void>;
};
