import type { Asset } from "../domain/asset";

export type AssetQuery = {
  tenantId: string;
  buildingId: string;
  assetId?: string;
  /** Matched as a fragment of the source system's location text, ignoring case and accents. */
  location?: string;
  assetType?: string;
};

export type AssetReadPort = {
  /**
   * Assets in the building that match the query, however many that is.
   *
   * The port deliberately does not narrow several matches down to one. tools.md §3.2 says a tool
   * that cannot tell candidates apart must say so rather than choose, and a port that picked the
   * first row would take that decision where no test would see it.
   */
  find(query: AssetQuery): Promise<Asset[]>;
};
