import type { Asset } from "../../../src/technical-tools";
import { BUILDING, NOW, TENANT } from "./world";

const days = (n: number) => new Date(NOW.getTime() - n * 86_400_000);

type AssetFixture = Asset & { proves?: string };

/**
 * The equipment of the sample estate.
 *
 * Sample data lives here rather than in the module, so no deployment can serve invented equipment
 * records as real ones. `createInMemoryAssetReadPort` is given this catalogue by the tests and
 * nothing by default.
 *
 * The apartment bathroom deliberately holds three assets, two of them the same type: that is the
 * case where `asset.read` has to refuse to choose.
 */
export const ASSETS: readonly AssetFixture[] = [
  {
    assetId: "AC-A1-1205-01",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "air_conditioner",
    model: "ACME-X1",
    location: "A1-1205/phòng khách",
    ownership: "resident",
    warrantyUntil: "2027-03-31",
    status: "active",
    updatedAt: days(10),
    etag: "etag-17",
    proves:
      "the happy path, and the accented location a request may arrive without accents",
  },
  {
    assetId: "AC-A1-1205-02",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "air_conditioner",
    model: "ACME-X2",
    location: "A1-1205/phòng ngủ 1",
    ownership: "resident",
    warrantyUntil: "2027-03-31",
    status: "active",
    updatedAt: days(10),
    etag: "etag-18",
    proves: "a second unit in the same apartment, distinguishable by room",
  },
  {
    assetId: "WH-A1-1205-01",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "water_heater",
    model: "Hotpoint-20L",
    location: "A1-1205/phòng tắm",
    ownership: "resident",
    warrantyUntil: "2026-12-31",
    status: "active",
    updatedAt: days(30),
    etag: "etag-21",
    proves: "asset_type settles a location that three assets share",
  },
  {
    assetId: "TL-A1-1205-01",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "toilet",
    model: "Inax-AC900",
    location: "A1-1205/phòng tắm",
    ownership: "resident",
    warrantyUntil: null,
    status: "active",
    updatedAt: days(200),
    etag: "etag-22",
    proves:
      "two assets of one type in one room, so asset_type is not enough either",
  },
  {
    assetId: "TL-A1-1205-02",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "toilet",
    model: "Inax-AC900",
    location: "A1-1205/phòng tắm",
    ownership: "resident",
    warrantyUntil: null,
    status: "retired",
    updatedAt: days(400),
    etag: "etag-23",
    proves:
      "a retired asset is still a record, and is reported with its status rather than hidden",
  },
  {
    assetId: "BP-A1-1205-01",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "breaker_panel",
    model: "Schneider-EZ9",
    location: "A1-1205/tủ điện",
    ownership: "management",
    warrantyUntil: null,
    status: "active",
    updatedAt: days(90),
    etag: "etag-31",
  },
  {
    assetId: "BP-A1-COMMON-12",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "breaker_panel",
    model: "Schneider-EZ9",
    location: "A1/tủ điện tầng 12",
    ownership: "management",
    warrantyUntil: null,
    status: "active",
    updatedAt: days(90),
    etag: "etag-32",
    proves:
      "common-area equipment belongs to the building rather than to an apartment",
  },
  {
    assetId: "AC-A1-1105-01",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    type: "air_conditioner",
    model: "ACME-X1",
    location: "A1-1105/phòng khách",
    ownership: "resident",
    warrantyUntil: "2027-03-31",
    status: "needs_service",
    updatedAt: days(5),
    etag: "etag-41",
    proves:
      "a room name alone matches two apartments, so it cannot identify one asset",
  },
  {
    assetId: "AC-A2-0803-01",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a2,
    type: "air_conditioner",
    model: "ACME-X3",
    location: "A2-0803/phòng khách",
    ownership: "resident",
    warrantyUntil: "2028-06-30",
    status: "active",
    updatedAt: days(15),
    etag: "etag-51",
    proves: "the neighbouring building has its own equipment",
  },
  {
    assetId: "AC-B1-0501-01",
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.b1,
    type: "air_conditioner",
    model: "ACME-X1",
    location: "B1-0501/phòng khách",
    ownership: "resident",
    warrantyUntil: null,
    status: "active",
    updatedAt: days(20),
    etag: "etag-61",
    proves: "equipment in a building outside the caller's grant",
  },
  {
    assetId: "AC-X1-0101-01",
    tenantId: TENANT.other,
    buildingId: BUILDING.x1,
    type: "air_conditioner",
    model: "ACME-X1",
    location: "X1-0101/phòng khách",
    ownership: "resident",
    warrantyUntil: null,
    status: "active",
    updatedAt: days(20),
    etag: "etag-71",
    proves: "another tenant's equipment",
  },
];
