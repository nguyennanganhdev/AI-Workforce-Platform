import { z } from "zod";

/**
 * The key a write tool deduplicates on (tools.md §1.4): the same key with the same request returns
 * the first result, and with a different request is a conflict.
 */
export const idempotencyKeySchema = z.string().min(8).max(128);

/** A list of ids with no repeats, as the specification's `uniqueItems` says. */
export const uniqueIdsSchema = z
  .array(z.string().min(1))
  .refine((ids) => new Set(ids).size === ids.length, {
    message: "The same id appears more than once.",
  });
