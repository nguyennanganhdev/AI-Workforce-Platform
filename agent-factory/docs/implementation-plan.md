# Standalone Agent Factory — user-authorized scope, 2026-10-01

## Current decision — Generated Skill replaces Skill selection, 2026-10-02

The user requests that construction stop selecting a skill from the catalogue and
instead generate the skill itself. Tools stay catalogue-only. This supersedes, for
new artifacts, the P0 plan's "Skills" paragraph (section 6), the `skill_instruction`
fulfillment, `kind: "skill"` resources and the "intent is never part of AgentSpec"
note (section 25). Bounded repair, the two-call budget, exact tool resolution,
hashing and BE ownership of persistence/grants/readiness/runtime are unchanged.

**Audit facts this rests on (2026-10-02).**

- The runtime never reads skill instructions for a generated agent: it runs the
  stored `systemPrompt` (`server/src/copilot.ts::registeredAgentFromRow`). A granted
  skill only indexes tool narrowing. Dropping selection removes a required grant and
  nothing the runtime used.
- No RAG tool, endpoint or MCP contract exists in the repository (README scaffolds
  and `platform_knowledge_*` tables only). The Factory therefore invents no ref.
- A stored artifact is valid only when `systemPrompt === renderCorePrompt(spec)`.
  Changing the v1 renderer or schema in place would invalidate every stored agent.

**Decisions.**

| Topic | Decision |
|---|---|
| Artifact | New `schemaVersion: 2` / `compilerVersion: 2` spec. v1 keeps its exact schema and renderer and is read, never produced. No migration. |
| Skill | `generatedSkill {name, objective, procedure, toolUsageGuidance[{toolRef, whenToUse, purpose, guidance}], constraints, completionCriteria}` inside the spec. v1's top-level `procedure` and `acceptanceCriteria` move into it. Declarative text only. |
| Generation | Same single generation completion writes the skill; code resolves tools and then checks the skill against the resolved set. A separate skill call would raise the budget to three calls and is not taken. |
| Default (RAG) tool | User decision: BE names it per request in `catalogue.defaultToolRefs`; each ref must be in `catalogue.tools`. The Factory records them in `spec.defaultTools` and hardcodes no ref. None named: none attached, and `verification.warnings` carries `NO_DEFAULT_TOOL`. |
| RAG policy | User decision: a default tool is available, not required. It blocks readiness only when a requirement binds it, in which case it is also an ordinary entry of `spec.resources`. BE readiness reads `spec.resources`, so no BE change and no grant is created. |
| Intent | The reading (`normalizedGoal`, `taskType`, explicit/inferred requirements) is stored in the spec and rendered into the prompt. |
| Skill catalogue | `catalogue.skills` is still accepted on the wire and ignored unread, so the BE projection and `PluginStore` are untouched. `FactorySkill` types and the skill fingerprint stay for BE readiness of v1 artifacts. |

**Static skill checks (new, code-owned).** Schema (objective, non-empty procedure
and completion criteria); every `toolRef` is a resolved or default tool, once;
every resolved tool has guidance; no skill text names a catalogue ref outside that
set; no executable content; no secret-shaped value. Codes: `UNKNOWN_SKILL_TOOL`,
`SKILL_TOOL_UNGUIDED`, `SKILL_EXECUTABLE_CONTENT`, `SKILL_SECRET`. The same checks
run on a stored v2 artifact and on a construction response before BE may persist it.
The reviewer gains `INADEQUATE_SKILL` (the skill does not guide this request's work).
All five are repairable within the scope `generatedSkill`; a repair cannot add a tool.

**Change surface.** Production: `src/contracts.ts`, `spec.ts`, `service.ts`,
`verification.ts`, `client.ts` only. No `server/src`, `app/`, database or dependency
change. Tests/tooling: `tests/*`, `server/tests/agent-factory*.ts`,
`server/tests/tavily-factory.integration.test.ts`, `server/scripts/factory-*.ts`.
The frozen golden JSON is not edited; recorded drafts are upgraded by a fixture
wrapper, as was done for the intent block.

**Steps and gates (executed 2026-10-02, Bun 1.3.14).**

- [x] 1 Contracts: v2 schema, `generatedSkill`, v1 parse/render preserved.
      The frozen v1 artifact passes integrity, and so do all 10 generated agents stored in
      the local dev database (all `schemaVersion 1`, 7 with a skill resource), read-only.
- [x] 2 Generation prompt/output writes the skill; no catalogue skill is read.
- [x] 3 Tool/default-tool wiring: skill branch removed from resolution; `defaultToolRefs` attached.
- [x] 4 Compiler renders intent + skill into the v2 prompt; hash covers them.
- [x] 5 Verification: static skill checks, reviewer criterion, repair scope. Each new guard was
      disabled in turn and the suite failed each time.
- [x] 6 Integration: real loopback HTTP Factory -> v2 artifact -> BE persistence, readiness and
      runtime normalization on the dedicated test database
      (`server/tests/agent-factory-routes.test.ts`, `tavily-factory.integration.test.ts`).
- [~] 7 Behavioral check: one real `BuiltInAgent` turn of the generated Web Researcher, with the
      model scripted by LLMock. It shows the stored prompt carries the generated skill, the tool
      is offered only after its grant, and the call goes through `PluginStore.callTool`. It does
      **not** show what a real model does with the skill.

**Executed verification.**

| Check | Result |
|---|---|
| `bun run check` in `agent-factory/` (typecheck + 3 files) | 44 pass / 0 fail |
| Every suite referencing the Factory, 18 files, `TEST_DATABASE_URL=...openbot_test` | 394 pass / 0 fail, exit 0 |
| `tsc --noEmit` in `server/`, `app/`, root `tsconfig.json` | no errors |
| `scripts/check-architecture.mjs` | Architecture imports: OK |
| Biome format + lint on the touched files | clean |

Not executed: a construction against a real model with the new generation and review prompts
(it spends provider credit, so it waits for the user); the full `test:ci`; browser/UI flows.
Real-model quality of generated skills is therefore unmeasured.

**Deviations from the request as written.**

- The skill is written in the same generation completion as the requirements and then checked
  against the resolved tools, instead of being generated after resolution. A separate call would
  have made three model calls.
- "Every agent has RAG" holds only once BE names a default tool; none exists to name today.
- `server/src/plugins/store.ts::factoryCatalogue` (BE-owned) still reads the skill table, so BE's
  own catalogue read can still fail on an oversized skill registry. Not changed here.

**Known limits.** Free-text mentions of a tool that is in no catalogue cannot be
detected by code and are left to the reviewer. Skill specificity ("not generic") is
a reviewer judgement, not a deterministic check. The executable-content and secret
checks are pattern lists, not parsers.

## Earlier decision — Backend integration delegated, 2026-10-02

The user now requests detaching production Backend wiring and handing integration
to another team. This supersedes the active BE HTTP wiring described below.
Factory remains an authenticated standalone construction service with its existing
model configuration, contract, client and tests.

Authorized change surface: `server/src/index.ts` only for production detachment
(remove Factory construction/client imports, service construction, the final
`createApp` injection and Factory-only socket timeout); current documentation and
environment-example comments; mark the prior BE smoke script as unavailable until
the BE team reconnects. Add `docs/backend-integration-spec.md` and JSON examples.
Existing BE artifact integrity/readiness guards, stored data, adapter seams and
integration tests remain; no direct/in-process fallback is enabled. No Frontend,
grants, database migration, runtime redesign or new dependency.

- [x] Remove production HTTP construction wiring; `/api/agent-factory/*` unmounted.
- [x] Restart the current local BE and verify real HTTP 404 for create/read/recheck;
      Factory and BE health still return 200 and Factory authentication still rejects bad tokens.
- [x] Deliver a Vietnamese integration specification based on current code/DTOs,
      with auth, catalogue, integrity, persistence/readiness, limits/errors and acceptance tests.
- [x] Run module/core/BE-route/runtime regressions, typechecks and architecture checks.

The subsequent sections record historical delivery and verification, not an active
production BE integration. The BE team owns any future reconnection.

The user explicitly requested a root-level folder beside agent-report/agent-coordination and selected a separate HTTP service. This supersedes the in-process-only relocation in the Meta-Agent impact map section 24.8.

## Historical delivery status before detachment — 2026-10-02

**PASS for module isolation, BE HTTP integration, shared root environment and local real-model HTTP smoke.**
Full original P0 release acceptance remains governed by its open quality/browser gates.
This current section supersedes the historical split-only deferrals and separate-env setup below.
The active cross-module plan/map are in
[docs/plans/meta-agent-p0-implementation-plan.md](../../docs/plans/meta-agent-p0-implementation-plan.md)
and [docs/plans/meta-agent-file-impact-map.md](../../docs/plans/meta-agent-file-impact-map.md).

- [x] Root agent-factory/ module, standalone authenticated POST /v1/constructions, health endpoint.
- [x] Production BE calls Factory HTTP; validates and saves through existing idempotency/readiness guards.
- [x] BE and Factory start/dev read the single repository root .env (native --env-file=../.env).
- [x] Recorded 389-test HTTP/DB/legacy regression run; typechecks, architecture and BE Docker verification.
- [x] Separate shared-env start/dev smoke processes passed with only a parent fixture .env.
- [x] Configure/verify local environment service token, model API key/name/provider/URL; start Factory and BE.
      Live Web Researcher construction, persistence/readiness and outage evidence is in
      [HTTP verification](http-integration-verification.md#live-configuration-and-real-model-follow-up--2026-10-02).
- [ ] Real-model creation through UI and runtime smoke after the HTTP switch.
- [ ] Original mandatory P0 quality/browser/release acceptance closure.

Current local command: `rtk bun run --cwd agent-factory start` at repository root.
All service and model variables are configured in that root `.env`; no module `.env` is required.
A copied-out module may run with an explicitly supplied local env file.
Model keys/names are the explicit FACTORY_MODEL_* values, with no automatic substitution from BE keys.

See [HTTP verification](http-integration-verification.md) for executed commands and limits,
[split verification](verification.md) for historical 359-test evidence, and [README](../README.md)
for startup and contracts. Recorded checks are not live-model or browser acceptance.

## Initial split scope and verification (historical)

## Real HTTP/model configuration verification — authorized 2026-10-02

The user authorizes configuring the existing root environment, running the standalone
Factory with a real model, and verifying Backend HTTP persistence/readiness without
granting resources. Scope: `src/model.ts` provider/credential routing validation,
`tests/http.test.ts` regression coverage, `src/service.ts` request-only intent prompt
clarification after live evidence of catalogue method leakage, setup/evidence documentation, and a runnable
Backend smoke script if needed. No frontend, orchestration, validator relaxation,
provider fallback, dependency or migration changes.

- [x] Configure service bearer and explicit model/provider/endpoint/key in root `.env`;
      secrets are read from environment and never printed.
- [x] Reject recognized provider credentials sent to another provider before fetch.
- [x] Start Factory independently; verify health, absent/incorrect bearer rejection,
      and Web Researcher construction through Backend HTTP with the current catalogue.
- [x] Verify artifact integrity, database persistence, owner readiness and unchanged grants.
- [x] Run Factory/core/HTTP/Backend/resource/runtime regressions, typechecks and architecture.
- [x] Record executed live results and remaining post-split E2E gates.

## Boundary
Factory owns request + trusted catalogue -> verified AgentSpec, compiled prompt and report. It owns neither user authentication, grants, persistence, idempotent creation of stored agents nor runtime execution. These remain BE responsibilities. At the initial split, BE API/guards used relocated imports. The later BE HTTP integration below is complete and supersedes that intermediate in-process construction state.

## Change surface
- MOVE the three core files to agent-factory/src/{spec,verification,service}.ts and the shared DTO file to agent-factory/src/contracts.ts. Define its existing recursive JsonValue locally so the service is independent of deleted develop scaffolding.
- NEW package manifest, independent tsconfig, HTTP handler, model HTTP adapter, server entry, HTTP/model tests, environment example, Dockerfile and documentation in agent-factory/.
- MOVE core charter/README and fixture data into the module. Existing BE/UI/core tests remain in their owning applications with import/path updates only.
- MODIFY only import lines in current BE/UI consumers, fixture paths in golden evaluation/tests, and the architecture checker/test for the new module boundary. Do not merge develop or change BE stores, auth, grants, runtime or model transport behavior.
- No new runtime dependency beyond existing Zod; use Bun.serve and fetch. No database migration or root workspace/lockfile change.

## Steps / checks
1. [x] Relocate existing core/contracts; existing Factory unit tests and architecture/type checks pass.
2. [x] Add authenticated POST /v1/constructions plus GET /health, bounded inputs, injected completion, model/time limits and safe errors. Test auth, schema/catalogue, happy-path generation/review, repair limits, timeout/cancellation, provider protocol and error sanitization.
3. [x] Verify the module copied outside the repository can install, typecheck, test and start without server/app/shared. Verify legacy focused tests and document database prerequisites and current limitations.

## HTTP contract
POST /v1/constructions with service Bearer token, body {request:{name,role,description},catalogue:{tools,skills}}. Catalogue contains metadata and refs only, no credentials. Success is 200 with {spec,systemPrompt,specHash,intent,verification}; there is no persisted agent or ready verdict. BE supplies an actor-scoped catalogue, validates received integrity, saves using its own idempotency key and performs fresh readiness checks. Invalid request is 400, body overflow 413, construction refusal 422, model failure 503, deadline 504. No provider response/secret is exposed.

## Acceptance and limits
Core behavior stays unchanged. Module imports only itself, Zod and platform standard APIs. Existing P0 release acceptance remains blocked by its original evidence; offline tests are not real-model quality evidence. Database-backed legacy tests require a migrated dedicated TEST_DATABASE_URL. Docker and live-model checks are reported separately if unavailable. Safe rollback restores moved files and import lines from the external pre-change backup while retaining all BE generated-artifact/readiness guards.


## Initial split verification — 2026-10-02 (historical)

PASS for the standalone split. All 359 focused tests across 14 files passed under Bun 1.3.14, including temporary dedicated PostgreSQL/pgvector tests. Module installed/typechecked/tested outside the repo, Docker built and started with /health 200. See verification.md for executed commands and scope. This initial split did not wire BE to HTTP. The completed HTTP integration and shared-env work below supersede that limitation; original P0 real-model/browser release gates remain open.


## BE HTTP integration — authorized 2026-10-02

User requested completing the switch to HTTP. Supersedes the prior deferral of remote BE wiring.

Scope: add `agent-factory/src/client.ts` (native fetch, service bearer, bounded response, cancellation, no redirect/retry/fallback); reuse schemas in `src/spec.ts` to validate the received artifact against request/catalogue/hash/prompt; export client through `src/index.ts`. Modify only the constructor injection in `server/src/agents/factory.ts` and production composition in `server/src/index.ts`. Local construction stays available for existing offline tests/evaluation. Production always uses HTTP; absent configuration fails construction with a safe dependency error without disabling unrelated BE routes.

Configuration/docs: `.env.example`, `docs/configuration.md`, `agent-factory/README.md`. BE uses FACTORY_SERVICE_URL (origin/base URL, default http://127.0.0.1:4010) and FACTORY_SERVICE_TOKEN. Model configuration belongs to the standalone service. Existing auth, idempotency, persistence, fresh readiness and runtime checks stay BE-owned. BE retains outcome/creation audits; detailed model-stage observations stay inside Factory and are not fabricated at the client.

Change budget: one new production file, four modified production files inside the listed boundaries, no dependencies/migrations/new process beyond the already authorized Factory service. Tests: new module client tests plus HTTP-backed cases in existing BE route integration suite.

- [x] Implement client and validate success/error, request/catalogue binding, bounded bodies, cancellation/deadline, auth and no redirect. Run module/core tests and architecture check.
- [x] Wire BE constructor and production composition; test real loopback HTTP -> BE database persistence/replay/pending readiness/read/recheck and refusal without writes. Run relevant Factory, runtime, route, model and architecture regressions against dedicated temporary DB; typecheck.
- [x] Update setup docs and record actual commands/results/limitations in docs/http-integration-verification.md.

Rollback: restore only this task's edits from the external snapshot, preserving all pre-existing work. No merge, commit or developer DB changes. Live model credentials and browser/deployment release acceptance are separate from offline integration evidence.

Packaging follow-up in authorized HTTP integration: both `Dockerfile` and `server/Dockerfile` copy only server/shared today. Add `COPY agent-factory/src agent-factory/src` in their app-build/runtime stages so BE imports resolve in shipped images. No Compose topology change: the existing standalone service is configured by URL. Verify the BE image build/import when available and existing compose regression tests. This adds two packaging files to the scope.

Transport follow-up: use the existing per-request `server.timeout` pattern in `server/src/index.ts::fetch` for `/api/agent-factory/` (120 seconds), so the 90-second construction deadline can return a response without Bun closing an idle socket first. Other routes retain their timeouts.

Docker dependency evidence: the root install isolates Zod under server/node_modules; copying Factory sources alone does not resolve it. Install the module with its own frozen lockfile and --production --ignore-scripts in both deps stages, then copy its node_modules into runtime. No new dependency or root lockfile edit.


## Shared root environment — authorized 2026-10-02

User requests BE and Factory use the repository root `.env`. Scope: change package `start`/`dev` to Bun's native `--env-file=../.env`; update root/module environment examples and current setup/configuration docs. No custom environment loader, provider fallback or credential migration. Existing local `.env` values remain untouched. Copied-out modules can explicitly run `bun --env-file=.env src/server.ts`; Docker consumes injected environment as before. Verify actual package start in an isolated temporary folder using only parent `.env`, health and authenticated HTTP without a live model.

Verification PASS: Bun 1.3.14 package `start` and `dev` were each launched from an isolated temporary project with only parent `.env` (no module `.env`, no inherited FACTORY variables). Both started, answered /health 200 and accepted the parent-file bearer before refusing an invalid construction body with 400. No live model call. Temporary processes/files removed. `rtk bun run check:architecture` and `rtk git diff --check` exit 0. Modified package.json, root/module .env.example, README, configuration docs and this plan; no new runtime symbol/dependency. Local root `.env` already has FACTORY_MODEL but lacks FACTORY_SERVICE_TOKEN and FACTORY_MODEL_API_KEY; no real credentials were changed. No deviation from the shared-file scope.
