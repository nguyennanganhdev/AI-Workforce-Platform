import { BUILDING, id, SITE, TENANT, ZONE } from "./world";

/** Apartments of the sample estate, each there for one thing an entry request could get wrong. */
export const UNIT = {
  a1_1205: id("76000000", 1),
  a1_1305: id("76000000", 2),
  a1_1105: id("76000000", 3),
  a2_0803: id("76000000", 4),
  x1_0101: id("76000000", 5),
} as const;

export type UnitFixture = {
  id: string;
  tenantId: string;
  siteId: string;
  zoneId: string | null;
  buildingId: string;
  code: string;
  floor: string;
  proves: string;
};

export const UNITS: readonly UnitFixture[] = [
  {
    id: UNIT.a1_1205,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    zoneId: ZONE.s1,
    buildingId: BUILDING.a1,
    code: "A1-1205",
    floor: "12",
    proves: "the apartment the sample incidents are reported from",
  },
  {
    id: UNIT.a1_1305,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    zoneId: ZONE.s1,
    buildingId: BUILDING.a1,
    code: "A1-1305",
    floor: "13",
    proves:
      "the apartment above, where a leak into A1-1205 comes from: tools.md §6.3's example",
  },
  {
    id: UNIT.a1_1105,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    zoneId: ZONE.s1,
    buildingId: BUILDING.a1,
    code: "A1-1105",
    floor: "11",
    proves: "an apartment with nobody verified living in it now",
  },
  {
    id: UNIT.a2_0803,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    zoneId: ZONE.s1,
    buildingId: BUILDING.a2,
    code: "A2-0803",
    floor: "8",
    proves: "an apartment in another building of the same tenant",
  },
  {
    id: UNIT.x1_0101,
    tenantId: TENANT.other,
    siteId: SITE.other,
    zoneId: null,
    buildingId: BUILDING.x1,
    code: "X1-0101",
    floor: "1",
    proves: "an apartment of another tenant",
  },
];

/** Residents, as `users` rows the residents table points at. */
export const RESIDENT_USER = {
  a1_1205: "fixture-resident-a1-1205",
  a1_1305: "fixture-resident-a1-1305",
  a1_1105Former: "fixture-resident-a1-1105-former",
  a1_1105Pending: "fixture-resident-a1-1105-pending",
  a2_0803: "fixture-resident-a2-0803",
} as const;

export type ResidentFixture = {
  id: string;
  unitId: string;
  userId: string;
  relation: "owner" | "tenant" | "household";
  verificationStatus: "pending" | "verified" | "rejected" | "expired";
  validFrom: Date;
  validTo: Date | null;
};

const since = new Date("2025-01-01T00:00:00Z");

export const RESIDENTS: readonly ResidentFixture[] = [
  {
    id: id("77000000", 1),
    unitId: UNIT.a1_1205,
    userId: RESIDENT_USER.a1_1205,
    relation: "owner",
    verificationStatus: "verified",
    validFrom: since,
    validTo: null,
  },
  {
    id: id("77000000", 2),
    unitId: UNIT.a1_1305,
    userId: RESIDENT_USER.a1_1305,
    relation: "owner",
    verificationStatus: "verified",
    validFrom: since,
    validTo: null,
  },
  {
    // Moved out in June: verified once, no longer living there.
    id: id("77000000", 3),
    unitId: UNIT.a1_1105,
    userId: RESIDENT_USER.a1_1105Former,
    relation: "tenant",
    verificationStatus: "verified",
    validFrom: since,
    validTo: new Date("2026-06-01T00:00:00Z"),
  },
  {
    // Moving in, not verified yet: nobody has confirmed they live there.
    id: id("77000000", 4),
    unitId: UNIT.a1_1105,
    userId: RESIDENT_USER.a1_1105Pending,
    relation: "tenant",
    verificationStatus: "pending",
    validFrom: new Date("2026-09-15T00:00:00Z"),
    validTo: null,
  },
  {
    id: id("77000000", 5),
    unitId: UNIT.a2_0803,
    userId: RESIDENT_USER.a2_0803,
    relation: "owner",
    verificationStatus: "verified",
    validFrom: since,
    validTo: null,
  },
];
