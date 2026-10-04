# Development

## Setup

Install Docker, [Bun](https://bun.sh) 1.3+, `lsof`, `python3`, `openssl`, and `curl`. The
Intelligence provisioning below also needs `npx` (Node); `scripts/start.sh` uses `openssl` to mint
the generated secrets on a first run.

```sh
cp .env.example .env
bun install
```

Provision CopilotKit Intelligence after `.env` exists:

```sh
npx --yes copilotkit@latest login
npx --yes copilotkit@latest project select
```

Put the `cpk-...` runtime key from `project select` in `.env` as
`INTELLIGENCE_API_KEY`. There is no licence step. Then add `OPENAI_API_KEY`.

Start the stack:

```sh
bash scripts/start.sh
```

## Running services

Use `bash scripts/start.sh` for the full local stack. It starts Docker services, applies migrations, starts the API server, the app, and the routine worker, and verifies health routes.

Use `bash scripts/stop.sh` to take it down: the app, the routine worker, the API server, the Docker services, and each Bot's computer, which the supervisor makes rather than compose and which therefore outlives `docker compose down`. Pass `--keep-computers` to leave those browsers signed in. Nothing is deleted either way.

Use `bun run dev` only when you want the app and API server without starting the Docker Bots and computers.

| Service           | Port                       |
| ----------------- | -------------------------- |
| `app`             | 3010                       |
| `server`          | 3001                       |
| `agent-computer`  | 4100                       |
| `agent-bot`       | 4200                       |
| `agent-langgraph` | 4201                       |
| `supervisor`      | 4500 host / 4300 container |
| PostgreSQL        | 5432                       |

`start.sh` leaves existing matching services alone and reports when a port is held by another process.

**Nothing here sweeps staged attachments.** A file dropped into the composer is stored before the
message is sent, and the only thing that reclaims the ones never sent is
`bun scripts/cull-staged-attachments.ts` from `server/`, which the Helm chart runs hourly and which
neither `docker-compose.yml` nor `start.sh` starts. It needs only `DATABASE_URL`, and takes a
retention window in hours as its one optional argument, defaulting to 24. On a laptop that is
usually nothing, because the rows are small and the database is yours. It stops being nothing at
thirty-two: one person may hold that many unsent files across every channel at once, the refusal on
the next one promises they are cleared within a day, and where nothing sweeps they are not, so a
long-lived local deployment can reach a state where attaching anything is refused. Removing a file
in the composer deletes it outright, so it takes abandoned drafts rather than ordinary use.
[deployment.md](deployment.md) says the same for a real deployment.

## Migrations

After changing the Drizzle schema:

```sh
bun run --filter server db:generate
bun run --filter server db:migrate
```

Review generated migration files before sharing them. `start.sh` applies existing migrations when it starts the stack.

**Do not hand-edit a generated migration.** It leaves a file that no longer matches what the
generator produced. If the generated SQL will not work — `ADD COLUMN ... NOT NULL` fails on a table
that already has rows — split it instead: generate the column nullable, add the data step, then
generate the constraint.

**A constraint that tightens an existing column belongs to a later release**, not to the release that
adds the column. A rolling deploy runs the migrations and then serves from old and new replicas at
once, and an old replica writes rows without the new column: under `NOT NULL` its writes start
failing, so the release that added the column breaks for everybody who lands on a replica that has
not been replaced yet. Ship the column nullable, let the fleet turn over, then tighten it. `issuer`
on `accounts` is the worked example: the column is nullable and no migration tightens it.

**A data step is its own migration**, created with the flag that exists for it:

```sh
bun run --filter server db:generate -- --custom --name=backfill_something
```

A generator diffs schema against schema, so a rule like "the rows whose provider is Google get
Google's issuer" can never come out of one: it is not in the schema. `--custom` writes an empty file
registered in the journal, and it is the only migration anybody should be writing by hand.

CI enforces two things about this: `drizzle-kit check` for collisions and gaps between migrations,
and a generate-and-fail-if-dirty probe that refuses a schema change with no migration written for it.

**If `drizzle-kit migrate` hangs and then exits non-zero with no error**, the journal names a
migration file that is not there. A rebase does this: `meta/_journal.json` is a checked-in file, so
restoring it can reinstate entries for migrations that were renamed. `drizzle-kit check` reports
"Everything's fine" in that state, because it compares schemas rather than checking that the journal
and the directory agree. Compare `meta/_journal.json` against `ls server/drizzle/*.sql`.

## Quality checks

Run these before opening a pull request:

```sh
bun run format:check
bun run lint
bun run typecheck
bun run test
bun run build
```

Integration tests expect a PostgreSQL database with pgvector. Point `TEST_DATABASE_URL` at a dedicated database such as `postgres://openbot:openbot@localhost:5432/openbot_test` before running them.

They refuse to use the application `openbot` database. `DATABASE_URL` is still the application setting, and the database client removes it from the process environment after opening a connection to preserve the Windows Bun connection fix, so tests use `TEST_DATABASE_URL` as their immutable fixture address. Running them against a deployment you are using puts test Bots in its audit trail and its activity reports, so create a separate database and migrate that before running the integration suite.

CI uses `bun run test:ci` to verify the expected test count in addition to normal tests.

`bun run test:smoke` is separate and needs a deployment that is up, and a session on it:

```sh
bash scripts/start.sh
export OPENBOT_SMOKE_COOKIE='better-auth.session_token=...'
bun run test:smoke
```

It drives one journey over HTTP against the running stack, so it covers the joins the rest of the
suite cannot reach: server to supervisor to computer, the gateway deciding before the browser acts,
and the audit row landing. Point it elsewhere with `OPENBOT_API_URL`. Without a deployment it is
skipped by `bun run test` and says what to start when asked for by name.

The session is not optional and not a convenience. Every route the journey proves is behind
`requireUser`, so without one the three tests that act on a computer answer 401 and the run reports
a broken deployment when nothing is broken. Take the cookie from a browser already signed in to the
deployment under test, from DevTools under Application, Cookies. It is a credential with that
person's reach: it belongs in the environment of the run, not in a file or a pull request comment.
Asked for without it, the run stops before the first test and names the variable.

`bun run test:live-screen` is separate for a related reason and needs no deployment, only this
directory's own dependencies:

```sh
cd agent-computer && bun install
cd .. && bun run test:live-screen
```

It drives the live screen against the real computer process with a real Chromium: a socket closing
while the browser is still starting, a second connection taking the screen from the first, the wheel
refusing input from the socket that owns it, and a browser closing by request or by the idle sweep.
Those need `agent-computer/src/index.ts`, which imports Playwright at module scope, and `playwright`
is declared only in `agent-computer/package.json`, which `bun install` at the root does not reach. So
without `OPENBOT_LIVE_SCREEN=1` the files skip before importing anything, which is what keeps
`bun run test` and CI working where that dependency was never installed.

## Contribution checklist

- Keep changes focused.
- Keep credentials, service-account JSON, customer data, and transcripts out of source control.
- Put sensitive behavior on the server, not only in the browser.
- Update [configuration](configuration.md), [architecture](architecture.md), or the root [README](../README.md) when behavior changes.
- Run the quality checks above and include the results in the pull request.

## Meta-Agent P0 verification

P0 is **BLOCKED**, not accepted. The [Step 9 report](plans/meta-agent-p0-implementation-plan.md#21-step-9-final-verification)
is historical. The [latest acceptance closure report](plans/meta-agent-p0-implementation-plan.md#22-p0-acceptance-closure-verification--2026-10-01)
records 20 PASS / 13 BLOCKED items, fresh-DB/CI/static results, the failed real-model diagnostic,
exact command artifacts and remaining work. The plan and impact map are currently ignored
local files; preserve them deliberately with the release evidence. No release-quality or
browser success may be inferred from deterministic fixture results.

Use the repository-pinned **Bun 1.3.14** (the host's default 1.4.2 is not the pinned
verification runtime), Node and Python, Docker PostgreSQL with pgvector, and `rtk`.
The Step 9 host used `PATH=/tmp/meta-agent-step1-toolchain/node_modules/.bin:$PATH`.
Install the standalone packages too; root workspaces do not install them:

```sh
rtk bun install --frozen-lockfile
rtk bun install --cwd agent-bot --frozen-lockfile
rtk bun install --cwd agent-langgraph --frozen-lockfile
rtk bun install --cwd agent-mastra
rtk bun install --cwd desktop --frozen-lockfile
rtk bun install --cwd agent-computer --frozen-lockfile
rtk bun agent-computer/node_modules/playwright/cli.js install chromium
```

`agent-mastra` has no committed lockfile; its install can generate a local lockfile.
Do not add dependency or lockfile changes to P0 merely to prepare verification. The
previously proposed `bun --cwd agent-computer x playwright ...` failed on this host;
the installed CLI path above uses the declared Playwright 1.62.1 dependency.

Create a **dedicated** test database, never the application database. For this run an
existing loopback test container (`meta-agent-step2-postgres`, port 55432) hosted a fresh
`openbot_p0_final_test` database, with pgvector and all 51 existing migrations. Example
for that verified local test container (replace only with your own isolated test target):

```sh
rtk docker exec meta-agent-step2-postgres createdb -U openbot openbot_p0_final_test
rtk docker exec meta-agent-step2-postgres psql -U openbot -d openbot_p0_final_test -c 'CREATE EXTENSION IF NOT EXISTS vector;'
export TEST_DATABASE_URL=postgres://openbot:openbot@127.0.0.1:55432/openbot_p0_final_test
cd server
rtk env DATABASE_URL="$TEST_DATABASE_URL" bunx drizzle-kit migrate --config=drizzle.config.ts
cd ..
rtk bun run generate:app-config
rtk bun test server/tests/agent-factory.test.ts server/tests/agent-factory.integration.test.ts server/tests/agent-factory-routes.test.ts server/tests/agent-factory-runtime.integration.test.ts server/tests/agent-factory-golden.test.ts app/tests/agent-factory-ui.test.tsx
rtk bun run check
rtk bun run lint
rtk bun run format:check
rtk bun run build
rtk bun run test:ci
```

Do not recreate an existing database or use app `.env` migrations to bypass the explicit
test target. Keep source backups outside the repository while running discovery-based
checks; `.logs` is ignored by Git but is still traversed by Biome.

### Configured-model quality gate

`rtk bun run eval:factory-quality` runs the frozen 20 cases through the actual construction
and review service without saving agents, granting access or calling business tools.
It resolves `BOT_PROVIDER` / `BOT_MODEL` and the tenant package the same way as the server.
Supply the selected provider's real `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the environment;
this runner does not read a key stored in the application database. Keep provider URL
settings consistent with the intended real deployment; do not point release evaluation
at the replay fixture server or silently switch providers.

`FACTORY_QUALITY_THRESHOLD_APPROVAL` must reference an actual owner decision, with approver
and approved values preserved in release evidence. Proposed values remain: precision and
recall 100%, forbidden selection and unsupported requirements 0%, positive construction
success 100%, repair rate at most 10%, exact states for all 20 cases, at most two generation
attempts/four model calls. A nonempty dummy string or test-fixture approval is not approval.

Use `FACTORY_QUALITY_REPORT` for an explicit output path, or retain the timestamped report
under `.logs/factory-quality/`. Preserve all failed runs, dataset/catalogue/prompt/compiler/model
fingerprints, per-case outcomes, latency and exact usage coverage. Missing credentials,
unapproved thresholds, unknown usage or failed gates are failures, not skips. The existing
`factory-quality` workflow runs on tags/manual dispatch; required release-status enforcement
must be configured and verified by the repository owner. Rerun on the final release candidate.

### Mandatory browser gate (currently BLOCKED)

`rtk bun run test:factory-e2e` currently exits 1 because the Step 8 script, process runner,
E01–E04 browser suite and browser CI job do not exist. Installing/launching Chromium is only
a prerequisite, not a passing application E2E result. Do not replace Intelligence or the
built-in runtime with fake browser responses.

Before implementing/running the approved Step 8 gate, provide dedicated test values:

- `FACTORY_E2E_INTELLIGENCE_API_URL`
- `FACTORY_E2E_INTELLIGENCE_GATEWAY_WS_URL`
- `FACTORY_E2E_INTELLIGENCE_API_KEY`
- An optional license token only if the selected Intelligence service requires it;
  current application configuration does not always require one.
- A dedicated migrated test DB, installed Chromium and available loopback ports for
  `SERVER_PORT` / `APP_PORT` and LLMock/MCPMock fixtures.

The runner must use explicit test-only configuration and `OPENBOT_SINGLE_USER=true` only
with approved loopback isolation. Existing server bootstrap omits a hostname and Vite binds
`::`; Step 8 stopped because this does not satisfy its loopback-only requirement. Vite needs no
config change (`vite --host 127.0.0.1` binds loopback only); the server's `serve` call has no
hostname option, so that half needs an approved change or an owner decision. Resolve
that isolation/approved-change-surface discrepancy before launch; do not open an unauthenticated
single-user deployment on the LAN. The future runner must reject missing prerequisites,
fewer than four cases or any skip, and preserve sanitized traces/screenshots/provider and MCP
counts for E01 create/run, E02 missing resource, E03 approve/run/revoke and E04 exhausted repair.

The full CI suite has separate opt-in live-screen, Composio, supervisor and deployment-smoke
skips. List them in the report; none supplies the missing Factory browser evidence.

The 2026-10-01 closure audit found that Bun child tests can auto-load a local `.env` even
when their fixture environment deliberately omits keys/model/port. Reproduce CI in a clean
source snapshot/checkout without local `.env` or ignored diagnostic code; the closure report
links the exact snapshot script and command manifest. Do not remove somebody's local config
to make the gate green. Final clean CI: 5,366 pass, 27 existing
opt-in skips, zero fail. One earlier unchanged voice-stream timeout is retained separately.
The fifteen files that failed `format:check` at HEAD were formatted in a separately authorized,
format-only cleanup; `format:check` now exits 0 on a clean checkout and still fails in a working
directory that holds ignored `.logs` artifacts. One attachment event-loop timing test failed once
under host load (40 ms against a strict under-40 ms limit) and passed on unchanged reruns.
The configured-model diagnostic hit HTTP 429/402 and failed quality/usage/approval gates;
it predates the corrected resource prompts and is not a final release report.
