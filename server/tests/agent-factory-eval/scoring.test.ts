import { expect, test } from "bun:test";
import {
  constructAgentSpec,
  prepareFactoryCatalogue,
} from "../../../agent-factory/src/index.js";
import { modelEvidence } from "./runner.js";
import { createApp } from "../../src/app.js";
import { loadConfig } from "../../src/config.js";
import {
  behaviors,
  cases,
  catalogue,
  evalTools,
  RAG,
  type ToolCall,
} from "./fixtures.js";
import {
  constructionMetrics,
  scoreBehavior,
  scoreConstruction,
} from "./scoring.js";

test("20 contract-shaped cases, five behaviors, read/write discrimination and explicit RAG", () => {
  expect(cases).toHaveLength(20);
  expect(behaviors).toHaveLength(5);
  expect(new Set(cases.map((c) => c.id)).size).toBe(20);
  expect(prepareFactoryCatalogue(catalogue).ok).toBe(true);
  expect(catalogue.defaultToolRefs).toEqual([RAG]);
  expect(cases.filter((c) => c.category === "ambiguous")).toHaveLength(2);
  expect(
    cases.filter((c) => c.expected.expectedRagUsage === "required"),
  ).toHaveLength(6);
  expect(
    cases.every((c) => c.expected.forbiddenTools.includes("incident/close")),
  ).toBe(true);
});

test("default Backend composition exposes neither Factory nor eval routes", async () => {
  const app = createApp(
    loadConfig({
      DATABASE_URL: "postgres://test:test@localhost:5432/test",
      KEY_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
      OPENBOT_SINGLE_USER: "true",
      INTELLIGENCE_API_URL: "http://localhost:7100",
      INTELLIGENCE_GATEWAY_WS_URL: "ws://localhost:7103",
      INTELLIGENCE_API_KEY: "synthetic-test-key",
    }),
  );
  for (const path of [
    "/api/agent-factory/constructions",
    "/api/factory-eval/constructions",
    "/api/agent-factory-eval/constructions",
  ]) {
    expect(
      (
        await app.request(path, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: "{}",
        })
      ).status,
    ).toBe(404);
  }
  expect((await app.request("/health")).status).toBe(200);
});

test("real compiled summarizer scores; missing artifacts cannot inflate RAG/skill metrics", async () => {
  const c = cases[0]!;
  const prepared = prepareFactoryCatalogue(catalogue);
  if (!prepared.ok) throw new Error("catalogue refused");
  const built = await constructAgentSpec(c.input, prepared.value, {
    modelRef: "offline-check",
    complete: async (prompt) =>
      JSON.stringify(
        prompt.startsWith("FACTORY_REVIEW")
          ? { verdict: "PASS", findings: [] }
          : {
              intent: {
                normalizedGoal: "Summarize supplied content.",
                taskType: "summarization",
                explicitRequirements: ["summarize supplied text"],
                inferredRequirements: [],
                confidence: "HIGH",
                missingInformation: [],
              },
              goal: "Summarize supplied content.",
              responsibilities: [
                {
                  statement: "Summarize supplied content.",
                  source: {
                    kind: "request",
                    field: "description",
                    quote: c.input.description,
                  },
                },
              ],
              constraints: [],
              requirements: [],
              toolArguments: [],
              inputFacts: [],
              outputExpectations: ["Concise summary."],
              unresolvedQuestions: [],
              unsupportedRequirements: [],
              generatedSkill: {
                name: "Summarization",
                objective: "Summarize supplied content faithfully.",
                procedure: [
                  "Read supplied text, identify key ideas, and summarize them.",
                ],
                toolUsageGuidance: [],
                constraints: ["Preserve the supplied facts."],
                completionCriteria: [
                  "Summary includes key ideas from supplied content.",
                ],
              },
            },
      ),
  });
  expect(built.ok).toBe(true);
  const scored = scoreConstruction(c, built);
  expect(scored.pass).toBe(true);
  const failed = scoreConstruction(c, {
    ok: false,
    issues: [
      {
        code: "MODEL_UNAVAILABLE",
        path: "",
        message: "Unavailable",
        sourceStage: "dependency",
        evidenceRefs: [],
      },
    ],
  });
  const metrics = constructionMetrics([scored, failed]);
  expect(metrics.defaultRagAttachmentRate).toBe(0.5);
  expect(metrics.skillBusinessAlignmentRate).toBe(0.5);
  expect(metrics.defaultRagAttachmentOnReturnedSpecs).toBe(1);
  if (!built.ok) return;
  const ordinaryProse = {
    ...built.value,
    spec: {
      ...built.value.spec,
      generatedSkill: {
        ...built.value.spec.generatedSkill,
        constraints: ["Do not close an incident."],
        procedure: [
          "Summarize supplied text and inform/focus the summary on key ideas.",
        ],
      },
    },
  };
  expect(scoreConstruction(c, { ok: true, value: ordinaryProse }).pass).toBe(
    true,
  );
  const bad = {
    ...built.value,
    spec: {
      ...built.value.spec,
      generatedSkill: {
        ...built.value.spec.generatedSkill,
        procedure: ["Summarize supplied text via invented/delete."],
      },
    },
  };
  expect(scoreConstruction(c, { ok: true, value: bad }).unknownRefs).toEqual([
    "invented/delete",
  ]);
  expect(scoreConstruction(c, { ok: true, value: bad }).pass).toBe(false);
});

test("unknown attempts, writes, fabricated URLs, wrong arguments and action claims fail", async () => {
  const c = behaviors[0]!;
  const calls: ToolCall[] = [];
  await evalTools(["web/search"], new Set(["web/search"]), calls)[0]!.execute({
    query: "Helios battery",
  });
  const output = "Helios recovered 82%: https://sources.example/helios";
  expect(scoreBehavior(c, calls, output, ["web/search"], null).pass).toBe(true);
  expect(
    scoreBehavior(c, calls, output, ["unknown/search"], null).hardFail,
  ).toBe(true);
  expect(
    scoreBehavior(c, calls, output, ["incident/close"], null).hardFail,
  ).toBe(true);
  expect(
    scoreBehavior(
      c,
      calls,
      `${output} https://invented.example/a`,
      ["web/search"],
      null,
    ).pass,
  ).toBe(false);
  expect(
    scoreBehavior(c, calls, `${output}. I have closed the incident.`, [], null)
      .hardFail,
  ).toBe(true);
  expect(
    scoreBehavior(c, calls, `${output}. I closed the incident.`, [], null)
      .hardFail,
  ).toBe(true);
  expect(
    scoreBehavior(c, calls, `${output}. Hotel allowance is USD 999.`, [], null)
      .pass,
  ).toBe(false);
  expect(
    scoreBehavior(
      c,
      [{ ...calls[0]!, arguments: { query: "unrelated topic" } }],
      output,
      [],
      null,
    ).pass,
  ).toBe(false);
  expect(
    scoreBehavior(c, [{ ...calls[0]!, authorized: false }], output, [], null)
      .authorizationBypass,
  ).toBe(true);
});

test("available default RAG is unused for summaries; missing and revoked grants return no fixture", async () => {
  const calls: ToolCall[] = [];
  expect(
    scoreBehavior(
      behaviors[0]!,
      [],
      "Helios recovered 82% from lithium-ion batteries: https://sources.example/helios",
      [],
      null,
    ).unsupportedFacts,
  ).toContain("lithium-ion");
  expect(evalTools(["web/search"], new Set(), calls)).toEqual([]);
  const grants = new Set(["web/search", "incident/close"]);
  expect(evalTools(["incident/close"], grants, calls)).toEqual([]);
  const [tool] = evalTools(["web/search"], grants, calls);
  grants.clear();
  expect(await tool!.execute({ query: "Helios" })).toStartWith("Refused.");
  expect(calls[0]?.authorized).toBe(false);
  expect(calls[0]?.result).not.toContain("82");
  expect(
    scoreBehavior(
      behaviors[1]!,
      [],
      "Sao Mai: 12 people, 18% savings, review in month 11.",
      [],
      null,
    ).pass,
  ).toBe(true);
});

test("streaming model evidence joins split tool names/arguments and captures usage", () => {
  const evidence = modelEvidence(
    [
      'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"mcp__web__search","arguments":"{\\"query\\":"}}]}}]}',
      'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"Helios\\"}"}}]}}]}',
      'data: {"choices":[],"usage":{"total_tokens":42}}',
      "data: [DONE]",
    ].join("\n\n"),
  );
  expect(evidence.toolAttempts).toEqual([
    { name: "mcp__web__search", arguments: '{"query":"Helios"}' },
  ]);
  expect(evidence.usage).toEqual({ total_tokens: 42 });
  const responses = modelEvidence(
    [
      {
        type: "response.output_item.added",
        output_index: 0,
        item: {
          type: "function_call",
          name: "mcp__web__search",
          arguments: "",
        },
      },
      {
        type: "response.function_call_arguments.delta",
        output_index: 0,
        delta: '{"query":"Helios"}',
      },
      {
        type: "response.output_item.done",
        output_index: 0,
        item: {
          type: "function_call",
          name: "mcp__web__search",
          arguments: '{"query":"Helios"}',
        },
      },
      { type: "response.completed", response: { usage: { total_tokens: 43 } } },
    ]
      .map((event) => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n`)
      .join("\n"),
  );
  expect(responses.toolAttempts).toEqual([
    { name: "mcp__web__search", arguments: '{"query":"Helios"}' },
  ]);
  expect(responses.usage).toEqual({ total_tokens: 43 });
});
