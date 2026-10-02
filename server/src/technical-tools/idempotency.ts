import { createHash } from "node:crypto";
import type { ToolStatus } from "./contracts/envelope";

/**
 * Statuses that mean the tool wrote something, and so the only ones a key is kept for.
 *
 * A refused call wrote nothing. Keeping its key would stop the agent from fixing the request and
 * sending it again under the same key, which is what an agent retrying a refused call naturally
 * does; and there is nothing to protect by refusing it.
 */
export const WRITTEN_STATUSES: ReadonlySet<ToolStatus> = new Set([
  "OK",
  "PENDING_APPROVAL",
]);

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [
          key,
          canonical((value as Record<string, unknown>)[key]),
        ]),
    );
  }
  return value;
}

/**
 * A fingerprint of what a call asked for, its key aside.
 *
 * Keys are sorted first, so the same request serialised in a different order is the same request:
 * an agent's framework is under no obligation to keep property order, and a retry that happened to
 * reorder its arguments must not be taken for a different request and refused.
 */
export function payloadHash(input: Record<string, unknown>): string {
  const { idempotency_key: _key, ...rest } = input;
  return createHash("sha256")
    .update(JSON.stringify(canonical(rest)))
    .digest("hex");
}
