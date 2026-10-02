import type { ExecutorResult } from "../../domain/executor-result";
import type { ExecutorResultStore } from "../../ports/executor-result-store";

/**
 * Submitted results held in memory, until a table exists.
 *
 * Lost on restart, like the measurement store beside it. `all()` is for tests.
 */
export function createInMemoryExecutorResultStore(): ExecutorResultStore & {
  all(): readonly ExecutorResult[];
} {
  const results: ExecutorResult[] = [];
  return {
    append: async (result) => {
      results.push(result);
    },
    findById: async (tenantId, resultId) =>
      results.find(
        (result) =>
          result.tenantId === tenantId && result.resultId === resultId,
      ) ?? null,
    all: () => [...results],
  };
}
