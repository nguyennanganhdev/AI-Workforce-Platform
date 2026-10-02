import { describe, expect, test } from "bun:test";
import {
  cosineRule,
  type EvalCase,
  evaluate,
  firstRelevantRank,
  leaks,
  lexicalRule,
  type Observation,
  type ObservedHit,
  sweepRejectionRules,
} from "../../src/knowledge/eval-metrics";

const hit = (overrides: Partial<ObservedHit> = {}): ObservedHit => ({
  rank: 1,
  title: "t",
  text: "",
  similarity: 0.5,
  keywordRank: 1,
  operator: "vinhomes",
  buildings: [],
  ...overrides,
});

const answer = (
  contains: string[],
  scope = "01-vinhomes/sapphire",
): EvalCase => ({
  id: "a",
  scope,
  query: "q",
  expect: "answer",
  contains,
});

describe("relevance", () => {
  test("matches any listed text, ignoring case and spacing", () => {
    const observation: Observation = {
      case: answer(["An ninh cao tầng"]),
      hits: [
        hit({ rank: 1, text: "Lễ tân." }),
        hit({ rank: 2, text: "an ninh  CAO tầng: 0858" }),
      ],
    };
    expect(firstRelevantRank(observation)).toBe(2);
  });
});

describe("leaks", () => {
  test("the other operator leaks, the urban area does not", () => {
    const c = answer([], "01-vinhomes/sapphire");
    expect(leaks(c, hit({ operator: "masterise" }))).toBe(true);
    expect(leaks(c, hit({ operator: "do_thi" }))).toBe(false);
  });

  test("a building file leaks unless it is the resident's own building", () => {
    expect(
      leaks(
        answer([], "01-vinhomes/sapphire/sapphire-1/S1.01"),
        hit({ buildings: ["S1.01"] }),
      ),
    ).toBe(false);
    expect(
      leaks(
        answer([], "01-vinhomes/sapphire/sapphire-1/S1.02"),
        hit({ buildings: ["S1.01"] }),
      ),
    ).toBe(true);
    expect(
      leaks(
        answer([], "01-vinhomes/sapphire/sapphire-1"),
        hit({ buildings: ["S1.01"] }),
      ),
    ).toBe(true);
  });
});

describe("evaluate", () => {
  const observations: Observation[] = [
    {
      case: answer(["x"]),
      hits: [hit({ rank: 1, text: "x", similarity: 0.6 })],
    },
    {
      case: answer(["y"]),
      hits: [
        hit({ rank: 1, text: "n" }),
        hit({ rank: 2, text: "y", similarity: 0.4 }),
      ],
    },
    {
      case: answer(["z"]),
      hits: [hit({ rank: 1, text: "n", similarity: 0.3 })],
    },
    {
      case: { id: "o", scope: "00-do-thi", query: "q", expect: "off_topic" },
      hits: [hit({ similarity: 0.35, keywordRank: null })],
    },
    {
      case: {
        id: "d",
        scope: "01-vinhomes/zenpark",
        query: "q",
        expect: "no_data",
        contains: ["Chưa thu"],
      },
      hits: [hit({ text: "Chưa thu được" })],
    },
  ];

  test("recall, MRR and the counts of each kind", () => {
    const summary = evaluate(observations, cosineRule(0.2), 5);
    expect(summary.answer.cases).toBe(3);
    expect(summary.answer.recallAt1).toBeCloseTo(1 / 3);
    expect(summary.answer.recallAtK).toBeCloseTo(2 / 3);
    expect(summary.answer.mrr).toBeCloseTo((1 + 0.5 + 0) / 3);
    expect(summary.noData).toEqual({ cases: 1, handled: 1 });
    expect(summary.offTopic).toEqual({ cases: 1, rejected: 0 });
  });

  test("a refused answerable question counts as a miss and as a false rejection", () => {
    // Only the third question's best passage (0.3) falls under 0.45.
    const summary = evaluate(observations, cosineRule(0.45), 5);
    expect(summary.answer.falseRejections).toBe(1);
    expect(summary.answer.recallAtK).toBeCloseTo(2 / 3);
    expect(summary.offTopic.rejected).toBe(1);
  });

  test("the lexical rule refuses weak matches only when no keyword matched", () => {
    const summary = evaluate(observations, lexicalRule(0.2, 0.45), 5);
    expect(summary.offTopic.rejected).toBe(1);
    expect(summary.answer.falseRejections).toBe(0);
  });

  test("the sweep ranks a rule that separates the two kinds first", () => {
    const [best] = sweepRejectionRules(observations, 5);
    expect(best?.offTopicRejected).toBe(1);
    expect(best?.falseRejections).toBe(0);
  });
});
