import type {
  BuildingPlacement,
  ScopeRecord,
} from "../../domain/approval-request";
import type { ScopeReadPort } from "../../ports/request-ports";

export type ScopedBuilding = BuildingPlacement & { tenantId: string };
export type TenantScope = ScopeRecord & { tenantId: string };

/**
 * Buildings and access scopes held in memory, for hosts and tests with no database behind them.
 * Given nothing it knows no building, so nothing is reachable.
 */
export function createInMemoryScopeReadPort(
  buildings: readonly ScopedBuilding[] = [],
  scopes: readonly TenantScope[] = [],
): ScopeReadPort {
  return {
    placement: async ({ tenantId, buildingId }) => {
      const building = buildings.find(
        (candidate) =>
          candidate.tenantId === tenantId &&
          candidate.buildingId === buildingId,
      );
      if (!building) return null;
      const { tenantId: _tenant, ...placement } = building;
      return placement;
    },
    findScopes: async ({ tenantId, ids }) =>
      scopes
        .filter(
          (scope) => scope.tenantId === tenantId && ids.includes(scope.id),
        )
        .map(({ tenantId: _tenant, ...scope }) => scope),
  };
}
