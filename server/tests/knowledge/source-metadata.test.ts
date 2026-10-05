import { describe, expect, test } from "bun:test";
import {
  keywordQuery,
  reliabilityOf,
  scopeKeyOf,
  searchText,
  sourceMetadata,
  unaccent,
} from "../../src/knowledge/source-metadata";

describe("sourceMetadata", () => {
  test("a building file under a cluster", () => {
    const meta = sourceMetadata(
      "01-vinhomes/sapphire/sapphire-1/S1.01/so-dien-thoai-truc-toa.md",
      { trang_thai: "da-thu-thap-mot-phan", cap_nhat: "2026-09-29" },
    );
    expect(meta).toMatchObject({
      don_vi: "vinhomes",
      phan_khu: "sapphire",
      cum: "sapphire-1",
      toa: ["S1.01"],
      cap: "toa",
      loai: "lien_he",
      cap_nhat: "2026-09-29",
      chua_xac_minh: false,
      duong_dan: "Vinhomes > sapphire > sapphire-1 > S1.01",
    });
  });

  test("urban-wide notices and low-rise areas", () => {
    expect(
      sourceMetadata("00-do-thi/quy-dinh-sac-xe-dien.md", {}),
    ).toMatchObject({
      don_vi: "do_thi",
      cap: "do_thi",
      loai: "xe",
      duong_dan: "Đô thị Ocean Park 1",
    });
    expect(
      sourceMetadata("04-thap-tang/ngoc-trai/quy-dinh.md", {}),
    ).toMatchObject({
      don_vi: "vinhomes",
      phan_khu: "ngoc-trai",
      cap: "phan_khu",
    });
  });

  test("everything under Masterise is flagged unverified", () => {
    const meta = sourceMetadata(
      "02-masterise/masteri-waterfront/miami/M1/phong-chay-chua-chay-va-thoat-hiem.md",
      {},
    );
    expect(meta).toMatchObject({
      don_vi: "masterise",
      cum: "miami",
      toa: ["M1"],
      loai: "pccc",
      chua_xac_minh: true,
    });
  });

  test("an unpublished Vinhomes technical reference stays unverified", () => {
    expect(
      sourceMetadata(
        "01-vinhomes/cau-hoi-thuong-gap-a2-01-cb-nhay-lap.md",
        {
          trang_thai: "tham-khao-noi-bo-chua-duyet",
          approval_status: "not_published",
        },
      ),
    ).toMatchObject({
      don_vi: "vinhomes",
      cap: "don_vi",
      loai: "faq",
      chua_xac_minh: true,
    });
  });

  test("a synthetic fixture stays unverified even without an approval label", () => {
    expect(
      sourceMetadata("01-vinhomes/quy-trinh-gia-lap-a2-01.md", {
        fixture_only: true,
        trang_thai: "du-lieu-gia-lap-khong-xuat-ban",
      }),
    ).toMatchObject({
      don_vi: "vinhomes",
      loai: "quy_trinh",
      chua_xac_minh: true,
      trang_thai: "du-lieu-gia-lap-khong-xuat-ban",
    });
  });

  test("a folded document lists all its buildings", () => {
    const meta = sourceMetadata(
      "02-masterise/masteri-waterfront/miami/{M1,M2,M3}/so-do-ham-gui-xe.md",
      {},
      ["M1", "M2", "M3"],
    );
    expect(meta.toa).toEqual(["M1", "M2", "M3"]);
    expect(meta.duong_dan).toBe(
      "Masterise > masteri-waterfront > miami > M1, M2, M3",
    );
  });

  test("YAML dates come back as plain dates", () => {
    expect(
      sourceMetadata("00-do-thi/x.md", { cap_nhat: new Date("2026-09-29") })
        .cap_nhat,
    ).toBe("2026-09-29");
  });
});

describe("scopeKeyOf", () => {
  test("material folders publish to their parent's scope", () => {
    expect(
      scopeKeyOf("04-thap-tang/ngoc-trai/biet-thu-dai-dien/quy-dinh-cu-dan.md"),
    ).toBe("04-thap-tang/ngoc-trai");
    expect(
      scopeKeyOf("02-masterise/masteri-waterfront/nguon/2024-11-21-hotline.md"),
    ).toBe("02-masterise/masteri-waterfront");
    expect(
      scopeKeyOf("01-vinhomes/sapphire/sapphire-1/S1.01/so-do-ham-gui-xe.md"),
    ).toBe("01-vinhomes/sapphire/sapphire-1/S1.01");
    expect(scopeKeyOf("00-do-thi/danh-ba-lien-he.md")).toBe("00-do-thi");
  });
});

describe("reliabilityOf", () => {
  test("the weakest source in the passage decides", () => {
    expect(reliabilityOf("Theo TB 134/2026/TBCT-VHOCP.")).toBe("van_ban_bql");
    expect(reliabilityOf("Ghi nhận team: 3–5 phút.")).toBe("ghi_nhan_team");
    expect(reliabilityOf("TB 05/2026; bài cư dân ghi khác.")).toBe("web");
    expect(reliabilityOf("Giữ liên lạc cabin.")).toBe("khong_ro");
    expect(
      reliabilityOf("Thông báo số 134/2026. Email info@vinhomes.vn."),
    ).toBe("van_ban_bql");
    expect(reliabilityOf("Nguồn: thuenhavinhomesoceanpark.com")).toBe("web");
  });
});

describe("keyword search text and query", () => {
  test("unaccent handles đ", () => {
    expect(unaccent("Phí gửi xe Đông")).toBe("Phi gui xe Dong");
  });

  test("search text carries an unaccented copy and splits slash codes", () => {
    const text = searchText(["M1/M2/M3", "Phí gửi xe"]);
    expect(text).toContain("M1 M2 M3");
    expect(text).toContain("Phi gui xe");
  });

  test("query keeps codes, drops stopwords and cannot inject tsquery syntax", () => {
    const query = keywordQuery(
      "phí gửi xe của tòa S1.01 là bao nhiêu? ') | !x",
    )?.any;
    expect(query).toContain("'s1.01'");
    expect(query).toContain("'phi'");
    expect(query).not.toContain("'của'");
    for (const token of (query ?? "").split(" | ")) {
      expect(token).toMatch(/^'[\p{L}\p{N}.]+'$/u);
    }
  });

  test("tokens with digits must all match for the exact-code tier", () => {
    expect(keywordQuery("TB 134/2026 quy định gì?")?.codes).toBe(
      "'134' & '2026'",
    );
    expect(keywordQuery("gọi 0858 001 080")?.codes).toBe(
      "'0858' & '001' & '080'",
    );
    expect(keywordQuery("phí gửi xe")?.codes).toBeNull();
  });

  test("a question of only stopwords has no keyword query", () => {
    expect(keywordQuery("là gì vậy?")).toBeNull();
  });
});
