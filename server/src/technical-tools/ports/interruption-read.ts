import type { InterruptionRecord, Utility } from "../domain/interruption";

export type InterruptionQuery = {
  tenantId: string;
  buildingId: string;
  utility: Utility;
  /**
   * The instants the caller is asking about, used only to bound how far back and forward to read.
   *
   * An adapter returns a superset: every interruption that could matter inside the window, in any
   * status. Which of them count is decided by `interruption-rules`, in one place, so a second
   * implementation of this port cannot disagree with the first about what "active" means.
   */
  window: { from: Date; to: Date };
};

export type InterruptionReadPort = {
  /**
   * Interruptions of one utility whose scope covers the building: the building's own scope, its
   * zone's, or its site's.
   *
   * `null` means the building is not in this tenant at all, which the caller reports differently
   * from a building with nothing scheduled.
   */
  listCovering(query: InterruptionQuery): Promise<InterruptionRecord[] | null>;
};
