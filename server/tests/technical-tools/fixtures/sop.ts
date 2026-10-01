import type {
  AcceptanceCriterion,
  SopProfile,
} from "../../../src/technical-tools";
import { CATEGORY, id, SCOPE, TENANT, USER } from "./world";

const at = (iso: string) => new Date(iso);

export const KNOWLEDGE_BASE = {
  /** The live technical library of the managed tenant. */
  technical: id("80000000", 1),
  /** Retired: its documents are history, not guidance. */
  retired: id("80000000", 2),
  other: id("80000000", 3),
} as const;

export const KNOWLEDGE_CATEGORY = {
  vinhomes: id("81000000", 1),
  other: id("81000000", 2),
} as const;

export type AclFixture = {
  principalKind: "role" | "user" | "workspace";
  roleCode?: string;
  userId?: string;
  workspaceId?: string;
  effect: "allow" | "deny";
};

export type SopFixture = {
  /** The label tests refer to it by. */
  key: string;
  documentId: string;
  tenantId: string;
  knowledgeBaseId: string;
  categoryId: string;
  code: string;
  title: string;
  status: "draft" | "published" | "archived";
  language: string;
  scopeId: string;
  appliesToDescendants: boolean;
  acl: readonly AclFixture[];
  /** `null` where `active_version_id` was never set. */
  version: {
    versionNo: number;
    effectiveFrom: Date;
    effectiveTo: Date | null;
  } | null;
  issueCodes: readonly string[];
  excerpt: string;
  acceptanceCriteria: readonly AcceptanceCriterion[];
  /** What this document is in the set to prove. */
  proves: string;
};

const allowStaff: AclFixture[] = [
  { principalKind: "role", roleCode: "staff", effect: "allow" },
];

/**
 * Sixteen knowledge documents, each there for one thing a SOP lookup could get wrong.
 *
 * Effective dates are read against 30/09/2026 09:00 UTC (`NOW`). The acceptance criteria are
 * written as structured checks: `sop_kb.retrieve` only reports their text, but
 * `technical.verify_resolution` will have to decide against them, and a criterion that exists only
 * as a sentence leaves that decision to a model.
 */
export const SOPS: readonly SopFixture[] = [
  {
    key: "S1",
    documentId: id("82000000", 1),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-ELEC-001",
    title: "Xử lý cầu dao nhảy liên tục trong căn hộ",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: [
      { principalKind: "role", roleCode: "staff", effect: "allow" },
      { principalKind: "role", roleCode: "management", effect: "allow" },
    ],
    version: {
      versionNo: 3,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.ELEC.BREAKER_TRIP"],
    excerpt:
      "Cô lập nhánh gây quá tải, đo dòng rò, kiểm tra cách điện rồi mới cấp điện trở lại.",
    acceptanceCriteria: [
      {
        id: "elec-001-1",
        text: "Dòng rò của nhánh dưới 30 mA sau xử lý",
        check: {
          kind: "measurement",
          metric: "leakage_current",
          op: "<=",
          value: 30,
          unit: "mA",
        },
      },
      {
        id: "elec-001-2",
        text: "Cầu dao giữ tải định mức trong 15 phút liên tục",
        check: { kind: "checklist", itemCode: "BREAKER_HOLDS_LOAD" },
      },
      {
        id: "elec-001-3",
        text: "Có ảnh tủ điện sau khi hoàn tất",
        check: { kind: "evidence", purpose: "after", min: 1 },
      },
    ],
    proves:
      "the happy path: published, in force, scoped to the building, granted to the role",
  },
  {
    key: "S2",
    documentId: id("82000000", 2),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-HVAC-012",
    title: "Xử lý nước ngưng điều hòa chảy ra sàn",
    status: "published",
    language: "vi",
    scopeId: SCOPE.zoneS1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 3,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.HVAC.CONDENSATION"],
    excerpt:
      "Vệ sinh đường thoát nước ngưng, kiểm tra độ dốc ống và thử tải 30 phút.",
    acceptanceCriteria: [
      {
        id: "hvac-012-1",
        text: "Không còn rò tại thời điểm kiểm tra",
        check: { kind: "checklist", itemCode: "DRAIN_CLEAR" },
      },
      {
        id: "hvac-012-2",
        text: "Có ảnh trước và sau khi vệ sinh đường thoát",
        check: { kind: "evidence", purpose: "after", min: 1 },
      },
    ],
    proves: "a document scoped to a zone reaches every building in that zone",
  },
  {
    key: "S3",
    documentId: id("82000000", 3),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-PLUMB-020",
    title: "Dò và xử lý rò ống nước âm tường",
    status: "published",
    language: "vi",
    scopeId: SCOPE.siteOceanPark,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 2,
      effectiveFrom: at("2026-03-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.PLUMB.CONCEALED_LEAK", "TECH.PLUMB.SEWAGE_BACKFLOW"],
    excerpt:
      "Dùng máy dò ẩm xác định vị trí rò trong tường, khoanh vùng rồi mới phá dỡ tối thiểu.",
    acceptanceCriteria: [
      {
        id: "plumb-020-1",
        text: "Độ ẩm bề mặt tường dưới 18 phần trăm sau xử lý",
        check: {
          kind: "measurement",
          metric: "surface_moisture",
          op: "<=",
          value: 18,
          unit: "%",
        },
      },
      {
        id: "plumb-020-2",
        text: "Kỹ sư cấp nước xác nhận đã thay đoạn ống bị rò",
        check: { kind: "manual" },
      },
    ],
    proves:
      "a document scoped to the whole site reaches a building, and one document can cover two issue codes",
  },
  {
    key: "S4",
    documentId: id("82000000", 4),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-PLUMB-021",
    title: "Xử lý thấm trần căn hộ phía dưới",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.PLUMB.CONCEALED_LEAK"],
    excerpt:
      "Khoanh vùng vết thấm trần, xác định nguồn ẩm từ căn phía trên trước khi sơn lại.",
    acceptanceCriteria: [
      {
        id: "plumb-021-1",
        text: "Vết thấm trần không lan thêm sau 48 giờ theo dõi",
        check: { kind: "checklist", itemCode: "CEILING_STAIN_STABLE" },
      },
    ],
    proves:
      "two documents serve one issue code, so the query decides which is reported first",
  },
  {
    key: "S5",
    documentId: id("82000000", 5),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-ARCH-005",
    title: "Đánh giá nứt tường và trần căn hộ",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: at("2026-09-01T00:00:00Z"),
    },
    issueCodes: ["TECH.ARCH.CRACK"],
    excerpt: "Đo chiều dài và độ mở vết nứt, theo dõi 7 ngày trước khi xử lý.",
    acceptanceCriteria: [
      {
        id: "arch-005-1",
        text: "Độ mở vết nứt không tăng trong 7 ngày",
        check: {
          kind: "measurement",
          metric: "crack_width",
          op: "<=",
          value: 0.3,
          unit: "mm",
        },
      },
    ],
    proves:
      "a version whose effective window has closed is not guidance any more",
  },
  {
    key: "S6",
    documentId: id("82000000", 6),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-ELEC-009",
    title: "Thay ổ cắm và công tắc trong căn hộ (bản nháp)",
    status: "draft",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.ELEC.FIXTURE_FAILURE"],
    excerpt: "Bản nháp đang chờ duyệt, chưa được dùng tại hiện trường.",
    acceptanceCriteria: [
      {
        id: "elec-009-1",
        text: "Ổ cắm giữ điện áp định mức khi thử tải",
        check: { kind: "checklist", itemCode: "OUTLET_HOLDS_LOAD" },
      },
    ],
    proves: "a draft is somebody's work in progress and is never returned",
  },
  {
    key: "S7",
    documentId: id("82000000", 7),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-PLUMB-031",
    title: "Xử lý bồn cầu rỉ nước và thay gioăng sàn",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: [
      { principalKind: "role", roleCode: "management", effect: "allow" },
      { principalKind: "role", roleCode: "staff", effect: "deny" },
    ],
    version: {
      versionNo: 4,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.PLUMB.TOILET_LEAK"],
    excerpt: "Tháo bồn cầu, thay gioăng sàn, thử nước 10 lần xả liên tiếp.",
    acceptanceCriteria: [
      {
        id: "plumb-031-1",
        text: "Không rò tại chân bồn cầu sau 10 lần xả",
        check: { kind: "checklist", itemCode: "TOILET_BASE_DRY" },
      },
    ],
    proves:
      "a deny row beats an allow row for another role, so one role reads it and another does not",
  },
  {
    key: "S8",
    documentId: id("82000000", 8),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-PLUMB-045",
    title: "Xử lý mùi cống và bẫy nước khô",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: [],
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.PLUMB.TRAP_ODOR"],
    excerpt: "Bơm nước mồi vào bẫy, kiểm tra thông hơi trục đứng.",
    acceptanceCriteria: [
      {
        id: "plumb-045-1",
        text: "Không còn mùi tại phễu thu sau 24 giờ",
        check: { kind: "manual" },
      },
    ],
    proves:
      "a document with no access row at all is refused, not shared by default",
  },
  {
    key: "S9",
    documentId: id("82000000", 9),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-ARCH-011",
    title: "Căn chỉnh cửa và cửa sổ (đã lưu trữ)",
    status: "archived",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 2,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.ARCH.DOOR_WINDOW"],
    excerpt: "Quy trình cũ, đã được thay bằng hướng dẫn của nhà sản xuất.",
    acceptanceCriteria: [
      {
        id: "arch-011-1",
        text: "Cánh cửa đóng kín, khe hở dưới 3 mm",
        check: {
          kind: "measurement",
          metric: "door_gap",
          op: "<=",
          value: 3,
          unit: "mm",
        },
      },
    ],
    proves:
      "an archived document is not guidance, even with a version still in force",
  },
  {
    key: "S10",
    documentId: id("82000000", 10),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-HVAC-020",
    title: "Xử lý nước ngưng điều hòa phân khu S2",
    status: "published",
    language: "vi",
    scopeId: SCOPE.zoneS2,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.HVAC.CONDENSATION"],
    excerpt: "Hướng dẫn riêng của phân khu S2 do khác chủng loại thiết bị.",
    acceptanceCriteria: [
      {
        id: "hvac-020-1",
        text: "Không còn rò tại thời điểm kiểm tra",
        check: { kind: "checklist", itemCode: "DRAIN_CLEAR" },
      },
    ],
    proves: "a zone's guidance does not reach a building in another zone",
  },
  {
    key: "S11",
    documentId: id("82000000", 11),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-PLUMB-050",
    title: "Kiểm tra trạm cấp nước tổng của khu",
    status: "published",
    language: "vi",
    scopeId: SCOPE.siteOceanPark,
    appliesToDescendants: false,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.PLUMB.SUPPLY_DRAIN_JOINT"],
    excerpt:
      "Chỉ áp dụng cho hạng mục cấp nước cấp khu, không áp dụng trong căn hộ.",
    acceptanceCriteria: [
      {
        id: "plumb-050-1",
        text: "Áp lực đầu trạm đạt tối thiểu 2 bar",
        check: {
          kind: "measurement",
          metric: "supply_pressure",
          op: ">=",
          value: 2,
          unit: "bar",
        },
      },
    ],
    proves:
      "a site-level document that does not apply to descendants stays at the site, so a building never gets it",
  },
  {
    key: "S12",
    documentId: id("82000000", 12),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-ELEC-030",
    title: "Replacing sockets and switches",
    status: "published",
    language: "en",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.ELEC.FIXTURE_FAILURE"],
    excerpt: "English edition, pending Vietnamese translation.",
    acceptanceCriteria: [
      {
        id: "elec-030-1",
        text: "Outlet holds rated voltage under load",
        check: { kind: "checklist", itemCode: "OUTLET_HOLDS_LOAD" },
      },
    ],
    proves:
      "a document in another language is not served to a Vietnamese request",
  },
  {
    key: "S13",
    documentId: id("82000000", 13),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.retired,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-PLUMB-060",
    title: "Xử lý máy nước nóng không nóng",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.PLUMB.WATER_HEATER"],
    excerpt: "Thuộc bộ tài liệu đã ngừng sử dụng.",
    acceptanceCriteria: [
      {
        id: "plumb-060-1",
        text: "Nước ra đạt 40 độ C sau 15 phút",
        check: {
          kind: "measurement",
          metric: "outlet_temperature",
          op: ">=",
          value: 40,
          unit: "C",
        },
      },
    ],
    proves: "a published document inside a retired collection is not guidance",
  },
  {
    key: "S14",
    documentId: id("82000000", 14),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-ARCH-050",
    title: "Xử lý tủ bếp xệ cánh",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingA1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: null,
    issueCodes: ["TECH.ARCH.CABINET_SAG"],
    excerpt: "Chưa kích hoạt phiên bản nào.",
    acceptanceCriteria: [],
    proves:
      "a published document whose active version was never set is reported as absent rather than as an empty answer",
  },
  {
    key: "S15",
    documentId: id("82000000", 15),
    tenantId: TENANT.vinhomes,
    knowledgeBaseId: KNOWLEDGE_BASE.technical,
    categoryId: KNOWLEDGE_CATEGORY.vinhomes,
    code: "SOP-TEN-001",
    title: "Xử lý ẩm mốc và bong sơn trong căn hộ",
    status: "published",
    language: "vi",
    scopeId: SCOPE.tenantWide,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.ARCH.PAINT_MOISTURE"],
    excerpt: "Áp dụng cho toàn bộ dự án của đơn vị quản lý.",
    acceptanceCriteria: [
      {
        id: "ten-001-1",
        text: "Độ ẩm tường dưới 16 phần trăm trước khi sơn lại",
        check: {
          kind: "measurement",
          metric: "surface_moisture",
          op: "<=",
          value: 16,
          unit: "%",
        },
      },
    ],
    proves: "a tenant-wide document reaches every building of that tenant",
  },
  {
    key: "S16",
    documentId: id("82000000", 16),
    tenantId: TENANT.other,
    knowledgeBaseId: KNOWLEDGE_BASE.other,
    categoryId: KNOWLEDGE_CATEGORY.other,
    code: "SOP-X-001",
    title: "Xử lý cầu dao nhảy (đơn vị khác)",
    status: "published",
    language: "vi",
    scopeId: SCOPE.buildingX1,
    appliesToDescendants: true,
    acl: allowStaff,
    version: {
      versionNo: 1,
      effectiveFrom: at("2026-01-01T00:00:00Z"),
      effectiveTo: null,
    },
    issueCodes: ["TECH.ELEC.BREAKER_TRIP"],
    excerpt: "Tài liệu của đơn vị quản lý khác.",
    acceptanceCriteria: [
      {
        id: "x-001-1",
        text: "Cầu dao giữ tải định mức trong 15 phút liên tục",
        check: { kind: "checklist", itemCode: "BREAKER_HOLDS_LOAD" },
      },
    ],
    proves: "another tenant's library is invisible",
  },
];

/** The knowledge bases and categories the documents hang on. */
export const KNOWLEDGE_BASES = [
  {
    id: KNOWLEDGE_BASE.technical,
    tenantId: TENANT.vinhomes,
    code: "technical",
    name: "Tài liệu kỹ thuật",
    status: "active",
  },
  {
    id: KNOWLEDGE_BASE.retired,
    tenantId: TENANT.vinhomes,
    code: "technical-legacy",
    name: "Tài liệu kỹ thuật cũ",
    status: "archived",
  },
  {
    id: KNOWLEDGE_BASE.other,
    tenantId: TENANT.other,
    code: "technical",
    name: "Tài liệu kỹ thuật",
    status: "active",
  },
] as const;

export const KNOWLEDGE_CATEGORIES = [
  {
    id: KNOWLEDGE_CATEGORY.vinhomes,
    tenantId: TENANT.vinhomes,
    code: "services",
    name: "Quy trình dịch vụ",
  },
  {
    id: KNOWLEDGE_CATEGORY.other,
    tenantId: TENANT.other,
    code: "services",
    name: "Quy trình dịch vụ",
  },
] as const;

/**
 * What the SOP profile port answers with, derived from the same fixtures the database is seeded
 * from, so a document and its profile cannot describe different things.
 */
export const SOP_PROFILES: readonly SopProfile[] = SOPS.filter(
  (sop) => sop.version !== null,
).map((sop) => ({
  code: sop.code,
  versionNo: sop.version?.versionNo ?? 0,
  issueCodes: sop.issueCodes,
  excerpt: sop.excerpt,
  acceptanceCriteria: sop.acceptanceCriteria,
}));

export function sopByKey(key: string): SopFixture {
  const found = SOPS.find((sop) => sop.key === key);
  if (!found) throw new Error(`No SOP fixture is called ${key}.`);
  return found;
}

/** The document ids of several fixtures, in the order given. */
export function sopIds(...keys: string[]): string[] {
  return keys.map((key) => sopByKey(key).documentId);
}

/** Unused by the seed, but it keeps the tenant's service category referenced in one place. */
export const SOP_TICKET_CATEGORY = CATEGORY.vinhomes;
export const SOP_AUTHOR = USER.manager;
