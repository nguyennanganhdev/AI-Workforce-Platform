/**
 * The sample estate every technical-tool test reads: one managed tenant with two zones and three
 * buildings, and a second tenant whose only job is to be invisible.
 *
 * Ids are fixed and shaped like UUID v4, so a failing assertion names a row a person can find in
 * this file, and so the same ids satisfy both the database's `uuid` columns and the tools' schemas.
 */
export const id = (group: string, n: number) =>
  `${group}-0000-4000-8000-${String(n).padStart(12, "0")}`;

/** "Now" for every test, so a case about an overdue outage does not depend on the machine's clock. */
export const NOW = new Date("2026-09-30T09:00:00Z");

export const TENANT = {
  vinhomes: id("10000000", 1),
  other: id("10000000", 2),
} as const;

export const USER = {
  manager: "fixture-manager-vinhomes",
  technician: "fixture-technician-vinhomes",
  otherManager: "fixture-manager-other",
} as const;

/** `execution_principals`, which a file's owner must be. One per tenant. */
export const PRINCIPAL = {
  vinhomes: id("71000000", 1),
  other: id("71000000", 2),
} as const;

/** Where a document's canonical file is kept, per tenant. */
export const STORAGE_LOCATION = {
  vinhomes: id("72000000", 1),
  other: id("72000000", 2),
} as const;

export const WORKSPACE = {
  vinhomes: id("73000000", 1),
  other: id("73000000", 2),
} as const;

export const DOMAIN = {
  vinhomes: id("20000000", 1),
  other: id("20000000", 2),
} as const;

export const SITE = {
  oceanPark: id("21000000", 1),
  other: id("21000000", 2),
} as const;

export const ZONE = {
  s1: id("22000000", 1),
  s2: id("22000000", 2),
} as const;

export const BUILDING = {
  /** Zone S1. The agent is granted this one. */
  a1: id("23000000", 1),
  /** Zone S1. The agent is granted this one too. */
  a2: id("23000000", 2),
  /** Zone S2, same tenant. The agent is NOT granted this one. */
  b1: id("23000000", 3),
  /** Another tenant's building, with no zone. */
  x1: id("23000000", 4),
  /** No such row anywhere. */
  missing: id("23000000", 99),
} as const;

export const SCOPE = {
  tenantWide: id("30000000", 8),
  siteOceanPark: id("30000000", 1),
  zoneS1: id("30000000", 2),
  zoneS2: id("30000000", 3),
  buildingA1: id("30000000", 4),
  buildingA2: id("30000000", 5),
  buildingB1: id("30000000", 6),
  buildingX1: id("30000000", 7),
} as const;

export const CATEGORY = {
  vinhomes: id("40000000", 1),
  other: id("40000000", 2),
} as const;

export const CHANNEL = {
  vinhomes: "fixture-maintenance-vinhomes",
  other: "fixture-maintenance-other",
} as const;

export const TICKET = {
  vinhomes: id("50000000", 1),
  other: id("50000000", 2),
} as const;

export const WORK_ORDER = {
  vinhomes: id("51000000", 1),
  other: id("51000000", 2),
} as const;

export const approvalId = (n: number) => id("52000000", n);
export const interruptionId = (n: number) => id("60000000", n);

/** The rows a tenant needs before it can hold an interruption or a document. */
export const TENANTS = [
  {
    tenantId: TENANT.vinhomes,
    code: "fixture-vinhomes",
    name: "Vinhomes (dữ liệu mẫu)",
    managerId: USER.manager,
    managerEmail: "quanly.a1@vinhomes.fixture.test",
    domainId: DOMAIN.vinhomes,
    siteId: SITE.oceanPark,
    siteName: "Vinhomes Ocean Park",
    categoryId: CATEGORY.vinhomes,
    channelId: CHANNEL.vinhomes,
    ticketId: TICKET.vinhomes,
    workOrderId: WORK_ORDER.vinhomes,
    principalId: PRINCIPAL.vinhomes,
    workspaceId: WORKSPACE.vinhomes,
    storageLocationId: STORAGE_LOCATION.vinhomes,
    storagePrefix: "t/vinhomes/",
  },
  {
    tenantId: TENANT.other,
    code: "fixture-other",
    name: "Đơn vị quản lý khác (dữ liệu mẫu)",
    managerId: USER.otherManager,
    managerEmail: "quanly@other.fixture.test",
    domainId: DOMAIN.other,
    siteId: SITE.other,
    siteName: "Khu đô thị khác",
    categoryId: CATEGORY.other,
    channelId: CHANNEL.other,
    ticketId: TICKET.other,
    workOrderId: WORK_ORDER.other,
    principalId: PRINCIPAL.other,
    workspaceId: WORKSPACE.other,
    storageLocationId: STORAGE_LOCATION.other,
    storagePrefix: "t/other/",
  },
] as const;

export const ZONES = [
  {
    id: ZONE.s1,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    code: "S1",
  },
  {
    id: ZONE.s2,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    code: "S2",
  },
] as const;

export const BUILDINGS = [
  {
    id: BUILDING.a1,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    zoneId: ZONE.s1,
    code: "A1",
  },
  {
    id: BUILDING.a2,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    zoneId: ZONE.s1,
    code: "A2",
  },
  {
    id: BUILDING.b1,
    tenantId: TENANT.vinhomes,
    siteId: SITE.oceanPark,
    zoneId: ZONE.s2,
    code: "B1",
  },
  {
    id: BUILDING.x1,
    tenantId: TENANT.other,
    siteId: SITE.other,
    zoneId: null,
    code: "X1",
  },
] as const;

export const SCOPES = [
  {
    id: SCOPE.tenantWide,
    tenantId: TENANT.vinhomes,
    kind: "tenant",
  },
  {
    id: SCOPE.siteOceanPark,
    tenantId: TENANT.vinhomes,
    kind: "site",
    siteId: SITE.oceanPark,
  },
  {
    id: SCOPE.zoneS1,
    tenantId: TENANT.vinhomes,
    kind: "zone",
    zoneId: ZONE.s1,
  },
  {
    id: SCOPE.zoneS2,
    tenantId: TENANT.vinhomes,
    kind: "zone",
    zoneId: ZONE.s2,
  },
  {
    id: SCOPE.buildingA1,
    tenantId: TENANT.vinhomes,
    kind: "building",
    buildingId: BUILDING.a1,
  },
  {
    id: SCOPE.buildingA2,
    tenantId: TENANT.vinhomes,
    kind: "building",
    buildingId: BUILDING.a2,
  },
  {
    id: SCOPE.buildingB1,
    tenantId: TENANT.vinhomes,
    kind: "building",
    buildingId: BUILDING.b1,
  },
  {
    id: SCOPE.buildingX1,
    tenantId: TENANT.other,
    kind: "building",
    buildingId: BUILDING.x1,
  },
] as const;

/**
 * Who the tests call as. The agent callback route proves these two ids before a tool is reached;
 * what they are allowed is what the fixture resolver in `support/harness.ts` answers.
 */
export const CALLER = {
  /** Technical Agent A2 acting for a technician: granted A1 and A2, role `staff`. */
  technicalAgent: { botId: "technical-agent-a2", actorId: USER.technician },
  /** The same agent acting for the building manager, whose role reads more documents. */
  managementAgent: { botId: "technical-agent-a2", actorId: USER.manager },
  /** A Bot of the same tenant that was granted none of these capabilities. */
  ungrantedAgent: { botId: "cleaning-agent", actorId: USER.technician },
  /** A Bot this deployment has no binding for. */
  unknownAgent: { botId: "nobody", actorId: "nobody" },
} as const;

/** Which business role each caller acts under, for `document_acl`. */
export const ROLE_OF: Record<string, "management" | "staff"> = {
  [USER.technician]: "staff",
  [USER.manager]: "management",
};

export const AGENT_VERSION = "technical-agent-a2@1.0.0-fixture";
export const SOURCE_RUN_ID = id("70000000", 1);
export const TRACE_ID = "tr-a2-fixture";
