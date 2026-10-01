import type { Reliability } from "./types";

/**
 * What a document's place in the Ocean Park knowledge tree says about it.
 *
 * The folder layout is the scope model: `00-do-thi` applies to the whole urban area, `01-vinhomes`
 * and `04-thap-tang` are run by Vinhomes, `02-masterise` by Masterise Property Management, and the
 * two operators never share fees, apps, hotlines or procedures. Everything here is derived from the
 * path and the front matter, so it is reproducible and needs no model call.
 */

export type Operator = "do_thi" | "vinhomes" | "masterise";
export type ScopeLevel = "do_thi" | "don_vi" | "phan_khu" | "cum" | "toa";

export type SourceMetadata = {
  don_vi: Operator;
  phan_khu: string | null;
  cum: string | null;
  /** More than one when identical building files were folded into one document. */
  toa: string[];
  cap: ScopeLevel;
  loai: string;
  trang_thai: string | null;
  cap_nhat: string | null;
  hieu_luc: string | null;
  van_ban: string | null;
  /** Masterise data is not verified until its review file is closed (RA-SOAT-DU-LIEU.md). */
  chua_xac_minh: boolean;
  /** The human-readable scope line put in front of every chunk before it is embedded. */
  duong_dan: string;
};

const OPERATOR_FOLDERS: Record<string, { don_vi: Operator; label: string }> = {
  "00-do-thi": { don_vi: "do_thi", label: "Đô thị Ocean Park 1" },
  "01-vinhomes": { don_vi: "vinhomes", label: "Vinhomes" },
  "02-masterise": { don_vi: "masterise", label: "Masterise" },
  "04-thap-tang": { don_vi: "vinhomes", label: "Vinhomes > Thấp tầng" },
};

/** Building codes as they appear as folder names: S1.01, R1.02, P1, M1, H3. */
export const BUILDING_FOLDER = /^(?:[SR]\d\.\d{2}|[PMH]\d)$/;
/** Sub-clusters: sapphire-1, miami, hawaii. */
const CLUSTER_FOLDER = /^(?:sapphire-\d|miami|hawaii)$/;
/**
 * Folders that hold material rather than scope: archived source captures, and the representative
 * villa and shophouse slots of a low-rise area, which apply to every villa or shophouse there.
 */
const NON_SCOPE_FOLDERS = new Set([
  "nguon",
  "biet-thu-dai-dien",
  "shophouse-dai-dien",
]);

/**
 * The scope a file is published to: its folder, minus any trailing material folders. A villa rule
 * in `ngoc-trai/biet-thu-dai-dien/` belongs to Ngọc Trai, where every resident of the area sees it.
 */
export function scopeKeyOf(code: string): string {
  const folders = code.split("/").slice(0, -1);
  while (folders.length > 1 && NON_SCOPE_FOLDERS.has(folders.at(-1) ?? "")) {
    folders.pop();
  }
  return folders.join("/");
}

const KIND_BY_FILE: [RegExp, string][] = [
  [/^phong-chay|thoat-hiem/, "pccc"],
  [/^so-dien-thoai|danh-ba|lien-he/, "lien_he"],
  [/^so-do-ham|trong-giu-xe|sac-xe|giao-thong|xe-buyt/, "xe"],
  [/^thong-tin-toa/, "thong_tin_toa"],
  [/^cau-hoi-thuong-gap/, "faq"],
  [/thanh-toan-phi|phi-dich-vu/, "phi"],
  [/^quy-trinh/, "quy_trinh"],
  [/^huong-dan-dich-vu|tien-ich/, "dich_vu"],
  [/^huong-dan-xu-ly/, "xu_ly_tinh_huong"],
  [/^huong-dan-an-toan/, "an_toan"],
  [/^quy-dinh|noi-quy/, "noi_quy"],
];

function text(value: unknown): string | null {
  if (value === undefined || value === null || value === "") return null;
  return value instanceof Date
    ? value.toISOString().slice(0, 10)
    : String(value);
}

/**
 * Metadata for a document at `code` (a path relative to the repository root). `buildings` overrides
 * the building list for a document that stands for several identical building files.
 */
export function sourceMetadata(
  code: string,
  frontMatter: Record<string, unknown>,
  buildings?: string[],
): SourceMetadata {
  const segments = code.split("/");
  const file = (segments.pop() ?? "").toLowerCase();
  const operator = OPERATOR_FOLDERS[segments[0] ?? ""] ?? {
    don_vi: "do_thi" as Operator,
    label: segments[0] ?? "",
  };
  const scopeFolders = segments
    .slice(1)
    // `{M1,M2}` is the folder of a folded document; its buildings arrive in `buildings`.
    .filter(
      (segment) => !NON_SCOPE_FOLDERS.has(segment) && !segment.startsWith("{"),
    );

  const phanKhu = scopeFolders[0] ?? null;
  const cum =
    scopeFolders.find((segment) => CLUSTER_FOLDER.test(segment)) ?? null;
  const toa =
    buildings ??
    scopeFolders.filter((segment) => BUILDING_FOLDER.test(segment)).slice(0, 1);

  const cap: ScopeLevel =
    toa.length > 0
      ? "toa"
      : cum
        ? "cum"
        : phanKhu
          ? "phan_khu"
          : operator.don_vi === "do_thi"
            ? "do_thi"
            : "don_vi";

  const loai =
    KIND_BY_FILE.find(([pattern]) => pattern.test(file))?.[1] ?? "khac";

  const path = [
    operator.label,
    ...scopeFolders.filter((s) => !BUILDING_FOLDER.test(s)),
  ];
  if (toa.length > 0) path.push(toa.join(", "));

  return {
    don_vi: operator.don_vi,
    phan_khu: phanKhu,
    cum,
    toa,
    cap,
    loai,
    trang_thai: text(frontMatter.trang_thai),
    cap_nhat: text(frontMatter.cap_nhat ?? frontMatter.cap_nhat_khung),
    hieu_luc: text(frontMatter.hieu_luc),
    van_ban: text(frontMatter.van_ban),
    chua_xac_minh: operator.don_vi === "masterise",
    duong_dan: path.join(" > "),
  };
}

/**
 * How well a passage is sourced, read off the passage itself. A file mixes management notices,
 * team notes and web posts, so this is per chunk, and it is the weakest signal present that wins:
 * one line of hearsay makes the passage something to confirm.
 */
export function reliabilityOf(passage: string): Reliability {
  if (
    // A bare domain counts as a web source; the domain of an email address (info@vinhomes.vn) does not.
    /https?:\/\/|(?<![@\w.-])[\w-]+(?:\.[\w-]+)*\.(?:com|vn)\b|bài (cư dân|tổng hợp|đăng|rao)|market vinhomes|facebook|zalo/i.test(
      passage,
    )
  ) {
    return "web";
  }
  if (/ghi nhận team|tài liệu team/i.test(passage)) return "ghi_nhan_team";
  if (
    /\b(TB|TBC|TBCT)\b|thông báo (số|ban quản lý)|VHOCP|bảng niêm yết|quy chế/i.test(
      passage,
    )
  ) {
    return "van_ban_bql";
  }
  return "khong_ro";
}

/** Strip Vietnamese diacritics, so "phi gui xe" finds "phí gửi xe". */
export function unaccent(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .normalize("NFC");
}

/**
 * The text behind `knowledge_chunks.search_tsv`. PostgreSQL's `simple` parser keeps `S1.01` whole but
 * also keeps `M1/M2/M3` and `134/2026/TBCT-VHOCP` as single tokens, so slashes become spaces; the
 * unaccented copy lets a query typed without diacritics match.
 */
export function searchText(parts: string[]): string {
  const joined = parts
    .filter((part) => part !== "")
    .join("\n")
    .normalize("NFC");
  return `${joined}\n${unaccent(joined)}`.replace(/\//g, " ");
}

/** Words too common to help a keyword match in this corpus. */
const STOPWORDS = new Set(
  [
    "và",
    "là",
    "của",
    "có",
    "không",
    "cho",
    "thì",
    "được",
    "các",
    "những",
    "này",
    "đó",
    "ở",
    "tại",
    "với",
    "khi",
    "nào",
    "gì",
    "ai",
    "bao",
    "nhiêu",
    "thế",
    "như",
    "để",
    "một",
    "trong",
    "ra",
    "vào",
    "lên",
    "xuống",
    "cần",
    "phải",
    "hay",
    "hoặc",
    "nếu",
    "mình",
    "tôi",
    "em",
    "anh",
    "chị",
    "bạn",
    "ạ",
    "nhé",
    "vậy",
    "sao",
    "đâu",
    "bị",
    "đã",
    "đang",
    "sẽ",
    "muốn",
    "hỏi",
  ].flatMap((word) => [word, unaccent(word)]),
);

export type KeywordQuery = {
  /** Any meaningful word, accented or not, OR-ed: what the keyword list matches on. */
  any: string;
  /**
   * Every token with a digit in it, AND-ed: building codes, notice numbers, phone numbers. A passage
   * carrying all of them ranks first in the keyword list, because "TB 134/2026" asks for that notice,
   * not for any passage that happens to say "quy định".
   */
  codes: string | null;
};

/**
 * `to_tsquery('simple', …)` expressions for a question. Every token is reduced to letters, digits
 * and dots before it is quoted, so nothing a user types can change the query's syntax. Returns null
 * when nothing meaningful is left.
 */
export function keywordQuery(question: string): KeywordQuery | null {
  const tokens = new Set<string>();
  const normalized = question
    .normalize("NFC")
    .toLowerCase()
    .replace(/\//g, " ");
  for (const raw of normalized.split(/[^\p{L}\p{N}.]+/u)) {
    const token = raw.replace(/^\.+|\.+$/g, "");
    if (token === "" || STOPWORDS.has(token)) continue;
    if (token.length < 2 && !/\d/.test(token)) continue;
    tokens.add(token);
    tokens.add(unaccent(token));
  }
  if (tokens.size === 0) return null;
  const codes = [...tokens].filter((token) => /\d/.test(token));
  return {
    any: [...tokens].map((token) => `'${token}'`).join(" | "),
    codes:
      codes.length === 0
        ? null
        : codes.map((token) => `'${token}'`).join(" & "),
  };
}
