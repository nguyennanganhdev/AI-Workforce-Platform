/**
 * Whether a building lies inside the scopes a caller was granted (the `BuildingAccessPort` idea
 * from dev_TeamQuang, 17e5826).
 *
 * Grants are made on `access_scopes`, the way the rest of the platform grants: a building, a zone,
 * a site or a whole tenant. Which buildings a scope reaches is answered here, once, so the host
 * asks one question for every tool and no tool interprets a scope on its own.
 */
export type BuildingAccessPort = {
  canAccessBuilding(query: {
    tenantId: string;
    buildingId: string;
    scopeIds: readonly string[];
  }): Promise<boolean>;
};
