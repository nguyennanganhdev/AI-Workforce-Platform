"""Receives cases from a domain, starts the leader, and reports the result."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import time
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .. import db
from ..casefile import build_view
from ..requests import RequestError, as_text, validate
from ..runtime import Runtime
from .agentscope_client import AgentScopeClient, owner_of
from .models import CaseIntake, CaseResult, FollowUp

log = logging.getLogger("awp.intake")

DeliverFn = Callable[[dict, CaseResult], Awaitable[None]]
MAX_ATTEMPTS = 8
DELIVERY_TIMEOUT = 20.0


class IntakeError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


class NoRetry(Exception):
    """Raised by a deliverer when retrying cannot help (the reason is kept)."""


def clamp(requested: float | None, ceiling: float) -> float:
    """A domain may ask for a lower budget than the operator's, never a higher one.
    0 means 'no ceiling' only for the operator."""
    want = requested if requested is not None and requested > 0 else 0.0
    if ceiling > 0:
        return min(want, ceiling) if want > 0 else ceiling
    return want


def check_callback_url(url: str, allow_private: bool) -> None:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise IntakeError(422, "callback_url must be an http(s) URL")
    if allow_private:
        return
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        raise IntakeError(422, "callback_url points at an internal host")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise IntakeError(422, "callback_url points at an internal address")


def opening_message(case_id: str, intake: CaseIntake, evidence_refs: list[tuple[str, str]]) -> str:
    facts = "\n".join(f"  {ref}: {text}" for ref, text in evidence_refs) or "  (none)"
    return (
        f'<case id="{case_id}" ref="{intake.external_ref}" priority="{intake.priority}">\n'
        f"Summary: {intake.summary}\n"
        f"{('Description: ' + intake.description) if intake.description else ''}\n"
        f"Facts from the requester (cite these evidence ids):\n{facts}\n"
        f"</case>\nHandle this case as the leader.")


class IntakeService:
    def __init__(self, rt: Runtime, client: AgentScopeClient,
                 default_leader: dict[str, str] | None = None) -> None:
        self.rt, self.client = rt, client
        rt.fail_hook = self.fail
        rt.close_hook = self.close
        self.default_leader = default_leader or {}  # domain -> leader profile key
        self.deliverers: dict[str, DeliverFn] = {}  # domain -> how a result goes back
        self.request_deliverers: dict[str, Callable[[dict, dict], Awaitable[None]]] = {}
        self._tasks: set[asyncio.Task] = set()
        self.webhook_client = httpx.AsyncClient(timeout=DELIVERY_TIMEOUT)

    # ---- new case ---------------------------------------------------------
    async def submit(self, tenant: str, domain: str, intake: CaseIntake) -> dict:
        cases = self.rt.cases
        existing = await cases.find_case(tenant, domain, intake.external_ref)
        if existing:
            await cases.remember_inbound(tenant, domain, intake.message_id, existing["id"])
            return {"case_id": existing["id"], "status": existing["status"], "replayed": True}

        s = self.rt.settings
        if intake.callback_url:
            if not s.callback_secret:
                raise IntakeError(422, "callbacks are not enabled on this platform")
            check_callback_url(intake.callback_url, s.callback_allow_private)
        key = intake.leader_profile or self.default_leader.get(domain)
        if not key:
            raise IntakeError(422, f"no leader profile for domain {domain!r}")
        rec = await self.rt.profiles.get_published(tenant, key)
        if rec is None or rec.profile.role != "leader":
            raise IntakeError(422, f"no published leader profile {key!r}")
        spec = self.rt.catalog.pick(rec.profile.model_tier)
        if spec is None:
            raise IntakeError(503, "no model is configured; add a provider key")

        try:
            case_id = await cases.create_case(
                tenant=tenant, domain=domain, external_ref=intake.external_ref,
                user_id=owner_of(tenant), intake=intake.model_dump(),
                budget_usd=clamp(intake.budget_usd, s.case_budget_usd),
                budget_tokens=int(clamp(intake.budget_tokens, s.case_budget_tokens)))
        except IntegrityError:  # the same case arrived twice at once
            existing = await cases.find_case(tenant, domain, intake.external_ref)
            return {"case_id": existing["id"], "status": existing["status"], "replayed": True}
        await cases.remember_inbound(tenant, domain, intake.message_id, case_id)

        try:
            refs = []
            for f in intake.facts:
                text = f"{f.key}: {f.value} ({f.source})"
                ev = await cases.add(case_id, "evidence", "intake",
                                     {"tool": "intake", "input": f.key, "text": text})
                refs.append((ev.ref, text))
            if intake.description:
                ev = await cases.add(case_id, "evidence", "intake", {
                    "tool": "intake", "input": "description", "text": intake.description})
                refs.append((ev.ref, intake.description))
            agent_id = await self.client.agent_id(tenant, rec.profile, rec.version)
            session_id = await self.client.new_session(
                tenant, agent_id, f"case {intake.external_ref}", spec)
            await cases.bind_session(case_id, session_id, agent_id, rec.profile.name, "leader")
            await cases.update_case(case_id, leader_agent_id=agent_id, leader_session_id=session_id)
        except Exception as e:
            # Never leave a case that nothing will ever start: close it so the
            # domain is told and can decide what to do.
            log.exception("could not set up case %s", case_id)
            await self.fail(case_id, f"could not start: {e}")
            return {"case_id": case_id, "status": "failed", "replayed": False}
        self._spawn(self._run(tenant, case_id, agent_id, session_id,
                              opening_message(case_id, intake, refs)))
        return {"case_id": case_id, "status": "open", "replayed": False}

    # ---- more information for an open case ---------------------------------
    async def follow_up(self, tenant: str, domain: str, external_ref: str, msg: FollowUp) -> dict:
        case = await self.rt.cases.find_case(tenant, domain, external_ref)
        if case is None:
            raise IntakeError(404, "no such case")
        if await self.rt.cases.inbound_seen(tenant, domain, msg.message_id):
            return {"case_id": case["id"], "status": case["status"], "replayed": True}
        if case["status"] != "open":
            raise IntakeError(409, f"case is {case['status']}")
        if msg.reply_to:
            await self._record_reply(case, msg)
        else:
            # intake evidence is the requester's word, not a system record
            ev = await self.rt.cases.add(case["id"], "evidence", "intake", {
                "tool": "intake", "input": msg.kind, "text": msg.text})
            leader = await self.rt.leader_name(case["id"])
            await self.rt.deliver(case["id"], leader or "", f'ref="{ev.ref}"', "intake",
                                  f"New information ({msg.kind}) as evidence {ev.ref}: {msg.text}")
        await self.rt.cases.remember_inbound(tenant, domain, msg.message_id, case["id"])
        return {"case_id": case["id"], "status": case["status"], "replayed": False}

    async def _record_reply(self, case: dict, msg: FollowUp) -> None:
        """A structured answer to a request an agent sent: check it, keep it as evidence, wake the sender."""
        view = build_view(await self.rt.cases.items(case["id"]))
        req = view.requests.get(msg.reply_to)
        if req is None or not req.data.get("expects_reply"):
            raise IntakeError(422, "no such request awaiting a reply")
        if msg.reply_to in view.replies:
            raise IntakeError(409, "that request was already answered")
        kind = self.rt.request_kinds.get(case["domain"], {}).get(req.data["kind"])
        try:
            validate(kind.reply if kind else None, msg.data, "reply")
        except RequestError as e:
            raise IntakeError(422, str(e))
        text = as_text(msg.data)
        # It comes from the domain's own systems, so it counts as tool-grade evidence.
        ev = await self.rt.cases.add(case["id"], "evidence", f"external:{req.data['kind']}", {
            "tool": f"external:{req.data['kind']}", "input": msg.reply_to, "text": text})
        await self.rt.cases.add(case["id"], "reply", f"external:{req.data['kind']}", {
            "to_ref": msg.reply_to, "kind": req.data["kind"], "data": msg.data, "text": text[:300]})
        await self.rt.deliver(
            case["id"], req.author, f'ref="{msg.reply_to}"', "external",
            f"Reply to {msg.reply_to} ({req.data['kind']}) recorded as evidence {ev.ref}:\n{text}")

    # ---- closing ----------------------------------------------------------
    async def result_of(self, case: dict, result: dict, outcome: str | None = None) -> CaseResult:
        return CaseResult(
            case_id=case["id"], external_ref=case["external_ref"],
            outcome=outcome or result.get("outcome", "failed"), answer=result.get("answer", ""),
            cites=result.get("cites", []), unknowns=result.get("unknowns", []),
            cost=await self.rt.cost.case_totals(case["id"]))

    async def close(self, case_id: str, status: str, result: dict) -> bool:
        """Close an open case and queue its result atomically. False if already closed."""
        case = await self.rt.cases.get_case(case_id)
        if case is None or case["status"] != "open":
            return False
        payload = await self.result_of(case, result)
        return await self.rt.cases.close_case(case_id, status, result, payload.model_dump())

    async def fail(self, case_id: str, reason: str) -> None:
        case = await self.rt.cases.get_case(case_id)
        if case is None or case["status"] != "open":
            return
        await self.rt.cases.add(case_id, "note", "platform", {"type": "failed", "reason": reason})
        await self.close(case_id, "failed", {
            "answer": self.rt.rules_for(case["domain"]).safe_reply, "outcome": "failed",
            "cites": [], "unknowns": [reason]})

    async def deliver_pending(self, limit: int = 20) -> int:
        """Send queued results to their domain. Rows nobody can deliver are skipped,
        failures retry up to MAX_ATTEMPTS and then stop with their reason kept."""
        async with self.rt.db.engine.connect() as conn:
            rows = (await conn.execute(select(db.outbox).where(
                db.outbox.c.status == "pending").order_by(db.outbox.c.id).limit(limit))).all()
        results = await asyncio.gather(*(self._deliver_one(r) for r in rows))
        return sum(1 for ok in results if ok)

    async def _deliver_one(self, row) -> bool:
        case = await self.rt.cases.get_case(row.case_id)
        deliver = self.deliverers.get(case["domain"]) if case else None
        if deliver is None and case and case["intake"].get("callback_url"):
            deliver = self._webhook
        status, error, ok = "sent", None, True
        if row.kind == "request":
            deliver = self.request_deliverers.get(case["domain"]) if case else None
        if deliver is None:  # a pull domain without a connector: nothing to send
            status, error, ok = "skipped", "no deliverer for this domain", False
        else:
            try:
                payload = row.payload if row.kind == "request" else CaseResult.model_validate(row.payload)
                await asyncio.wait_for(deliver(case, payload), DELIVERY_TIMEOUT)
            except NoRetry as e:
                status, error, ok = "failed", str(e)[:300], False
            except Exception as e:  # keep it queued; the next sweep retries
                log.warning("delivery of %s failed: %r", row.case_id, e)
                status, error, ok = "pending", repr(e)[:300], False
                if row.attempts + 1 >= MAX_ATTEMPTS:
                    status = "failed"
        async with self.rt.db.engine.begin() as conn:
            await conn.execute(update(db.outbox).where(db.outbox.c.id == row.id).values(
                status=status, attempts=row.attempts + 1, last_error=error))
        return ok

    async def _webhook(self, case: dict, result: CaseResult) -> None:
        """Signed callback for domains that push (no pack connector)."""
        secret = self.rt.settings.callback_secret
        if not secret:
            raise NoRetry("callbacks are not enabled on this platform")
        body = json.dumps(result.model_dump(), ensure_ascii=False).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        r = await self.webhook_client.post(
            case["intake"]["callback_url"], content=body,
            headers={"Content-Type": "application/json", "X-AWP-Signature": f"sha256={sig}",
                     "X-AWP-Case": case["external_ref"]})
        r.raise_for_status()

    async def expire_stalled(self) -> int:
        """Fail open cases that stopped moving, so the domain is never left waiting."""
        idle = self.rt.settings.case_stall_seconds
        if idle <= 0:
            return 0
        closed = 0
        for cid in await self.rt.cases.stalled(idle):
            if self.rt.workforce is not None and await self.rt.workforce.workflow_of_case(cid):
                continue  # Workforce jobs have leases/deadlines; waiting for a resident is not a stalled agent.
            open_requests = build_view(await self.rt.cases.items(cid)).open_requests()
            if open_requests:
                # Waiting for an outside reply is normal; give up only after the request timeout.
                limit = self.rt.settings.request_timeout_hours * 3600
                if time.time() - min(r.created_at for r in open_requests) <= limit:
                    continue
                case = await self.rt.cases.get_case(cid)
                await self.close(cid, "finalized", {
                    "answer": self.rt.rules_for(case["domain"]).safe_reply, "outcome": "needs_human",
                    "cites": [], "unknowns": [f"no reply to {r.ref} ({r.data.get('kind')})" for r in open_requests]})
            else:
                await self.fail(cid, f"no activity for {idle} seconds")
            closed += 1
        return closed

    # ---- internals --------------------------------------------------------
    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, tenant: str, case_id: str, agent_id: str, session_id: str, text: str) -> None:
        try:
            await self.client.say(tenant, agent_id, session_id, text)
        except Exception as e:
            log.exception("could not start case %s", case_id)
            await self.fail(case_id, f"could not start: {e}")

    async def aclose(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        await self.client.aclose()
        await self.webhook_client.aclose()
