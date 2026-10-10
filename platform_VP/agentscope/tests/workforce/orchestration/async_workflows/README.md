# PHH Phase B module tests

Owner: **Phan Huy Hoàng**. Baseline `develop2@8487404`; local branch `dev2PHH-B`.

175 backend scenarios B001–B175 and 71 UI scenarios UI001–UI071. Each has a unique ID; the backend runner rejects fewer than 50 cases, duplicate IDs and skips. Fake UOW/store/clock/runtime/operations/signals live only in `fakes.py`.

Backend tests cover request/reply/close, three lifecycle patterns, immutable binding/pins, HITL authority, lease/fence, rollback and public projections. B131–B151 add per-frame SSE authorization, public errors and stop-tracking without consent. UI tests cover receipt/event/snapshot reducers, replay/dedupe, 410 recovery, identity isolation, API/transport/auth refresh/abort and React static render. UI053–UI063 mount React components in Happy DOM and click/check/submit/retry/switch tickets; they do not certify a browser or global app. B106 verifies the PHH lifecycle slice with fake dependencies; it is not the global MB gate.

```powershell
python tests/workforce/orchestration/async_workflows/run_phase_b.py --isolated-imports --dependency-path .venv/Lib/site-packages
pnpm --dir tests/workforce/orchestration/async_workflows install --ignore-workspace --ignore-scripts --frozen-lockfile
bun test ./tests/workforce/orchestration/async_workflows/timeline.test.ts ./tests/workforce/orchestration/async_workflows/timeline-render.test.tsx ./tests/workforce/orchestration/async_workflows/timeline-interaction.test.tsx
python tests/workforce/orchestration/async_workflows/verify_phase_b.py --dependency-path .venv/Lib/site-packages
python tests/workforce/orchestration/async_workflows/run_dependency_regressions.py --suite registry --dependency-path .venv/Lib/site-packages
python tests/workforce/orchestration/async_workflows/run_dependency_regressions.py --suite foundation --dependency-path .venv/Lib/site-packages
```

`--isolated-imports` skips service initializers while loading real workforce source. Happy DOM 20.14.6 is pinned in this test folder's private package.json/pnpm-lock.yaml; application dependencies are unchanged. Quality formatting/matrix export requires explicit `--format`/`--export-matrix`; ordinary tests never regenerate expected artifacts. Dependency runners only read other owners' source.

See [PHH status](../../../../docs/workforce/handoffs/phan-huy-hoang/STATUS.md) for evidence and [matrix](../../../../docs/workforce/handoffs/phan-huy-hoang/PHASE_B_TEST_MATRIX.md) for inputs/expected assertions/source lines. PostgreSQL, real HTTP/provider/browser and multi-process restart require later integration checks.

B152–B175 cover mixed operation completion and retained history, advisory signal hangs/slow cleanup/cancellation, lost notifications with durable result, and new close CAS versus ledger retries. The fake operation lookup has per-operation pending overrides, so terminal A and pending B are independently represented. UI064–UI071 cover concurrent POST/snapshot recovery, cached cursor, repeated revisions, abort/backoff, foreign snapshots, authorization failure and same-revision state conflicts.
