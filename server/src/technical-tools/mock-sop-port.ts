import type { z } from "zod";
import { ToolError } from "./errors";
import type { SopPort } from "./ports";
import type { sopRetrieveOutput } from "./schemas";

type SopData = z.output<typeof sopRetrieveOutput>["documents"][number];

export interface MockSopDocument extends SopData {
  tenantId: string;
  buildingIds: readonly string[];
  issueCodes: readonly string[];
  language: string;
  status: "draft" | "published" | "archived";
  activeVersion: boolean;
  reviewed: boolean;
  ingested: boolean;
  allowedPrincipalIds: readonly string[];
  deniedPrincipalIds?: readonly string[];
  allowedWorkspaceIds?: readonly string[];
  deniedWorkspaceIds?: readonly string[];
}

/** POC fixture adapter. Production retrieval must resolve full DB ACL and scope ancestry. */
export function createMockSopPort(
  documents: readonly MockSopDocument[],
): SopPort {
  return {
    async retrieve(context, input) {
      const at = Date.parse(input.effective_at ?? context.received_at);
      const terms = input.query
        .toLocaleLowerCase()
        .split(/\s+/)
        .filter(Boolean);
      const matches = documents
        .filter((doc) => {
          if (
            doc.tenantId !== context.tenant_id ||
            !doc.buildingIds.includes(input.building_id)
          )
            return false;
          if (
            !doc.issueCodes.includes(input.issue_code) ||
            doc.language !== input.language
          )
            return false;
          if (
            doc.status !== "published" ||
            !doc.activeVersion ||
            !doc.reviewed ||
            !doc.ingested
          )
            return false;
          if (
            Date.parse(doc.effective_from) > at ||
            (doc.effective_to && Date.parse(doc.effective_to) <= at)
          )
            return false;
          if (doc.deniedPrincipalIds?.includes(context.principal_id))
            return false;
          if (
            context.workspace_id &&
            doc.deniedWorkspaceIds?.includes(context.workspace_id)
          )
            return false;
          return (
            doc.allowedPrincipalIds.includes(context.principal_id) ||
            Boolean(
              context.workspace_id &&
                doc.allowedWorkspaceIds?.includes(context.workspace_id),
            )
          );
        })
        .map((doc) => ({
          doc,
          score: terms.reduce(
            (score, term) =>
              score +
              Number(
                `${doc.title} ${doc.excerpt ?? ""}`
                  .toLocaleLowerCase()
                  .includes(term),
              ),
            0,
          ),
        }))
        .filter((item) => item.score > 0)
        .sort(
          (a, b) => b.score - a.score || b.doc.version_no - a.doc.version_no,
        )
        .slice(0, input.limit);
      if (matches.length === 0)
        throw new ToolError(
          "NOT_FOUND",
          "No permitted, effective SOP was found.",
        );
      return {
        data: {
          documents: matches.map(({ doc }) => ({
            document_id: doc.document_id,
            code: doc.code,
            title: doc.title,
            version_no: doc.version_no,
            effective_from: doc.effective_from,
            effective_to: doc.effective_to ?? null,
            excerpt: doc.excerpt,
            acceptance_criteria: doc.acceptance_criteria,
            source_refs: doc.source_refs,
          })),
        },
        provenance: matches.map(({ doc }) => ({
          source_system: "sop_mock_poc",
          source_record_id: doc.document_id,
          source_version: doc.version_no,
          retrieved_at: context.received_at,
        })),
      };
    },
  };
}
