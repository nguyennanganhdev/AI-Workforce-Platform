# Platform execution durability audit

Audit date: 2026-10-09. Scope: the new platform service in this worktree, using its own source as the primary authority. No Vinhomes files or implementation files were changed by this audit. The implementation was being updated concurrently; findings below describe the reviewed code and explicitly distinguish fixes already observed from recommendations still needing verification.

Final source refresh during this audit: D1–D6 were remediated by the main implementation agent. The original failure scenarios remain documented for regression coverage. There are no independently confirmed outstanding P1 findings from this audit refresh; PostgreSQL-specific acceptance still needs the main validation run.

## Evidence and limits

- Read queue, worker, runtime, domain, context, knowledge, integration, budget, maintenance, security, automation and evaluation modules, plus current reliability/runtime tests.
- Ran isolated SQLite probes in temporary directories, with intercepted model creation or fake MCP transport. No provider API calls, real credentials or external writes were used.
- PostgreSQL lock cycles below are established by transaction/lock-order analysis. This audit did not run a PostgreSQL deadlock reproduction. SQLite cannot establish PostgreSQL row-lock correctness.
- Sequential tasks within each session and eight bounded workers are the intended design; their existence is not a finding. Twenty-session production capacity still requires the separate PostgreSQL load acceptance run.
- Independent command `.venv/Scripts/python.exe -m pytest tests/test_reliability.py -q` completed with **8 passed in 7.75s**, against the default isolated test database. This suite is not a replacement for PostgreSQL concurrency tests.

## Findings

### D1 — P1: maintenance can invert the session/wallet lock order

Source: [maintenance.py](../../services/platform-api/vp/maintenance.py), `settle_abandoned`, reviewed lines 10–25; [limits.py](../../services/platform-api/vp/limits.py), `reconcile`, reviewed lines 104–129; `reserve`, reviewed lines 49–68.

`settle_abandoned` iterates reservations for multiple sessions in one transaction. `reconcile` locks the reservation's session, then reservation, then shared workspace/month wallet. After reconciling session A, that transaction retains the wallet lock while requesting session B's lock. A normal session B execution can already hold B's lock through `fence` and wait for the same wallet through `reserve` or `reconcile`.

Reproducible PostgreSQL schedule:

1. Create abandoned reservations A and B in the same workspace/month.
2. Maintenance reconciles A and retains wallet W.
3. Worker B acquires session B, then attempts to reserve/reconcile against W.
4. Maintenance proceeds to B: maintenance waits B; worker waits W.

PostgreSQL must abort one transaction. An uncaught exception in maintenance also ends its long-lived task, which causes the worker process to exit under [worker.py](../../services/platform-api/vp/worker.py), `main`.

Recommendation: select candidate IDs first, then process each reservation in its own transaction. Alternatively acquire all affected session locks in a stable order before any wallet. Add a PostgreSQL regression that controls the interleaving; repeating SQLite tests is insufficient.

Remediation observed: `settle_abandoned` now gathers IDs in an initial transaction and reconciles each reservation in a separate transaction (`maintenance.py`, refreshed lines 10–30). The cross-session wallet lock retention described above is removed by source inspection. A PostgreSQL interleaving test remains the appropriate independent acceptance check.

### D2 — P1: exact-call approval does not bind the MCP endpoint/configuration

Source: [integrations.py](../../services/platform-api/vp/integrations.py), `mcp_tools` intent creation, reviewed lines 83–101; `perform`, reviewed lines 140–152; [api.py](../../services/platform-api/vp/api.py), `update_resource` and `approve_tool`.

The initial execution intent records MCP ID, tool and arguments. `perform` obtains the current MCP configuration later. Unlike provider model identity, MCP URL and credential binding can be edited. Thus an approved write can execute against a different remote system while retaining the approval.

Independent SQLite/fake-transport probe output before remediation:

```text
approved_endpoint = server-a.example
actual_endpoint = https://server-b.example/mcp
write_calls = 1
```

The probe committed an approved intent originally associated with A, updated the MCP record URL and version to B, then ran `execute_approved`. No network traffic occurred.

Recommendation: persist the connection identity/config version and relevant tool schema fingerprint in the execution intent. At execution, require an unchanged binding or require a new approval. Freeze the actual configuration used across the validation/call boundary; do not validate one revision and send to another. Credential rotation of the same bound record should have an explicitly documented policy.

Remediation observed: intents now store `config_version`, and `perform` compares it against the current MCP record before using the copied config (`integrations.py`, refreshed lines 95 and 153). A second isolated SQLite probe confirmed `config_change_rejected=True` and `remote_calls=0`. This confirms the administrative URL/config drift scenario; remote servers can still change implementation independently of platform configuration.

### D3 — P2: a recovered successful MCP call becomes uncertain

Source: [integrations.py](../../services/platform-api/vp/integrations.py), `perform` result commit, reviewed lines 184–201, and `execute_approved`, reviewed lines 204–225.

`perform` commits `succeeded` and its evidence before `execute_approved` commits the external job completion and queues the agent continuation. A crash between these commits leaves a recoverable running job with a durable successful execution. On reclaim, `execute_approved` treats every status other than `approved` as `uncertain`, overwrites the successful status and stops the session for review.

The broker avoids a duplicate external write, which is correct. The defect is losing known-success state and automatic continuation despite a durable result.

Recommendation: define an explicit recovery state machine. `approved` may start a call; `started` without a durable terminal result is uncertain; `succeeded` must resume continuation without calling again; existing `uncertain` and `rejected` must remain terminal. Queue continuation idempotently in the same fenced transaction as job completion. Add a crash-window test after `perform` commits.

Remediation observed: recovery now converts only `started` to `uncertain`, preserves `succeeded`, and queues its continuation without recalling the tool (`integrations.py`, refreshed `execute_approved`). An independent isolated probe confirmed `durable_success_preserved=True`, `recovery_job_done=True`, and `remote_calls=0` for a recovered terminal success.

### D4 — P2: ordinary quota delays consume the crash recovery limit

Source: [queue.py](../../services/platform-api/vp/queue.py), `claim`, reviewed line 62; `worker_loop`, reviewed lines 138–159.

Every claim increments `attempts`, including jobs intentionally requeued after `RateExceeded`. After three quota delays, the fourth claim fails with `recovery_limit` before invoking runtime, even when the worker never crashed and the provider quota is now available.

Reproduction: keep a model rate window exhausted over three retries; let the next window admit the request. The task still fails at the generic attempt check. This is especially visible when a session competes with busy sessions under bounded provider RPM/TPM.

Recommendation: separate expired-lease/crash recovery attempts from controlled rate-delay attempts, or undo the attempt increment on a controlled quota delay. Verify both prolonged healthy throttling and genuine repeated worker crashes.

Remediation observed: the `RateExceeded` branch decrements the controlled claim attempt before requeue (`queue.py`, refreshed line 158). Source inspection confirms quota-only delays no longer accumulate toward the generic recovery limit. A dedicated prolonged-delay test should retain this behavior.

### D5 — P2: concurrent evaluation completions can overwrite each other

Source: [evaluations.py](../../services/platform-api/vp/evaluations.py), `record_evaluation`, reviewed lines 32–47; [api.py](../../services/platform-api/vp/api.py), `run_evaluation`, reviewed lines 965–987.

Evaluation cases execute in separate sessions, so their session locks do not serialize writes to the shared evaluation record. `record_evaluation` reads `run.body['results']`, merges one case locally, then replaces the JSON object without locking the run row. Two concurrent cases can both read an empty map and commit different one-entry maps; one result disappears and completion may remain `running`.

Recommendation: lock the evaluation record before reading/merging results, using a refreshed ORM value after lock acquisition, or store one uniquely keyed durable result per case and aggregate. Add a concurrent PostgreSQL completion test.

Remediation observed: `record_evaluation` now selects the shared run with `FOR UPDATE` and `populate_existing=True` (`evaluations.py`, refreshed lines 38–41). This serializes the read/merge/write on PostgreSQL. Independent concurrent PostgreSQL test evidence is not claimed by this audit.

### D6 — P1: DashScope client retry and endpoint configuration bypassed governance

Source: [providers.py](../../services/platform-api/vp/providers.py), DashScope and Gemini constructor branches; [AgentScope DashScope model](../../agentscope/src/agentscope/model/_dashscope/_model.py), reviewed lines 163–170.

The initially reviewed DashScope branch set AgentScope `max_retries=0` but did not forward that setting to the underlying OpenAI client. It also ignored a configured custom endpoint. Gemini similarly ignored its catalog endpoint. One platform reservation could therefore cover multiple underlying transport attempts, and a custom endpoint selection could silently send data to the default cloud instead.

Independent fake-key constructor probe, with no provider network request, initially returned `client_retries=2` and `custom_endpoint_used=False` for a DashScope catalog entry configured with a custom URL.

Remediation observed: DashScope now forwards `client_kwargs` containing retry/timeout settings and constructs its credential with the configured base URL. Gemini forwards its base URL through `HttpOptions`. The repeated DashScope constructor probe returned `client_retries=0` and `custom_endpoint_used=True`. The Gemini change was source-inspected; provider authentication and endpoint compatibility still require real-provider smoke acceptance.

## Corrections observed during the audit

### F1 — pinned model credential binding

The first reviewed `execute_agent` read a credential ID from the live model record while executing the pinned model snapshot. Editing the credential binding could silently move an old agent revision to a different provider account. The implementation was corrected during the audit: [runtime.py](../../services/platform-api/vp/runtime.py), reviewed lines 415–426, resolves `pinned['credential_id']` and checks credential workspace/kind.

An independent isolated SQLite probe froze an agent against `original-credential`, changed the live model to `new-credential`, intercepted `create_model` and observed:

```text
pinned_credential_id = original-credential
actual_credential_matches_pinned = True
```

This confirms binding selection after the fix; it does not assert any provider authentication or billing acceptance.

### F2 — execution owner revocation

Initially normal agent model calls checked the session owner's current membership, while external MCP jobs and indexing used lease fencing alone. The implementation added [queue.py](../../services/platform-api/vp/queue.py), `fence_for_execution`, reviewed lines 72–76, and changed runtime, knowledge, integration and Jev execution paths to import it.

The new guard combines lease/session validation with [domain.py](../../services/platform-api/vp/domain.py), `authorize_execution`, reviewed lines 122–128, rejecting missing/disabled users or memberships below operator. This was confirmed by source inspection; an independent revocation runtime test remains necessary. Revocation cannot undo an external call already sent before the administrative action.

## Existing guarantees supported by source

- [queue.py](../../services/platform-api/vp/queue.py), `claim`, uses PostgreSQL `FOR UPDATE SKIP LOCKED` and a generation/status predicate; `fence` locks the session then job and rejects expired leases, stale generations or wrong turns. Claims do not retain a job lock while asking for a session lock.
- [limits.py](../../services/platform-api/vp/limits.py), `reserve`/`reconcile`, uses integer micro-dollars and a locked workspace/month wallet. Missing usage is charged conservatively, and already reconciled reservations are not charged again. These are accounting estimates, not independently verified provider bills.
- [context.py](../../services/platform-api/vp/context.py), `build_context`, selects artifacts by session, current-turn inbox by recipient, and private verified memory by workspace/owner/agent. Source evidence is revalidated against revocation, expiration and private knowledge ownership through [domain.py](../../services/platform-api/vp/domain.py), `evidence_valid`.
- Context snapshots distinguish preparation, model submission, provider response and accepted result in [runtime.py](../../services/platform-api/vp/runtime.py). A prepared snapshot alone is not proof that a provider consumed its contents. Selected context and persisted SDK state are different objects; `sanitize_state` removes `thinking` blocks consistent with [AgentScope ThinkingBlock](../../agentscope/src/agentscope/message/_block.py).
- [knowledge.py](../../services/platform-api/vp/knowledge.py), `space_name`, includes workspace, adapter, endpoint, model, dimensions, catalog identity and version. Vector retrieval is followed by database ACL/source checks. This avoids treating vector-store matches as authorization.
- MCP uncertain writes are not automatically replayed. This is a deliberate at-most-once safety posture for non-idempotent external effects, with an explicit human-review outcome; it is not a claim of exactly-once effects.

## Recommended acceptance checks

1. PostgreSQL controlled lock interleaving for D1 and parallel evaluation commits for D5.
2. MCP endpoint/config change between request, approval and execution; assert no call occurs without renewed approval.
3. Crash after durable MCP success; assert one external call and eventual continuation.
4. Quota delays longer than three windows, then successful execution; separate crash-limit test.
5. Owner disabled or downgraded before indexed/model/MCP/Jev work starts; assert no charged or external call.
6. Pinned model/skill/config behavior across edits, plus private knowledge revocation and cross-session context isolation.
7. Provider constructors: underlying transport retries disabled, configured endpoint honored, output limits transmitted. These constructor checks must stay separate from billed provider smoke tests.

The main implementation agent received each high-impact finding during the audit. This note is an audit record rather than a release acceptance declaration; remediation and final test results should be tracked with the implementation's validation evidence.
