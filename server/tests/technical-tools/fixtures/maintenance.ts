import type { MaintenanceEvent } from "../../../src/technical-tools";
import { BUILDING, id, TENANT } from "./world";

const event = (
  overrides: Partial<MaintenanceEvent> &
    Pick<MaintenanceEvent, "eventId" | "assetId" | "occurredAt" | "outcome">,
): MaintenanceEvent => ({
  tenantId: TENANT.vinhomes,
  buildingId: BUILDING.a1,
  incidentId: null,
  workorderId: null,
  sourceRefs: [`event:${overrides.eventId}`],
  supersedesEventId: null,
  ...overrides,
});

/**
 * Twenty-five events ten days apart through 2026, alternately raised by an incident and
 * scheduled, so a page of twenty is not the whole window and the repeat count has to be counted
 * over all of it: thirteen incidents among the twenty-five.
 */
const everyTenDays = Array.from({ length: 25 }, (_, n) =>
  event({
    eventId: `ME-1105-${String(n + 1).padStart(2, "0")}`,
    assetId: "AC-A1-1105-01",
    occurredAt: new Date(Date.UTC(2026, 0, 5 + n * 10, 3)),
    outcome: n % 2 === 0 ? "cleaned_drain_line" : "scheduled_inspection",
    ...(n % 2 === 0 ? { incidentId: id("90000000", 100 + n) } : {}),
  }),
);

/**
 * The maintenance record of the sample estate.
 *
 * The living-room air conditioner in A1-1205 carries the case that matters most: the same fault
 * twice this year, one routine service that is not a fault, and one entry recorded wrong and then
 * corrected. An answer that reported the wrong entry, or counted the routine service as a repeat,
 * would send a technician to replace a pump nobody replaced.
 */
export const MAINTENANCE_EVENTS: readonly MaintenanceEvent[] = [
  event({
    eventId: "ME-101",
    assetId: "AC-A1-1205-01",
    occurredAt: new Date("2026-03-01T02:00:00Z"),
    outcome: "scheduled_cleaning",
    sourceRefs: ["schedule:PM-2026-Q1"],
  }),
  event({
    eventId: "ME-102",
    assetId: "AC-A1-1205-01",
    incidentId: id("90000000", 1),
    workorderId: id("91000000", 1),
    occurredAt: new Date("2026-07-02T04:00:00Z"),
    outcome: "cleaned_drain_line",
    sourceRefs: [`workorder:${id("91000000", 1)}`],
  }),
  event({
    // Recorded wrong: nobody replaced the pump. ME-104 corrects it.
    eventId: "ME-103",
    assetId: "AC-A1-1205-01",
    incidentId: id("90000000", 2),
    workorderId: id("91000000", 2),
    occurredAt: new Date("2026-08-15T03:00:00Z"),
    outcome: "replaced_drain_pump",
    sourceRefs: [`workorder:${id("91000000", 2)}`],
  }),
  event({
    eventId: "ME-104",
    assetId: "AC-A1-1205-01",
    incidentId: id("90000000", 2),
    workorderId: id("91000000", 2),
    occurredAt: new Date("2026-08-15T03:00:00Z"),
    outcome: "cleaned_drain_line",
    sourceRefs: [`workorder:${id("91000000", 2)}`, "correction:ME-103"],
    supersedesEventId: "ME-103",
  }),

  // Serviced last November, nothing since.
  event({
    eventId: "ME-201",
    assetId: "BP-A1-1205-01",
    incidentId: id("90000000", 3),
    workorderId: id("91000000", 3),
    occurredAt: new Date("2025-11-20T06:00:00Z"),
    outcome: "replaced_breaker",
    sourceRefs: [`workorder:${id("91000000", 3)}`],
  }),

  ...everyTenDays,

  event({
    eventId: "ME-B1-01",
    assetId: "AC-B1-0501-01",
    buildingId: BUILDING.b1,
    occurredAt: new Date("2026-06-01T02:00:00Z"),
    outcome: "cleaned_drain_line",
  }),
  event({
    eventId: "ME-X1-01",
    assetId: "AC-X1-0101-01",
    tenantId: TENANT.other,
    buildingId: BUILDING.x1,
    occurredAt: new Date("2026-06-01T02:00:00Z"),
    outcome: "cleaned_drain_line",
  }),
];
