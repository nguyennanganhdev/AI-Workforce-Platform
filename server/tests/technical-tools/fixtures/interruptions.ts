import { interruptionId, SCOPE, TENANT } from "./world";

const at = (iso: string) => new Date(iso);

export type InterruptionFixture = {
  /** The label the tests and the plan refer to it by. */
  key: string;
  id: string;
  tenantId: string;
  utility: "water" | "power";
  status:
    | "proposed"
    | "approved"
    | "notified"
    | "active"
    | "restored"
    | "cancelled";
  reason: string;
  plannedStart: Date;
  plannedEnd: Date;
  actualStart: Date | null;
  actualEnd: Date | null;
  scopeIds: readonly string[];
  /** What this row is in the set to prove. */
  proves: string;
};

/**
 * Ten interruptions around 30/09/2026 09:00 UTC (`NOW`), one per thing a tool could get wrong.
 *
 * Times are UTC. Each row exists for the reason in `proves`; adding a row that proves nothing new
 * only makes the expected results harder to read.
 */
export const INTERRUPTIONS: readonly InterruptionFixture[] = [
  {
    key: "I1",
    id: interruptionId(1),
    tenantId: TENANT.vinhomes,
    utility: "water",
    status: "active",
    reason: "Khóa nước tòa A1 để thay van tổng tầng kỹ thuật",
    plannedStart: at("2026-09-30T06:00:00Z"),
    plannedEnd: at("2026-09-30T08:30:00Z"),
    actualStart: at("2026-09-30T06:05:00Z"),
    actualEnd: null,
    scopeIds: [SCOPE.buildingA1],
    proves:
      "an outage still running past its planned end is still an outage, and its announced end is reported unchanged",
  },
  {
    key: "I2",
    id: interruptionId(2),
    tenantId: TENANT.vinhomes,
    utility: "power",
    status: "notified",
    reason: "Bảo trì định kỳ tủ điện tổng tòa A1 và A2",
    plannedStart: at("2026-10-01T02:00:00Z"),
    plannedEnd: at("2026-10-01T04:00:00Z"),
    actualStart: null,
    actualEnd: null,
    scopeIds: [SCOPE.buildingA1, SCOPE.buildingA2],
    proves:
      "an announced schedule is returned once, with both of its scopes, not once per scope",
  },
  {
    key: "I3",
    id: interruptionId(3),
    tenantId: TENANT.vinhomes,
    utility: "water",
    status: "proposed",
    reason: "Đề nghị khóa nước tòa A2 để xử lý rò ống gần tủ điện tầng 8",
    plannedStart: at("2026-09-30T09:10:00Z"),
    plannedEnd: at("2026-09-30T10:10:00Z"),
    actualStart: null,
    actualEnd: null,
    scopeIds: [SCOPE.buildingA2],
    proves:
      "a request nobody has approved is never reported as an outage or a schedule",
  },
  {
    key: "I4",
    id: interruptionId(4),
    tenantId: TENANT.vinhomes,
    utility: "power",
    status: "cancelled",
    reason: "Cắt điện thay máy biến áp tòa A1 (đã hủy)",
    plannedStart: at("2026-09-30T13:00:00Z"),
    plannedEnd: at("2026-09-30T15:00:00Z"),
    actualStart: null,
    actualEnd: null,
    scopeIds: [SCOPE.buildingA1],
    proves: "a cancelled cut is not a schedule",
  },
  {
    key: "I5",
    id: interruptionId(5),
    tenantId: TENANT.vinhomes,
    utility: "water",
    status: "restored",
    reason: "Khóa nước tòa A1 sửa đường ống cấp tầng 12",
    plannedStart: at("2026-09-29T14:00:00Z"),
    plannedEnd: at("2026-09-29T16:00:00Z"),
    actualStart: at("2026-09-29T14:10:00Z"),
    actualEnd: at("2026-09-29T15:40:00Z"),
    scopeIds: [SCOPE.buildingA1],
    proves:
      "a finished outage is found by an incident inside the hours it actually ran, and not outside them",
  },
  {
    key: "I6",
    id: interruptionId(6),
    tenantId: TENANT.vinhomes,
    utility: "power",
    status: "active",
    reason: "Sự cố trạm biến áp phân khu S1",
    plannedStart: at("2026-09-30T08:30:00Z"),
    plannedEnd: at("2026-09-30T10:30:00Z"),
    actualStart: at("2026-09-30T08:32:00Z"),
    actualEnd: null,
    scopeIds: [SCOPE.zoneS1],
    proves: "a cut declared for a zone reaches every building in that zone",
  },
  {
    key: "I7",
    id: interruptionId(7),
    tenantId: TENANT.vinhomes,
    utility: "water",
    status: "approved",
    reason: "Súc rửa bể nước ngầm toàn khu",
    plannedStart: at("2026-10-02T01:00:00Z"),
    plannedEnd: at("2026-10-02T03:00:00Z"),
    actualStart: null,
    actualEnd: null,
    scopeIds: [SCOPE.siteOceanPark],
    proves: "a cut declared for the whole site reaches every building on it",
  },
  {
    key: "I8",
    id: interruptionId(8),
    tenantId: TENANT.vinhomes,
    utility: "water",
    status: "active",
    reason: "Khóa nước tòa B1 sửa trục cấp nước",
    plannedStart: at("2026-09-30T07:00:00Z"),
    plannedEnd: at("2026-09-30T12:00:00Z"),
    actualStart: at("2026-09-30T07:02:00Z"),
    actualEnd: null,
    scopeIds: [SCOPE.buildingB1],
    proves:
      "a building outside the caller's grant says nothing about its outages",
  },
  {
    key: "I9",
    id: interruptionId(9),
    tenantId: TENANT.other,
    utility: "power",
    status: "active",
    reason: "Mất điện tòa X1",
    plannedStart: at("2026-09-30T08:00:00Z"),
    plannedEnd: at("2026-09-30T10:00:00Z"),
    actualStart: at("2026-09-30T08:00:00Z"),
    actualEnd: null,
    scopeIds: [SCOPE.buildingX1],
    proves: "another tenant's rows are invisible",
  },
  {
    key: "I10",
    id: interruptionId(10),
    tenantId: TENANT.vinhomes,
    utility: "power",
    status: "notified",
    reason: "Bản ghi lỗi: giờ kết thúc sớm hơn giờ bắt đầu",
    plannedStart: at("2026-10-01T10:00:00Z"),
    plannedEnd: at("2026-10-01T08:00:00Z"),
    actualStart: null,
    actualEnd: null,
    scopeIds: [SCOPE.buildingA1],
    proves:
      "a row that ends before it begins, which the table does not forbid, is left out rather than matched against every window",
  },
];

/** The id of a fixture by the label the cases use. */
export function idOf(key: string): string {
  const found = INTERRUPTIONS.find((interruption) => interruption.key === key);
  if (!found) throw new Error(`No interruption fixture is called ${key}.`);
  return found.id;
}
