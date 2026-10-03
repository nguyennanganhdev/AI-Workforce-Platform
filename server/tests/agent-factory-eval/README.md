# Isolated Backend/Factory evaluation

```sh
rtk bunx bun@1.3.14 test server/tests/agent-factory-eval/scoring.test.ts
rtk bunx bun@1.3.14 --env-file=.env server/scripts/factory-eval.ts
```

The second command makes paid calls using the explicitly configured Factory model
and the existing tenant/BOT runtime model and OpenAI credential. It returns nonzero
when any case fails or infrastructure is blocked; evidence still survives in
`.logs/agent-factory-eval-<timestamp>/`. No fallback model or selective rerun.
It waits 20 seconds between construction cases to reduce low-TPM rate limiting.

The script calls the retained Backend construction service over real loopback HTTP
to Factory's authenticated handler, then its normal response-integrity client. It
runs generated artifacts through the Backend's integrity/readiness checks and
existing headless BuiltInAgent. Synthetic metadata is a supplied catalogue, not a
registry; default RAG is attached to every returned spec. Tool execution uses only
injected test access facts and fixture responses, rechecking grants at execution.
Missing-grant readiness and stale-offer revocation are negative cases. No DB,
production data, FE, DAG, real business tool, route or env-mode branch is involved.

Temporary Factory/proxy servers bind loopback on random ports and stop in `finally`.
The proxy observes actual runtime model responses; it adds no agent instructions.
It supports the installed runtime's Responses streaming protocol and Chat Completions,
records token usage when supplied, and removes provider diagnostics from failed replies.
Normal application startup never imports these files. Production source/config
hashes before/after and detached composition checks are in `cleanup.json`.

Scoring uses deterministic tools/ref/schema/URL/fixture facts and multilingual
clause patterns, not whole-prose snapshots. Skill alignment and goal/grounding
checks are bounded evidence. Factory's own semantic review is reported separately;
there is no independent semantic judge. Reports do not establish correctness of
every possible natural-language claim. Runtime token usage is null when the stream
does not provide it; totals are never estimated. All refused constructions stay in
the recall/attachment/skill denominators. Ambiguous cases have no expected artifact.

The current Factory forbids arguments sourced from tool results (unknown output
schemas in P0). Multi-tool cases therefore supply record IDs and topics as input;
this evaluation does not claim support for data-dependent tool chains.

Keep this directory and the script for future runs. Do not mount the harness in
production. Dedicated-DB regressions still require `TEST_DATABASE_URL` and the
existing `server/tests/support/database.ts` safeguards.
