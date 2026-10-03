"""The Supervisor service for the Vinhomes business API: inbox poller, worker, status.

Run from agent-coordination/:  python -m vinhomes     (settings: see Settings.from_env)

The backend's V2 inbox is the source. Each poll copies new messages into this runtime's own
durable inbox, so a message survives a restart between "read" and "handled", and reading the
inbox is never taken as having handled it. One worker then handles one message at a time under
a lease: verify with the backend, create or load the session checkpoint, let the Supervisor
continue, and report what the session is now waiting for.

Storage is team Đông's development store (a SQLite file on this host). It keeps checkpoints,
the inbox and the cursor across restarts, and it is not shared between hosts.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from adapters.backend.errors import AdapterError
from groupchat.room import RoomService
from persistence.sqlite import DevelopmentStore
from supervisor.models import SupervisorError, SupervisorState
from supervisor.planner import Planner
from supervisor.room_bridge import RoomBridge
from supervisor.service import SupervisorService

from .backend import Backend, Refused
from .ports import (Authority, NoSpecialists, Reception, UnboundBackendActions, UnboundEvents,
                    UnboundInvocation, UnboundResolver)

log = logging.getLogger("coordination.vinhomes")
LEASE_SECONDS = 60
RETRY_SECONDS = 15  # the backend could not be reached: try the same message again
SETTLE_SECONDS = 5  # an action is in flight or unknown: reconcile it on the next round


@dataclass(frozen=True)
class Settings:
    backend_url: str
    service_token: str = field(repr=False)
    state_path: str = ".coordination-state/coordination.sqlite3"
    host: str = "127.0.0.1"
    port: int = 4300
    poll_seconds: float = 2.0

    @classmethod
    def from_env(cls) -> Settings:
        url = os.getenv("COORDINATION_BACKEND_URL", "").strip()
        token = os.getenv("COORDINATION_SERVICE_TOKEN", "").strip()
        if len(token) < 32 or not url.startswith(("http://", "https://")):
            raise ValueError("COORDINATION_BACKEND_URL and COORDINATION_SERVICE_TOKEN (32+ characters) are required")
        return cls(backend_url=url, service_token=token,
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
                "checkpoint_version": state.version, "results_sent": [a.operation for a in state.journal],
                "action_in_flight": state.action.status if state.action else None})
        return [{"blocked_inbox_items": blocked}, *sessions] if blocked else sessions


class Runtime:
    def __init__(self, backend: Backend, store: Store, *, owner: str | None = None):
        self.backend, self.store, self.owner = backend, store, owner or str(uuid4())
        authority = Authority(backend)
        self.teams: dict[tuple, str] = {}  # scope -> team, known once the backend verified a message

        async def group_pin(context):
            return await authority.group_pin(context, self.teams[context.scope()])

        self.service = SupervisorService(
            store=store, authority=authority, verifier=UnboundEvents("backend_events"), event_types={},
            planner=Planner(NoSpecialists()), reception=Reception(backend),
            room=RoomBridge(RoomService(UnboundResolver("participants"), UnboundInvocation("agent_invocation"), store)),
            backend=UnboundBackendActions("backend_actions"), groupchat_version_id="vinhomes-supervisor",
            groupchat_resolver=group_pin)

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
        return len(page["items"])

    async def handle(self, claim) -> float | None:
        """One message, from verification to whatever the session now waits for."""
        wire, team = claim.payload["wire"], claim.payload["team_id"]
        self.teams[(wire["tenant_id"], wire["ticket_id"], wire["ticket_generation"])] = team
        try:
            state = await self.service.handle_reception(wire, team)
        except Refused as error:
            if error.status != 409:
                raise
            # The team finished, or the ticket moved to a new generation, before this message was
            # handled. The backend still holds the message; there is nothing left to do with it here.
            log.info("obsolete message for ticket=%s: the team is no longer current", wire["ticket_id"])
            return None
        state = await self.service.resume(state.context)
        log.info("session ticket=%s generation=%s phase=%s reason=%s checkpoint=%s", state.context.ticket_id,
                 state.context.ticket_generation, state.phase, state.pause_reason, state.version)
        try:
            await self.backend.status(team, state.phase, state.pause_reason, state.version)
        except AdapterError as error:
            log.warning("status not reported for ticket=%s: %s", state.context.ticket_id, error.code)
        if state.action and state.action.status in ("sending", "unknown", "accepted"):
            return SETTLE_SECONDS
        return None

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
            else:
                await self.store.defer(claim, retry)
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
        try:
            await self.poll()
        except AdapterError as error:
            log.warning("inbox not read: %s", error.code)
        while await self.work():
            pass


def create_app(settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    settings = settings or Settings.from_env()
    box: dict = {}

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(transport=transport) as client:
            runtime = Runtime(Backend(settings.backend_url, settings.service_token, client), Store(settings.state_path))
            stopping = asyncio.Event()

            async def loop():
                while not stopping.is_set():
                    await runtime.round()
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
        return JSONResponse({"status": "ok"})

    async def ready(request):
        try:
            await asyncio.wait_for(box["runtime"].backend.inbox(box["runtime"].store.cursor(), limit=1), 5)
            return JSONResponse({"ready": True})
        except Exception:  # noqa: BLE001 - any failure means not ready
            return JSONResponse({"ready": False}, status_code=503)

    async def sessions(request):
        return JSONResponse({"items": box["runtime"].store.sessions()})

    return Starlette(routes=[Route("/health", health), Route("/ready", ready), Route("/sessions", sessions)],
                     lifespan=lifespan)
