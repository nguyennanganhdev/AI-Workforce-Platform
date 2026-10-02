/**
 * Vietnamese text reduced to something two strings can be compared by.
 *
 * Lower case and without diacritics, because people type both ways: a technician searching
 * "tieu chi nghiem thu" means the same as "tiêu chí nghiệm thu", and a location typed
 * "A1-1205/Phong khach" means the apartment recorded as "A1-1205/phòng khách". Matching the raw
 * strings would make the answer depend on somebody's keyboard.
 *
 * NFD splits an accented letter into a letter plus a combining mark, which `\p{M}` then removes.
 * `đ` is not an accented `d` in Unicode, so it is replaced on its own.
 */
export function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

/**
 * Words with too little meaning to search on.
 *
 * Deliberately short. It exists to catch a query that says nothing, such as "cái đó" or "và
 * với", not to do stemming: dropping a word that turns out to matter would silently change which
 * SOP ranks first.
 */
const STOP_WORDS = new Set([
  "va",
  "voi",
  "cua",
  "cai",
  "do",
  "nay",
  "cho",
  "la",
  "thi",
  "de",
  "cac",
  "nhung",
  "mot",
  "the",
  "and",
  "the",
  "for",
  "of",
]);

/**
 * The words of a query worth searching on.
 *
 * A query left with nothing is what `sop_kb.retrieve` answers NEEDS_INPUT to: it cannot rank
 * documents by a question that asks nothing, and returning an arbitrary few would look like an
 * answer.
 */
export function searchTerms(query: string): string[] {
  const terms = normalizeText(query)
    .split(/[^\p{L}\p{N}]+/u)
    .filter((term) => term.length >= 2 && !STOP_WORDS.has(term));
  return [...new Set(terms)];
}

/** How many of `terms` appear anywhere in `haystack`, which is already normalised. */
export function termMatchCount(
  haystack: string,
  terms: readonly string[],
): number {
  return terms.filter((term) => haystack.includes(term)).length;
}
