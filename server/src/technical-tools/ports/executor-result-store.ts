import type { ExecutorResult } from "../domain/executor-result";

/**
 * Where submitted results are kept. Append-only: a correction is a new submission, and the one it
 * corrects stays on the record (tools.md §1.4).
 */
export type ExecutorResultStore = {
  append(result: ExecutorResult): Promise<void>;
};
