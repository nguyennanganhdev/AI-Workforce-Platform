import type { Asset } from "../../domain/asset";
import type { AssetReadPort } from "../../ports/asset-read";
import { normalizeText } from "../../tools/text";

/**
 * An asset source held in memory, for use until a table exists.
 *
 * The catalogue is passed in rather than written here on purpose. A deployment that shipped
 * invented equipment records would answer an agent's question about a resident's air conditioner
 * with a plausible fiction, and the agent would go on to propose work on it. Given nothing, this
 * answers nothing, and `asset.read` reports NOT_FOUND — which is true, and which the person
 * standing up the deployment can act on.
 *
 * Matching is by exact asset id, or by a fragment of the location text compared without case or
 * accents, because a location is free text somebody typed. It never narrows several matches to
 * one; that is the tool's rule and the tool refuses instead.
 */
export function createInMemoryAssetReadPort(
  assets: readonly Asset[] = [],
): AssetReadPort {
  return {
    find: async ({ tenantId, buildingId, assetId, location, assetType }) => {
      const wanted = location ? normalizeText(location) : undefined;
      return assets.filter((asset) => {
        if (asset.tenantId !== tenantId) return false;
        if (asset.buildingId !== buildingId) return false;
        if (assetId && asset.assetId !== assetId) return false;
        if (assetType && asset.type !== assetType) return false;
        if (wanted && !normalizeText(asset.location).includes(wanted)) {
          return false;
        }
        return true;
      });
    },
  };
}
