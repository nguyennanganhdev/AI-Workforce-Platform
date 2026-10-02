import { describe, expect, test } from "bun:test";
import type {
  ContactAttempt,
  ResidentRecord,
  Vendor,
} from "../../src/technical-tools";
import {
  CONTACT_FRESHNESS_MS,
  CONTACT_SPACING_MS,
  contactIsSufficient,
  entryWindowProblem,
  hasCurrentResident,
  looksLikeCredential,
  MAX_ENTRY_WINDOW_MS,
  requiredApprovals,
} from "../../src/technical-tools/tools/entry-rules";
import {
  candidates,
  LICENCE_REVIEW_MS,
  qualificationOf,
} from "../../src/technical-tools/tools/vendor-rules";
import { NOW, SITE, TENANT } from "./fixtures/world";

/**
 * The decisions behind the last two request tools, as plain functions: has the resident been
 * tried enough, who must approve entering their home, does a text carry a code, and which vendors
 * may be put in front of an approver.
 */
const minutesAgo = (n: number) => new Date(NOW.getTime() - n * 60 * 1000);

const attempt = (
  minutes: number,
  outcome: ContactAttempt["outcome"] = "no_answer",
  channel: ContactAttempt["channel"] = "phone",
): ContactAttempt => ({ channel, attemptedAt: minutesAgo(minutes), outcome });

describe("whether the resident has been tried enough", () => {
  test("twice, fifteen minutes apart, within the day", () => {
    expect(
      contactIsSufficient(
        [attempt(60, "delivered", "app"), attempt(30)],
        NOW,
        false,
      ),
    ).toBe(true);
    expect(contactIsSufficient([attempt(20), attempt(5)], NOW, false)).toBe(
      true,
    );
  });

  test("not once, and not twice in quick succession", () => {
    expect(contactIsSufficient([attempt(1)], NOW, false)).toBe(false);
    expect(contactIsSufficient([attempt(10), attempt(5)], NOW, false)).toBe(
      false,
    );
    // One minute short of the spacing.
    expect(
      contactIsSufficient(
        [attempt(0), attempt(CONTACT_SPACING_MS / 60000 - 1)],
        NOW,
        false,
      ),
    ).toBe(false);
  });

  test("not with attempts from yesterday", () => {
    const dayAndAMinute = CONTACT_FRESHNESS_MS / 60000 + 1;
    expect(
      contactIsSufficient(
        [attempt(dayAndAMinute + 30), attempt(dayAndAMinute)],
        NOW,
        false,
      ),
    ).toBe(false);
  });

  test("once is enough for an emergency ticket, but not zero, and not a stale once", () => {
    expect(contactIsSufficient([attempt(2)], NOW, true)).toBe(true);
    expect(contactIsSufficient([], NOW, true)).toBe(false);
    expect(contactIsSufficient([attempt(60 * 25)], NOW, true)).toBe(false);
  });

  test("a resident who answered, yes or no, has been reached", () => {
    expect(contactIsSufficient([attempt(1, "rejected")], NOW, false)).toBe(
      true,
    );
    expect(contactIsSufficient([attempt(1, "approved")], NOW, false)).toBe(
      true,
    );
  });
});

describe("who must approve entering", () => {
  test("a refusal takes management and safety together", () => {
    expect(
      requiredApprovals([attempt(30), attempt(5, "rejected")], true),
    ).toEqual(["management_override", "safety_officer"]);
  });

  test("a yes the agent reports is not a permission: the resident confirms in writing", () => {
    expect(requiredApprovals([attempt(5, "approved")], true)).toEqual([
      "resident_written_confirmation",
    ]);
  });

  test("the latest answer decides when there were two", () => {
    expect(
      requiredApprovals(
        [attempt(30, "approved"), attempt(5, "rejected")],
        true,
      ),
    ).toEqual(["management_override", "safety_officer"]);
    expect(
      requiredApprovals(
        [attempt(30, "rejected"), attempt(5, "approved")],
        true,
      ),
    ).toEqual(["resident_written_confirmation"]);
  });

  test("no answer: the resident or management; nobody living there: management", () => {
    expect(requiredApprovals([attempt(30), attempt(5)], true)).toEqual([
      "resident_or_authorized_management",
    ]);
    expect(requiredApprovals([attempt(30), attempt(5)], false)).toEqual([
      "authorized_management",
    ]);
  });
});

describe("whether anybody lives there now", () => {
  const resident = (change: Partial<ResidentRecord> = {}): ResidentRecord => ({
    userId: "u",
    relation: "owner",
    verificationStatus: "verified",
    validFrom: new Date("2025-01-01T00:00:00Z"),
    validTo: null,
    ...change,
  });

  test("a verified resident whose record is current", () => {
    expect(hasCurrentResident([resident()], NOW)).toBe(true);
  });

  test("not one who moved out, nor one nobody has verified, nor one not yet moved in", () => {
    expect(
      hasCurrentResident(
        [
          resident({ validTo: new Date("2026-06-01T00:00:00Z") }),
          resident({ verificationStatus: "pending" }),
          resident({ validFrom: new Date("2026-12-01T00:00:00Z") }),
        ],
        NOW,
      ),
    ).toBe(false);
  });
});

/*
 * tools.md §6.3: the tool neither takes nor returns credentials. The check has to catch the ways a
 * code is actually written down, and leave alone a repair description that only mentions a lock.
 */
describe("whether a text carries a door code, PIN or password", () => {
  test.each([
    "Chủ nhà nói mã cửa là 4821#, vào kiểm tra giúp",
    "MÃ KHÓA: 120788",
    "pin:4821",
    "Mật khẩu két 998877",
    "door code 5521",
    "access code is 0000",
  ])("%s", (text) => {
    expect(looksLikeCredential(text)).toBe(true);
  });

  test.each([
    "Cần thợ mở khóa cửa căn hộ A1-1305",
    "Pin cảm biến khói hết, thay pin 9V",
    "Rò nước từ căn 1305 xuống căn 1205",
    "Mã sự cố INC-3111",
  ])("not %s", (text) => {
    expect(looksLikeCredential(text)).toBe(false);
  });
});

describe("how long an entry window may be", () => {
  const later = (minutes: number) => new Date(NOW.getTime() + minutes * 60000);

  test("up to eight hours, ending in the future", () => {
    expect(
      entryWindowProblem({ from: later(60), to: later(180) }, NOW),
    ).toBeNull();
    expect(
      entryWindowProblem(
        { from: later(0), to: later(MAX_ENTRY_WINDOW_MS / 60000) },
        NOW,
      ),
    ).toBeNull();
  });

  test("not over, and not longer", () => {
    expect(
      entryWindowProblem({ from: later(-120), to: later(-60) }, NOW),
    ).toContain("already ended");
    expect(
      entryWindowProblem(
        { from: later(0), to: later(MAX_ENTRY_WINDOW_MS / 60000 + 1) },
        NOW,
      ),
    ).toContain("longer than 8 hours");
  });
});

const vendor = (vendorId: string, change: Partial<Vendor> = {}): Vendor => ({
  vendorId,
  tenantId: TENANT.vinhomes,
  displayName: vendorId,
  specialtyCodes: ["STRUCTURAL_ENGINEER"],
  siteIds: [SITE.oceanPark],
  status: "active",
  licenseExpiresAt: new Date("2027-09-30T00:00:00Z"),
  insuranceVerified: true,
  contactPhone: "+84900000000",
  hourlyRate: 500000,
  ...change,
});

describe("which vendors may be offered", () => {
  const at = (ms: number) => new Date(NOW.getTime() + ms);

  test("licensed beyond thirty days and insured: eligible", () => {
    expect(qualificationOf(vendor("V"), SITE.oceanPark, NOW)).toBe("eligible");
    expect(
      qualificationOf(
        vendor("V", { licenseExpiresAt: at(LICENCE_REVIEW_MS + 1) }),
        SITE.oceanPark,
        NOW,
      ),
    ).toBe("eligible");
  });

  test("licence within thirty days, or insurance unverified: for review", () => {
    expect(
      qualificationOf(
        vendor("V", { licenseExpiresAt: at(LICENCE_REVIEW_MS) }),
        SITE.oceanPark,
        NOW,
      ),
    ).toBe("needs_review");
    expect(
      qualificationOf(
        vendor("V", { insuranceVerified: false }),
        SITE.oceanPark,
        NOW,
      ),
    ).toBe("needs_review");
  });

  test("not at all: lapsed, suspended, or not serving this site", () => {
    expect(
      qualificationOf(
        vendor("V", { licenseExpiresAt: NOW }),
        SITE.oceanPark,
        NOW,
      ),
    ).toBeNull();
    expect(
      qualificationOf(
        vendor("V", { status: "suspended" }),
        SITE.oceanPark,
        NOW,
      ),
    ).toBeNull();
    expect(
      qualificationOf(
        vendor("V", { siteIds: [SITE.other] }),
        SITE.oceanPark,
        NOW,
      ),
    ).toBeNull();
  });

  test("eligible first, then for review, each by name, and nothing but id, name and status", () => {
    const listed = candidates(
      [
        vendor("V-3", { displayName: "Zeta", insuranceVerified: false }),
        vendor("V-2", { displayName: "Beta" }),
        vendor("V-1", { displayName: "Alpha", status: "suspended" }),
        vendor("V-4", { displayName: "Alpha2" }),
      ],
      SITE.oceanPark,
      NOW,
    );
    expect(listed).toEqual([
      {
        vendorId: "V-4",
        displayName: "Alpha2",
        qualificationStatus: "eligible",
      },
      { vendorId: "V-2", displayName: "Beta", qualificationStatus: "eligible" },
      {
        vendorId: "V-3",
        displayName: "Zeta",
        qualificationStatus: "needs_review",
      },
    ]);
  });
});
