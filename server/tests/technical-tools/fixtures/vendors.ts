import type { Vendor } from "../../../src/technical-tools";
import { SITE, TENANT } from "./world";

const vendor = (
  change: Partial<Vendor> &
    Pick<Vendor, "vendorId" | "displayName" | "specialtyCodes">,
): Vendor => ({
  tenantId: TENANT.vinhomes,
  siteIds: [SITE.oceanPark],
  status: "active",
  licenseExpiresAt: new Date("2027-09-30T00:00:00Z"),
  insuranceVerified: true,
  contactPhone: "+84911111111",
  hourlyRate: 450000,
  ...change,
});

/**
 * The vendor catalogue of the sample estate, read against 30/09/2026 09:00 UTC (`NOW`).
 *
 * Each vendor is there for one thing matching could get wrong. Each also carries a phone number
 * and a rate, so a test can show neither ever reaches an answer.
 */
export const VENDORS: readonly Vendor[] = [
  vendor({
    vendorId: "VEN-21",
    displayName: "Đơn vị kiểm định A",
    specialtyCodes: ["STRUCTURAL_ENGINEER"],
    contactPhone: "+84912345021",
    hourlyRate: 1200000,
  }),
  vendor({
    // Licence runs out on 10/10/2026, ten days from NOW.
    vendorId: "VEN-22",
    displayName: "Đơn vị kiểm định B",
    specialtyCodes: ["STRUCTURAL_ENGINEER"],
    licenseExpiresAt: new Date("2026-10-10T00:00:00Z"),
  }),
  vendor({
    vendorId: "VEN-23",
    displayName: "Đơn vị kiểm định C",
    specialtyCodes: ["STRUCTURAL_ENGINEER"],
    licenseExpiresAt: new Date("2026-08-31T00:00:00Z"),
  }),
  vendor({
    vendorId: "VEN-24",
    displayName: "Chống thấm D",
    specialtyCodes: ["WATERPROOFING"],
    insuranceVerified: false,
  }),
  vendor({
    vendorId: "VEN-25",
    displayName: "Chống thấm E",
    specialtyCodes: ["WATERPROOFING"],
    status: "suspended",
  }),
  vendor({
    vendorId: "VEN-26",
    displayName: "Điện trung thế F",
    specialtyCodes: ["HV_ELECTRICAL"],
    siteIds: [SITE.other],
  }),
  vendor({
    vendorId: "VEN-X1",
    displayName: "Kiểm định tenant khác",
    specialtyCodes: ["STRUCTURAL_ENGINEER"],
    tenantId: TENANT.other,
    siteIds: [SITE.other],
  }),
];
