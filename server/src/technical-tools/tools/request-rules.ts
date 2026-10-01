import type {
  BuildingPlacement,
  OpenIsolation,
  ScopeRecord,
} from "../domain/approval-request";
import { normalizeText } from "./text";

/** The kinds of area a utility can be cut across, narrowest first. */
const PHYSICAL_SCOPES = ["building", "zone", "site"] as const;

/** The longest an area restriction may be asked for before somebody must ask again. */
export const MAX_RESTRICTION_MS = 7 * 24 * 60 * 60 * 1000;

/** Interruption statuses that are over: nothing more will happen under them. */
const CLOSED_STATUSES = new Set(["cancelled", "restored"]);

/**
 * Whether a scope is an area that contains this building: the building itself, its zone, or its
 * site.
 *
 * A request about one building may reach the zone or site around it, since a riser can feed
 * several buildings, but never another building on its own, and never a whole tenant, which is an
 * organisation rather than a place a valve can close.
 */
export function scopeCovers(
  scope: ScopeRecord,
  building: BuildingPlacement,
): boolean {
  switch (scope.kind) {
    case "building":
      return scope.buildingId === building.buildingId;
    case "zone":
      return building.zoneId !== null && scope.zoneId === building.zoneId;
    case "site":
      return scope.siteId === building.siteId;
    default:
      return false;
  }
}

/** Scope ids that name no area containing the building, one line each. */
export function scopeProblems(
  requested: readonly string[],
  found: readonly ScopeRecord[],
  building: BuildingPlacement,
): string[] {
  const byId = new Map(found.map((scope) => [scope.id, scope]));
  return requested.flatMap((id) => {
    const scope = byId.get(id);
    return scope && scopeCovers(scope, building)
      ? []
      : [`scope ${id} is not an area that contains this building`];
  });
}

/**
 * The scope whose approver must decide: the widest area the request reaches. Whoever approves
 * cutting a zone has to have authority over the whole zone, not only the building that asked.
 */
export function widestScope(scopes: readonly ScopeRecord[]): ScopeRecord {
  const rank = (scope: ScopeRecord) =>
    PHYSICAL_SCOPES.indexOf(scope.kind as (typeof PHYSICAL_SCOPES)[number]);
  const [widest] = [...scopes].sort(
    (a, b) => rank(b) - rank(a) || a.id.localeCompare(b.id),
  );
  if (!widest) throw new Error("A request names at least one scope.");
  return widest;
}

/**
 * Isolations already on record that overlap the window asked for.
 *
 * Over `[planned_start, planned_end)`. One that was cancelled or has been restored is over, and a
 * new request may follow it.
 */
export function overlappingIsolations(
  open: readonly OpenIsolation[],
  window: { from: Date; to: Date },
): OpenIsolation[] {
  return open.filter(
    (isolation) =>
      !CLOSED_STATUSES.has(isolation.status) &&
      isolation.plannedStart.getTime() < window.to.getTime() &&
      isolation.plannedEnd.getTime() > window.from.getTime(),
  );
}

const areaKey = (area: string) =>
  normalizeText(area)
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();

/** Two descriptions of one area, written differently: case, accents, spacing and punctuation aside. */
export function sameArea(left: string, right: string): boolean {
  return areaKey(left) === areaKey(right);
}

/** Why a restriction's end cannot be accepted, or `null` if it can. */
export function restrictionUntilProblem(until: Date, now: Date): string | null {
  if (until.getTime() <= now.getTime()) {
    return "requested_until has already passed.";
  }
  if (until.getTime() - now.getTime() > MAX_RESTRICTION_MS) {
    return "requested_until is more than 7 days away. Ask for a shorter restriction and renew it if it is still needed.";
  }
  return null;
}
