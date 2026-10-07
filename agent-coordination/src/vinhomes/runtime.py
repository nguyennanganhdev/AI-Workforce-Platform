"""The Supervisor service for the Vinhomes business API: inbox poller, worker, status.

Run from agent-coordination/:  python -m vinhomes     (settings: see Settings.from_env)

The backend's V2 inbox is the source. Each poll copies new messages into this runtime's own
durable inbox, so a message survives a restart between "read" and "handled", and reading the
inbox is never taken as having handled it. One worker then handles one message at a time under
a lease: verify with the backend, create or load the session checkpoint, let the Supervisor
continue, and report what the session is now waiting for.

When a planner model and an OpenBot are configured, the Supervisor opens a room with the
specialists the backend offers for the ticket, gives them tasks and runs their turns. What the
room holds is mirrored to the backend after every step so management can read it. When every
task is done the Supervisor proposes a plan, the backend stores it with the Supervisor as its
author, and the session waits for management's decision.

Storage is team Đông's development store (a SQLite file on this host). It keeps checkpoints,
rooms, the inbox and the cursor across restarts, and it is not shared between hosts.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from adapters.backend.errors import AdapterError
from adapters.backend.events import PendingDelivery
from adapters.backend.messages import fingerprint
from groupchat.models import CloseRoom, Command, Context, MentionAgent, Success, TurnPolicy
from groupchat.models import RoomData
from groupchat.room import RoomService
from persistence.budget import ScopedBudgets
from persistence.sqlite import DevelopmentStore
from runtime.publication import DraftPublisher
from supervisor.models import SupervisorError, SupervisorState
from supervisor.planner import Planner
from supervisor.room_bridge import RoomBridge
from supervisor.service import SupervisorService

from .backend import Backend, Refused
from .models import model_endpoint
from .ports import (Authority, BackendActions, BackendEvents, OpenBot, PlannerModel, Plans, Reception, Releases, Resolver,
                    Specialists, ToolGateway, UnboundInvocation)

log = logging.getLogger("coordination.vinhomes")
LEASE_SECONDS = 60
RETRY_SECONDS = 15  # the backend could not be reached: try the same message again
SETTLE_SECONDS = 5  # an action is in flight or unknown: reconcile it on the next round
SETTLE_ATTEMPTS = 3  # after that an unknown outcome waits for a person instead of being asked again
MAX_STEPS = 40  # decisions and dispatches per message: open, tasks, turns and a plan fit well inside
TURN_RETRIES = 2  # a turn that failed for certain is planned again this many times before a person is needed
# A session that stopped because the model could not be reached runs again on its own: after a
# minute, then each time after as long as it has been failing so far, for two hours. After that
# it waits for management to resume it, as it always did.
MODEL_PAUSES = ("model_unavailable", "model_timeout")
MODEL_RETRY_FIRST, MODEL_RETRY_LIMIT = 60, 7200
# A category's room often has one specialist, so the same agent may speak several times in a row.
TURNS = TurnPolicy(max_turns=8, max_consecutive_turns=8, timeout_seconds=150)


@dataclass(frozen=True)
class Settings:
    backend_url: str
    service_token: str = field(repr=False)
    state_path: str = ".coordination-state/coordination.sqlite3"
    host: str = "127.0.0.1"
    port: int = 4300
    poll_seconds: float = 2.0
    # The planner model and the OpenBot specialists run on. Both or neither: without them the
    # Supervisor accepts a ticket and hands it to management.
    model: str | None = None
    model_base_url: str = "https://api.openai.com/v1"
    model_provider: str = "openai"
    model_key: str = field(default="", repr=False)
    # The name the provider answers with, when it is not the configured name or a dated form of it.
    model_answers_as: str | None = None
    openbot: OpenBot | None = None
    token_limit: int = 400_000  # per session, in the ledger's conservative units
    # The technical tool host for specialists (server/src/technical-api/serve.ts). Optional:
    # without it a specialist that asks for a tool gets a failed turn.
    tools_url: str | None = None
    tools_token: str = field(default="", repr=False)
    database_url: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> Settings:
        url = os.getenv("COORDINATION_BACKEND_URL", "").strip()
        token = os.getenv("COORDINATION_SERVICE_TOKEN", "").strip()
        if len(token) < 32 or not url.startswith(("http://", "https://")):
            raise ValueError("COORDINATION_BACKEND_URL and COORDINATION_SERVICE_TOKEN (32+ characters) are required")
        model = os.getenv("COORDINATION_MODEL", "").strip() or None
        bot = os.getenv("COORDINATION_OPENBOT_URL", "").strip()
        if bool(model) != bool(bot):
            raise ValueError("COORDINATION_MODEL and COORDINATION_OPENBOT_URL are set together or not at all")
        provider, base_url, key = model_endpoint("COORDINATION")
        if model and not (key and os.getenv("MANAGED_AGENT_TOKEN")):
            raise ValueError("The planner's key (COORDINATION_MODEL_API_KEY, or OPENAI_API_KEY for OpenAI) and "
                             "MANAGED_AGENT_TOKEN are required with COORDINATION_MODEL")
        tools = os.getenv("COORDINATION_TOOLS_URL", "").strip() or None
        tools_token = os.getenv("COORDINATION_TOOLS_TOKEN", "").strip()
        if tools and len(tools_token) < 32:
            raise ValueError("COORDINATION_TOOLS_TOKEN (32+ characters) is required with COORDINATION_TOOLS_URL")
        return cls(backend_url=url, service_token=token, model=model,
                   model_base_url=base_url, model_provider=provider, model_key=key,
                   model_answers_as=os.getenv("COORDINATION_MODEL_ANSWERS_AS", "").strip() or None,
                   openbot=OpenBot(bot, os.getenv("COORDINATION_OPENBOT_MODEL", "").strip() or model) if bot else None,
                   token_limit=int(os.getenv("COORDINATION_TOKEN_LIMIT", "") or cls.token_limit),
                   tools_url=tools, tools_token=tools_token,
                   database_url=os.getenv("COORDINATION_DATABASE_URL", "").strip() or None,
                   state_path=os.getenv("COORDINATION_STATE_PATH", "").strip() or cls.state_path,
                   host=os.getenv("COORDINATION_HOST", "").strip() or cls.host,
                   port=int(os.getenv("COORDINATION_PORT", "") or cls.port),
                   poll_seconds=float(os.getenv("COORDINATION_POLL_SECONDS", "") or cls.poll_seconds))


class Store(DevelopmentStore):
    """Team Đông's development store, plus where this runtime is in the backend's inbox."""

    def __init__(self, path, **options):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(path, **options)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS cursors (name TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def cursor(self) -> str | None:
        with self.connection() as db:
            row = db.execute("SELECT value FROM cursors WHERE name='inbox'").fetchone()
        return row[0] if row else None

    def save_cursor(self, value: str) -> None:
        with self.atomic() as db:
            db.execute("INSERT OR REPLACE INTO cursors VALUES ('inbox',?)", (value,))

    def sessions(self) -> list[dict]:
        """One line per session for operators: identifiers and state, no resident text."""
        with self.connection() as db:
            rows = db.execute("SELECT body FROM checkpoints WHERE kind='supervisor' ORDER BY rowid").fetchall()
            blocked = db.execute("SELECT COUNT(*) FROM inbox WHERE status='blocked'").fetchone()[0]
        sessions = []
        for (body,) in rows:
            state = SupervisorState.model_validate_json(body)
            sessions.append({
                "ticket_id": state.context.ticket_id, "ticket_generation": state.context.ticket_generation,
                "ticket_code": state.reception.ticket_code if state.reception else None,
                "run_id": state.supervisor_run_id, "phase": state.phase, "pause_reason": state.pause_reason,
                "checkpoint_version": state.version, "actions_done": [a.operation for a in state.journal],
                "action_in_flight": state.action.status if state.action else None})
        return [{"blocked_inbox_items": blocked}, *sessions] if blocked else sessions


class Runtime:
    def __init__(self, backend: Backend, store: Store, *, owner: str | None = None,
                 client: httpx.AsyncClient | None = None, settings: Settings | None = None):
        self.backend, self.store, self.owner = backend, store, owner or str(uuid4())
        self.client = client
        self.settings = settings
        self.teams: dict[tuple, str] = {}  # scope -> team, known once the backend verified a message
        self.recovered = False  # sessions paused for the model before this start were queued for their retry
        self.model_hold = 0.0  # no session asks the model again before this time: it has just failed one of them

        async def group_pin(context):
            return await authority.group_pin(context, self.teams[context.scope()])

        budget = ScopedBudgets(store, token_limit=settings.token_limit if settings else Settings.token_limit)
        tools = ToolGateway(client, settings.tools_url, settings.tools_token) if settings and settings.tools_url else None
        self.releases = Releases(backend, self.teams, settings.openbot) if settings and settings.openbot else None
        specialists = (Specialists(self.releases, store, budget, client, tools=tools)
                       if self.releases else UnboundInvocation("agent_invocation"))
        async def instructions(context):
            return (await backend.view(self.teams[context.scope()])).get('supervisor_instructions', '')
        model = PlannerModel(budget, client, model=settings.model if settings else None,
                             base_url=settings.model_base_url if settings else Settings.model_base_url,
                             key=settings.model_key if settings else None,
                             provider=settings.model_provider if settings else "openai",
                             answers_as=settings.model_answers_as if settings else None,
                             instruction_loader=instructions,
                             config_loader=backend.model_config if hasattr(backend, 'model_config') else None)
        # The planner also judges, once per session, which other departments a request needs.
        authority = Authority(backend, store=store, invite=model.invited)
        self.rooms = RoomService(Resolver(backend, self.teams), specialists, store)
        self.service = SupervisorService(
            store=store, authority=authority, verifier=BackendEvents(backend),
            event_types={"approval.responded": "approval.responded"},
            planner=Planner(model), reception=Reception(backend),
            room=RoomBridge(self.rooms),
            backend=BackendActions(backend, self.teams), publisher=DraftPublisher(Plans(backend, self.teams)),
            groupchat_version_id="vinhomes-supervisor",
            groupchat_resolver=group_pin, max_steps=MAX_STEPS, turn_policy=TURNS)

    async def poll(self) -> int:
        """Copy what is new in the backend's inbox into the durable local inbox."""
        cursor = self.store.cursor()
        page = await self.backend.inbox(cursor)
        for item in page["items"]:
            message = item["message"]
            key = json.dumps((message["tenant_id"], "reception", message["message_id"]), separators=(",", ":"))
            await self.store.accept(key, {"kind": "reception", "wire": message, "team_id": item["team_id"]})
        if page.get("next_cursor") and page["next_cursor"] != cursor:
            self.store.save_cursor(page["next_cursor"])
        # Questions management asked a specialist inside a session. The backend lists one until its
        # outcome is reported; the local inbox takes each once.
        for item in (await self.backend.mentions())["items"]:
            key = json.dumps((item["context"]["tenant_id"], "mention", item["message_id"]), separators=(",", ":"))
            await self.store.accept(key, {"kind": "mention", **item})
        for item in (await self.backend.events())["items"]:
            key = json.dumps((item["event"]["tenant_id"], "event", item["event"]["event_id"]), separators=(",", ":"))
            await self.store.accept(key, {"kind": "management", **item})
        for item in (await self.backend.controls())["items"]:
            key = json.dumps((item["context"]["tenant_id"], "control", item["command"]["request_id"]), separators=(",", ":"))
            await self.store.accept(key, {"kind": "control", **item})
        if hasattr(self.backend, 'session_mentions'):
            for item in (await self.backend.session_mentions())['items']:
                key = json.dumps((str(item['tenant_id']), 'session-mention', str(item['message_id']), item['agent_id']))
                await self.store.accept(key, {'kind': 'session-mention', **item})
        if hasattr(self.backend, 'room_mentions'):
            for item in (await self.backend.room_mentions())['items']:
                key = json.dumps((str(item['tenant_id']), 'room-mention', str(item['message_id']), item['agent_id']))
                await self.store.accept(key, {'kind': 'room-mention', **item})
        return len(page["items"])

    async def handle(self, claim) -> float | None:
        """One message, from verification to whatever the session now waits for."""
        if claim.payload["kind"] == "mention":
            return await self.answer(claim.payload)
        if claim.payload["kind"] == "management":
            return await self.management_decision(claim.payload)
        if claim.payload["kind"] == "control":
            return await self.control_session(claim.payload)
        if claim.payload['kind'] in ('room-mention', 'session-mention'):
            return await self.answer_room(claim.payload)
        if claim.payload["kind"] == "model-retry":
            return await self.retry_session(claim.payload)
        wire, team = claim.payload["wire"], claim.payload["team_id"]
        self.teams[(wire["tenant_id"], wire["ticket_id"], wire["ticket_generation"])] = team
        held = next((s for s in self.store.sessions() if s.get("ticket_id") == wire["ticket_id"]
                     and s.get("ticket_generation") == wire["ticket_generation"]), None)
        if held and held["phase"] == "paused" and held["pause_reason"] == "management_pause":
            return RETRY_SECONDS
        try:
            state = await self.service.handle_reception(wire, team)
        except Refused as error:
            if error.status != 409:
                raise
            # The team finished, or the ticket moved to a new generation, before this message was
            # handled. The backend still holds the message; there is nothing left to do with it here.
            log.info("obsolete message for ticket=%s: the team is no longer current", wire["ticket_id"])
            return None
        if wire["message_type"] in ("plan_rejected", "plan_change_requested"):
            current = await self.backend.view(team)
            if state.ticket_version != current["ticket_version"]:
                previous = state.version
                state.ticket_version, state.version = current["ticket_version"], previous + 1
                if not await self.store.commit(state, previous):
                    raise SupervisorError("state_conflict")
        # The resident's committed approval already queued the work orders in the business API.
        # Staff allocation stays with management; do not invent or offer an assignment here.
        if wire["message_type"] != "plan_approved":
            state = await self.service.resume(state.context)
        for _ in range(TURN_RETRIES):
            if not (state.phase == "paused" and state.pause_reason in ("AGENT_FAILURE", "AGENT_TIMEOUT")):
                break
            # The turn is known to have failed. The Supervisor's own recovery asks the planner again.
            state = await self.service.resume(state.context)
        log.info("session ticket=%s generation=%s phase=%s reason=%s checkpoint=%s", state.context.ticket_id,
                 state.context.ticket_generation, state.phase, state.pause_reason, state.version)
        await self.retry_later(state, team)
        try:
            await self.backend.status(team, state.phase, state.pause_reason, state.version)
            if state.room is not None:
                await self.mirror(team, state.room, state.terminal_results.values())
        except AdapterError as error:
            log.warning("session not reported for ticket=%s: %s", state.context.ticket_id, error.code)
        if state.action and state.action.status in ("sending", "unknown", "accepted"):
            return SETTLE_SECONDS
        return None

    async def retry_later(self, state: SupervisorState, team: str, first: int | None = None) -> None:
        """Queue one more run of a session the model failed. `first`: the checkpoint at which it first failed."""
        if state.phase != "paused" or state.pause_reason not in MODEL_PAUSES:
            return
        # A provider that is down or rate-limiting fails every session alike: the others wait instead of
        # each spending a call to find out.
        self.model_hold = self.store.clock() + MODEL_RETRY_FIRST
        await self.run_again(state, team, first)

    async def run_again(self, state: SupervisorState, team: str, first: int | None = None) -> None:
        context = state.context
        key = json.dumps((context.tenant_id, "model-retry", context.ticket_id, context.ticket_generation, state.version),
                         separators=(",", ":"))
        try:
            await self.store.accept(key, {"kind": "model-retry", "context": context.model_dump(mode="json"), "team_id": team,
                                          "version": state.version, "first": first or state.version, "key": key})
        except AdapterError as error:
            if error.code != "conflict":
                raise
            # Already queued for this checkpoint, by the run that failed it: after a restart it is found again.

    async def noted(self, namespace: str, key: str) -> float:
        """The time this was first seen, kept across restarts."""
        held = await self.store.get(namespace, key)
        if held is None:
            held = {"at": self.store.clock()}
            await self.store.put_once(namespace, key, held)
        return held["at"]

    async def retry_session(self, item: dict) -> float | None:
        """Run a session again: one paused for the model once its wait is over, or one left mid-work."""
        context, team = Context.model_validate(item["context"]), item["team_id"]
        self.teams[context.scope()] = team
        state = await self.store.load(context)
        if state is None:
            return None
        if await self.store.get("model_retry_started", item["key"]) is None:
            if state.version != item["version"]:
                return None  # management resumed or stopped it, or it moved on
            if state.phase == "paused":
                if state.pause_reason not in MODEL_PAUSES:
                    return None
                streak = json.dumps((context.tenant_id, context.ticket_id, context.ticket_generation, item["first"]),
                                    separators=(",", ":"))
                # When the model first failed this session, and when this attempt was queued.
                since, seen = await self.noted("model_retry_since", streak), await self.noted("model_retry_seen", item["key"])
                now = self.store.clock()
                if now - since > MODEL_RETRY_LIMIT:
                    log.warning("session ticket=%s still has no model after %s seconds: it waits for management",
                                context.ticket_id, MODEL_RETRY_LIMIT)
                    return None
                if now < max(self.model_hold, seen + max(MODEL_RETRY_FIRST, seen - since)):
                    return RETRY_SECONDS
                previous = state.version
                state.phase, state.pause_reason, state.resume_phase = state.resume_phase or "planning", None, None
                state.version = previous + 1
                if not await self.store.commit(state, previous):
                    raise SupervisorError("state_conflict")
            elif state.phase != "planning":
                return None
            # From here the session is this item's to finish: a restart or an action still in flight
            # brings the item back, and it goes on instead of finding the checkpoint "moved on".
            await self.store.put_once("model_retry_started", item["key"], {"at": self.store.clock()})
        state = await self.service.resume(context)
        log.info("session ticket=%s ran again: phase=%s reason=%s", context.ticket_id, state.phase, state.pause_reason)
        await self.retry_later(state, team, item["first"])
        await self.backend.status(team, state.phase, state.pause_reason, state.version)
        if state.room is not None:
            await self.mirror(team, state.room, state.terminal_results.values())
        if state.action and state.action.status in ("sending", "unknown", "accepted"):
            return SETTLE_SECONDS
        return None

    async def recover_sessions(self) -> None:
        """What a stopped process left behind: sessions the model failed get their retry, and a session
        that was mid-planning, with no message left to drive it, is taken up again."""
        with self.store.connection() as db:
            rows = db.execute("SELECT body FROM checkpoints WHERE kind='supervisor' ORDER BY rowid").fetchall()
        for (body,) in rows:
            state = SupervisorState.model_validate_json(body)
            if state.reception is None:
                continue
            if state.phase == "planning" and state.pause_reason is None:
                await self.run_again(state, state.reception.team_id)
            else:
                await self.retry_later(state, state.reception.team_id)
        self.model_hold = 0.0  # nothing failed in this process yet

    async def answer_room(self, item: dict) -> None:
        message, agent = str(item['message_id']), item['agent_id']
        key = json.dumps((str(item['tenant_id']), message, agent))
        session = item.get('kind') == 'session-mention'
        async def outcome(result):
            if session:
                return await self.backend.session_outcome(str(item['team_id']), message, result)
            return await self.backend.room_outcome(message, agent, result)
        result = await self.store.get('room_mention_result', key)
        if result is None:
            snapshot = await self.backend.session_turn(str(item['team_id']), message) if session else await self.backend.room_turn(message, agent)
            if snapshot.get('refused'):
                return None
            # Persist intent before billing. An interrupted generation is marked failed and
            # needs a new explicit question; it is never silently generated a second time.
            started = await self.store.put_once('room_mention_intent', key, snapshot['run_id'])
            result = {'run_id': snapshot['run_id'], 'status': 'failed', 'content': ''}
            if started and self.settings and self.settings.openbot:
                from .publish import answer
                async def tool(name, arguments):
                    return await self.backend.room_tool(snapshot['run_id'], name, arguments)
                try:
                    async with asyncio.timeout(150):
                        content, _ = await answer(self.client, snapshot['instructions'], {
                            'name': key, 'instruction': snapshot['instruction'], 'ticket': snapshot.get('ticket', {}),
                            'messages': snapshot['messages'], 'images': snapshot.get('images', []),
                            'workspace': snapshot.get('workspace')}, snapshot['tools'], {},
                            endpoint=self.settings.openbot.endpoint, token=os.environ[self.settings.openbot.token_env],
                            invoke_tool=tool, model_config=snapshot.get('model_config'))
                    result.update(status='done', content=content[:20000])
                except (AdapterError, ValueError, httpx.HTTPError, TimeoutError) as error:
                    # The reason, never the content: which step gave up decides what to fix.
                    log.warning('room agent turn failed: message=%s reason=%s', message,
                                getattr(error, 'code', None) or type(error).__name__)
            await self.store.put_once('room_mention_result', key, result)
        try:
            await outcome(result)
        except Refused as error:
            if error.status not in (403, 404, 409) or result['status'] != 'done':
                raise
            # A revocation during model execution refuses publication; close the run as
            # failed so later questions do not inherit an abandoned active binding.
            await outcome({**result, 'status': 'failed', 'content': ''})
        return None

    async def management_decision(self, item: dict) -> float | None:
        context, team, event = Context.model_validate(item["context"]), item["team_id"], item["event"]
        self.teams[context.scope()] = team
        state = await self.store.load(context)
        if state is None:
            raise AdapterError("session_checkpoint_missing")
        if state.phase == "paused" and state.pause_reason == "management_pause":
            return RETRY_SECONDS
        # Settle an earlier dispatch before applying an event; never change an in-flight action.
        if state.action is not None:
            state = await self.service.resume(context)
            if state.action is not None:
                return SETTLE_SECONDS
        delivery = PendingDelivery(event["tenant_id"], event["event_id"], fingerprint(event), "supervisor",
                                   "approval.responded", item["context"], event)
        state = await self.service.handle_delivery(delivery, team, acknowledge=False)
        if event["payload"]["decision"] != "approve" and state.phase == "planning":
            # A committed refusal advances the backend ticket. The next proposal is based on
            # that new version; an approval keeps the old version until pending() binds the ask.
            current = await self.backend.view(team)
            if state.ticket_version != current["ticket_version"]:
                previous = state.version
                state.ticket_version, state.version = current["ticket_version"], previous + 1
                if not await self.store.commit(state, previous):
                    raise SupervisorError("state_conflict")
        state = await self.service.resume(context)
        await self.backend.status(team, state.phase, state.pause_reason, state.version)
        if state.room is not None:
            await self.mirror(team, state.room, state.terminal_results.values())
        if state.action is not None and state.action.status in ("sending", "unknown", "accepted"):
            return SETTLE_SECONDS
        await self.backend.decision_delivered(team, item["plan_id"])
        return None

    async def control_session(self, item: dict) -> None:
        context, team, command = Context.model_validate(item["context"]), item["team_id"], item["command"]
        request = command["request_id"]
        record_key = json.dumps((context.tenant_id, team, request), separators=(",", ":"))
        self.teams[context.scope()] = team
        result = await self.store.get("control_result", record_key)
        if result is None:
            verified = await self.backend.control(team, request)
            original = {k: verified["command"][k] for k in command}
            if original != command or Context.model_validate(verified["context"]) != context:
                raise AdapterError("verified_control_mismatch")
            state = await self.store.load(context)
            if state is None:
                raise AdapterError("session_checkpoint_missing")
            key, digest = "management-control:" + request, fingerprint(command)
            reason = None
            if key in state.events:
                if state.events[key] != digest:
                    raise AdapterError("conflict")
            elif state.version != command["expected_version"]:
                reason = "session_changed"
            elif state.action is not None or (state.room and state.room.room_state == "running") or state.pause_reason == "outcome_unknown":
                reason = "outcome_unknown"
            elif state.phase in ("completed", "cancelled", "failed"):
                reason = "session_finished"
            else:
                old = state.version
                operation = command["operation"]
                if operation == "pause":
                    if state.phase != "paused":
                        state.resume_phase = state.phase
                    state.phase, state.pause_reason = "paused", "management_pause"
                elif operation == "resume":
                    if state.phase == "paused":
                        state.phase, state.pause_reason = state.resume_phase or "planning", None
                        state.resume_phase = None
                elif operation == "stop":
                    if state.room:
                        intent = await self.store.get("control_close_intent", record_key)
                        if intent is None:
                            room = await self.service.room.read(context, state.room.room_id)
                            intent = Command(request_id=key, trace_id=key, idempotency_key=key,
                                context=context, payload=CloseRoom(room_id=room.room_id, expected_room_version=room.room_version)).model_dump(mode="json")
                            await self.store.put_once("control_close_intent", record_key, intent)
                        closed = await self.rooms.execute(Command.model_validate(intent))
                        if not isinstance(closed, Success):
                            reason = closed.error.code
                        else:
                            state.room = closed.data
                    if reason is None:
                        state.phase, state.pause_reason = "cancelled", "management_stopped"
                else:
                    raise AdapterError("invalid_control")
                if reason is None:
                    state.events[key], state.version = digest, old + 1
                    if not await self.store.commit(state, old):
                        raise SupervisorError("state_conflict")
            result = {"status": "refused" if reason else "applied", "reason": reason or state.pause_reason,
                      "phase": state.phase, "state_version": state.version}
            await self.store.put_once("control_result", record_key, result)
        await self.backend.control_result(team, request, result)
        if result["status"] == "applied" and command["operation"] == "resume":
            state = await self.store.load(context)
            if state.phase != "execution_ready":
                state = await self.service.resume(context)
            await self.backend.status(team, state.phase, state.pause_reason, state.version)
        return None

    async def answer(self, item: dict) -> float | None:
        """A question management asked a specialist inside a session: one turn of that agent in the room."""
        context, team, question = Context.model_validate(item["context"]), item["team_id"], item["message_id"]
        self.teams[context.scope()] = team
        asked = await self.store.get("mention_result", question)
        if asked is None:
            state = await self.store.load(context)
            turn = None
            if state is not None and state.room is not None:
                room = await self.service.room.read(context, state.room.room_id)
                key = "mention:" + question
                # Asked under the agent's latest task, so it reads what it answered there.
                task = next((t.task_id for t in reversed(room.tasks)
                             if t.assignee_agent_version_id == item["agent_version_id"]), None)
                # Photos on the question reach the model beside its text, for this one turn only.
                pictures = [{"type": "image", "source": {"type": "data", "value": image["data"], "mimeType": image["mimeType"]}}
                            for image in item.get("images") or []]
                if pictures and self.releases:
                    self.releases.attached[context.scope()] = pictures
                try:
                    result = await self.rooms.execute(Command(
                        request_id=key, trace_id=key, idempotency_key=key, context=context,
                        payload=MentionAgent(room_id=room.room_id, expected_room_version=room.room_version,
                                             mentioned_agent_id=item["agent_id"], instruction=item["text"], task_id=task)))
                finally:
                    if pictures and self.releases:
                        self.releases.attached.pop(context.scope(), None)
                        for thread in [t for t, held in self.releases.pictures.items() if held is pictures]:
                            del self.releases.pictures[thread]
                if isinstance(result, Success):
                    turn = result.data
                else:
                    log.warning("question not answered for ticket=%s: %s", context.ticket_id, result.error.code)
            answered = turn is not None and turn.turn_status == "success"
            asked = {"status": "done" if answered else "failed", "run_id": turn.source_run_id if turn else None,
                     "room": turn.model_dump(mode="json") if turn else None}
            # Kept before anything is reported, so a restart reports this outcome instead of asking again.
            await self.store.put_once("mention_result", question, asked)
        if asked["room"]:
            turn = RoomData.model_validate(asked["room"])
            await self.mirror(team, turn, [turn])
        await self.backend.mention_outcome(team, question, asked["status"], asked["run_id"])
        log.info("question ticket=%s answered=%s", context.ticket_id, asked["status"])
        return None

    async def mirror(self, team: str, room: RoomData, turns) -> None:
        """Send the backend what the room holds: tasks, specialist replies and finished turns."""
        members = {p.agent_version_id for p in room.participants}
        await self.backend.room(team, {
            "tasks": [{"task_id": t.task_id, "description": t.description[:4000],
                       "assignee_agent_version_id": t.assignee_agent_version_id, "status": t.status}
                      for t in room.tasks],
            "messages": [{"message_id": m.message_id, "sender_agent_version_id": m.sender, "content": m.content[:20000],
                          **({"task_id": m.task_id} if m.task_id else {})}
                         for m in room.messages if m.sender in members][-500:],
            "runs": [{"run_id": r.source_run_id, "status": "succeeded" if r.turn_status == "success" else "failed"}
                     for r in turns if r.source_run_id][-200:]})

    async def work(self) -> bool:
        """Handle one claimed message. False when there was nothing to do."""
        claim = await self.store.claim(self.owner, LEASE_SECONDS)
        if not claim:
            return False

        async def heartbeat():
            while True:
                await asyncio.sleep(LEASE_SECONDS / 3)
                await self.store.renew(claim, LEASE_SECONDS)

        async def process():
            with self.store.lease_scope(claim):
                return await self.handle(claim)

        execution, renewal = asyncio.create_task(process()), asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait((execution, renewal), return_when=asyncio.FIRST_COMPLETED)
            if renewal in done:
                await renewal  # the lease was lost: another owner continues from the checkpoint
            retry = await execution
            if retry is None:
                await self.store.ack(claim)
            elif retry == RETRY_SECONDS:
                # Management pause is not an uncertain effect: keep the message until resume.
                await self.store.defer(claim, retry)
            elif claim.recovery_attempts >= SETTLE_ATTEMPTS:
                # Asked again and still unknown: a person decides. The checkpoint keeps the action.
                await self.store.park(claim, reason="outcome_unknown")
                log.error("inbox item parked: the outcome of an action stayed unknown")
            else:
                await self.store.defer(claim, retry, recovery=True)
        except Exception as error:  # noqa: BLE001 - every failure ends in a durable inbox state
            code = error.code if isinstance(error, (AdapterError, SupervisorError)) else type(error).__name__
            try:
                if code == "stale_fence":
                    pass
                elif isinstance(error, AdapterError) and (error.outcome_unknown or error.retryable):
                    # The backend was unreachable. Nothing is known to be wrong with the message.
                    await self.store.defer(claim, RETRY_SECONDS)
                else:
                    # A definite refusal or an inconsistent message: kept for a person, never dropped.
                    await self.store.park(claim, reason=code)
                    log.error("inbox item parked: %s", code)
            except AdapterError:
                pass  # the lease moved on; its new owner decides
        finally:
            for task in (execution, renewal):
                if not task.done():
                    task.cancel()
            await asyncio.gather(execution, renewal, return_exceptions=True)
        return True

    async def round(self) -> None:
        if not self.recovered:
            self.recovered = True
            await self.recover_sessions()
        try:
            await self.poll()
        except AdapterError as error:
            log.warning("inbox not read: %s", error.code)
        while await self.work():
            pass


class EvaluationCase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=2000)
    expected: str = Field(min_length=1, max_length=2000)
    ticket: dict = Field(default_factory=dict)
    must: list[str] = Field(default_factory=list, max_length=20)
    must_not: list[str] = Field(default_factory=list, max_length=20)
    must_call: list[str] = Field(default_factory=list, max_length=20)
    must_not_call: list[str] = Field(default_factory=list, max_length=20)
    tool_results: dict = Field(default_factory=dict)


class EvaluationRequest(BaseModel):
    room_id: str = Field(min_length=1, max_length=160)
    agent_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=160)
    request_id: str = Field(min_length=1, max_length=120)
    configuration_hash: str = Field(pattern='^[a-f0-9]{64}$')
    cases: list[EvaluationCase] = Field(min_length=6, max_length=12)


class TrialRequest(BaseModel):
    room_id: str = Field(min_length=1, max_length=160)
    agent_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=160)
    configuration_hash: str = Field(pattern='^[a-f0-9]{64}$')
    question: str = Field(min_length=1, max_length=2000)


def create_app(settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    settings = settings or Settings.from_env()
    box: dict = {}

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(transport=transport) as client:
            if settings.database_url:
                from persistence.postgres import PostgreSQLStore
                store = PostgreSQLStore(settings.database_url)
            else:
                store = Store(settings.state_path)
            runtime = Runtime(Backend(settings.backend_url, settings.service_token, client), store,
                              client=client, settings=settings)
            stopping = asyncio.Event()

            async def loop():
                while not stopping.is_set():
                    try:
                        await runtime.round()
                    except Exception:  # noqa: BLE001 - one bad round must not end the service while /health says ok
                        log.exception("a round failed; the next one starts as usual")
                    try:
                        await asyncio.wait_for(stopping.wait(), settings.poll_seconds)
                    except TimeoutError:
                        pass

            box["runtime"], task = runtime, asyncio.create_task(loop())
            try:
                yield
            finally:
                stopping.set()
                await asyncio.wait_for(task, LEASE_SECONDS)

    async def health(request):
        # Which models work here, for the administrator's screen. Never a key or an address.
        return JSONResponse({"status": "ok", "model": settings.model, "provider": settings.model_provider,
                             "specialist_model": settings.openbot.model if settings.openbot else None})

    async def ready(request):
        try:
            await asyncio.wait_for(box["runtime"].backend.inbox(box["runtime"].store.cursor(), limit=1), 5)
            return JSONResponse({"ready": True})
        except Exception:  # noqa: BLE001 - any failure means not ready
            return JSONResponse({"ready": False}, status_code=503)

    async def sessions(request):
        return JSONResponse({"items": box["runtime"].store.sessions()})

    async def evaluate(request):
        if not settings.service_token or not hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + settings.service_token):
            return JSONResponse({'error': 'Service authentication required'}, status_code=401)
        raw = await request.body()
        if len(raw) > 128 * 1024:
            return JSONResponse({'error': 'Evaluation request too large'}, status_code=413)
        try:
            body = EvaluationRequest.model_validate_json(raw).model_dump()
            cases = body['cases']
            if len({c['name'] for c in cases}) != len(cases) or not settings.openbot:
                return JSONResponse({'error': 'Evaluation cases or model unavailable'}, status_code=422)
            runtime = box['runtime']
            snapshot = await runtime.backend.evaluation_view(body)
            key = json.dumps((body['room_id'], body['agent_id'], body['actor'], body['request_id']))
            marker = fingerprint(body)
            try:
                started = await runtime.store.put_once('evaluation_intent', key, marker)
            except AdapterError as error:
                if error.code == 'conflict':
                    return JSONResponse({'error': 'Evaluation id already used for different content'}, status_code=409)
                raise
            if not started:
                if await runtime.store.get('evaluation_intent', key) != marker:
                    return JSONResponse({'error': 'Evaluation id already used for different content'}, status_code=409)
                result = await runtime.store.get('evaluation_result', key)
                return JSONResponse(result or {'error': 'Evaluation is running or interrupted'}, status_code=200 if result else 409)
            from .publish import answer, judge
            records = []
            async with asyncio.timeout(240):
                for case in cases:
                    try:
                        content, called = await answer(runtime.client, snapshot['instructions'], {**case, 'workspace': snapshot.get('workspace')}, snapshot['tools'], {},
                            endpoint=settings.openbot.endpoint, token=os.environ[settings.openbot.token_env], model_config=snapshot.get('model_config'))
                        problems = judge(case, content, called)
                    except (AdapterError, ValueError, httpx.HTTPError) as error:
                        content, problems = 'Không có câu trả lời hợp lệ.', [getattr(error, 'code', None) or type(error).__name__]
                    records.append({'name': case['name'], 'input': case['instruction'], 'expected': case['expected'],
                        'actual': content[:5000], 'passed': not problems,
                        'explanation': '; '.join(problems)[:2000] if problems else 'Đạt các điều kiện của ca đánh giá.'})
            result = {'cases': records}
            await runtime.store.put_once('evaluation_result', key, result)
            return JSONResponse(result)
        except ValidationError:
            return JSONResponse({'error': 'Invalid evaluation request'}, status_code=422)
        except (AdapterError, KeyError, ValueError, TimeoutError):
            return JSONResponse({'error': 'Evaluation could not be completed'}, status_code=503)

    async def trial(request):
        """One question to a saved draft, answered once and kept nowhere: how it replies, before any case is written.
        It is no evaluation and attests nothing. Its tools answer that they found nothing, as in a case that is
        silent about them, so the reply shows conduct and not data."""
        if not settings.service_token or not hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + settings.service_token):
            return JSONResponse({'error': 'Service authentication required'}, status_code=401)
        try:
            body = TrialRequest.model_validate_json(await request.body()).model_dump()
            if not settings.openbot:
                return JSONResponse({'error': 'Model unavailable'}, status_code=422)
            runtime = box['runtime']
            snapshot = await runtime.backend.evaluation_view({k: body[k] for k in ('room_id', 'agent_id', 'actor', 'configuration_hash')})
            from .publish import answer
            async with asyncio.timeout(120):
                content, called = await answer(runtime.client, snapshot['instructions'],
                    {'name': 'trial-' + uuid4().hex, 'instruction': body['question'], 'ticket': {}, 'workspace': snapshot.get('workspace')}, snapshot['tools'], {},
                    endpoint=settings.openbot.endpoint, token=os.environ[settings.openbot.token_env], model_config=snapshot.get('model_config'))
            return JSONResponse({'answer': content[:5000], 'called': called})
        except ValidationError:
            return JSONResponse({'error': 'Invalid trial request'}, status_code=422)
        except (AdapterError, KeyError, ValueError, TimeoutError, httpx.HTTPError):
            return JSONResponse({'error': 'The draft gave no answer'}, status_code=503)

    return Starlette(routes=[Route("/health", health), Route("/ready", ready), Route("/sessions", sessions),
                            Route('/internal/evaluations', evaluate, methods=['POST']),
                            Route('/internal/trials', trial, methods=['POST'])],
                     lifespan=lifespan)
