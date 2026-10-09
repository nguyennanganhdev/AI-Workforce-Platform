"""The Vinhomes domain pack: polls the domain's case inbox, hands results back.

Flow
  inbox (GET /cases/inbox) -> mapping -> intake.submit / intake.follow_up -> core runs the case
  core finalizes -> outbox -> deliver_result -> GET case, POST result

Delivery guarantees
  * The inbox cursor is a file, saved only after every message of a page was handled. If it is
    lost the loop reads the inbox from the start, and the core drops what it already saw (it keeps
    every message_id), so a lost cursor costs time, never a duplicate case. A file is enough
    because there is one tenant per pack and no second writer.
  * A page that fails part-way is read again next time (the inbox pages by cursor, not by message).
  * A transient failure backs off 1s, 2s, ... up to 60s and keeps the cursor. A message that can
    never be handled (malformed, or for a case that is already over) is logged and skipped so it
    cannot block the ones behind it.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path

from awp.guard import Rules
from awp.intake.models import CaseResult
from awp.intake.service import IntakeError, IntakeService, NoRetry
from awp.runtime import Binding, Runtime

from . import mapping
from .client import Conflict, VinhomesClient, VinhomesError
from .profiles import LEADER, vinhomes_profiles
from .rules import vinhomes_rules
from .tools import GetTicket, Knowledge, ProposePlan, SearchKnowledge

log = logging.getLogger("awp.vinhomes")
MIN_BACKOFF, MAX_BACKOFF = 1.0, 60.0


class DeliveryRejected(NoRetry):
    """The domain will not take this result as it is. The core stops retrying and keeps
    the reason in its outbox; sending it again unchanged would fail the same way."""


class VinhomesPack:
    domain = "vinhomes"
    default_leader = LEADER

    def __init__(self, client: VinhomesClient, *, cursor_file: str | Path | None = None,
                 poll_seconds: float = 3.0, page_size: int = 50, knowledge_ttl: float = 300.0,
                 start_delay: float = 2.0, owns_client: bool = False) -> None:
        self.client = client
        self.cursor_file = Path(cursor_file) if cursor_file else None
        self.poll_seconds, self.page_size = poll_seconds, page_size
        # The core calls start() before AgentScope has finished its own startup. A ticket read in
        # that gap would create a case that cannot be started, so the first read waits a little.
        self.start_delay = start_delay
        self.knowledge = Knowledge(client, knowledge_ttl)
        self._owns_client = owns_client
        self.cursor: str | None = self._load_cursor()
        self.tenant: str | None = None
        self.intake: IntakeService | None = None
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "VinhomesPack":
        e = os.environ if env is None else env
        return cls(VinhomesClient.from_env(e),
                   cursor_file=e.get("VINHOMES_CURSOR_FILE", "./vinhomes_inbox_cursor.json"),
                   poll_seconds=float(e.get("VINHOMES_POLL_SECONDS", 3) or 3),
                   knowledge_ttl=float(e.get("VINHOMES_KNOWLEDGE_TTL", 300) or 300),
                   start_delay=float(e.get("VINHOMES_START_DELAY", 0) or 0), owns_client=True)

    # ---- what the core asks for -------------------------------------------------
    def profiles(self):
        return vinhomes_profiles()

    def rules(self) -> Rules:
        return vinhomes_rules()

    def tools(self, rt: Runtime, binding: Binding) -> list:
        return [GetTicket(self.client, rt, binding, self.knowledge),
                SearchKnowledge(self.client, rt, binding, self.knowledge),
                ProposePlan(self.client, rt, binding, self.knowledge)]

    # ---- inbox ------------------------------------------------------------------
    def _load_cursor(self) -> str | None:
        try:
            return json.loads(self.cursor_file.read_text(encoding="utf-8")).get("cursor") if self.cursor_file else None
        except (OSError, ValueError):
            return None

    def _save_cursor(self, cursor: str | None) -> None:
        self.cursor = cursor
        if self.cursor_file is None or cursor is None:
            return
        tmp = self.cursor_file.with_suffix(".tmp")  # write then rename: never a half-written file
        tmp.write_text(json.dumps({"cursor": cursor}), encoding="utf-8")
        os.replace(tmp, self.cursor_file)

    async def start(self, rt: Runtime, intake: IntakeService, tenant: str) -> None:
        if self._task is not None:
            raise RuntimeError("the Vinhomes pack serves one tenant")
        self.tenant, self.intake = tenant, intake
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, 5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self._task
            self._task = None
        if self._owns_client:
            await self.client.aclose()

    async def _run(self) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stop.wait(), self.start_delay)
        delay = 0.0
        while not self._stop.is_set():
            try:
                more = await self.poll_once()
                delay, wait = 0.0, 0.0 if more else self.poll_seconds
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep the cursor, wait, try the same page again
                delay = min(max(delay * 2, MIN_BACKOFF), MAX_BACKOFF)
                wait = delay
                log.warning("Vinhomes inbox: %s; retrying in %.1fs", e, delay)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop.wait(), wait)

    async def poll_once(self) -> bool:
        """Read one page and hand each message to the core. True when a full page came back
        (there may be more). Raises on a transient failure, leaving the cursor where it was."""
        page = await self.client.inbox(self.cursor, self.page_size)
        items = page.get("items") or []
        for msg in items:
            await self._handle(msg)
        if items:
            self._save_cursor(page.get("next_cursor"))
        return len(items) >= self.page_size

    async def _handle(self, msg: dict) -> None:
        assert self.intake is not None and self.tenant is not None
        try:
            if msg.get("message_type") == "ticket_submitted":
                out = await self.intake.submit(self.tenant, self.domain, mapping.intake_from_message(msg))
                if not out.get("replayed"):
                    await self._acknowledge(msg)
            else:
                ref, follow_up = mapping.follow_up_from_message(msg)
                await self.intake.follow_up(self.tenant, self.domain, ref, follow_up)
        except mapping.BadMessage as e:
            log.error("Vinhomes inbox: skipping message %s: %s", msg.get("message_id"), e)
        except IntakeError as e:
            # 404/409 on a follow-up: the case is unknown or already over (for example the resident
            # approves a plan after the platform finalized its part). Nothing to do, and waiting
            # would only block the messages behind it. Anything else (no model, no profile) may pass.
            if e.status not in (404, 409):
                raise
            log.info("Vinhomes inbox: %s is not needed any more (%s)", msg.get("message_id"), e.message)

    async def _acknowledge(self, msg: dict) -> None:
        """Tell the domain the ticket was taken. Courtesy only: failing must not lose the ticket."""
        body = mapping.accepted_message(msg)
        try:
            await self.client.post_result(msg["ticket_id"], body, body["message_id"])
        except VinhomesError as e:
            log.info("Vinhomes: could not send the receipt for %s: %s", msg.get("ticket_code"), e)

    # ---- result -------------------------------------------------------------------
    async def deliver_result(self, case: dict, result: CaseResult) -> None:
        attrs = (case.get("intake") or {}).get("attributes") or {}
        ticket_id = attrs.get("ticket_id")
        if not ticket_id:
            raise DeliveryRejected("the case carries no ticket id")
        current = await self.client.get_case(ticket_id)  # transient errors propagate: the core retries
        if int(current["ticket_generation"]) != int(attrs["ticket_generation"]):
            log.info("Vinhomes: result of %s is for an older round of the ticket; dropped", ticket_id)
            return
        body = mapping.result_message(attrs, result, current)
        try:
            await self.client.post_result(ticket_id, body, body["message_id"])
            return
        except Conflict as first:
            # 409 is either "your snapshot is old" or "the domain is not in that state".
            # Read again to tell them apart; never send the same thing a second time.
            fresh = await self.client.get_case(ticket_id)
            if int(fresh["ticket_generation"]) != int(attrs["ticket_generation"]):
                return
            if str(fresh["ticket"]["version"]) != body["ticket_version"]:
                body = mapping.result_message(attrs, result, fresh)
            else:
                # Not stale. For "completed" this means the domain does not consider the work done
                # (open work orders, a question pending); it would refuse a softer message for a
                # finished ticket too, so there is nothing honest to send instead.
                raise DeliveryRejected(str(first)) from first
        try:
            await self.client.post_result(ticket_id, body, body["message_id"])
        except Conflict as e:
            raise DeliveryRejected(str(e)) from e
