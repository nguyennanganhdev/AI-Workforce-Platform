import { describe, expect, test } from "bun:test";
import { createInMemoryVendorCatalog } from "../../src/technical-tools";
import { VENDORS } from "./fixtures/vendors";
import { TENANT } from "./fixtures/world";

/** The in-memory vendor catalogue: what `vendor_dispatch.request` matches against. */
describe("the vendor catalogue", () => {
  test("is empty unless given vendors, so nobody unvetted is ever recommended", async () => {
    expect(
      await createInMemoryVendorCatalog().findBySpecialty({
        tenantId: TENANT.vinhomes,
        specialtyCode: "STRUCTURAL_ENGINEER",
      }),
    ).toEqual([]);
  });

  test("answers with this tenant's vendors of the specialty, in any status", async () => {
    const found = await createInMemoryVendorCatalog(VENDORS).findBySpecialty({
      tenantId: TENANT.vinhomes,
      specialtyCode: "STRUCTURAL_ENGINEER",
    });
    // Which of them may be offered is the rules' decision, not the catalogue's.
    expect(found.map((vendor) => vendor.vendorId).sort()).toEqual([
      "VEN-21",
      "VEN-22",
      "VEN-23",
    ]);
  });

  test("never another tenant's", async () => {
    const found = await createInMemoryVendorCatalog(VENDORS).findBySpecialty({
      tenantId: TENANT.other,
      specialtyCode: "STRUCTURAL_ENGINEER",
    });
    expect(found.map((vendor) => vendor.vendorId)).toEqual(["VEN-X1"]);
  });

  /*
   * Matching is all a technical tool may do. A catalogue the tools could book, contract or pay
   * through would let a request turn into a commitment before anybody approved it.
   */
  test("has no way to book, contract with or pay a vendor", () => {
    expect(Object.keys(createInMemoryVendorCatalog())).toEqual([
      "findBySpecialty",
    ]);
  });
});
