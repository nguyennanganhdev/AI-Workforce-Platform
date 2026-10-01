import type { MaintenanceEvent } from "../../domain/maintenance";
import type { MaintenanceReadPort } from "../../ports/maintenance-read";

/**
 * A maintenance history held in memory, for use until a table exists.
 *
 * Given nothing, every asset has an empty history, which `maintenance_history.read` reports as
 * such. It is passed its events rather than holding any, so no deployment can present an invented
 * repair as something a technician did.
 */
export function createInMemoryMaintenanceReadPort(
  events: readonly MaintenanceEvent[] = [],
): MaintenanceReadPort {
  return {
    listForAsset: async ({ tenantId, buildingId, assetId, until }) =>
      events.filter(
        (event) =>
          event.tenantId === tenantId &&
          event.buildingId === buildingId &&
          event.assetId === assetId &&
          event.occurredAt.getTime() < until.getTime(),
      ),
  };
}
