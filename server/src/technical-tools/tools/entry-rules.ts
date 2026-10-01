import type { ContactAttempt, ResidentRecord } from "../domain/unit";
import { normalizeText } from "./text";

const MINUTE = 60 * 1000;

/** How recent the attempts must be: a call yesterday says nothing about whether anyone is home now. */
export const CONTACT_FRESHNESS_MS = 24 * 60 * MINUTE;

/** How far apart the first and last attempts must be, so one ring and a request is not "tried twice". */
export const CONTACT_SPACING_MS = 15 * MINUTE;

/** The longest an entry window may be. */
export const MAX_ENTRY_WINDOW_MS = 8 * 60 * MINUTE;

const DECISIVE = new Set(["approved", "rejected"]);

/**
 * Whether the resident has been tried enough to ask to enter without them.
 *
 * - An emergency ticket: one attempt in the last day. A sparking breaker does not wait fifteen
 *   minutes for a second call.
 * - The resident answered, yes or no: that is enough, the decision is theirs to record.
 * - Otherwise: two attempts in the last day, the first and last at least fifteen minutes apart.
 */
export function contactIsSufficient(
  attempts: readonly ContactAttempt[],
  now: Date,
  isEmergency: boolean,
): boolean {
  const recent = attempts.filter(
    (attempt) =>
      now.getTime() - attempt.attemptedAt.getTime() <= CONTACT_FRESHNESS_MS,
  );
  if (recent.length === 0) return false;
  if (isEmergency) return true;
  if (recent.some((attempt) => DECISIVE.has(attempt.outcome))) return true;
  if (recent.length < 2) return false;
  const times = recent.map((attempt) => attempt.attemptedAt.getTime());
  return Math.max(...times) - Math.min(...times) >= CONTACT_SPACING_MS;
}

/** Whether anybody verified lives in the unit at `at`. */
export function hasCurrentResident(
  residents: readonly ResidentRecord[],
  at: Date,
): boolean {
  return residents.some(
    (resident) =>
      resident.verificationStatus === "verified" &&
      resident.validFrom.getTime() <= at.getTime() &&
      (resident.validTo === null || at.getTime() < resident.validTo.getTime()),
  );
}

/**
 * Who must approve entry, decided by the tool from the record and never by the agent.
 *
 * The resident's latest answer decides. Entering against a refusal takes two people, management
 * and safety, because it overrides a resident in their own home. A yes the agent reports from a
 * phone call is not a permission anyone can show afterwards, so it asks for the resident's own
 * written confirmation. Without an answer, the resident or management may approve, or management
 * alone when nobody verified lives there.
 */
export function requiredApprovals(
  attempts: readonly ContactAttempt[],
  residentKnown: boolean,
): string[] {
  const latestAnswer = [...attempts]
    .filter((attempt) => DECISIVE.has(attempt.outcome))
    .sort((a, b) => b.attemptedAt.getTime() - a.attemptedAt.getTime())[0];
  if (latestAnswer?.outcome === "rejected") {
    return ["management_override", "safety_officer"];
  }
  if (latestAnswer?.outcome === "approved") {
    return ["resident_written_confirmation"];
  }
  return residentKnown
    ? ["resident_or_authorized_management"]
    : ["authorized_management"];
}

const CREDENTIAL_WORDS =
  /(ma\s*(khoa|cua|mo)|mat\s*khau|password|passcode|pass\s*code|door\s*code|access\s*code|lock\s*code|\botp\b|\bpin\s*[:=#])/;

/**
 * Whether a piece of free text looks like it carries a door code, PIN or password.
 *
 * tools.md §6.3: the tool neither takes nor returns credentials. Text that pairs a credential word
 * with a run of digits is refused rather than stored, so a code an agent was told on the phone
 * does not end up in a request every approver can read. A word alone, "mở khóa" in a repair
 * description, is not a code.
 */
export function looksLikeCredential(text: string): boolean {
  const plain = normalizeText(text);
  const word = CREDENTIAL_WORDS.exec(plain);
  if (!word) return false;
  const after = plain.slice(word.index, word.index + word[0].length + 25);
  return /\d{3,}/.test(after);
}

/** Why an entry window cannot be accepted, or `null` if it can. */
export function entryWindowProblem(
  window: { from: Date; to: Date },
  now: Date,
): string | null {
  if (window.to.getTime() <= now.getTime()) {
    return "requested_window has already ended.";
  }
  if (window.to.getTime() - window.from.getTime() > MAX_ENTRY_WINDOW_MS) {
    return "requested_window is longer than 8 hours. Ask for the time the work needs.";
  }
  return null;
}
