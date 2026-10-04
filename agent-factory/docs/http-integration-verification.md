# BE → standalone Agent Factory HTTP — 2026-10-02

**Current decision:** The user subsequently requested removing production BE wiring
and delegating integration to the BE team. The integration/live-model results below
are historical evidence. They do not describe the current production connection.
See [integration specification](backend-integration-spec.md) and the detachment
verification appended at the end of this document.

Status: **PASS for BE HTTP integration**. Production wiring, focused regressions and BE Docker build passed.

## Result and ownership

Production `server/src/index.ts` injects `createFactoryClient` into the existing `createAgentFactoryService`. The same authenticated UI/BE API now builds through `POST /v1/constructions`. BE continues to read an actor-scoped catalogue, own idempotency/persistence/audit, check fresh resource fingerprints and readiness, and guard runtime execution. A missing token or unavailable service returns 503 for construction without falling back to local model calls. Existing read/recheck/runtime do not depend on Factory being online. Local core injection remains available for offline tests and the quality evaluator.

## Files / symbols

Created:
- `agent-factory/src/client.ts`: `createFactoryClient`, bearer-authenticated fetch with 90-second maximum deadline, caller cancellation, 1 MiB response limit, no redirects/retries, sanitized dependency errors.
- `agent-factory/tests/client.test.ts`: six runnable checks for HTTP/auth, catalogue projection, response integrity/request/resource binding, structured refusal, bounded deadlines/cancellation and redirect secret protection.
- This verification report.

Modified:
- `agent-factory/src/spec.ts`: export existing issue schema for reuse; `parseFactoryConstructionResponse` reuses existing spec/intent/verification schemas, validates request identity, hash/prompt, PASS review and catalogue fingerprints.
- `agent-factory/src/index.ts`: public HTTP client export.
- `server/src/agents/factory.ts::createAgentFactoryService`: constructor injection at the existing catalogue/construction boundary; persistence/access code unchanged.
- `server/src/index.ts`: replace production completer with HTTP client using `FACTORY_SERVICE_URL`/`FACTORY_SERVICE_TOKEN`; apply existing per-request socket timeout pattern (120 seconds) to Factory routes, allowing their 90-second construction deadline to complete.
- `server/tests/agent-factory-routes.test.ts`: three real-loopback HTTP + dedicated-DB cases covering authenticated persisted creation, replay/conflict/read/recheck, pending resources until BE observes owner grant, and failure without writes/fallback.
- `.env.example`, `docs/configuration.md`, `agent-factory/README.md`: setup and ownership instructions.
- `Dockerfile`, `server/Dockerfile`: five added lines each to install the independent module's production dependency with its frozen lockfile and copy module sources/dependency into the BE build/runtime images.
- `agent-factory/docs/implementation-plan.md` and the two local `docs/plans/meta-agent-*` plan/map files: explicit authorized scope addenda.

No root dependency/lockfile, database schema/migration, UI, grant, runtime or routing API changes.

## Executed validation

- Initial module/core/architecture run: 92 PASS, 0 FAIL; module typecheck PASS.
- Focused existing BE route suite plus new HTTP cases: 18 PASS, 0 FAIL, 195 assertions.
- Full focused regression run with Bun 1.3.14: **389 PASS, 0 FAIL, 3,576 assertions across 17 files**, 22.73 seconds, exit 0.
- `rtk bun run typecheck`: app/server/worker PASS; server typecheck repeated after per-request socket change, PASS.
- `rtk bun run typecheck:workforce`, `rtk bun run check:architecture`: PASS.
- Scoped Biome format/lint with `--error-on-warnings`: PASS.
- `rtk git diff --check`: PASS.

Full regression command (dedicated test URL supplied explicitly):

```sh
rtk env TEST_DATABASE_URL=<temporary-dedicated-test-url> bunx bun@1.3.14 test \
  agent-factory/tests \
  server/tests/agent-factory.test.ts \
  server/tests/agent-factory-golden.test.ts \
  server/tests/model-providers.test.ts \
  server/tests/copilot.test.ts \
  app/tests/agent-factory-ui.test.tsx \
  tests/architecture.test.mjs \
  server/tests/agent-factory.integration.test.ts \
  server/tests/agent-factory-routes.test.ts \
  server/tests/agent-factory-runtime.integration.test.ts \
  server/tests/agent-profile-store.integration.test.ts \
  server/tests/runtime-agents.integration.test.ts \
  server/tests/tavily-factory.integration.test.ts \
  server/tests/agent-routes.test.ts \
  tests/compose.test.ts tests/app.test.ts
```

Temporary container `factory-http-regression` used pgvector/pgvector:pg17 with a dedicated `factory_test` database, enabled vector, and applied existing migrations using `bunx bun@1.3.14 x drizzle-kit migrate --config=drizzle.config.ts` with an explicit DATABASE_URL. Container was stopped/auto-removed after checks. The application database was not used.

Two checks initially failed and were corrected: a fixture sourceStage needed a literal type; the new integration assertion expected 422 for corrupt artifacts, but the existing BE contract is 409 ARTIFACT_INVALID. Final results above are the passing reruns. Lint also caught unsafe optional chaining in a new test assertion, corrected without production changes.

## Scope adjustments and limits

- Docker packaging was added after inspection showed missing module sources and isolated Zod resolution. Both Dockerfiles now install/copy the module's existing dependency. No extra package was introduced.
- BE records creation/outcome audits across HTTP. Individual generate/review/repair timings are internal to Factory and are not fabricated or transmitted by the client.
- Model replies are offline fixtures; real HTTP and real database storage were exercised. No paid live-model call, browser E2E or deployed environment acceptance was performed. This evidence covers the HTTP integration, not the prior P0 release gates.
- `.env` credentials were not created or changed. Current setup (updated after the shared-env change): configure FACTORY_SERVICE_TOKEN and FACTORY_MODEL_* in the repository root `.env`, shared by BE and Factory; start Factory and restart BE. Setup is documented in README.
- No pull/merge/commit/push; existing develop reconciliation remains separate.
- Pre-task copies of touched files: `/Users/phaihoang/Documents/Codex/factory-http-backup-20261002-002026`. Diff against these copies confirms BE code changes are limited to the constructor boundary, production wiring and Factory socket timeout.


## Packaging evidence

`rtk docker build -f server/Dockerfile -t factory-http-be:verified .` completed with exit 0, including the Vite application build and isolated Factory dependency install. The first earlier build (`factory-http-be:check`) was intentionally canceled after the missing isolated dependency was identified, then replaced by this corrected full build. Image retained locally; no deployment was performed.

The root all-in-one `Dockerfile` received the same five-line source/dependency change, and existing Compose/Dockerfile regression tests passed. Its full Chromium/s6 image was not rebuilt. The actual full-image build above verifies the dedicated BE packaging used by the repository's migration service.

Runtime smoke: `rtk docker run --rm factory-http-be:verified bun -e '<import BE shell and Factory client; construct with missing token>'` exited 0. Both modules/dependencies resolved inside the finished image; missing service authentication returned the safe MODEL_UNAVAILABLE result. The temporary container was removed automatically.

`agent-factory/docs/verification.md` also now links this follow-up so its historical in-process limitation is not mistaken for current behavior. Final `git diff --check` exited 0; the real Git index remained empty. No required code/integration checks remain blocked. Running with a real model still requires the documented local service configuration.

## Live configuration and real-model follow-up — 2026-10-02

Status: **PASS for local real HTTP/model configuration and construction smoke.**
This follow-up supersedes the earlier missing-credentials/no-live-call limitation.
It is not full P0 quality, browser or runtime E2E acceptance.

### Current configuration and processes

The root `.env` now explicitly configures `FACTORY_SERVICE_URL`,
`FACTORY_SERVICE_TOKEN`, `FACTORY_MODEL_PROVIDER`, `FACTORY_MODEL_API_URL`,
`FACTORY_MODEL_API_KEY` and `FACTORY_MODEL`. The private service bearer was
generated locally; the model credential was read from the existing OpenAI
environment credential and assigned explicitly to Factory. No secret was printed,
committed, included in construction bodies/catalogue/specs/evidence or used as a code constant.
The private environment stays ignored and mode 0600. There is no runtime fallback
from Factory variables to Backend model variables.

- Provider: `openai`; model: `gpt-4.1`.
- Model endpoint: `https://api.openai.com/v1/chat/completions`.
- Authenticated OpenAI model lookup returned 200 with the exact configured model.
- Factory is a standalone Bun 1.3.14 process on `127.0.0.1:4010`.
- Production Backend `server/src/index.ts` is a separate Bun 1.3.14 process on
  `127.0.0.1:3101`, using the existing local single-user configuration and application DB.
- `FACTORY_HOST`/`FACTORY_PORT` use defaults; these are optional deployment overrides.
- `TEST_DATABASE_URL` was supplied separately for a temporary migrated test DB.

### Actual HTTP flow and authentication

Backend authenticates its existing actor, reads the current actor-scoped PluginStore
catalogue, and POSTs only `{request, catalogue}` to Factory `/v1/constructions` with
`Authorization: Bearer <FACTORY_SERVICE_TOKEN>`. Factory authenticates before model
work and calls the configured provider directly. It normalizes intent, reasons about
requirements, resolves exact catalogue refs, compiles/verifies the artifact, performs
semantic review, and allows at most one repair. It returns a 200 verified construction.

Backend's HTTP client validates schema, request identity, resource fingerprints,
PASS verification, hash and compiled prompt. Backend checks fresh owner resource facts,
persists through `createConstructed`, owns idempotency/audits/readiness and returns
201 ready or 202 pending. Read/recheck and runtime gating remain Backend-owned.
No grants or credentials cross the Factory HTTP contract.

Observed checks:

| Check | Observed result |
|---|---|
| Factory GET /health | 200, agent-factory/ok |
| Backend GET /health | 200, ok |
| Missing service bearer | 401 UNAUTHENTICATED |
| Incorrect service bearer | 401 UNAUTHENTICATED |
| Correct bearer and real construction | Verified Factory artifact, 200 |
| Production Backend creation | 202, persisted pending_resources |
| Persisted integrity and Backend inspection | PASS; GET returns 200 |
| Factory deliberately stopped, fresh Backend creation | 503 MODEL_UNAVAILABLE; zero saved rows; no local fallback |
| Existing Backend inspection while Factory is stopped | 200 |
| Existing Backend recheck while Factory is stopped | 409 RESOURCES_PENDING |
| Pending runtime readiness gate | Blocked; zero grants for the smoke agent |

The outage checks were executed against an intermediate smoke agent before cleanup.
Factory was restarted after the outage; both services remain running locally.

### Real Web Researcher smoke

The exact Vietnamese input requested by the user was used:

```json
{
  "name": "Web Researcher",
  "role": "Internet Research Agent",
  "description": "Tìm kiếm thông tin trên Internet và tổng hợp câu trả lời có dẫn nguồn."
}
```

Current production catalogue contained 1 tool and 8 skills, including both requested
research resources. The final direct Factory intent was HIGH confidence,
`web_research`, with normalized goal “Search for information on the Internet and
synthesize an answer with cited sources.” Explicit capabilities were internet search,
answer synthesis and citations. Inferred capabilities were source comparison, clear
reporting and source attribution; there were no missing-information questions.

Both the direct Factory call and production Backend HTTP creation resolved exactly
`tavily/tavily_search` and `research-synthesis` with catalogue fingerprints. Static
verification and semantic review were PASS with no issues/findings, using
`openai/gpt-4.1`, attempt 1. No real repair was necessary. Offline suites separately
exercise successful scoped repair, exhaustion and scope-violation refusal.

The Backend agent is
`agent_factory_f9b0ca6b3a41d2cc98e5bd86c85aeee4659d0671460872a95457682f1d8ee27b`.
Database reload/integrity, fresh readiness, HTTP inspection, creation audit and
secret-absence checks passed. It is private and `pending_resources`, with
GRANT_REQUIRED for both resources. The entire grant table remained unchanged across
construction. Two earlier smoke agents were soft-deleted through the existing
profile store; the final agent is retained with no grants.

The runnable `server/scripts/factory-http-smoke.ts` checks the live paths and saves
the full verified spec, intent, verification and Backend artifact in the ignored,
secret-checked `.logs/factory-real-http-smoke.json`. Repeating it is paid model work
and retains one new private agent per successful run. It never grants or executes tools.

### Root causes corrected and exact file surface

- `agent-factory/src/model.ts`: reject recognizable OpenAI/OpenRouter credentials
  directed to a different provider/endpoint before fetch; reject credential-bearing,
  query/fragment URLs; malformed URLs produce a generic error without echoing input.
- `agent-factory/tests/http.test.ts`: runnable mismatch/malformed-URL tests with
  placeholder credentials and zero outbound calls on invalid configuration.
- `agent-factory/src/service.ts`: clarify the existing request-only intent instruction
  after repeated live evidence showed skill source preferences leaking into inferred
  requirements. Skill methods belong in procedure. No validator or repair limit changed.
- `server/scripts/factory-http-smoke.ts`: new live HTTP/DB verification script, including
  a regression assertion rejecting unrequested source/style preferences in this input's intent.
- Root `.env`: private configuration only; no secret values included in this report.
- `agent-factory/README.md`, `agent-factory/docs/implementation-plan.md`, this report:
  setup, authorized verification surface and current evidence.

No existing Backend production file, Frontend file, grant model, runtime, dependency,
migration or orchestration implementation changed. Pre-task snapshots are under
`/Users/phaihoang/Documents/Codex/factory-real-http-20261002-125259`.

### Executed commands and results

- `rtk bunx bun@1.3.14 run --cwd agent-factory check`: typecheck PASS;
  **17 PASS / 0 FAIL, 104 assertions**, exit 0.
- Final regression command below: **392 PASS / 0 FAIL, 3,504 assertions,
  17 files, 18.01 seconds**, exit 0. This is a fresh run after the prompt/config fixes.
- `rtk bunx bun@1.3.14 run typecheck`: app/server/worker PASS, exit 0.
- `rtk bunx bun@1.3.14 run typecheck:workforce`: PASS, exit 0.
- `rtk bunx bun@1.3.14 run check:architecture`: PASS, exit 0.
- `rtk bunx bun@1.3.14 run check:runtime`: PASS, exit 0.
- Scoped Biome format/lint with `--error-on-warnings`: PASS, exit 0.
- `rtk git diff --check`: PASS, exit 0.
- Real smoke command below: PASS, exit 0; final evidence timestamp
  `2026-10-02T06:04:47.351Z`. The added intent-preference assertion was also executed
  directly against that live evidence and passed.

```sh
rtk bunx bun@1.3.14 run --cwd agent-factory start
# Separate process, in server/:
rtk bunx bun@1.3.14 --env-file=../.env src/index.ts
# Repository root:
rtk bunx bun@1.3.14 --env-file=.env server/scripts/factory-http-smoke.ts
rtk env TEST_DATABASE_URL=<dedicated-test-url> bunx bun@1.3.14 test \
  agent-factory/tests \
  server/tests/agent-factory.test.ts server/tests/agent-factory-golden.test.ts \
  server/tests/model-providers.test.ts server/tests/copilot.test.ts \
  tests/architecture.test.mjs \
  server/tests/agent-factory.integration.test.ts server/tests/agent-factory-routes.test.ts \
  server/tests/agent-factory-runtime.integration.test.ts \
  server/tests/agent-profile-store.integration.test.ts server/tests/runtime-agents.integration.test.ts \
  server/tests/tavily-factory.integration.test.ts server/tests/agent-routes.test.ts \
  server/tests/tavily-rest.test.ts tests/compose.test.ts tests/app.test.ts
```

Temporary container `factory-real-http-tests` used pgvector/pgvector:pg17, enabled
vector, and applied existing migrations with an explicitly separate DATABASE_URL.
The temporary container was stopped and auto-removed after verification.
Regression tests did not run against the application DB. Live smoke deliberately used
the current application catalogue and persisted the user-requested constructed agent.

### Next gate and limitations

**The local real HTTP Factory configuration is sufficient to proceed to post-HTTP-split
real E2E.** No configuration/auth/HTTP/persistence blocker remains. Execution still
requires explicit grants for this generated agent; required resources are not authorized
resources. No automatic grant, Tavily execution, browser journey, runtime model response,
full live golden quality evaluation or deployment acceptance was performed. Prompt
clarification and this live example are not a guarantee of model behavior on all inputs;
the original P0 quality/browser/release gates remain open.

## Production BE detachment and team handoff — 2026-10-02

Status: **PASS for detachment and documentation handoff.** The user's new request
supersedes the prior active BE integration. Factory remains a standalone service;
future Backend integration belongs to the BE team using
[backend-integration-spec.md](backend-integration-spec.md).

### Exact change

`server/src/index.ts` no longer imports/constructs `createFactoryClient` or
`createAgentFactoryService`, passes no Factory service into `createApp`, and no
longer applies a Factory-only socket timeout. There is no replacement local model
constructor or fallback. The Backend process was restarted from this modified source.

Existing `createFactoryRuntimeReadiness`, stored artifact integrity, persistence
data, grants and optional adapter/test seams remain. These guards do not call the
Factory service and must not be removed to permit existing pending/corrupt agents
to run. No Frontend, Factory core, provider secret, database schema, dependency or
grant behavior changed.

The historical `server/scripts/factory-http-smoke.ts` now preflights the BE endpoint
and exits clearly when it is unmounted, before paid model work or persistence.
It is retained for the BE team after reconnection, not an active integration.

### Actual runtime checks after restart

| Check | Result |
|---|---|
| Backend GET /health | 200 |
| Factory GET /health | 200 |
| Backend POST /api/agent-factory/constructions | 404 |
| Backend GET /api/agent-factory/:agentId | 404 |
| Backend POST /api/agent-factory/:agentId/recheck | 404 |
| Factory missing/wrong service bearer | 401 / 401 |
| Factory correct bearer with invalid body | 400; authenticates before validating body |
| Historical BE smoke script | Expected exit 1, explicit detached/inaccessible message before model work |

Both local processes remain running: Factory on 4010, Backend on 3101. Keeping
FACTORY environment values does not reconnect production Backend. No new live-model
construction was needed or claimed for this detachment; prior live smoke is historical.

### New handoff artifacts

- `agent-factory/docs/backend-integration-spec.md`: Vietnamese normative integration
  specification with ownership, environment, authentication, exact HTTP/catalogue/
  response/error contracts, integrity/hash/prompt/fingerprint checks, persistence,
  idempotency, readiness/runtime gates, deadlines/client examples and acceptance matrix.
- (Superseded 2026-10-02: both example files were regenerated offline for the generated-skill
  contract; see the backend integration spec, section 8. The lines below describe the earlier files.)
- `agent-factory/docs/examples/web-researcher-request.json`: actual catalogue metadata
  filtered to resources selected in the previously verified example, for illustration only.
- `agent-factory/docs/examples/web-researcher-response.json`: full verified Factory
  response from the earlier real `gpt-4.1` smoke, without Backend/storage/grant data.

Both JSON fixtures were checked offline against `prepareFactoryCatalogue` and
`parseFactoryConstructionResponse`: schema, request identity, resources/fingerprints,
hash, compiler prompt and PASS verification all passed. A scan against configured
environment secrets passed. Neither fixture is a production resource whitelist.

Modified files: `server/src/index.ts`, `server/scripts/factory-http-smoke.ts`,
`agent-factory/README.md`, `agent-factory/docs/implementation-plan.md`, this report,
`docs/plans/meta-agent-p0-implementation-plan.md`,
`docs/plans/meta-agent-file-impact-map.md`, `docs/configuration.md`, `.env.example`.
Only comment text changed in `.env.example`; private `.env` values were not changed.
Pre-detachment copies:
`/Users/phaihoang/Documents/Codex/factory-be-detach-20261002-131559`.

### Fresh executed validation

- `rtk bunx bun@1.3.14 run --cwd agent-factory check`: module typecheck PASS;
  17 PASS / 0 FAIL, 104 assertions, exit 0.
- The 17-file regression command recorded in the live follow-up above was rerun
  against a new dedicated DB: **392 PASS / 0 FAIL, 3,504 assertions, 11.56 seconds**,
  exit 0. Includes the existing route test proving optional absent Factory is unmounted,
  HTTP-client cases and profile/runtime/auth/model regressions. Test-injected services
  do not imply the production BE is connected.
- `rtk bunx bun@1.3.14 run typecheck`: app/server/worker PASS, exit 0.
- `rtk bunx bun@1.3.14 run typecheck:workforce`: PASS, exit 0.
- `rtk bunx bun@1.3.14 run check:architecture`: PASS, exit 0.
- Scoped Biome lint with `--error-on-warnings`, format and `rtk git diff --check`: PASS.
- Actual post-restart HTTP probes and offline example validation: PASS as detailed above.

Dedicated container `factory-be-detach-tests` used pgvector/pgvector:pg17, enabled
vector and applied only the existing migrations. The application DB was not used
for regression tests. The temporary container was stopped/auto-removed after checks.

No blocker remains for this handoff. **Backend integration is deliberately not
enabled.** The BE team must implement/reconnect it and provide new real HTTP/model/
persistence/readiness evidence before claiming the next E2E integration gate.
