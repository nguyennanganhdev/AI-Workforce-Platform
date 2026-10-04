# Coordination runtime

Python 3.12, AgentScope **2.0.9**. Runtime and test dependencies are pinned in
`requirements.lock`; keep this environment separate from the other teams.

From repository root:

```bash
python3.12 -m venv agent-coordination/.venv
agent-coordination/.venv/bin/python -m pip install -r agent-coordination/requirements.lock
agent-coordination/.venv/bin/python -m pip install --no-deps --no-build-isolation -e agent-coordination
agent-coordination/.venv/bin/python -m pytest -q agent-coordination
agent-coordination/.venv/bin/python -m main
```

## Configuration and production dependencies

`COORDINATION_CONFIG` points to a JSON file validated by `config.ServiceConfig`.
Start from `config.example.json`. Credentials are environment references, never
literal config values; the service does not automatically load `.env`.
`COORDINATION_INGRESS_TOKEN` requires at least 32 characters. Bindings separately
verify source actors and delegation; this bearer token does not grant business
authority. No implicit model or production factory is supplied.

A trusted `module:factory` assembles `runtime.composition.build` with
`ProductionBindings`: allocated storage, Authority/event verifier, Reception
authentication, published agent/group resolver, released OpenBot sessions,
tool grants, Supervisor model/budget, delegation, worker authentication and
producer readiness. Factories in `tests` or `support` are rejected.
`runtime.backend.ProducerOperations` requires evidenced routes and explicit wire
encode/decode mappings. `runtime.contracts.SchemaValidator` requires all eight
pinned producer schemas. Interfaces and test fixtures do not establish readiness.

The service defaults to `127.0.0.1:4300`. `/health` checks process health;
`/ready` stays 503 until required bindings are ready. Proposed routes are
`POST /v2/reception`, `/v2/events`, `/v2/contributions`, `/v2/reports`, and
`/v2/report-downloads`; Platform owns their deployment mount. Durable acceptance
must be confirmed before HTTP 202. New ingress rejects V1.

Production producer mappings, canonical backend schemas, published agent resolver
and allocated storage remain external integration dependencies. C13 contribution
and C14 report ports are consumer proposals, not frozen backend endpoints.
Unbound workflows fail closed. Do not mark the full business flow ready based on
local unit tests. Backend owns approvals, staff assignment, QC and ticket closure;
`RUN_FINISHED` alone is not business completion.

## Checkpoints and recovery

`persistence.sqlite.DevelopmentStore` is isolated development framework storage;
it rejects production and `:memory:`. It is not a business database. Platform must
provide equivalent checkpoint/CAS, records, inbox/lease and receipt semantics.
Only the Supervisor action journal dispatches outgoing intents. Network/model
calls and resolver preparation stay outside Room transactions.

Worker claims carry a monotonically increasing fencing token and an independent,
durable `recovery_attempts` count. Normal `Continuation` yields preserve that count.
Recovery deferrals increment it atomically with the scheduling update; takeover of
an expired owner also counts abandoned work. The development store uses the
existing `records` namespace `inbox_recovery_count`, so old stores need no new SQL
column. Production inbox adapters must expose `claim.recovery_attempts` and support
`defer(claim, seconds, recovery=True)` with the same fenced atomic semantics.
Default recovery stops after three attempts, five seconds apart; exhausted jobs
stay `blocked` and are never successfully ACKed. Counters survive worker restart.

Unknown remote dispatch must reconcile its original operation/attempt; it must
not be blindly replayed under a fresh identity. OpenBot durable lookup/cancel/usage
remains a producer dependency. Inspect the current receipt/fence before operator
recovery; do not delete the journal or fabricate a not-applied proof. Worker lease
renewal prevents stale writes, and shutdown drains for ten seconds before local
cancellation. Remote cancellation requires producer confirmation.

V1 checkpoint migration and same-generation processing after `completed` remain
deferred. Coordinate rollout with Reception/Backend and drain or explicitly
reconcile old pending requests before enabling V2; do not reinterpret old replies
as new approvals. Reopened tickets use backend-issued generations.

## Report and contribution integration

D07 accepts backend-verified staff/source/evidence and keeps actual cost separate
from model spend. A verified `work.completed` queues the producer's stable staff
request before inbox ACK. Agent output cannot approve or publish contributions.

D08 binds `report_producer` and verified `ReportArtifacts`. Mount the existing
Report schema/config/template/prompt and narrative implementation read-only;
`COORDINATION_REPORT_ROOT` and `COORDINATION_REPORT_HASH` select an approved bundle.
Room turns and mentions persist its hash in `ActiveOperation`; released sessions
must attest the same hash. Snapshot/export/download permissions remain producer
controlled. Downloads are authenticated, bounded and checked for revocation;
no public bucket or local file URLs are returned.

## Contract regeneration and evaluation

Regenerate the published room contracts using the pinned environment:

```bash
PYTHONPATH=agent-coordination/src agent-coordination/.venv/bin/python agent-coordination/scripts/generate_room_schemas.py
```

Contract tests read the published JSON files and compare them with runtime models.
They must not replace published contracts with dynamically generated schemas.

Offline guards exercise the real safety validators, with synthetic business data:

```bash
agent-coordination/.venv/bin/python -m evaluation.runner --model-pin offline-no-model --release-pin offline-catalog-v1 --output /tmp/coordination-evaluation.json
```

Add `--observations <json-file>` to score supplied recorded decisions: an object
keyed by dataset case ID, each with `state`, `authority`, `decision`, and an explicit
`effects` list. Missing cases/evidence, wrong specialties and forbidden effects
fail with a nonzero exit status. Results pin dataset/source hashes and model/release
labels, with `live_status: NOT RUN` and unknown cost. Offline guards measure safety,
not live model quality. `tests/live/l1.py` retains the ProviderModel-to-Planner
harness with simulated business bindings; paid execution requires explicit
credentials, budget and authorization. No live command or automatic paid run is
configured by this package.

## Vinhomes composition (`src/vinhomes`, added 03/10/2026 by Team Chiến)

A second composition next to `runtime.composition`, for the Vinhomes business API. It does
not change the Supervisor or group chat cores. Instead of waiting for a platform factory to
push into `/v2/reception`, it pulls the backend's durable V2 inbox and binds the Supervisor
to `/internal/coordination/v1` (services/vinhomes-api, `v3_coordination.py`).

```sh
# Python 3.12 venv with requirements.lock and the package itself, as described at the top.
scripts/start_vinhomes.ps1      # add -Connected for the password-login backend
```

Settings in `agent-coordination/.env`: `COORDINATION_BACKEND_URL` and
`COORDINATION_SERVICE_TOKEN` (equal to the backend's `VINHOMES_API_COORDINATION_SERVICE_TOKEN`).
Port 4300 serves `/health`, `/ready` and `/sessions`.

For specialists, also `COORDINATION_MODEL` (the planner model), `COORDINATION_OPENBOT_URL` and
`MANAGED_AGENT_TOKEN`; the model key is read from `agent-reception/.env`. The OpenBot is
`agent-bot`: `scripts/start_openbot.ps1` starts it on 4200. Without these the Supervisor
accepts a ticket and hands it to management, as before.

Bound today: Reception hands a ticket over, the backend verifies it and allocates the
session binding and agent run, the Supervisor creates a durable checkpoint and sends
`accepted`. It then opens a room with the specialists the backend offers for the ticket's
category (published, in the management room), gives them tasks, runs their turns on OpenBot
with the agent's published instructions, and mirrors tasks and replies to the backend for
management to read. When every task is done the planner is asked for a plan only (`PLAN_GUIDE`);
the backend stores it in its plan table with the Supervisor as author (`Plans`), the Supervisor
confirms it waits for management (`BackendActions`), and the session stays in `waiting_management`.
A model that writes no plan leaves the session paused with `planner:analysis_ready`.

A specialist's tool call goes through `ToolGateway` to the technical tool host
(`server/src/technical-api/serve.ts`, port 8788; `COORDINATION_TOOLS_URL`, `COORDINATION_TOOLS_TOKEN`).
The host decides from the agent run of the turn what the call may do; only read tools are open.

Not bound: what follows management's decision (backend events, the resident's approval through
Reception), resident questions, summaries, assignments, and tools that write. Their ports refuse
(`dependency_unavailable:*` or `operation_not_configured`). Storage is
`persistence.sqlite.DevelopmentStore` (one host). Tests: `tests/vinhomes` (24). On Windows run
pytest with `PYTHONUTF8=1`.

`scripts/publish_agent.ps1` takes an agent definition through the platform's flow: draft,
evaluation on OpenBot, admin review (`docs/teams/quang/agent/`).

What this composition wraps instead of changing in the cores, for Team Đông to review:
`ProviderModel` cannot call `gpt-5.4-mini` (`max_tokens`, exact model-name match), so
`vinhomes.ports.PlannerModel` is used; `OpenbotAdapter` sends no agent instructions and reads
only a JSON reply, so `InstructedClient` adds the instructions and builds the reply object from
the Bot's plain text and lets the stream stay quiet while a reasoning model thinks (the shared
client's 5 s read timeout cut `gpt-5.5` turns short); one specialist may take consecutive turns
(`TURNS`); the plan's `result_refs` are filled from the session, not taken from the model.

Contract tables, acceptance matrix and open questions:
`docs/teams/chien/SUPERVISOR_SESSION_V2_M0_M1_2026-10-03.md`,
`docs/teams/chien/SUPERVISOR_SESSION_V2_M2_2026-10-04.md`, for tools
`docs/teams/chien/TOOL_GATEWAY_VA_KHAO_SAT_NHANH_2026-10-04.md`, and for plans
`docs/teams/chien/SUPERVISOR_PHUONG_AN_M3A_2026-10-04.md`.
