import type { ChatMessage, Draft, Photo } from "./types";

/** What one thing the resident does in the connected chat becomes. */
export type ChatTurn =
  // Open (or start) the conversation and send nothing.
  | { kind: "open" }
  // A field of the form being filled in: not a message to Reception.
  | { kind: "form"; draft: Draft }
  // A message to Reception, in the resident's own words.
  | { kind: "message"; text: string };

/**
 * Reception leads the conversation. "Báo sự cố" only opens it: sent as a message it reads as a
 * report of nothing, and Reception filed that. While the form is open its lines are the form's
 * fields. Photos alone are sent without words, so nothing is put in the resident's mouth.
 */
export function chatTurn(text: string, photos: Photo[], form: Draft | null): ChatTurn {
  if (text === "Báo sự cố") return { kind: "open" };
  if (!form) return { kind: "message", text: text.trim() };
  const draft = { ...form, photos: [...form.photos, ...photos].slice(0, 3) };
  if (form.step === "description") {
    draft.description = text.trim();
    draft.step = "location";
  } else if (form.step === "location") {
    draft.location = text.trim();
    draft.step = "review";
  }
  return { kind: "form", draft };
}

/**
 * The form is the way around Reception when it could not answer: Reception and the backend name
 * it ("biểu mẫu") only in that reply. A conversation that already has a request has no use for it.
 */
export function formOffered(messages: ChatMessage[]): boolean {
  const last = messages.findLast((m) => m.role === "assistant" && !m.requestId);
  return !!last?.text.includes("biểu mẫu") && !messages.some((m) => m.requestId);
}

/**
 * The separate things a question from management asks, so the resident answers them in one go.
 * The Supervisor writes one question per line; a single sentence stays one item.
 */
export function questionItems(question: string): { lead: string; items: string[] } {
  const lines = question
    // A numbered list written on one line is still a list, and so is one question strung together
    // with semicolons ("A không; B không; và C không?").
    .replace(/\s+(?=\d{1,2}[.)]\s)/g, "\n")
    .split(/\r?\n|;\s+/)
    .map((line) => line.replace(/^\s*(?:\d+[.)]|[-•*])\s*/, "").replace(/^(?:và|hoặc)\s+/i, "").trim())
    .filter(Boolean)
    .map((line, _, all) => (all.length > 1 && !/[?.!:]$/.test(line) ? line + "?" : line))
    .map((line) => line.charAt(0).toUpperCase() + line.slice(1));
  const asked = lines.filter((line) => line.endsWith("?"));
  // Lines that ask nothing introduce the questions.
  if (asked.length > 1)
    return { lead: lines.filter((line) => !line.endsWith("?")).join(" "), items: asked.slice(0, 8) };
  return { lead: "", items: [lines.join(" ")] };
}

/**
 * One message carrying every answer, numbered like the questions. The questions are not repeated:
 * they stay in the conversation above, and quoting "có mùi khét không?" in the resident's own
 * message would read as the resident reporting it.
 */
export function answerText(items: string[], answers: string[]): string {
  if (items.length === 1) return (answers[0] ?? "").trim();
  return items.map((_, index) => `${index + 1}. ${(answers[index] ?? "").trim() || "Chưa rõ"}`).join("\n");
}
