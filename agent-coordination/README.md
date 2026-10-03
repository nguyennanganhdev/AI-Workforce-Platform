# Coordination runtime

Python 3.12 (tested 3.12.3), AgentScope **2.0.9**. All dependencies are pinned in
`requirements.lock`; only this package/environment changes. Five SDK tests use a
stub model. No paid/live model request has been made.

From repository root:

```bash
python3 -m venv agent-coordination/.venv
agent-coordination/.venv/bin/python -m pip install -r agent-coordination/requirements.lock
agent-coordination/.venv/bin/python -m pip install --no-deps --no-build-isolation -e agent-coordination
agent-coordination/.venv/bin/python -m pytest -q agent-coordination
agent-coordination/.venv/bin/python -m main
```

If the host lacks `ensurepip` (as this workstation does), create the isolated venv,
download `https://bootstrap.pypa.io/get-pip.py` **inside `.venv`**, run it with
`.venv/bin/python3`, then install the lockfile. Do not install packages globally.
Editable installation needs pinned setuptools/wheel already in the lockfile.
Schema regeneration: `PYTHONPATH=agent-coordination/src
agent-coordination/.venv/bin/python agent-coordination/scripts/generate_room_schemas.py`.
The compatibility test runners now call standard pytest; no namespace preloading.

The service starts on `127.0.0.1:4300`. `/health` is process health; `/ready` is 503
without every required producer/storage/auth binding. Proposed Coordination routes
are `POST /v2/reception`, `POST /v2/events`, `POST /v2/contributions`,
`POST /v2/reports` and authenticated `POST /v2/report-downloads`; Platform must
register their actual mount. D07/D08 use Coordination consumer proposals, not
frozen backend C13/C14 wire contracts. Ingress uses `Authorization: Bearer <runtime service secret>` (minimum 32
characters). Backend verification/delegation separately authorizes source actors.
ACK 202 requires confirmed durable accept. V1 is rejected on new service ingress.
These routes are not invented backend Authority endpoints.

`COORDINATION_CONFIG` names a JSON file conforming to `config.ServiceConfig`.
`config.example.json` intentionally has no factory/model. Secrets are environment
references, never config values. Dev model overrides are rejected in production;
provider/model/allowlist/API/output/deadline/input limits are explicit. Provider
calls have no automatic retry/fallback, each repair uses a separate budget entry,
and config/budget hashes persist per run. There is no model default and no UI.
Openbot is still responsible for its runtime compatibility guard and effective
specialist model; Coordination cannot override the current Bot's global model.

A trusted factory `module:factory` calls `runtime.composition.build` with
`ProductionBindings` from allocated storage and evidenced backend operations.
`runtime.backend.ProducerOperations` requires explicit URL, source evidence,
request/response validators and producer wire encode/decode mappings. There are no
fake/default Authority decisions or operation-to-URL guesses. The producer must
supply all eight schemas required by `runtime.contracts.SchemaValidator`.
Current repo has no frozen mappings for Authority/drafts/releases/C13/C14, so
production assembly remains blocked. Do not set readiness flags to True based on
interfaces, source files or test fixtures. Factory paths in `tests`/`support` are
rejected. Signed proof creation/checking belongs to the backend delegation/tool
producer, not model output or local bearer authentication.

`persistence.sqlite.DevelopmentStore` is **development-only Coordination framework
storage**, explicitly rejects production and `:memory:`. It stores checkpoint,
Room/mailbox/tasks/action journal, dedup/inbox/receipts/release pins and quota ledger,
not ticket/approval/business state. It proves local file/process restart and lease
semantics, not production allocation, RPO/RTO or remote exactly-once. Platform must
implement the same ports in its allocated namespace; no shared business SQL or new
business DB/migration was added.

Only the Supervisor journal dispatches outgoing intents. The inbox worker carries
its lease via request context; stale leases cannot commit state/receipts. Network,
model, resolver and remote prepare calls are outside Room transactions. Child-run
prepare IDs are deterministic; backend must guarantee provisioning idempotency.
Unknown dispatch survives restart and reconciles the **current dispatch_attempt**;
not_applied requires producer fencing of the old sender. Openbot lacks durable
lookup/cancel/usage today: lost response blocks replay, cancel records a tombstone
and returns unconfirmed. RUN_FINISHED never grants business completion. Default
worker recovery is three attempts five seconds apart (development guard, not a
product SLA); exhausted jobs remain `blocked`, not ACKed. The worker renews its
lease during bounded network/model I/O, cancels local execution on renewal loss,
and cannot resurrect an expired/stolen lease. Shutdown drains for ten
seconds then cancels local tasks; remote outcomes remain unknown.

Recovery: inspect durable job/action/attempt metadata in the allocated test store;
ask producer for the current-attempt receipt/fence. Do not delete journal, rewrite
wire, generate a new operation ID or reuse an old not_applied proof. Local blocked
jobs need an authorized operator recovery contract from Platform; no unsafe reset
endpoint is exposed. Key rotation resolves env-backed credentials at call time;
request-scoped references must be renewed/reverified by Backend. Logs contain no
raw exception bodies, credentials or resident history; additional observability
and retention policy remain EXT-10.

D07 accepts only backend-verified staff/evidence and exact contribution hash,
submits review proposals idempotently and never acts as staff/reviewer/publisher.
D08 reads existing `agent-report` config/schema/template/prompt plus
`server/src/reporting/narrative/operations.py`, preserving missing vs zero and
metric provenance. Those artifacts must be mounted read-only in deployment via a
trusted repository/artifact root; Docker contains Coordination only. The metric
catalog retains `proposal_pending_DD07_C14_review`; it is not a published metric
release. Download rechecks producer permission; no public bucket/local file URL.
No new scheduler, UI, backend API or migration.

D07/D08 production factory injects `workflow_authority`, `contribution_producer`,
`report_producer` and `report_artifacts` in `ProductionBindings`. Each route checks
required producer methods before durable ACK. `runtime/workflow_ports.py` defines
consumer proposals; schemas and wire examples are documented in
`docs/teams/dong/workflow-proposals/README.md`. Backend revalidates exact original
wire, actor, source, generation/version and current worker fence, and issues
apply-bound delegated credentials. No credentials are stored in inbox payloads.
Records `put_once` must return True only to the atomic insert owner; identical
nonowners reconcile rather than applying again. Tool boundary requires producer
verification of both signed authorization and receipt before forwarding results.

On verified `work.completed`, Supervisor composition asks the C13 producer's
`staff_request_for_work` for a stable, real-source staff request (or explicit None
by backend policy), then durably enqueues it before work inbox ACK. Missing trigger
binding blocks that input when D07 is configured. The independent contribution
worker requests procedure/actual cost/evidence, submits staff-verified revisions,
observes backend review/reject/request-change/publish/revoke and never reopens or
rewrites the Supervisor terminal checkpoint. Corrections need backend permission
and exact predecessor revision. Actual cost is separate from estimate/model spend.

Report sequence: submit real source/config → prepare authorized snapshot → run
released Report instance → persist code-owned narrative through H09/H10 → export
canonical artifact → authenticated download. Snapshot/request/tenant/workspace,
metric/source lineage, as-of/hash and artifact/config pins are checked. Report
release must attest report capability and exact Report artifact hash. Model cannot
change canonical numbers/units/lineage; optional commentary remains advisory.
Cancel writes a scoped durable tombstone, prevents new run/result publication and
reconciles until backend cancellation confirmation; remote Openbot termination
remains unproven without EXT-05. Status retry returns the same receipt for the same
message ID; use a new real control message for a fresh status query. Download is
read-only authenticated response requiring artifact and report request identity,
bounded streaming to 10 MiB with checksum/revoke/deadline checks; producer must
yield bounded chunks without buffering upstream. bytes-only downloads fail closed.
Worker routes do not return file bytes or public/local URLs.

Offline evaluation now executes actual core safety validators:

```bash
agent-coordination/.venv/bin/python -m evaluation.runner --model-pin offline-no-model --release-pin offline-catalog-v1 --output docs/teams/dong/COORDINATION_OFFLINE_EVALUATION.json
```

Eight guard cases have individual pass/fail checks. Output pins dataset and tested
source hashes, mode, model/release labels, cost unknown and `live_status: NOT RUN`.
This measures hard guards, not LLM domain selection quality. To score supplied
recorded decisions, add `--observations <json-file>`: object keyed by dataset case
ID, each containing `state`, `authority`, `decision`, and explicit `effects` list.
Capabilities are resolved from the supplied catalog, decisions use the actual
Planner validator, forbidden effects/missing cases/evidence fail; exit status is
nonzero on failure. Recorded observations are supplied offline evidence, not live
verification. Paid evaluation still requires explicit credentials/budget.

See the three handoff reports under `docs/teams/dong`. V1 migration and accepting
processing after completed are **deferred**. No deployment or Git mutation beyond
local file editing is part of these instructions.

Hardening H0–H6 now has an independent review and executable local/live preflight:
`docs/teams/dong/COORDINATION_HARDENING_REVIEW.md` and
`docs/teams/dong/COORDINATION_LIVE_TEST_RUNBOOK.md`. Docker installs the actual
package; evaluation JSON is included in wheel/sdist. Production ReportArtifacts
requires an approved expected hash, optionally from COORDINATION_REPORT_ROOT /
COORDINATION_REPORT_HASH; only tests explicitly use development=True. Deferred
source ACK belongs to the composed worker after D07 policy decision/enqueue.

Monetary limits are not remote billing guarantees. Provider hard_cost_required is
rejected without tokenizer/price-bound attestation; Openbot monetary-cap budgets
fail before network because current Bot ignores release output_tokens and has no
usage receipt. Local call/continuation/deadline limits retain unknown reservations.
Live examples default approved=false; real execution needs explicit permission
and confirmed provider budget/account policy, never just a present key. L2/L3
preflight remains contract-blocked. Ingress token rotation needs process restart;
provider/released runtime credential references resolve at call time.

## Vinhomes composition (`src/vinhomes`, added 03/10/2026 by Team Chiến)

A second composition next to `runtime.composition`, for the Vinhomes business API. It does
not change the Supervisor or group chat cores. Instead of waiting for a platform factory to
push into `/v2/reception`, it pulls the backend's durable V2 inbox and binds the Supervisor
to `/internal/coordination/v1` (services/vinhomes-api, `v3_coordination.py`).

```sh
python -m venv .venv            # Python 3.12; then pip install -r requirements.lock
scripts/start_vinhomes.ps1      # add -Connected for the password-login backend
```

Settings in `agent-coordination/.env`: `COORDINATION_BACKEND_URL` and
`COORDINATION_SERVICE_TOKEN` (equal to the backend's `VINHOMES_API_COORDINATION_SERVICE_TOKEN`).
Port 4300 serves `/health`, `/ready` and `/sessions`.

Bound today: Reception hands a ticket over, the backend verifies it and allocates the
session binding and agent run, the Supervisor creates a durable checkpoint and sends
`accepted`. Not bound: rooms and specialists, the planner model, backend actions, drafts and
backend events. Their ports refuse (`dependency_unavailable:*`), and because no specialist is
published the session pauses with `planner:no_specialist_available` and management continues
by hand. Storage is `persistence.sqlite.DevelopmentStore` (one host). Tests:
`tests/vinhomes` (11). On Windows run pytest with `PYTHONUTF8=1`.

Contract table, acceptance matrix and open questions:
`docs/teams/chien/SUPERVISOR_SESSION_V2_M0_M1_2026-10-03.md`.
