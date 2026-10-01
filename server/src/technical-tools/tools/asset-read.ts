import {
  assetReadInputSchema,
  assetReadOutputSchema,
} from "../contracts/asset";
import type { Asset } from "../domain/asset";
import { defineTool } from "../tool";
import { needsInput, notFound, provenanceOf } from "./outcomes";

/** The POC adapter names itself, so provenance does not imply the data came from the database. */
const ASSET_ADAPTER = "asset_adapter";

function reported(asset: Asset) {
  return {
    asset_id: asset.assetId,
    type: asset.type,
    model: asset.model,
    location: asset.location,
    ownership: asset.ownership,
    warranty_until: asset.warrantyUntil,
    status: asset.status,
    updated_at: asset.updatedAt.toISOString(),
  };
}

/**
 * `asset.read` (tools.md §3.2).
 *
 * Which equipment a fault is about: model, location, ownership, warranty and status. Its one firm
 * rule is that it never picks between candidates. Asked about "the air conditioner in 1205" where
 * two are recorded, it hands both back and says which field would settle it, because an agent that
 * silently got the wrong unit would go on to read the wrong history and propose work on the wrong
 * machine.
 */
export const assetReadTool = defineTool({
  name: "asset.read",
  version: "1.0.0",
  description:
    "Read the equipment record for a building by asset id, or search by location. Use it to " +
    "identify the model, ownership, warranty and status behind a fault. If several assets match, " +
    "the answer is NEEDS_INPUT with the candidates: ask which one rather than assuming, and " +
    "never invent an asset id.",
  effect: "read",
  capability: "asset:read",
  timeoutMs: 5_000,
  inputSchema: assetReadInputSchema,
  outputSchema: assetReadOutputSchema,
  async run(context, input, { assets, clock }) {
    const found = await assets.find({
      tenantId: context.tenant_id,
      buildingId: input.building_id,
      ...(input.asset_id ? { assetId: input.asset_id } : {}),
      ...(input.location ? { location: input.location } : {}),
      ...(input.asset_type ? { assetType: input.asset_type } : {}),
    });

    const retrievedAt = clock.now().toISOString();
    const provenance = provenanceOf(
      found.map((asset) => ({ id: asset.assetId, version: asset.etag })),
      retrievedAt,
      ASSET_ADAPTER,
    );

    if (found.length === 0) {
      return notFound(
        "No asset in this building matches. Give the asset id, or a more exact location.",
        { field: input.asset_id ? "asset_id" : "location" },
      );
    }

    if (found.length > 1) {
      /*
       * The candidates travel with the refusal rather than being withheld. Told only that its
       * question was ambiguous, an agent has to guess what to ask; given the list, it can ask the
       * resident or the technician which machine they mean. The list is the same shape as a
       * successful answer, so nothing has to parse two formats.
       */
      return needsInput(
        `${found.length} assets match. Name the asset_id of the one you mean.`,
        ["asset_id"],
        {
          data: { assets: found.map(reported) },
          field: input.asset_id ? "asset_id" : "location",
          provenance,
        },
      );
    }

    return {
      status: "OK",
      data: { assets: found.map(reported) },
      provenance,
      resultCount: found.length,
    };
  },
});
