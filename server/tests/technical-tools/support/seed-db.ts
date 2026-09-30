import {
  accessScopes,
  buildings,
  channels,
  domains,
  interruptionScopes,
  serviceCategories,
  serviceInterruptions,
  sites,
  tenants,
  tickets,
  users,
  workApprovals,
  workOrders,
  zones,
} from "../../../src/db/schema";
import type { TechnicalToolsDatabase } from "../../../src/technical-tools";
import { INTERRUPTIONS } from "../fixtures/interruptions";
import {
  approvalId,
  BUILDINGS,
  SCOPE,
  SCOPES,
  TENANT,
  TENANTS,
  ZONES,
} from "../fixtures/world";

/**
 * Puts the sample estate into the real tables, in foreign-key order.
 *
 * An interruption cannot exist on its own: `service_interruptions.work_order_id` and `approval_id`
 * are both NOT NULL, so each tenant gets one maintenance ticket and work order to hang them on, and
 * each interruption gets its own approval. The approval kind is `management_water_shutdown` even
 * for power, because `work_approvals.kind` has no value for a power cut — a gap recorded in
 * docs/teams/quang/requests/Q02-interruptions.md, not a modelling choice.
 *
 * Runs as the database owner, before the tests drop to a role the row-level security applies to.
 */
export async function seedWorld(database: TechnicalToolsDatabase) {
  for (const tenant of TENANTS) {
    await database.insert(tenants).values({
      id: tenant.tenantId,
      code: tenant.code,
      name: tenant.name,
      status: "active",
    });
    await database.insert(users).values({
      id: tenant.managerId,
      email: tenant.managerEmail,
      name: "Quản lý kỹ thuật",
    });
    await database.insert(domains).values({
      id: tenant.domainId,
      tenantId: tenant.tenantId,
      code: "housing",
      name: "Quản lý căn hộ",
      status: "active",
    });
    await database.insert(sites).values({
      id: tenant.siteId,
      tenantId: tenant.tenantId,
      domainId: tenant.domainId,
      code: "site",
      name: tenant.siteName,
      address: "Gia Lâm, Hà Nội",
      status: "active",
    });
    await database.insert(serviceCategories).values({
      id: tenant.categoryId,
      tenantId: tenant.tenantId,
      code: "technical",
      name: "Kỹ thuật",
    });
  }

  for (const zone of ZONES) {
    await database
      .insert(zones)
      .values({ ...zone, name: `Phân khu ${zone.code}`, status: "active" });
  }
  for (const building of BUILDINGS) {
    await database
      .insert(buildings)
      .values({ ...building, name: `Tòa ${building.code}`, status: "active" });
  }
  for (const scope of SCOPES) {
    await database.insert(accessScopes).values(scope);
  }

  for (const tenant of TENANTS) {
    await database.insert(channels).values({
      id: tenant.channelId,
      tenantId: tenant.tenantId,
      name: "Bảo trì hạ tầng",
      description: "Kênh tiếp nhận của phiếu bảo trì hạ tầng (dữ liệu mẫu)",
      kind: "reception",
    });
    await database.insert(tickets).values({
      id: tenant.ticketId,
      tenantId: tenant.tenantId,
      code: "FIXTURE-MAINT-1",
      requesterUserId: tenant.managerId,
      channelId: tenant.channelId,
      title: "Bảo trì hạ tầng điện nước",
      description: "Phiếu mang các đợt cắt điện nước của dữ liệu mẫu",
      status: "new",
      contactName: "Quản lý kỹ thuật",
      contactPhone: "+84900000000",
      addressSnapshot: {},
      domainId: tenant.domainId,
      requestKind: "incident",
    });
    await database.insert(workOrders).values({
      id: tenant.workOrderId,
      tenantId: tenant.tenantId,
      ticketId: tenant.ticketId,
      categoryId: tenant.categoryId,
      requiredSpecialtyId: tenant.categoryId,
      description: "Công việc mang các đợt cắt điện nước của dữ liệu mẫu",
      status: "in_progress",
    });
  }

  for (const [index, interruption] of INTERRUPTIONS.entries()) {
    const tenant = TENANTS.find(
      (candidate) => candidate.tenantId === interruption.tenantId,
    );
    if (!tenant) throw new Error(`${interruption.key} names no seeded tenant.`);

    const decided =
      interruption.status !== "proposed" && interruption.status !== "cancelled";
    const approval = approvalId(index + 1);
    await database.insert(workApprovals).values({
      id: approval,
      tenantId: tenant.tenantId,
      workOrderId: tenant.workOrderId,
      kind: "management_water_shutdown",
      requiredScopeId:
        tenant.tenantId === TENANT.vinhomes
          ? SCOPE.siteOceanPark
          : SCOPE.buildingX1,
      requestDetail: { reason: interruption.reason },
      requestHash: `fixture-${interruption.key}`,
      status: decided
        ? "approved"
        : interruption.status === "proposed"
          ? "pending"
          : "cancelled",
      ...(decided
        ? { decidedBy: tenant.managerId, decidedAt: interruption.plannedStart }
        : {}),
    });

    const { key: _key, proves: _proves, scopeIds, ...row } = interruption;
    await database.insert(serviceInterruptions).values({
      ...row,
      workOrderId: tenant.workOrderId,
      approvalId: approval,
    });
    for (const scopeId of scopeIds) {
      await database.insert(interruptionScopes).values({
        tenantId: interruption.tenantId,
        interruptionId: interruption.id,
        scopeId,
      });
    }
  }
}
