# Standalone Agent Factory verification — 2026-10-02

Historical split evidence. BE HTTP wiring was completed afterward; see
[HTTP integration verification](http-integration-verification.md) for the current integration.

Status: **PASS for module isolation and standalone HTTP service**.
The user selected a separate process/service. Previous in-process-only relocation
scope was superseded explicitly; both historical planning files have an addendum.

## Implemented symbols / files

- Moved existing `spec.ts`, `verification.ts`, `service.ts` into `agent-factory/src/`;
  compiler, reviewer and repair logic are byte-identical after normalizing the one
  DTO import. `constructAgentSpec` behavior is preserved.
- Moved `agent-spec.ts` to `src/contracts.ts`; its recursive JSON type is local and
  no longer imports `shared/platform/context.ts`. Added standalone request/response DTOs.
- Moved the charter, legacy integration README and golden/intent fixture data into
  this folder. Frozen fixture contents are unchanged.
- Added `src/http.ts::createFactoryHandler`, `src/model.ts::createHttpCompleter`,
  `src/io.ts::readBoundedText`, `src/server.ts` and public `src/index.ts`.
- Added package/lockfile, independent TypeScript configuration, environment example,
  git/docker ignores, Dockerfile, README, offline HTTP/model/entry tests and this evidence.
- Existing BE/UI/core tests/evaluation runner changed only their Factory import/fixture
  paths. BE storage, auth, grants, readiness, runtime and existing API logic remain intact.
- Extended `scripts/check-architecture.mjs` and its tests: Factory imports stay within
  its own folder (plus Zod/standard APIs); consumers use the public entry/DTOs; UI cannot
  import Factory execution. No root workspace/lockfile or database schema changes.

## Final tests

Bun **1.3.14** executed the complete focused set in one process:
**359 PASS / 0 FAIL**, **3,408 assertions**, **14 files**, 15.90 seconds.
All network/model responses in these checks are fixtures/mocks, not paid live model calls.
A fresh temporary Docker PostgreSQL/pgvector database was migrated using the existing
migrations and supplied explicitly through `TEST_DATABASE_URL`; no application database
was used. The temporary database container was stopped and removed after verification.

```sh
rtk env TEST_DATABASE_URL=<dedicated-temporary-test-url> bunx bun@1.3.14 test \
  agent-factory/tests/http.test.ts \
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
  server/tests/agent-routes.test.ts
```

## Other executed checks

| Check | Result |
|---|---|
| Root `rtk bun run typecheck` (app/server/worker) | PASS |
| Root `rtk bun run typecheck:workforce` | PASS |
| Root `rtk bun run check:architecture` | PASS |
| Module `rtk bun run typecheck` | PASS |
| Module `rtk bunx bun@1.3.14 test` | 10 PASS |
| Scoped Biome format and lint with error-on-warnings | PASS |
| `rtk git diff --check` | PASS |
| Copy only `agent-factory/` outside repository; pinned frozen install | PASS |
| External copy: pinned typecheck, all 10 tests and real child-server HTTP construction | PASS |
| `rtk docker build -t agent-factory:local-check ./agent-factory` | PASS |
| Start resulting container with offline config; `GET /health` | 200; container removed |

The lockfile was generated with Bun 1.3.14 (version 1), and frozen installs work
both in the independent copy and Docker. Runtime dependency is the already-used
Zod **4.4.3**; no new framework or model SDK was added.

## Diff and backup checks

The pre-task tracked snapshot was reconstructed with a private temporary Git index
and compared against current files. There are no unexpected tracked file changes;
BE/UI production changes from this task are import specifiers only. The real index
and HEAD remain unchanged; HEAD is `495412e` on `main`. No pull, merge, commit or push
was performed. Pre-existing local work remains in place.

The pre-move Factory source archive and tracked patch are outside the repository at:
`/Users/phaihoang/Documents/Codex/agent-factory-backup-20261001-232521`.

## Integration and acceptance limits

- Standalone `POST /v1/constructions` takes a trusted service bearer and an actor-scoped
  catalogue supplied by BE; success is a verified construction artifact, not a saved
  agent or a runtime permission/readiness decision.
- Existing BE adapter/API retain their in-process behavior. Changing BE to call remote
  HTTP remains a separate integration change. BE owns persistence/idempotency, audit,
  user/tenant auth, grants/connections and runtime readiness.
- Standalone model transport supports OpenAI Chat Completions and compatible endpoints.
  It requires its own model URL/name/key and service token. Existing BE Anthropic support
  is unchanged; Anthropic Messages is not a standalone transport in this change.
- Live-model quality, original browser release cases and deploy acceptance were not
  rerun or claimed. Original P0 release gates remain as recorded in legacy evidence.
- `origin/develop` was not merged; the existing BE V3 reconciliation remains separate.
