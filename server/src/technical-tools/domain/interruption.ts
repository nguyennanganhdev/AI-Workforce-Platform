/** Utilities `service_interruptions.utility` may hold. */
export const UTILITIES = ["water", "power"] as const;

export type Utility = (typeof UTILITIES)[number];

/**
 * The statuses an interruption may be reported under.
 *
 * `proposed` and `cancelled` are deliberately absent. A proposal is a request nobody has approved,
 * and reporting it as an outage would let the agent tell a resident the water is already off while
 * it is still running.
 */
export const OFFICIAL_INTERRUPTION_STATUSES = [
  "approved",
  "notified",
  "active",
  "restored",
] as const;

export type OfficialInterruptionStatus =
  (typeof OFFICIAL_INTERRUPTION_STATUSES)[number];

/**
 * One row of `service_interruptions` with every scope it is attached to.
 *
 * `status` stays a plain string: it is whatever the table holds, and deciding which values count is
 * the rules' job rather than the adapter's.
 */
export type InterruptionRecord = {
  id: string;
  utility: Utility;
  status: string;
  plannedStart: Date;
  plannedEnd: Date;
  actualStart: Date | null;
  actualEnd: Date | null;
  updatedAt: Date;
  scopeIds: string[];
};
