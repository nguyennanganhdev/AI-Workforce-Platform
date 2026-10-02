/**
 * Scoring for the retrieval evaluation (Q06). Pure functions over what retrieval returned, so the
 * metrics are tested without a database or a model, and a rejection rule can be swept over one set
 * of observations without searching again.
 */

export type EvalExpectation =
  /** The knowledge base answers it; `contains` names text a correct passage carries. */
  | "answer"
  /** The data is known to be missing; a passage saying so, or a refusal, is correct. */
  | "no_data"
  /** Nothing in the knowledge base should be offered; only a refusal is correct. */
  | "off_topic"
  /** A question built to pull in another operator's or building's data; only leakage is scored. */
  | "trap";

export type EvalCase = {
  id: string;
  /** The folder the resident lives under, as in the CLI's `/scope`. */
  scope: string;
  query: string;
  expect: EvalExpectation;
  /** Any one of these, case-insensitive, in a passage makes it relevant. */
  contains?: string[];
  tags?: string[];
};

export type EvalDataset = { version: string; cases: EvalCase[] };

export type ObservedHit = {
  rank: number;
  title: string;
  text: string;
  similarity: number;
  keywordRank: number | null;
  operator: string;
  buildings: string[];
};

export type Observation = { case: EvalCase; hits: ObservedHit[] };

const BUILDING = /^(?:[SR]\d\.\d{2}|[PMH]\d)$/;

function normalize(text: string): string {
  return text.normalize("NFC").toLowerCase().replace(/\s+/g, " ");
}

export function isRelevant(evalCase: EvalCase, hit: ObservedHit): boolean {
  const haystack = normalize(`${hit.title}\n${hit.text}`);
  return (evalCase.contains ?? []).some((needle) =>
    haystack.includes(normalize(needle)),
  );
}

/** 1-based rank of the first relevant passage, or null when none is in the hits. */
export function firstRelevantRank(observation: Observation): number | null {
  for (const hit of observation.hits) {
    if (isRelevant(observation.case, hit)) return hit.rank;
  }
  return null;
}

/** The operator a resident of `scope` belongs to; null for the urban area, which sees everything. */
export function operatorOf(scope: string): string | null {
  const root = scope.split("/")[0];
  if (root === "02-masterise") return "masterise";
  if (root === "01-vinhomes" || root === "04-thap-tang") return "vinhomes";
  return null;
}

/**
 * A hit the resident should never have been shown: the other operator's data, or a building file
 * for a building that is not theirs (a resident whose scope is not a building sees no building
 * file at all).
 */
export function leaks(evalCase: EvalCase, hit: ObservedHit): boolean {
  const operator = operatorOf(evalCase.scope);
  if (operator && hit.operator !== "do_thi" && hit.operator !== operator) {
    return true;
  }
  if (hit.buildings.length === 0) return false;
  const last = evalCase.scope.split("/").at(-1) ?? "";
  return !BUILDING.test(last) || !hit.buildings.includes(last);
}

export type RejectionRule = {
  name: string;
  reject: (observation: Observation) => boolean;
};

function topSimilarity(observation: Observation): number {
  return Math.max(0, ...observation.hits.map((hit) => hit.similarity));
}

function anyKeyword(observation: Observation): boolean {
  return observation.hits.some((hit) => hit.keywordRank !== null);
}

/** Refuse when the best passage is less similar than `threshold`. What retrieval does today. */
export function cosineRule(threshold: number): RejectionRule {
  return {
    name: `cosine < ${threshold.toFixed(2)}`,
    reject: (o) => o.hits.length === 0 || topSimilarity(o) < threshold,
  };
}

/**
 * Refuse below `floor` regardless, and below `threshold` when no passage shares a single keyword
 * with the question: weak meaning with no lexical overlap is the signature of an off-topic question.
 */
export function lexicalRule(floor: number, threshold: number): RejectionRule {
  return {
    name: `cosine < ${floor.toFixed(2)} or (no keyword and cosine < ${threshold.toFixed(2)})`,
    reject: (o) =>
      o.hits.length === 0 ||
      topSimilarity(o) < floor ||
      (!anyKeyword(o) && topSimilarity(o) < threshold),
  };
}

export type CaseResult = {
  id: string;
  expect: EvalExpectation;
  query: string;
  scope: string;
  firstRelevantRank: number | null;
  rejected: boolean;
  topSimilarity: number;
  anyKeyword: boolean;
  leakedHits: number;
  topTitle: string | null;
  tags: string[];
};

export type EvalSummary = {
  rule: string;
  k: number;
  answer: {
    cases: number;
    recallAt1: number;
    recallAt3: number;
    recallAtK: number;
    mrr: number;
    /** Answerable questions the rule refused: the cost of a strict rule. */
    falseRejections: number;
  };
  noData: { cases: number; handled: number };
  offTopic: { cases: number; rejected: number };
  leakage: { hits: number; totalHits: number; casesWithLeak: number };
  byTag: Record<string, { cases: number; recallAtK: number }>;
  results: CaseResult[];
};

function ratio(part: number, whole: number): number {
  return whole === 0 ? 0 : part / whole;
}

export function evaluate(
  observations: Observation[],
  rule: RejectionRule,
  k: number,
): EvalSummary {
  const results: CaseResult[] = observations.map((o) => {
    const hits = o.hits.filter((hit) => hit.rank <= k);
    const view = { ...o, hits };
    return {
      id: o.case.id,
      expect: o.case.expect,
      query: o.case.query,
      scope: o.case.scope,
      firstRelevantRank: firstRelevantRank(view),
      rejected: rule.reject(view),
      topSimilarity: topSimilarity(view),
      anyKeyword: anyKeyword(view),
      leakedHits: hits.filter((hit) => leaks(o.case, hit)).length,
      topTitle: hits[0]?.title ?? null,
      tags: o.case.tags ?? [],
    };
  });

  const answers = results.filter((r) => r.expect === "answer");
  // A refused answerable question found nothing for the resident, whatever retrieval ranked.
  const servedRank = (r: CaseResult) =>
    r.rejected ? null : r.firstRelevantRank;
  const within = (r: CaseResult, n: number) => {
    const rank = servedRank(r);
    return rank !== null && rank <= n;
  };

  const byTag: EvalSummary["byTag"] = {};
  for (const result of answers) {
    for (const tag of result.tags) {
      byTag[tag] ??= { cases: 0, recallAtK: 0 };
      byTag[tag].cases++;
      if (within(result, k)) byTag[tag].recallAtK++;
    }
  }
  for (const entry of Object.values(byTag)) {
    entry.recallAtK = ratio(entry.recallAtK, entry.cases);
  }

  const noData = results.filter((r) => r.expect === "no_data");
  const offTopic = results.filter((r) => r.expect === "off_topic");
  return {
    rule: rule.name,
    k,
    answer: {
      cases: answers.length,
      recallAt1: ratio(
        answers.filter((r) => within(r, 1)).length,
        answers.length,
      ),
      recallAt3: ratio(
        answers.filter((r) => within(r, 3)).length,
        answers.length,
      ),
      recallAtK: ratio(
        answers.filter((r) => within(r, k)).length,
        answers.length,
      ),
      mrr: ratio(
        answers.reduce((sum, r) => {
          const rank = servedRank(r);
          return sum + (rank === null ? 0 : 1 / rank);
        }, 0),
        answers.length,
      ),
      falseRejections: answers.filter((r) => r.rejected).length,
    },
    noData: {
      cases: noData.length,
      handled: noData.filter((r) => r.rejected || r.firstRelevantRank !== null)
        .length,
    },
    offTopic: {
      cases: offTopic.length,
      rejected: offTopic.filter((r) => r.rejected).length,
    },
    leakage: {
      hits: results.reduce((sum, r) => sum + r.leakedHits, 0),
      totalHits: observations.reduce(
        (sum, o) => sum + o.hits.filter((hit) => hit.rank <= k).length,
        0,
      ),
      casesWithLeak: results.filter((r) => r.leakedHits > 0).length,
    },
    byTag,
    results,
  };
}

/**
 * Try a grid of rejection rules and rank them by off-topic questions refused minus answerable ones
 * refused, ties going to the rule that refuses fewer answerable questions. A tuning aid: the
 * winner on one small dataset is a candidate to confirm, not a setting to ship blindly.
 */
export function sweepRejectionRules(
  observations: Observation[],
  k: number,
): { rule: string; offTopicRejected: number; falseRejections: number }[] {
  const steps = (from: number, to: number) =>
    Array.from(
      { length: Math.round((to - from) / 0.01) + 1 },
      (_, i) => Math.round((from + i * 0.01) * 100) / 100,
    );
  const rules: RejectionRule[] = [
    ...steps(0.2, 0.55).map(cosineRule),
    ...steps(0.2, 0.35).flatMap((floor) =>
      steps(floor + 0.01, 0.6).map((threshold) =>
        lexicalRule(floor, threshold),
      ),
    ),
  ];
  return rules
    .map((rule) => {
      const summary = evaluate(observations, rule, k);
      return {
        rule: rule.name,
        offTopicRejected: summary.offTopic.rejected,
        falseRejections: summary.answer.falseRejections,
      };
    })
    .sort(
      (a, b) =>
        b.offTopicRejected -
          b.falseRejections -
          (a.offTopicRejected - a.falseRejections) ||
        a.falseRejections - b.falseRejections,
    );
}
