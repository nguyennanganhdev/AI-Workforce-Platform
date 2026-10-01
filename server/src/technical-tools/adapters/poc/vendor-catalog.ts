import type { Vendor } from "../../domain/vendor";
import type { VendorCatalogPort } from "../../ports/entry-vendor-ports";

/**
 * A vendor catalogue held in memory, until the deployment has one.
 *
 * Given nothing, there are no vendors, and a dispatch request lists none: procurement then finds
 * one. It is passed its vendors rather than holding any, so no deployment recommends a contractor
 * nobody vetted.
 */
export function createInMemoryVendorCatalog(
  vendors: readonly Vendor[] = [],
): VendorCatalogPort {
  return {
    findBySpecialty: async ({ tenantId, specialtyCode }) =>
      vendors.filter(
        (vendor) =>
          vendor.tenantId === tenantId &&
          vendor.specialtyCodes.includes(specialtyCode),
      ),
  };
}
