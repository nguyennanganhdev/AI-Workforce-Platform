import { describe, expect, test } from "bun:test";
import type {
  BuildingPlacement,
  OpenIsolation,
  ScopeRecord,
} from "../../src/technical-tools";
import {
  MAX_RESTRICTION_MS,
  overlappingIsolations,
  restrictionUntilProblem,
  sameArea,
  scopeCovers,
  scopeProblems,
  widestScope,
} from "../../src/technical-tools/tools/request-rules";
import { BUILDING, NOW, SCOPE, SITE, ZONE } from "./fixtures/world";

/**
 * The decisions the two request tools make, as plain functions: which areas a request about a
 * building may reach, who must approve it, and when a request repeats one already waiting.
 */
const A1: BuildingPlacement = {
  buildingId: BUILDING.a1,
  zoneId: ZONE.s1,
  siteId: SITE.oceanPark,
};

const scope = (
  id: string,
  kind: string,
  where: Partial<ScopeRecord> = {},
): ScopeRecord => ({
  id,
  kind,
  buildingId: null,
  zoneId: null,
  siteId: null,
  ...where,
});

const OWN = scope(SCOPE.buildingA1, "building", { buildingId: BUILDING.a1 });
const ZONE_S1 = scope(SCOPE.zoneS1, "zone", { zoneId: ZONE.s1 });
const SITE_OP = scope(SCOPE.siteOceanPark, "site", { siteId: SITE.oceanPark });
const NEIGHBOUR = scope(SCOPE.buildingA2, "building", {
  buildingId: BUILDING.a2,
});
const OTHER_ZONE = scope(SCOPE.zoneS2, "zone", { zoneId: ZONE.s2 });
const WHOLE_TENANT = scope(SCOPE.tenantWide, "tenant");

describe("which areas a request about building A1 may reach", () => {
  test.each([
    ["the building itself", OWN],
    ["its zone, which a shared riser may feed", ZONE_S1],
    ["its site", SITE_OP],
  ])("%s", (_label, candidate) => {
    expect(scopeCovers(candidate, A1)).toBe(true);
  });

  test.each([
    ["the neighbouring building, on its own", NEIGHBOUR],
    ["another zone", OTHER_ZONE],
    [
      "the whole tenant, which is an organisation and not a place",
      WHOLE_TENANT,
    ],
  ])("not %s", (_label, candidate) => {
    expect(scopeCovers(candidate, A1)).toBe(false);
  });

  test("a building in no zone is reached by no zone scope", () => {
    expect(scopeCovers(ZONE_S1, { ...A1, zoneId: null })).toBe(false);
  });

  test("every wrong or unknown scope is named, the right ones are not", () => {
    expect(
      scopeProblems(
        [SCOPE.buildingA1, SCOPE.buildingA2, "missing-scope"],
        [OWN, NEIGHBOUR],
        A1,
      ),
    ).toEqual([
      `scope ${SCOPE.buildingA2} is not an area that contains this building`,
      "scope missing-scope is not an area that contains this building",
    ]);
  });
});

/*
 * Whoever approves cutting a zone must have authority over the whole zone. Routing it to the
 * building's manager because the request started in their building would let a narrower authority
 * decide for a wider area.
 */
describe("who must approve", () => {
  test("the widest area the request reaches", () => {
    expect(widestScope([OWN]).id).toBe(SCOPE.buildingA1);
    expect(widestScope([OWN, ZONE_S1]).id).toBe(SCOPE.zoneS1);
    expect(widestScope([ZONE_S1, SITE_OP, OWN]).id).toBe(SCOPE.siteOceanPark);
  });
});

describe("whether a request repeats one already on record", () => {
  const at = (hhmm: string) => new Date(`2026-09-30T${hhmm}:00Z`);
  const open = (
    requestId: string,
    from: string,
    to: string,
    status = "proposed",
  ): OpenIsolation => ({
    requestId,
    interruptionId: `i-${requestId}`,
    status,
    plannedStart: at(from),
    plannedEnd: at(to),
  });
  const window = { from: at("10:00"), to: at("11:00") };

  test("an overlapping window is a repeat, whatever stage it has reached", () => {
    for (const status of ["proposed", "approved", "notified", "active"]) {
      expect(
        overlappingIsolations([open("R1", "10:30", "12:00", status)], window),
      ).toHaveLength(1);
    }
  });

  test("windows that only touch do not overlap", () => {
    expect(
      overlappingIsolations(
        [open("R1", "09:00", "10:00"), open("R2", "11:00", "12:00")],
        window,
      ),
    ).toEqual([]);
  });

  test("a cancelled or restored isolation is over, and a new one may follow", () => {
    expect(
      overlappingIsolations(
        [
          open("R1", "10:00", "11:00", "cancelled"),
          open("R2", "10:00", "11:00", "restored"),
        ],
        window,
      ),
    ).toEqual([]);
  });

  test("one inside the window, and one around it, both overlap", () => {
    expect(
      overlappingIsolations(
        [open("R1", "10:15", "10:45"), open("R2", "09:00", "12:00")],
        window,
      ).map((isolation) => isolation.requestId),
    ).toEqual(["R1", "R2"]);
  });
});

describe("whether two areas are the same area", () => {
  test("written with different case, accents, spacing or punctuation", () => {
    expect(
      sameArea("Hành lang tầng 12, tháp A1", "hanh lang  tang 12 thap a1"),
    ).toBe(true);
    expect(sameArea("Hành lang tầng 12", " HÀNH LANG TẦNG 12. ")).toBe(true);
  });

  test("but not a different floor", () => {
    expect(sameArea("Hành lang tầng 12", "Hành lang tầng 11")).toBe(false);
  });
});

describe("how long a restriction may be asked for", () => {
  const later = (ms: number) => new Date(NOW.getTime() + ms);

  test("up to seven days ahead", () => {
    expect(restrictionUntilProblem(later(60 * 60 * 1000), NOW)).toBeNull();
    expect(restrictionUntilProblem(later(MAX_RESTRICTION_MS), NOW)).toBeNull();
  });

  test("not a moment already past", () => {
    expect(restrictionUntilProblem(NOW, NOW)).toContain("already passed");
  });

  test("not beyond seven days", () => {
    expect(
      restrictionUntilProblem(later(MAX_RESTRICTION_MS + 1), NOW),
    ).toContain("more than 7 days");
  });
});
