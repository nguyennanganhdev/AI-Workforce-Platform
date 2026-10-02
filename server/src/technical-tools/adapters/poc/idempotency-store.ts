import type {
  IdempotencyScope,
  IdempotencyStore,
  StoredOutcome,
} from "../../ports/idempotency-store";

type Entry =
  | { state: "in_progress"; payloadHash: string }
  | { state: "completed"; stored: StoredOutcome };

/**
 * Keys held in memory, for use until a table exists.
 *
 * `reserve` looks and claims without an `await` in between, so within one process two concurrent
 * calls cannot both find the key free. Across processes, and across a restart, it guarantees
 * nothing: every key is forgotten, and a retry after a restart writes again. That is the limit of a
 * POC store and the reason the production one belongs in the database, beside the records it
 * guards.
 */
export function createInMemoryIdempotencyStore(): IdempotencyStore {
  const entries = new Map<string, Entry>();
  // The separator cannot occur in a tenant id, a tool name or a key the schemas admit.
  const keyOf = ({ tenantId, tool, key }: IdempotencyScope) =>
    `${tenantId}\u0000${tool}\u0000${key}`;

  return {
    reserve: async (scope, payloadHash) => {
      const existing = entries.get(keyOf(scope));
      if (existing?.state === "completed") {
        return { state: "completed", stored: existing.stored };
      }
      if (existing?.state === "in_progress") {
        return { state: "in_progress", payloadHash: existing.payloadHash };
      }
      entries.set(keyOf(scope), { state: "in_progress", payloadHash });
      return { state: "reserved" };
    },
    complete: async (scope, stored) => {
      entries.set(keyOf(scope), { state: "completed", stored });
    },
    release: async (scope) => {
      entries.delete(keyOf(scope));
    },
  };
}
