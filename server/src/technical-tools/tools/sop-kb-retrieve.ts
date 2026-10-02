import {
  sopRetrieveInputSchema,
  sopRetrieveOutputSchema,
} from "../contracts/sop";
import { defineTool } from "../tool";
import {
  APPLICATION_DB,
  buildingNotFound,
  forbidden,
  needsInput,
  notFound,
  provenanceOf,
} from "./outcomes";
import { selectSops } from "./sop-rules";
import { searchTerms } from "./text";

/**
 * `sop_kb.retrieve` (tools.md §3.1).
 *
 * The approved technical guidance for a fault, and what counts as done afterwards. Only published
 * documents whose version is in force at the moment asked about: a draft is somebody's work in
 * progress and a lapsed version is guidance that has been replaced, and following either on site
 * is the failure this tool exists to prevent. Where no SOP is available the agent is told so, so
 * that it stops and asks for a person rather than improvising a repair procedure (general.md §11).
 */
export const sopKbRetrieveTool = defineTool({
  name: "sop_kb.retrieve",
  version: "1.0.0",
  description:
    "Look up the approved SOP and acceptance criteria for a technical issue code in one " +
    "building. Use it once the issue code is known and the building is verified. Returns only " +
    "published documents with a version in force; a draft, an archived document or a lapsed " +
    "version is never returned, and there is no fallback to one. NOT_FOUND means no approved " +
    "guidance exists for this fault here: hand the case to somebody qualified rather than " +
    "describing a repair of your own.",
  effect: "read",
  capability: "sop:read",
  timeoutMs: 5_000,
  inputSchema: sopRetrieveInputSchema,
  outputSchema: sopRetrieveOutputSchema,
  async run(context, input, { sop, sopProfiles, clock }) {
    const terms = searchTerms(input.query);
    if (terms.length === 0) {
      return needsInput(
        "The query carries no term to search on. Say which symptom or step you need guidance for.",
        ["query"],
        { field: "query" },
      );
    }

    const records = await sop.listForBuilding({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
    });
    if (records === null) return buildingNotFound();

    const selection = selectSops({
      records,
      profile: (code, versionNo) => sopProfiles.find(code, versionNo),
      issueCode: input.issue_code,
      // The caller may ask what applied at the time of the incident rather than now.
      at: input.effective_at ? new Date(input.effective_at) : clock.now(),
      language: input.language,
      subject: {
        ...(context.role_code ? { roleCode: context.role_code } : {}),
        ...(context.user_id ? { userId: context.user_id } : {}),
        ...(context.workspace_id ? { workspaceId: context.workspace_id } : {}),
      },
      terms,
      limit: input.limit,
    });

    if (selection.outcome === "none") {
      return notFound(
        "No approved SOP is in force for that issue code in this building.",
        { field: "issue_code" },
      );
    }
    /*
     * Usable guidance exists here and this caller may read none of it, which tools.md §3.1 answers
     * FORBIDDEN to rather than NOT_FOUND. The caller already supplied the issue code and the
     * building, so this says only that the configuration withholds the document from its role: an
     * administrator can then fix a missing grant instead of hunting a document that "does not
     * exist".
     */
    if (selection.outcome === "forbidden") return forbidden();

    return {
      status: "OK",
      data: {
        documents: selection.documents.map(({ record, version, profile }) => ({
          document_id: record.documentId,
          code: record.code,
          title: record.title,
          version_no: version.versionNo,
          effective_from: version.effectiveFrom.toISOString(),
          effective_to: version.effectiveTo?.toISOString() ?? null,
          excerpt: profile.excerpt,
          acceptance_criteria: profile.acceptanceCriteria.map(
            (criterion) => criterion.text,
          ),
          // Pinned to the version, so a later revision cannot be mistaken for what was followed.
          source_refs: [`doc:${record.code}:v${version.versionNo}`],
        })),
      },
      provenance: provenanceOf(
        selection.documents.map(({ record, version }) => ({
          id: record.documentId,
          version: version.versionNo,
        })),
        clock.now().toISOString(),
        APPLICATION_DB,
      ),
      resultCount: selection.documents.length,
    };
  },
});
