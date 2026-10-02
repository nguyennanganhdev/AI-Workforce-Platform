import type { SopProfile } from "../../domain/sop";
import type { SopProfilePort } from "../../ports/sop-read";

/**
 * Which faults a SOP covers and what counts as done, held in memory until the schema carries it.
 *
 * `knowledge_documents` has no link to an issue code, and a document's acceptance criteria are
 * inside its file in object storage rather than in any column, so there is nowhere to read either
 * from yet. Both gaps are written up for the schema owner in
 * docs/teams/quang/requests/Q02-interruptions.md.
 *
 * Keyed by the document's code and version, so a profile cannot drift onto a revision it was not
 * written for: a SOP whose steps changed gets a new version, and an old profile then matches
 * nothing rather than describing the new one.
 *
 * Passed in rather than written here, for the reason the asset adapter's catalogue is. A profile
 * invented by this deployment would tell a technician that a repair met criteria nobody approved.
 */
export function createInMemorySopProfilePort(
  profiles: readonly SopProfile[] = [],
): SopProfilePort {
  const byKey = new Map(
    profiles.map((profile) => [
      `${profile.code}:${profile.versionNo}`,
      profile,
    ]),
  );
  return { find: (code, versionNo) => byKey.get(`${code}:${versionNo}`) };
}
