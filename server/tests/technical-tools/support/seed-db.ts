import { createHash } from "node:crypto";
import { eq } from "drizzle-orm";
import {
  accessScopes,
  buildings,
  channels,
  documentAcl,
  documentScopes,
  documentVersions,
  domains,
  executionPrincipals,
  fileObjects,
  files,
  interruptionScopes,
  knowledgeBases,
  knowledgeCategories,
  knowledgeDocuments,
  serviceCategories,
  serviceInterruptions,
  sites,
  storageLocations,
  tenantMemberships,
  tenants,
  tickets,
  users,
  workApprovals,
  workOrders,
  zones,
} from "../../../src/db/schema";
import type { TechnicalToolsDatabase } from "../../../src/technical-tools";
import { INTERRUPTIONS } from "../fixtures/interruptions";
import { KNOWLEDGE_BASES, KNOWLEDGE_CATEGORIES, SOPS } from "../fixtures/sop";
import {
  approvalId,
  BUILDINGS,
  id,
  SCOPE,
  SCOPES,
  TENANT,
  TENANTS,
  USER,
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
    await database.insert(tenantMemberships).values({
      tenantId: tenant.tenantId,
      userId: tenant.managerId,
      status: "active",
    });
    // A file's owner must be an execution principal, and a document version must have a file.
    await database.insert(executionPrincipals).values({
      id: tenant.principalId,
      tenantId: tenant.tenantId,
      kind: "user",
      userId: tenant.managerId,
      status: "active",
      authzVersion: 0,
    });
    await database.insert(storageLocations).values({
      id: tenant.storageLocationId,
      tenantId: tenant.tenantId,
      provider: "minio",
      endpointRef: "minio",
      bucketName: "documents",
      tenantPrefix: tenant.storagePrefix,
      credentialSecretRef: "vault/fixture",
      encryptionMode: "sse_s3",
      purpose: "documents",
      status: "active",
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

  // The technician the technical agent acts for. No tenant of their own; a membership is enough.
  await database.insert(users).values({
    id: USER.technician,
    email: "kythuat.a1@vinhomes.fixture.test",
    name: "Kỹ thuật viên",
  });
  await database.insert(tenantMemberships).values({
    tenantId: TENANT.vinhomes,
    userId: USER.technician,
    status: "active",
  });

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

  await seedDocuments(database);
}

/**
 * The knowledge documents, with the whole chain a version needs.
 *
 * `document_versions.file_id` is NOT NULL and `app_validate_file` will not let a file be `ready`
 * without an original object that has been scanned and verified, so each version costs a file, an
 * object and an update. That chain is the schema's, not the fixture's: it is how the deployment
 * keeps guidance from pointing at bytes nobody checked.
 *
 * The document is inserted first with no active version, because the file names the document it
 * belongs to and the version names the file. The pointer is set at the end.
 */
async function seedDocuments(database: TechnicalToolsDatabase) {
  for (const base of KNOWLEDGE_BASES) {
    const tenant = TENANTS.find(
      (candidate) => candidate.tenantId === base.tenantId,
    );
    if (!tenant) throw new Error(`${base.code} names no seeded tenant.`);
    await database
      .insert(knowledgeBases)
      .values({ ...base, domainId: tenant.domainId });
  }
  for (const category of KNOWLEDGE_CATEGORIES) {
    await database.insert(knowledgeCategories).values(category);
  }

  for (const [index, sop] of SOPS.entries()) {
    const tenant = TENANTS.find(
      (candidate) => candidate.tenantId === sop.tenantId,
    );
    if (!tenant) throw new Error(`${sop.key} names no seeded tenant.`);

    await database.insert(knowledgeDocuments).values({
      id: sop.documentId,
      tenantId: sop.tenantId,
      knowledgeBaseId: sop.knowledgeBaseId,
      categoryId: sop.categoryId,
      code: sop.code,
      title: sop.title,
      status: sop.status,
      language: sop.language,
    });
    await database.insert(documentScopes).values({
      tenantId: sop.tenantId,
      documentId: sop.documentId,
      scopeId: sop.scopeId,
      appliesToDescendants: sop.appliesToDescendants,
    });
    for (const entry of sop.acl) {
      await database.insert(documentAcl).values({
        tenantId: sop.tenantId,
        documentId: sop.documentId,
        principalKind: entry.principalKind,
        ...(entry.roleCode ? { roleCode: entry.roleCode } : {}),
        ...(entry.userId ? { userId: entry.userId } : {}),
        ...(entry.workspaceId ? { workspaceId: entry.workspaceId } : {}),
        effect: entry.effect,
      });
    }
    if (!sop.version) continue;

    const fileId = id("83000000", index + 1);
    const objectId = id("84000000", index + 1);
    await database.insert(files).values({
      id: fileId,
      tenantId: sop.tenantId,
      ownerPrincipalId: tenant.principalId,
      scopeKind: "document",
      documentId: sop.documentId,
      status: "staged",
      originalName: `${sop.code}-v${sop.version.versionNo}.md`,
      uploadedBy: tenant.managerId,
    });
    await database.insert(fileObjects).values({
      id: objectId,
      tenantId: sop.tenantId,
      fileId,
      locationId: tenant.storageLocationId,
      objectKey: `${tenant.storagePrefix}${sop.code}-v${sop.version.versionNo}.md`,
      versionId: `v${sop.version.versionNo}`,
      variant: "original",
      mimeType: "text/markdown",
      sizeBytes: 2048,
      sha256: sha256Of(sop.code, sop.version.versionNo),
      scanStatus: "clean",
      verifiedAt: sop.version.effectiveFrom,
      encryptionMode: "sse_s3",
      status: "ready",
    });
    await database
      .update(files)
      .set({ acceptedObjectId: objectId, status: "ready" })
      .where(eq(files.id, fileId));

    const versionId = id("85000000", index + 1);
    await database.insert(documentVersions).values({
      id: versionId,
      tenantId: sop.tenantId,
      documentId: sop.documentId,
      versionNo: sop.version.versionNo,
      fileId,
      contentHash: sha256Of(sop.code, sop.version.versionNo),
      effectiveFrom: sop.version.effectiveFrom,
      effectiveTo: sop.version.effectiveTo,
      submittedBy: tenant.managerId,
      extractionConfig: {},
    });
    await database
      .update(knowledgeDocuments)
      .set({ activeVersionId: versionId })
      .where(eq(knowledgeDocuments.id, sop.documentId));
  }
}

/** A stable stand-in for a real content hash; `file_objects.sha256` must be 64 hex characters. */
function sha256Of(code: string, versionNo: number): string {
  return createHash("sha256").update(`${code}:v${versionNo}`).digest("hex");
}
