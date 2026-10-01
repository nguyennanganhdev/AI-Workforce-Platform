/** An apartment, as an entry request needs it: which building it is in. */
export type UnitRecord = {
  unitId: string;
  code: string;
  /** `null` for a unit outside any building, such as a townhouse on a site. */
  buildingId: string | null;
};

/**
 * A row of `unit_residents`, as the table holds it. Whether this person counts as living there now
 * is the rules' decision.
 */
export type ResidentRecord = {
  userId: string;
  relation: string;
  verificationStatus: string;
  validFrom: Date;
  validTo: Date | null;
};

export const CONTACT_CHANNELS = ["phone", "message", "app", "other"] as const;

export const CONTACT_OUTCOMES = [
  "no_answer",
  "delivered",
  "rejected",
  "approved",
  "unknown",
] as const;

/**
 * One attempt to reach the resident: how, when, how it went, and a reference to the record of it.
 * Only that. The content of a message is not carried, and is not needed to show an attempt was
 * made.
 */
export type ContactAttempt = {
  channel: (typeof CONTACT_CHANNELS)[number];
  attemptedAt: Date;
  outcome: (typeof CONTACT_OUTCOMES)[number];
  referenceId?: string;
};
