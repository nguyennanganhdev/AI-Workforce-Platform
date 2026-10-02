import type { SopDocumentRecord, SopProfile } from "../domain/sop";

export type SopQuery = {
  tenantId: string;
  buildingId: string;
};

export type SopReadPort = {
  /**
   * Every knowledge document whose scope covers the building, in whatever state it is in.
   *
   * A superset on purpose, like the interruption port's: draft, archived and expired documents come
   * back too, and `sop-rules` decides which may be used. That keeps "what counts as a usable SOP"
   * in one testable place instead of spread through a WHERE clause.
   *
   * `null` means the building is not in this tenant at all.
   */
  listForBuilding(query: SopQuery): Promise<SopDocumentRecord[] | null>;
};

/**
 * What a document is about and what counts as done, for a document code and version.
 *
 * Separate from `SopReadPort` because it is answered from a different place: the documents are in
 * the database, while the issue codes and acceptance criteria have nowhere to live in the schema
 * yet. When they do, one implementation can answer both.
 */
export type SopProfilePort = {
  find(code: string, versionNo: number): SopProfile | undefined;
};
