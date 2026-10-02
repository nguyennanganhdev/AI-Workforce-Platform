import type { Provenance } from "../contracts/envelope";
import type { ToolOutcome } from "../tool";

/**
 * One sentence for every refusal, whatever caused it.
 *
 * A building outside the grant, a building in another tenant and a building that does not exist
 * must be indistinguishable to the caller, or the refusal itself answers the question of which
 * buildings exist. The reason is written to the audit entry, where the people who need it can read
 * it. Shared by the host and by tools that refuse for themselves, so there is one wording and not
 * a family of them to tell apart.
 */
export const FORBIDDEN_MESSAGE =
  "This call is not permitted for the current identity and scope.";

/** Where the deployment's own tables are named as a source. */
export const APPLICATION_DB = "application_db";

/**
 * Where each reported record came from, and at which revision.
 *
 * An empty result still names the source. "Nothing was found" is a claim about one system at one
 * moment, and an agent that cannot tell where it came from cannot tell a resident either.
 */
export function provenanceOf(
  records: readonly { id: string; version?: string | number | null }[],
  retrievedAt: string,
  sourceSystem: string,
): Provenance[] {
  if (records.length === 0) {
    return [{ source_system: sourceSystem, retrieved_at: retrievedAt }];
  }
  return records.map((record) => ({
    source_system: sourceSystem,
    source_record_id: record.id,
    source_version: record.version ?? null,
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
  return notFound("No building with that id is available in this scope.", {
    field: "building_id",
  });
}

export function notFound<TData>(
  message: string,
  options: { field?: string } = {},
): ToolOutcome<TData> {
  return {
    status: "NOT_FOUND",
    data: null,
    errors: [
      {
        code: "NOT_FOUND",
        message,
        ...(options.field ? { field: options.field } : {}),
        retryable: false,
      },
    ],
  };
}

/**
 * The call could proceed once the caller supplies something more.
 *
 * Distinct from `INVALID_INPUT`: the request was well formed, and what is missing is a fact about
 * the world rather than a field of the schema. `data` may carry what the tool did find, which is
 * how `asset.read` hands back the candidates it refused to choose between.
 */
export function needsInput<TData>(
  message: string,
  missingFields: string[],
  options: { data?: TData; field?: string; provenance?: Provenance[] } = {},
): ToolOutcome<TData> {
  return {
    status: "NEEDS_INPUT",
    data: options.data ?? null,
    errors: [
      {
        code: "NEEDS_INPUT",
        message,
        ...(options.field ? { field: options.field } : {}),
        retryable: false,
      },
    ],
    missingFields,
    ...(options.provenance ? { provenance: options.provenance } : {}),
  };
}

/**
 * The data is real but too old to reason from.
 *
 * It travels with the answer, as tools.md §3.3 asks: an agent can still show a technician what the
 * sensor last said. What it may not do is conclude from it, and `retryable` is false because asking
 * again a second later would return the same old reading.
 */
export function staleData<TData>(
  data: TData,
  message: string,
  provenance: Provenance[],
): ToolOutcome<TData> {
  return {
    status: "STALE_DATA",
    data,
    errors: [{ code: "STALE_DATA", message, retryable: false }],
    provenance,
  };
}

/**
 * The request was well formed and the schema could not have known it was wrong: a unit the metric
 * is not recorded in, a time the server has not reached.
 */
export function invalidInput<TData>(
  message: string,
  field: string,
): ToolOutcome<TData> {
  return {
    status: "INVALID_INPUT",
    data: null,
    errors: [{ code: "INVALID_INPUT", message, field, retryable: false }],
  };
}

/**
 * The request names things whose state does not allow it: an assignment no longer active, a photo
 * still uploading. One error per problem, so everything wrong is reported in one answer.
 *
 * Nothing was written. `retryable` is false because the same request will fail the same way until
 * the state changes, and the caller should read the state again before sending it.
 */
export function conflict<TData>(
  problems: readonly string[],
  field: string,
): ToolOutcome<TData> {
  return {
    status: "CONFLICT",
    data: null,
    errors: problems.map((message) => ({
      code: "CONFLICT" as const,
      message,
      field,
      retryable: false,
    })),
  };
}

/** A tool refusing for a reason of its own, in the host's words. */
export function forbidden<TData>(): ToolOutcome<TData> {
  return {
    status: "FORBIDDEN",
    data: null,
    errors: [
      { code: "FORBIDDEN", message: FORBIDDEN_MESSAGE, retryable: false },
    ],
  };
}
