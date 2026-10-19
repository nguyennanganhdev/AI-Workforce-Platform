# Dong/open-platform regression fixes — 19/10/2026

Base: PR #105 at `ce058f3b`, including `Dongg_dev@cb866cfa` and its AgentToolsPanel/session MCP changes.

## Required behavior

1. A growing shared packet refreshes the private-history compression budget and recovers before inference. Source paging consumes tokens/time, but does not spend the work-iteration budget.
2. Existing Dong agents retain legacy Knowledge bindings while being adopted into Agent Spec. Runtime and borrowed sessions can use their existing KBs before adoption.
3. Published agents with no MCP tools retain an empty execution tool set. Workspace coding/planning/schedule tools and default MCPs are not added implicitly.
4. The first Leader turn has SharedContextRead before TeamCreate; its membership is checked again when the tool is called.
5. Long assignment goals and acceptance criteria remain in immutable, readable source snapshots; ordinary teams do not receive unresolvable partner-only brief references.
6. Source grants are scoped to owner, team, task, reply and context mode. References-only turns cannot read arbitrary team events; isolated turns revoke source grants.

## Implementation and regression coverage

- Restore Dong's immutable source paging, grant validation, advancing-page accounting and late context recovery on the merged engine, retaining trailing context messages, recalled memory and provider usage accounting.
- Preserve legacy AgentData fields and move KB IDs into Agent Spec on adoption; enforce tool allowlists for both legacy and versioned agents.
- Keep partner rooms on their existing CaseEvidence path and preserve specialist-owned customer questions, peer routing and per-agent public chat projection.
- Restore `shared_context_budget_recovery_test.py`; add `dong_merge_compatibility_test.py`; extend the existing collaboration tests to exercise scoped snapshots.
- Fix Phase D fixture imports and include the compatibility/recovery suites in the required gate.
- Align the synthetic Domain test with the existing applied-result-receipt gate. No Domain production code changes are included.

All automated checks use fakes or isolated local services. No real model/provider calls are authorized for validation.

## Release target

Existing VPS Platform (`vagen-platform.duckdns.org`), app/web only. Preserve existing runtime environment, mounts, networks, data services and Domain stack. Record a fresh four-store backup, isolated restore and rollback image identity before cutover; verify the deployed source/image identity and public routes afterward.

## Validation evidence

- Linux production-image regression selection: 222 tests and 10 subtests passed, with networking disabled.
- Vin-enabled React browser fixtures: 26 tests passed, using only mocked same-origin HTTP responses. The registration assertion follows Dong's administrator-approval message while still rejecting role/scope submission.
- Frontend lint, TypeScript/Vite production build, and six chat/HTTP/crypto tests passed. Production images use `/api`.
- Isolated Domain HTTP confirmation/concurrent-decision and rework scenarios: two tests passed without Agent/model calls.
- A broad upstream Windows sweep is not a passing release gate: optional dependencies (`moto`, `mem0`, `textual`, `dingtalk_stream`) and the separate resident-test import environment are absent. The required Linux CI gates are assessed from their JUnit reports, including failures, errors and skips.
- Fresh VPS four-store backup and isolated restore passed. Verification includes PostgreSQL migration/counts, MinIO bucket readiness, workspace file hashes, and canonical values plus stream/consumer-group state for 736 persistent Redis keys. Raw RDB/DUMP hashes are unsuitable for unordered hash/set comparison across reloads.

Final CI and deployment evidence is recorded on [PR #106](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/106) and in the scoped VPS release directory `/opt/awp-platform/releases/dongfix-037563a7-20261019`. Real-model chat quality and business acceptance remain owner-run checks.
