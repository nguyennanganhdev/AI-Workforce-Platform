import type { ResidentRecord, UnitRecord } from "../domain/unit";
import type { Vendor } from "../domain/vendor";

export type UnitReadPort = {
  /** The unit, if it is this tenant's. Which building it is in is for the caller to check. */
  findUnit(query: {
    tenantId: string;
    unitId: string;
  }): Promise<UnitRecord | null>;
  /** Every resident record of the unit, current or not. */
  residents(query: {
    tenantId: string;
    unitId: string;
  }): Promise<ResidentRecord[]>;
};

/**
 * The vendor catalogue. Read only: there is no way here to book, contract with or pay a vendor,
 * because matching candidates is all a technical tool may do.
 */
export type VendorCatalogPort = {
  /** This tenant's vendors with the specialty, whatever their status. */
  findBySpecialty(query: {
    tenantId: string;
    specialtyCode: string;
  }): Promise<Vendor[]>;
};
