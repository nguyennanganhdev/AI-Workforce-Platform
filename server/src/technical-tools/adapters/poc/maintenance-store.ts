import type { MaintenanceEvent } from "../../domain/maintenance";
import type { MaintenanceReadPort } from "../../ports/maintenance-read";
import type { MaintenanceStore } from "../../ports/maintenance-store";

/**
 * A maintenance history held in memory that can be written to as well as read, until a table
 * exists.
 *
 * One store answers both ports, so an event `maintenance_history.append` records is what
 * `maintenance_history.read` reports next. Given nothing it starts empty; it is passed whatever
 * history it starts with, so no deployment presents an invented repair as real.
 *
 * Lost on restart. `all()` is for tests.
 */
export function createInMemoryMaintenanceStore(
  initial: readonly MaintenanceEvent[] = [],
): MaintenanceStore &
  MaintenanceReadPort & { all(): readonly MaintenanceEvent[] } {
  const events: MaintenanceEvent[] = [...initial];
  const replacing = (tenantId: string, eventId: string) =>
    events.find(
      (event) =>
        event.tenantId === tenantId && event.supersedesEventId === eventId,
    );

  return {
    listForAsset: async ({ tenantId, buildingId, assetId, until }) =>
      events.filter(
        (event) =>
          event.tenantId === tenantId &&
          event.buildingId === buildingId &&
          event.assetId === assetId &&
          event.occurredAt.getTime() < until.getTime(),
      ),
    findEvent: async (tenantId, eventId) =>
      events.find(
        (event) => event.tenantId === tenantId && event.eventId === eventId,
      ) ?? null,
    supersededBy: async (tenantId, eventId) =>
      replacing(tenantId, eventId)?.eventId ?? null,
    // Checks and writes with no `await` between, so within a process two corrections of one
    // entry cannot both land.
    append: async (event) => {
      if (event.supersedesEventId) {
        const already = replacing(event.tenantId, event.supersedesEventId);
        if (already) {
          return { state: "already_superseded", byEventId: already.eventId };
        }
      }
      events.push(event);
      return { state: "appended" };
    },
    all: () => [...events],
  };
}
