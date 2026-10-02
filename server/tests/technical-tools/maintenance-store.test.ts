import { describe, expect, test } from "bun:test";
import {
  createInMemoryMaintenanceStore,
  type MaintenanceEvent,
} from "../../src/technical-tools";
import { MAINTENANCE_EVENTS } from "./fixtures/maintenance";
import { BUILDING, NOW, TENANT } from "./fixtures/world";

/**
 * The in-memory maintenance store: what `maintenance_history.append` writes to until a table
 * exists, and what `maintenance_history.read` then reads.
 *
 * Asked only what a store can get wrong: whether a correction can be corrected twice, whether one
 * tenant's history reaches another, and whether what is written can be read back.
 */
const event = (
  eventId: string,
  change: Partial<MaintenanceEvent> = {},
): MaintenanceEvent => ({
  eventId,
  tenantId: TENANT.vinhomes,
  buildingId: BUILDING.a1,
  assetId: "AC-A1-1205-01",
  incidentId: null,
  workorderId: null,
  occurredAt: new Date("2026-09-30T08:50:00Z"),
  outcome: "cleaned_drain_line",
  sourceRefs: [`event:${eventId}`],
  supersedesEventId: null,
  ...change,
});

const history = (store: ReturnType<typeof createInMemoryMaintenanceStore>) =>
  store.listForAsset({
    tenantId: TENANT.vinhomes,
    buildingId: BUILDING.a1,
    assetId: "AC-A1-1205-01",
    until: NOW,
  });

describe("an empty store", () => {
  test("starts with no history at all, so nothing invented is reported", async () => {
    const store = createInMemoryMaintenanceStore();
    expect(await history(store)).toEqual([]);
    expect(store.all()).toEqual([]);
  });
});

describe("what is written is what is read", () => {
  test("an appended event is in the asset's history next time it is read", async () => {
    const store = createInMemoryMaintenanceStore(MAINTENANCE_EVENTS);
    const before = (await history(store)).length;

    expect(await store.append(event("ME-NEW"))).toEqual({ state: "appended" });

    const after = await history(store);
    expect(after).toHaveLength(before + 1);
    expect(after.map((e) => e.eventId)).toContain("ME-NEW");
    expect(await store.findEvent(TENANT.vinhomes, "ME-NEW")).toMatchObject({
      outcome: "cleaned_drain_line",
    });
  });

  test("the history it was given is not changed by writing to it", async () => {
    const given = [...MAINTENANCE_EVENTS];
    const store = createInMemoryMaintenanceStore(given);
    await store.append(event("ME-NEW"));
    expect(given).toHaveLength(MAINTENANCE_EVENTS.length);
  });
});

/*
 * History is corrected by appending, never by editing. An entry that two corrections both replaced
 * would leave two versions of what happened, and a reader could not tell which one stands.
 */
describe("correcting an entry", () => {
  test("knows which event replaced which", async () => {
    const store = createInMemoryMaintenanceStore(MAINTENANCE_EVENTS);
    // In the sample history ME-104 corrects ME-103.
    expect(await store.supersededBy(TENANT.vinhomes, "ME-103")).toBe("ME-104");
    expect(await store.supersededBy(TENANT.vinhomes, "ME-104")).toBeNull();
  });

  test("an entry already corrected cannot be corrected again", async () => {
    const store = createInMemoryMaintenanceStore(MAINTENANCE_EVENTS);
    expect(
      await store.append(event("ME-AGAIN", { supersedesEventId: "ME-103" })),
    ).toEqual({ state: "already_superseded", byEventId: "ME-104" });
    expect(await store.findEvent(TENANT.vinhomes, "ME-AGAIN")).toBeNull();
  });

  test("of two corrections of one entry, only the first is written", async () => {
    const store = createInMemoryMaintenanceStore([event("ME-1")]);
    const [first, second] = await Promise.all([
      store.append(event("ME-2a", { supersedesEventId: "ME-1" })),
      store.append(event("ME-2b", { supersedesEventId: "ME-1" })),
    ]);
    expect(first).toEqual({ state: "appended" });
    expect(second).toEqual({ state: "already_superseded", byEventId: "ME-2a" });
    expect(store.all().map((e) => e.eventId)).toEqual(["ME-1", "ME-2a"]);
  });

  test("the latest correction can itself be corrected", async () => {
    const store = createInMemoryMaintenanceStore(MAINTENANCE_EVENTS);
    expect(
      await store.append(event("ME-105", { supersedesEventId: "ME-104" })),
    ).toEqual({ state: "appended" });
  });
});

describe("one tenant's history", () => {
  test("is not found, read or corrected under another tenant", async () => {
    const store = createInMemoryMaintenanceStore(MAINTENANCE_EVENTS);
    expect(await store.findEvent(TENANT.other, "ME-101")).toBeNull();
    expect(await store.supersededBy(TENANT.other, "ME-103")).toBeNull();
    expect(
      await store.listForAsset({
        tenantId: TENANT.other,
        buildingId: BUILDING.a1,
        assetId: "AC-A1-1205-01",
        until: NOW,
      }),
    ).toEqual([]);
  });
});
