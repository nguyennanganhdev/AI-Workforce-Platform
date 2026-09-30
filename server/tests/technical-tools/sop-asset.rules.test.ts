import { describe, expect, test } from "bun:test";
import type {
  DocumentAclEntry,
  SopDocumentRecord,
  SopProfile,
} from "../../src/technical-tools";
import {
  aclDecision,
  isInForce,
  isUsable,
  selectSops,
} from "../../src/technical-tools/tools/sop-rules";
import {
  normalizeText,
  searchTerms,
} from "../../src/technical-tools/tools/text";

/**
 * The rules that decide which SOP may be followed, with no database in the way.
 *
 * This is the part worth testing hardest. Every other failure here is an empty answer; a mistake in
 * these rules hands a technician a draft, a superseded revision or a document their role was
 * refused, and the mistake reads as a normal answer.
 */
const at = (iso: string) => new Date(iso);
const NOW = at("2026-09-30T09:00:00Z");

function document(
  overrides: Partial<SopDocumentRecord> & { code?: string } = {},
): SopDocumentRecord {
  return {
    documentId: `doc-${overrides.code ?? "SOP-1"}`,
    code: overrides.code ?? "SOP-1",
    title: "Xử lý nước ngưng điều hòa",
    status: "published",
    knowledgeBaseStatus: "active",
    language: "vi",
    activeVersion: {
      id: "ver-1",
      versionNo: 3,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
      contentHash: "hash",
    },
    acl: [{ principalKind: "role", roleCode: "staff", effect: "allow" }],
    updatedAt: at("2026-01-01T00:00:00Z"),
    ...overrides,
  };
}

function profile(overrides: Partial<SopProfile> = {}): SopProfile {
  return {
    code: "SOP-1",
    versionNo: 3,
    issueCodes: ["TECH.HVAC.CONDENSATION"],
    excerpt: "Vệ sinh đường thoát nước ngưng.",
    acceptanceCriteria: [
      {
        id: "c1",
        text: "Không còn rò tại thời điểm kiểm tra",
        check: { kind: "checklist", itemCode: "DRAIN_CLEAR" },
      },
    ],
    ...overrides,
  };
}

const staff = { roleCode: "staff", userId: "tech-1" };

function select(
  records: SopDocumentRecord[],
  options: {
    profiles?: SopProfile[];
    subject?: typeof staff;
    at?: Date;
    language?: string;
    query?: string;
    limit?: number;
  } = {},
) {
  const profiles = options.profiles ?? [profile()];
  return selectSops({
    records,
    profile: (code, versionNo) =>
      profiles.find(
        (candidate) =>
          candidate.code === code && candidate.versionNo === versionNo,
      ),
    issueCode: "TECH.HVAC.CONDENSATION",
    at: options.at ?? NOW,
    language: options.language ?? "vi",
    subject: options.subject ?? staff,
    terms: searchTerms(options.query ?? "nước ngưng"),
    limit: options.limit ?? 5,
  });
}

describe("what the access list says about a caller", () => {
  const allowStaff: DocumentAclEntry = {
    principalKind: "role",
    roleCode: "staff",
    userId: null,
    workspaceId: null,
    effect: "allow",
  };
  const denyStaff: DocumentAclEntry = { ...allowStaff, effect: "deny" };

  test("a matching allow row admits the caller", () => {
    expect(aclDecision([allowStaff], staff)).toBe("allow");
  });

  /*
   * The rule that matters most. A document withheld from one role while being granted to another
   * must stay withheld, or an agent acting for a technician reads what only a manager may.
   */
  test("a deny row beats an allow row for another role", () => {
    const acl = [
      { ...allowStaff, roleCode: "management" },
      denyStaff,
      allowStaff,
    ];
    expect(aclDecision(acl, staff)).toBe("deny");
    expect(aclDecision(acl, { roleCode: "management" })).toBe("allow");
  });

  test("a document with no row for the caller is refused, not shared", () => {
    expect(aclDecision([], staff)).toBe("unset");
    expect(
      aclDecision([{ ...allowStaff, roleCode: "management" }], staff),
    ).toBe("unset");
  });

  test("a grant to one person admits that person and nobody else", () => {
    const acl: DocumentAclEntry[] = [
      {
        principalKind: "user",
        roleCode: null,
        userId: "tech-1",
        workspaceId: null,
        effect: "allow",
      },
    ];
    expect(aclDecision(acl, { userId: "tech-1" })).toBe("allow");
    expect(aclDecision(acl, { userId: "tech-2" })).toBe("unset");
  });

  test("a grant to a workspace admits the runs of that workspace", () => {
    const acl: DocumentAclEntry[] = [
      {
        principalKind: "workspace",
        roleCode: null,
        userId: null,
        workspaceId: "ws-1",
        effect: "allow",
      },
    ];
    expect(aclDecision(acl, { workspaceId: "ws-1" })).toBe("allow");
    expect(aclDecision(acl, { workspaceId: "ws-2" })).toBe("unset");
  });

  /*
   * A scheduled run has a service principal and no business role. Matching a row whose role is
   * null against a caller whose role is undefined would let such a run read everything granted to
   * "no role", which is not a role anybody configured.
   */
  test("a caller with no role matches no role grant", () => {
    expect(aclDecision([allowStaff], { userId: "tech-1" })).toBe("unset");
    expect(
      aclDecision(
        [{ ...allowStaff, roleCode: null, principalKind: "role" }],
        {},
      ),
    ).toBe("unset");
  });

  test("a principal kind the table does not define matches nobody", () => {
    expect(
      aclDecision([{ ...allowStaff, principalKind: "everyone" }], staff),
    ).toBe("unset");
  });
});

describe("whether a version is in force", () => {
  const window = {
    effectiveFrom: at("2026-01-01T00:00:00Z"),
    effectiveTo: at("2026-09-01T00:00:00Z"),
  };

  test.each([
    ["the moment before it starts", "2025-12-31T23:59:59Z", false],
    ["the moment it starts", "2026-01-01T00:00:00Z", true],
    ["inside it", "2026-05-01T00:00:00Z", true],
    ["the moment it ends", "2026-09-01T00:00:00Z", false],
    ["after it ends", "2026-09-30T09:00:00Z", false],
  ])("%s", (_label, iso, expected) => {
    expect(isInForce(window, at(iso))).toBe(expected);
  });

  test("an open-ended version stays in force", () => {
    expect(
      isInForce(
        { effectiveFrom: window.effectiveFrom, effectiveTo: null },
        NOW,
      ),
    ).toBe(true);
  });
});

describe("which documents are guidance at all", () => {
  test("a published document with a version in force is", () => {
    expect(isUsable(document(), NOW, "vi")).toBe(true);
  });

  test.each([
    ["a draft", { status: "draft" }],
    ["an archived document", { status: "archived" }],
    ["a status the table does not define", { status: "in_review" }],
    ["one inside a retired collection", { knowledgeBaseStatus: "archived" }],
    ["one in another language", { language: "en" }],
    ["one whose active version was never set", { activeVersion: null }],
  ])("%s is not", (_label, change) => {
    expect(isUsable(document(change), NOW, "vi")).toBe(false);
  });

  test("a lapsed version is not, however current the document looks", () => {
    const lapsed = document({
      activeVersion: {
        id: "ver-1",
        versionNo: 1,
        effectiveFrom: at("2026-01-01T00:00:00Z"),
        effectiveTo: at("2026-09-01T00:00:00Z"),
        contentHash: "hash",
      },
    });
    expect(isUsable(lapsed, NOW, "vi")).toBe(false);
    // The same document was guidance in June, which is what `effective_at` exists to ask.
    expect(isUsable(lapsed, at("2026-06-01T00:00:00Z"), "vi")).toBe(true);
  });
});

describe("selecting the SOPs to report", () => {
  test("reports a document that covers the issue code", () => {
    const selection = select([document()]);
    expect(selection.outcome).toBe("found");
    expect(
      selection.outcome === "found"
        ? selection.documents.map((sop) => sop.record.code)
        : [],
    ).toEqual(["SOP-1"]);
  });

  test("a document whose profile covers another issue code is not a candidate", () => {
    expect(
      select([document()], {
        profiles: [profile({ issueCodes: ["TECH.ELEC.BREAKER_TRIP"] })],
      }).outcome,
    ).toBe("none");
  });

  /*
   * A profile is keyed by code and version so it cannot describe a revision it was not written
   * for. A SOP whose steps changed gets a new version, and the old profile then matches nothing —
   * which is reported as no guidance rather than as the previous revision's criteria.
   */
  test("a profile written for another version does not describe this one", () => {
    expect(
      select([document()], { profiles: [profile({ versionNo: 2 })] }).outcome,
    ).toBe("none");
  });

  test("a draft covering the issue code leaves the agent with nothing", () => {
    expect(select([document({ status: "draft" })]).outcome).toBe("none");
  });

  /*
   * tools.md §3.1 answers FORBIDDEN here rather than NOT_FOUND. The two are different facts: one
   * says no guidance exists, the other that a grant is missing, and an administrator can only fix
   * the second if the answer distinguishes it.
   */
  test("usable guidance the caller may not read is a refusal, not an absence", () => {
    expect(select([document({ acl: [] })], { subject: staff }).outcome).toBe(
      "forbidden",
    );
    expect(
      select(
        [
          document({
            acl: [{ principalKind: "role", roleCode: "staff", effect: "deny" }],
          }),
        ],
        { subject: staff },
      ).outcome,
    ).toBe("forbidden");
  });

  test("a draft the caller may not read either is still an absence", () => {
    // Nothing usable exists, so there is no grant to fix and nothing to hint at.
    expect(select([document({ status: "draft", acl: [] })]).outcome).toBe(
      "none",
    );
  });

  test("the one document a manager may read is found for the manager", () => {
    const managerOnly = document({
      acl: [
        { principalKind: "role", roleCode: "management", effect: "allow" },
        { principalKind: "role", roleCode: "staff", effect: "deny" },
      ],
    });
    expect(select([managerOnly], { subject: staff }).outcome).toBe("forbidden");
    expect(
      select([managerOnly], { subject: { roleCode: "management" } }).outcome,
    ).toBe("found");
  });
});

describe("the order documents are reported in", () => {
  const first = document({ code: "SOP-A", title: "Xử lý thấm trần căn hộ" });
  const second = document({
    code: "SOP-B",
    title: "Dò rò ống nước âm tường",
  });
  const profiles = [
    profile({ code: "SOP-A", excerpt: "Khoanh vùng vết thấm trần." }),
    profile({ code: "SOP-B", excerpt: "Dùng máy dò ẩm trong tường." }),
  ];

  test("the document that mentions what was asked comes first", () => {
    const byStain = select([second, first], {
      profiles,
      query: "thấm trần",
    });
    expect(
      byStain.outcome === "found"
        ? byStain.documents.map((sop) => sop.record.code)
        : [],
    ).toEqual(["SOP-A", "SOP-B"]);

    const byWall = select([first, second], {
      profiles,
      query: "âm tường",
    });
    expect(
      byWall.outcome === "found"
        ? byWall.documents.map((sop) => sop.record.code)
        : [],
    ).toEqual(["SOP-B", "SOP-A"]);
  });

  /*
   * The issue code decides which documents are candidates; the query only orders them. Dropping the
   * one approved SOP for a fault because a technician phrased the question differently would leave
   * the agent with no guidance and nothing to say why.
   */
  test("a document matching none of the query's words is still reported, last", () => {
    const selection = select([first, second], {
      profiles,
      query: "chuyện hoàn toàn khác",
    });
    expect(
      selection.outcome === "found"
        ? selection.documents.map((sop) => sop.record.code)
        : [],
    ).toEqual(["SOP-A", "SOP-B"]);
  });

  test("the same question always gets the same order", () => {
    const once = select([first, second], { profiles, query: "kiểm tra" });
    const again = select([second, first], { profiles, query: "kiểm tra" });
    expect(
      once.outcome === "found" ? once.documents.map((s) => s.record.code) : [],
    ).toEqual(
      again.outcome === "found"
        ? again.documents.map((s) => s.record.code)
        : [],
    );
  });

  test("the limit caps how much is reported", () => {
    const selection = select([first, second], {
      profiles,
      query: "kiểm tra",
      limit: 1,
    });
    expect(selection.outcome === "found" ? selection.documents.length : 0).toBe(
      1,
    );
  });
});

/*
 * People type Vietnamese with and without diacritics, and a location or a search that only matched
 * the accented form would make the answer depend on somebody's keyboard.
 */
describe("comparing Vietnamese text", () => {
  test("accents and case do not change what a string matches", () => {
    expect(normalizeText("Phòng Tắm")).toBe("phong tam");
    expect(normalizeText("Điều hòa")).toBe("dieu hoa");
    expect(normalizeText("A1-1205/phòng khách")).toBe("a1-1205/phong khach");
  });

  test("a query is reduced to the words worth searching on", () => {
    expect(searchTerms("tiêu chí nghiệm thu sau xử lý nước ngưng")).toEqual([
      "tieu",
      "chi",
      "nghiem",
      "thu",
      "sau",
      "xu",
      "ly",
      "nuoc",
      "ngung",
    ]);
  });

  test("a repeated word is counted once", () => {
    expect(searchTerms("nước nước nước")).toEqual(["nuoc"]);
  });

  test.each([
    ["punctuation alone", "???"],
    ["stop words alone", "và với của"],
    ["single letters", "a b c"],
    ["whitespace", "   "],
  ])("%s leaves nothing to search on", (_label, query) => {
    expect(searchTerms(query)).toEqual([]);
  });
});
