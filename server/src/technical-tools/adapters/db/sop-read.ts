import { and, eq, inArray, or } from "drizzle-orm";
import {
  accessScopes,
  buildings,
  documentAcl,
  documentScopes,
  documentVersions,
  knowledgeBases,
  knowledgeDocuments,
} from "../../../db/schema";
import type { DocumentAclEntry, SopDocumentRecord } from "../../domain/sop";
import type { SopReadPort } from "../../ports/sop-read";
import { asTenantSession, type TenantSessionSource } from "./tenant-session";

/**
 * Reads the knowledge tables for documents whose scope covers one building.
 *
 * Like the interruption adapter, each call is one read-only transaction that sets `app.tenant_id`
 * first, so the tables' row-level security agrees with the `tenant_id` in the query rather than
 * relying on it.
 *
 * Whether a document may actually be used is not decided here. This returns drafts, archived
 * documents and lapsed versions as well, and `sop-rules` filters them, so the rule is in one place
 * and is tested without a database.
 */
export function createDbSopReadPort(source: TenantSessionSource): SopReadPort {
  const session = asTenantSession(source);
  return {
    listForBuilding: ({ tenantId, buildingId }) =>
      session.read(tenantId, async (tx) => {
        const [building] = await tx
          .select({ siteId: buildings.siteId, zoneId: buildings.zoneId })
          .from(buildings)
          .where(
            and(eq(buildings.tenantId, tenantId), eq(buildings.id, buildingId)),
          )
          .limit(1);
        if (!building) return null;

        /*
         * Which scopes reach this building.
         *
         * Its own scope always does. A zone, a site or the whole tenant reaches it only where the
         * document says so: `applies_to_descendants` is how guidance meant for one tower is kept
         * from being served for every tower on the site.
         */
        const covering = tx
          .select({ documentId: documentScopes.documentId })
          .from(documentScopes)
          .innerJoin(
            accessScopes,
            and(
              eq(accessScopes.tenantId, documentScopes.tenantId),
              eq(accessScopes.id, documentScopes.scopeId),
            ),
          )
          .where(
            and(
              eq(documentScopes.tenantId, tenantId),
              or(
                and(
                  eq(accessScopes.kind, "building"),
                  eq(accessScopes.buildingId, buildingId),
                ),
                and(
                  eq(documentScopes.appliesToDescendants, true),
                  or(
                    and(
                      eq(accessScopes.kind, "site"),
                      eq(accessScopes.siteId, building.siteId),
                    ),
                    eq(accessScopes.kind, "tenant"),
                    building.zoneId
                      ? and(
                          eq(accessScopes.kind, "zone"),
                          eq(accessScopes.zoneId, building.zoneId),
                        )
                      : undefined,
                  ),
                ),
              ),
            ),
          );

        const rows = await tx
          .select({
            documentId: knowledgeDocuments.id,
            code: knowledgeDocuments.code,
            title: knowledgeDocuments.title,
            status: knowledgeDocuments.status,
            knowledgeBaseStatus: knowledgeBases.status,
            language: knowledgeDocuments.language,
            updatedAt: knowledgeDocuments.updatedAt,
            versionId: documentVersions.id,
            versionNo: documentVersions.versionNo,
            effectiveFrom: documentVersions.effectiveFrom,
            effectiveTo: documentVersions.effectiveTo,
            contentHash: documentVersions.contentHash,
          })
          .from(knowledgeDocuments)
          .innerJoin(
            knowledgeBases,
            and(
              eq(knowledgeBases.tenantId, knowledgeDocuments.tenantId),
              eq(knowledgeBases.id, knowledgeDocuments.knowledgeBaseId),
            ),
          )
          // Left, because a document whose version was never activated is still a document, and
          // reporting it as absent would hide a configuration mistake behind an empty answer.
          .leftJoin(
            documentVersions,
            and(
              eq(documentVersions.tenantId, knowledgeDocuments.tenantId),
              eq(documentVersions.id, knowledgeDocuments.activeVersionId),
            ),
          )
          .where(
            and(
              eq(knowledgeDocuments.tenantId, tenantId),
              inArray(knowledgeDocuments.id, covering),
            ),
          );
        if (rows.length === 0) return [];

        const acl = await tx
          .select({
            documentId: documentAcl.documentId,
            principalKind: documentAcl.principalKind,
            roleCode: documentAcl.roleCode,
            userId: documentAcl.userId,
            workspaceId: documentAcl.workspaceId,
            effect: documentAcl.effect,
          })
          .from(documentAcl)
          .where(
            and(
              eq(documentAcl.tenantId, tenantId),
              inArray(
                documentAcl.documentId,
                rows.map((row) => row.documentId),
              ),
            ),
          );

        const byDocument = new Map<string, DocumentAclEntry[]>();
        for (const { documentId, ...entry } of acl) {
          byDocument.set(documentId, [
            ...(byDocument.get(documentId) ?? []),
            entry,
          ]);
        }

        return rows.map(
          ({
            versionId,
            versionNo,
            effectiveFrom,
            effectiveTo,
            contentHash,
            ...document
          }): SopDocumentRecord => ({
            ...document,
            activeVersion:
              versionId && versionNo !== null && effectiveFrom
                ? {
                    id: versionId,
                    versionNo,
                    effectiveFrom,
                    effectiveTo,
                    contentHash: contentHash ?? "",
                  }
                : null,
            acl: byDocument.get(document.documentId) ?? [],
          }),
        );
      }),
  };
}
