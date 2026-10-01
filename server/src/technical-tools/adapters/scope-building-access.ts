import type {
  BuildingPlacement,
  ScopeRecord,
} from "../domain/approval-request";
import type { BuildingAccessPort } from "../ports/building-access";
import type { ScopeReadPort } from "../ports/request-ports";
import { scopeCovers } from "../tools/request-rules";

/**
 * Whether a granted scope reaches a building: the building itself, its zone, its site, or the
 * whole tenant. Unlike a utility isolation, a grant may name the tenant: it is a grant of
 * authority over every building the tenant has, not a place a valve can close.
 */
export function grantReaches(
  scope: ScopeRecord,
  building: BuildingPlacement,
): boolean {
  return scope.kind === "tenant" || scopeCovers(scope, building);
}

/**
 * Building access answered from `access_scopes`, through the same scope reader the request tools
 * use. A building the tenant does not have is reached by nothing, and a scope id the tenant does
 * not have grants nothing; neither is distinguishable to the caller from a building outside the
 * grant.
 */
export function createScopeBuildingAccess(
  scopes: ScopeReadPort,
): BuildingAccessPort {
  return {
    async canAccessBuilding({ tenantId, buildingId, scopeIds }) {
      if (scopeIds.length === 0) return false;
      const building = await scopes.placement({ tenantId, buildingId });
      if (!building) return false;
      const granted = await scopes.findScopes({ tenantId, ids: scopeIds });
      return granted.some((scope) => grantReaches(scope, building));
    },
  };
}
