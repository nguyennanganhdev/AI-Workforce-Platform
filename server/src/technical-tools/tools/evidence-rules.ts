import type { EvidenceLookup } from "../domain/work-order";

/**
 * What is wrong with each id offered as evidence for a ticket, as one line per problem.
 *
 * An empty list means every id is usable evidence: registered, not withdrawn, its file uploaded and
 * verified, and on this ticket. Anything else is refused rather than quietly dropped, because a
 * result that silently lost a photo would then be judged against less evidence than the technician
 * thinks they sent.
 *
 * A photo still uploading is the case worth naming. It is an id the agent really holds, and it
 * will be valid in a minute; calling it evidence now would record a completion nobody can yet
 * check.
 */
export function evidenceProblems(
  requested: readonly string[],
  found: readonly EvidenceLookup[],
  ticketId: string,
): string[] {
  const byId = new Map(found.map((lookup) => [lookup.id, lookup]));
  return requested.flatMap((id) => {
    const lookup = byId.get(id);
    if (!lookup) return [`evidence ${id} does not exist`];
    if (lookup.kind === "file") {
      return [
        `evidence ${id} is an upload that has not been registered as evidence (file ${lookup.fileStatus})`,
      ];
    }
    if (lookup.ticketId !== ticketId) {
      return [`evidence ${id} belongs to another ticket`];
    }
    if (lookup.status !== "active") return [`evidence ${id} was withdrawn`];
    if (lookup.fileStatus !== "ready") {
      return [`evidence ${id} is not ready (file ${lookup.fileStatus})`];
    }
    return [];
  });
}
