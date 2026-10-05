import type {
  QualificationStatus,
  Vendor,
  VendorCandidate,
} from "../domain/vendor";

/** How close to expiry a licence may be before a person should look at the vendor first. */
export const LICENCE_REVIEW_MS = 30 * 24 * 60 * 60 * 1000;

/**
 * Whether a vendor may be offered for this site, and how.
 *
 * `null` means the vendor is not offered at all: suspended, licence lapsed, or not serving this
 * site. A vendor whose licence runs out within thirty days, or whose insurance nobody has
 * verified, is offered for review rather than as eligible.
 */
export function qualificationOf(
  vendor: Vendor,
  siteId: string,
  now: Date,
): QualificationStatus | null {
  if (vendor.status !== "active") return null;
  if (!vendor.siteIds.includes(siteId)) return null;
  const remaining = vendor.licenseExpiresAt.getTime() - now.getTime();
  if (remaining <= 0) return null;
  if (remaining <= LICENCE_REVIEW_MS || !vendor.insuranceVerified) {
    return "needs_review";
  }
  return "eligible";
}

/**
 * The candidates to put in front of whoever approves: eligible first, then for review, each group
 * by name. Only the id, the name and the qualification: a candidate is not an engagement, and the
 * vendor's phone number and rate are for procurement once a person has decided.
 */
export function candidates(
  vendors: readonly Vendor[],
  siteId: string,
  now: Date,
): VendorCandidate[] {
  const rank = { eligible: 0, needs_review: 1 } as const;
  return vendors
    .flatMap((vendor) => {
      const qualificationStatus = qualificationOf(vendor, siteId, now);
      return qualificationStatus
        ? [
            {
              vendorId: vendor.vendorId,
              displayName: vendor.displayName,
              qualificationStatus,
            },
          ]
        : [];
    })
    .sort(
      (a, b) =>
        rank[a.qualificationStatus] - rank[b.qualificationStatus] ||
        a.displayName.localeCompare(b.displayName),
    );
}
