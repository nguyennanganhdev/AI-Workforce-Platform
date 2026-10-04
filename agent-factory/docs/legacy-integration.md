# Legacy BE integration evidence

The original Factory evidence below is retained after the user-authorized standalone split. Core paths are now `agent-factory/src/{spec,verification,service}.ts`; DTOs are `agent-factory/src/contracts.ts`. The BE-specific storage/readiness and existing authenticated API remain in their application adapters. See `../README.md` for the independent HTTP service and its construction-only contract.

# Agent Factory (Meta-Agent P0)

Owner: **Platform**. Construction is implemented; P0 acceptance is **BLOCKED**.
See [the final evidence](../../docs/plans/meta-agent-p0-implementation-plan.md#21-step-9-final-verification).

## Boundary and API

`spec.ts` owns strict parsing, exact catalogue resolution, deterministic compilation,
canonical SHA-256 hashing and stored-artifact integrity validation. `verification.ts`
owns static verification, independent semantic review and allowed repair paths.
`service.ts::constructAgentSpec` orchestrates one generation and one review, with at
most one scoped repair (two generation attempts, four total model calls).

Core imports are limited to shared Platform DTOs, sibling modules, Zod and Node's
standard library. Completion, cancellation and observations are injected. The core
has no Hono, database, PluginStore, MCP transport, credentials, UI or runtime dependency.
The shell adapters in `server/src/agents/factory.ts` and `factory-routes.ts` reuse the
existing registry, model transport, profile store and authorization infrastructure.

## Intent normalization

Every generation starts with an `intent` block: the model's reading of the three request
fields, written in English whatever the request's language (`IntentNormalizationResult` in
`agent-factory/src/contracts.ts`): `normalizedGoal`, a free `taskType` label,
`explicitRequirements`, `inferredRequirements`, `confidence` and `missingInformation`. It is
part of the existing generation call, not a stage with a model call of its own, so the
normal path still makes exactly two calls.

`parseIntentNormalization` in `spec.ts` checks the block before any draft field. A missing
or malformed block is `INVALID_SCHEMA` at `intent…` and takes the one ordinary repair. `LOW`
ends construction with one `NEEDS_INPUT` issue per open point
(`intent.missingInformation.N`, HTTP 422): no draft field is read and nothing is resolved,
reviewed, repaired or saved. `HIGH` must list nothing missing; `MEDIUM` and `LOW` must list
something.

The reading informs the draft and decides nothing else. It names no resource and selects
none: tools and skills still come only from `requirements[].proposedRefs` through
`resolveDraftResources`, every requirement still cites the request or its own resource, and
the reviewer still judges the artifact against the original request without seeing the
reading. It is held in request memory and returned by `constructAgentSpec`; it is not part
of `AgentSpec`, the spec hash, the compiled prompt or the stored configuration.

## Artifact and runtime contract

- `AgentSpec.schemaVersion` and `compilerVersion` are both **1**.
- Trimmed request limits are **80 name / 120 role / 1,000 description** characters.
- The snapshot contains at most 64 tools / 32 skills / 96 KiB; drafts at most 64 KiB,
  compiled prompts at most 16 KiB, selected resources at most 8 tools / 4 skills.
  Overflow is an error, never silent truncation.
- Canonical storage is `agents.configuration.factory.spec`. The adjacent
  `configuration.systemPrompt` is exactly `renderCorePrompt(spec)`; verification,
  request/key hashes and stored readiness accompany it. No migration, new store or
  Workforce version/publish dual-write is introduced.
- Core prompts contain task behavior and declared resource/argument requirements.
  Runtime-owned provenance, standing instructions, granted-tool and computer guidance
  are appended by the existing runtime, never duplicated by the compiler.
- Contracts are nonempty text over AG-UI messages. Output requirements are **prompt-only**,
  not enforced structured-output schemas or guarantees of business correctness.
- Semantic review is a separate model call after deterministic checks. Invalid or
  unavailable review fails closed; it cannot override schema/resource validation.
- Generated artifacts are private and explicitly built-in, even with a managed remote
  endpoint configured. Identity/spec editing and duplication are rejected in P0.

## Readiness and failure behavior

Construction never grants resources or calls business tools. A verified artifact can
be stored as `pending_resources`; current owner-scoped grant/configuration/connection
facts must be satisfied and explicitly rechecked before execution. Every runtime load
rechecks resource fingerprints and access. Missing collaborators, malformed artifacts,
revoked access and changed resources fail closed before model/tool execution.
Changed semantic fingerprints require reconstruction; recheck does not rewrite the spec.

The normal path makes exactly two model calls. Calls are limited to 20 seconds and 4,096
output tokens on either provider, and the outer construction to 90 seconds. They run on
`FACTORY_MODEL` when it is set (a stronger model than coworkers answer on, same provider,
key and endpoint) and on the runtime model otherwise; `factoryCompletionOptions` in
`server/src/agents/factory.ts` is the one place those values are named. There is no
provider fallback or permission retry. A repair is shown the validator's own JSON Schema
for each field it must fix (`draftFieldSchema`), never a relaxed one.
The shared completer retains its legacy defaults for callers that omit Factory options.
Its abort listener stays installed across key lookup, HTTP fetch and body parsing,
including on the repository's pinned Bun 1.3.14. Core and shell deadline listeners also
stay installed across completed stages and are removed when the request finishes.

API: authenticated `POST /api/agent-factory/constructions` requires `Idempotency-Key`;
201 means ready, 202 means persisted pending. Owner/admin `GET /:agentId` inspects the
artifact; `POST /:agentId/recheck` requires the expected spec hash and uses the creator's
facts. Invalid input is 400, unresolved scope/resources or exhausted construction 422,
conflicts/stale resources 409, unavailable dependencies 503 and deadline expiry 504.
Idempotent replay and recheck make zero generation calls. Public errors omit provider
payloads and secrets.

## Verification and deployment

Run with Bun **1.3.14**, declared dependencies, and a migrated dedicated PostgreSQL/pgvector
`TEST_DATABASE_URL`; see [development prerequisites](../../docs/development.md#meta-agent-p0-verification).

```sh
rtk bun test server/tests/agent-factory.test.ts server/tests/agent-factory.integration.test.ts server/tests/agent-factory-routes.test.ts server/tests/agent-factory-runtime.integration.test.ts server/tests/agent-factory-golden.test.ts app/tests/agent-factory-ui.test.tsx
rtk bun run check
rtk bun run eval:factory-quality
```

Golden replay is deterministic implementation coverage, not model-quality evidence.
Real-model credentials, owner-approved thresholds and a passing configured-model report
remain required. Browser E01–E04 and their runner remain unimplemented/blocked. No P0
release is authorized by passing unit or runtime integration tests alone.

Rollout must replace all unguarded server/worker replicas before enabling Factory creation.
Do not roll an old binary back onto generated rows: it can treat the prompt as an ordinary
editable/runnable built-in. Disable creation/execution while keeping the guards and
canonical artifacts/history intact; no destructive rollback migration is provided.
Artifacts created under the former oversized input limits fail the corrected validator
when over 80/120/1000; recreate them with valid input rather than trimming stored data.
