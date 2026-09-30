import type { Provenance } from "../contracts/envelope";
import type { InterruptionRecord } from "../domain/interruption";
import type { ToolOutcome } from "../tool";

const SOURCE_SYSTEM = "application_db";

/**
 * Where each reported interruption came from, and at which revision.
 *
 * An empty result still names the source. "Nothing is scheduled" is a claim about one system at one
 * moment, and an agent that cannot tell where it came from cannot tell a resident either.
 */
export function interruptionProvenance(
  records: InterruptionRecord[],
  retrievedAt: string,
): Provenance[] {
  if (records.length === 0) {
    return [{ source_system: SOURCE_SYSTEM, retrieved_at: retrievedAt }];
  }
  return records.map((record) => ({
    source_system: SOURCE_SYSTEM,
    source_record_id: record.id,
    source_version: record.updatedAt.toISOString(),
    retrieved_at: retrievedAt,
  }));
}

/**
 * The building is inside the caller's grant and yet not in the tenant's data.
 *
 * Only reachable for a building the caller was explicitly granted, so saying it is missing reveals
 * nothing the grant did not already. A building outside the grant never gets this far: the host
 * answers `FORBIDDEN` for it whether or not it exists.
 */
export function buildingNotFound<TData>(): ToolOutcome<TData> {
  return {
    status: "NOT_FOUND",
    data: null,
    errors: [
      {
        code: "NOT_FOUND",
        message: "No building with that id is available in this scope.",
        field: "building_id",
        retryable: false,
      },
    ],
  };
}
