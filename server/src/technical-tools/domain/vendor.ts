/**
 * An external contractor as the vendor catalogue holds it.
 *
 * The contact and price fields are there because a real catalogue has them, and so that a test can
 * show they never reach an answer: matching a vendor is not engaging one, and the agent has no use
 * for a phone number or a rate except to act on its own.
 */
export type Vendor = {
  vendorId: string;
  tenantId: string;
  displayName: string;
  specialtyCodes: readonly string[];
  /** The sites the vendor has agreed to serve. */
  siteIds: readonly string[];
  status: "active" | "suspended";
  licenseExpiresAt: Date;
  insuranceVerified: boolean;
  contactPhone: string;
  hourlyRate: number;
};

export const QUALIFICATION_STATUSES = ["eligible", "needs_review"] as const;

export type QualificationStatus = (typeof QUALIFICATION_STATUSES)[number];

export type VendorCandidate = {
  vendorId: string;
  displayName: string;
  qualificationStatus: QualificationStatus;
};
