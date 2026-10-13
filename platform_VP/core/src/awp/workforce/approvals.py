"""The approval gate: a tool that needs the resident's consent never runs on the agent's say-so (spec 6.1, 13.1-7).

`ConsentGate` sits in `ToolGateMiddleware.on_check_permission`. The tools that need consent are CaseAskConsent and
the route's `wf_tools` with `requires_consent`. For one of them the gate

  first call    writes the approval row, the `approval.required` event and the workflow's new state in ONE
                transaction, then answers ASK, which parks the run (also under permission mode dont_ask,
                P0). Asking again for the same (session, tool call) finds the row and writes nothing.
  after the     lets the call through only when the row says `approved`, the arguments are exactly the ones
  decision      the resident was shown (sha256 of the canonical JSON), the workflow is still open and the row
                was not used yet. AgentScope copies the arguments of the resume event into the call, so this
                is what stops a changed call, `used_at` is what stops a replayed resume event from running the
                tool twice, and the open check (under the conversation's lock, with the `used_at` write) is
                what stops a tool from running for a workflow that was closed or blocked after the decision.

Everything the engine needs to wake the agent that asked (its session, the parked reply, the canonical arguments)
is stored on the row, so a decision never takes anything from the client. `rules` are never granted.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from agentscope.event import UserConfirmResultEvent, UserInterruptEvent
from agentscope.message import ToolCallState
from agentscope.permission import PermissionBehavior, PermissionDecision
from sqlalchemy import func, insert, select, update

from ..assets import masked
from ..casefile import build_view
from ..guard import figures_missing
from ..guard import figures_text
from . import tables as t
from .schemas import NONCE_ARG as NONCE
from .common import iso, now
from .events import emit, lock_conversation
from .lookup import route_of, workflow_of_case
from .tables import new_id
from .workflows import BLOCKED, StateConflict, bump, transition

log = logging.getLogger("awp.workforce")

CONSENT_TOOL = "CaseAskConsent"
RESUME = "resume_"  # the id of the event that wakes a parked agent is resume_<approval id>
MAX_SUMMARY = 300
MAX_ARGUMENTS = 4000  # characters of canonical JSON a partner tool's consent may carry: it is shown and stored whole


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def args_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def deny(message: str) -> PermissionDecision:
    return PermissionDecision(behavior=PermissionBehavior.DENY, message=message)


class _Open(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def summary_of(name: str, args: dict, tool: dict) -> dict:
    """What the resident is shown for a partner tool: the route's sentence for it, and the arguments the
    hash covers. Where an argument holds a signed link to an image (CaseAssetLink) the summary says "[image link]":
    the resident learns that a photo goes along, and is shown no address."""
    text = tool.get("consent_summary") or f"Run {name}"
    args = masked(args)
    try:
        text = text.format_map(_Open(args))
    except (ValueError, IndexError, AttributeError, TypeError):
        pass  # a template that does not fit its arguments is shown as written
    return {"text": text[:MAX_SUMMARY], "tool": name, "arguments": args}


async def find(conn, session_id: str, tool_call_id: str, reply_id: str | None = None) -> Any:
    """The approval of a tool call. A model server may reuse call ids from one reply to the next, so the reply
    is part of the key."""
    return (await conn.execute(select(t.approvals).where(
        t.approvals.c.session_id == session_id, t.approvals.c.tool_call_id == tool_call_id,
        t.approvals.c.reply_id == reply_id))).mappings().first()


async def pending_count(conn, workflow_id: str) -> int:
    return (await conn.execute(select(func.count()).select_from(t.approvals).where(
        t.approvals.c.workflow_id == workflow_id, t.approvals.c.status == "pending"))).scalar_one()


async def resolve(conn, wf: Any, row: Any, status: str, *, request_id: str | None, reason: str,
                  why: str | None = None, wake: bool = True) -> tuple[dict, str | None]:
    """Decide a pending approval inside the caller's transaction, which holds the conversation's write lock
    and read `wf` under it: the row, `approval.resolved`, the workflow (active again when nothing else waits
    for the resident, otherwise only its revision moves) and the job that wakes the agent that asked.
    `why` goes with the job: what the leader is told about a cancellation depends on it (resume.notice).
    `wake=False`: no job (recover.orphan_approvals: nobody is parked, and the turn that asked runs again by itself).
    Returns the workflow and the job id."""
    done = await conn.execute(update(t.approvals).where(
        t.approvals.c.id == row["id"], t.approvals.c.status == "pending")
        .values(status=status, decided_at=now(), decision_request_id=request_id))
    if done.rowcount != 1:
        raise StateConflict(row["id"])
    await emit(conn, wf["conversation_id"], "approval.resolved",
               {"approval_id": row["id"], "status": status}, workflow=wf)
    if wf["state"] == "awaiting_approval" and not await pending_count(conn, wf["id"]):
        wf = await transition(conn, wf, "active", reason=reason, request_id=request_id)
    else:
        wf = await bump(conn, wf)
    if not wake:
        return wf, None
    job = new_id("job")
    await conn.execute(insert(t.jobs).values(
        id=job, workflow_id=wf["id"], kind="approval_resume", request_id=request_id, status="queued",
        payload={"approval_id": row["id"], **({"why": why} if why else {})}, attempts=0, created_at=now()))
    return wf, job


class ConsentGate:
    def __init__(self, rt, binding) -> None:
        self.rt, self.b = rt, binding
        self._scope: tuple[dict | None, dict] | None = None

    async def scope(self) -> tuple[dict | None, dict]:
        """(the workflow of this agent's case or None, the route's tools that need consent by name). Read once
        for the life of the agent: AgentScope assembles an agent for every run."""
        if self._scope is None:
            db = getattr(self.rt, "db", None)  # a runtime without a database has no workflows (a unit test's)
            wf = await workflow_of_case(db, self.b.case_id) if db is not None else None
            tools: dict = {}
            if wf is not None:
                async with self.rt.db.engine.connect() as conn:
                    rows = (await conn.execute(select(t.tools).where(
                        t.tools.c.route_id == wf["route_id"], t.tools.c.requires_consent.is_(True)))).mappings().all()
                tools = {r["name"]: dict(r) for r in rows}
            self._scope = (wf, tools)
        return self._scope

    async def check(self, agent: Any, input_kwargs: dict) -> PermissionDecision | None:
        """None: not for the gate, or approved and let through. Otherwise the decision (ASK or DENY)."""
        wf, tools = await self.scope()
        call = input_kwargs["tool_call"]
        if wf is None or (call.name != CONSENT_TOOL and call.name not in tools):
            return None
        args = input_kwargs.get("tool_input") or {}
        text = canonical(args)
        digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        reply = agent.state.reply_id
        async with self.rt.db.engine.connect() as conn:
            row = await find(conn, self.b.session_id, call.id, reply)
        if row is None:
            if call.state == ToolCallState.ALLOWED:  # allowed by an event of ours? We never sent one for this call
                return deny("No consent was asked for this call.")
            summary = await self._review(call, args, text, tools, wf, input_kwargs)
            if isinstance(summary, PermissionDecision):
                return summary
            row = await self._ask(agent, call, args, text, digest, summary, wf)
            if isinstance(row, PermissionDecision):
                return row
            if self.rt.turn_hook is not None:  # a specialist's run has no recorder: the engine settles the request now
                self.rt.turn_hook(wf["id"])
        elif call.state == ToolCallState.ALLOWED and row["status"] != "approved":
            return deny("The resident has not agreed to this call.")  # an allow nobody decided on
        return await self._existing(row, digest)

    async def _review(self, call: Any, args: dict, text: str, tools: dict, wf: dict, input_kwargs: dict) -> Any:
        """What the resident will be shown, or the DENY that keeps them from being asked. What the model sent is
        checked first: a wrong total, a figure no evidence states, a size that is not reasonable. A check that
        itself fails is a refusal the model can read, never a failed turn."""
        try:
            if call.name == CONSENT_TOOL:  # the numbers are checked before the resident is asked
                why, summary = await input_kwargs["tool"].review(**args)
            else:
                summary, why = summary_of(call.name, args, tools[call.name]), await self._grounded(text, call, args, tools)
            if not why and await self._declined(wf, call.name, text):
                why = ("Not asked: the resident declined exactly this and has not written since. Ask them in "
                       "words what they want instead.")
        except Exception:
            log.exception("could not check the request for consent of %s", call.name)
            why = "Not asked: the request could not be checked. Send it again with plain values."
        return deny(why) if why else summary

    async def _grounded(self, text: str, call: Any, args: dict, tools: dict) -> str | None:
        """A partner tool's consent shows the resident the model's own arguments, so they get the check a
        CaseAskConsent gets: every figure stated is in the evidence of the case, and the size is bounded."""
        if len(text) > MAX_ARGUMENTS:
            return f"Not asked: the arguments are longer than {MAX_ARGUMENTS} characters."
        shown = summary_of(call.name, args, tools[call.name])
        known = [i.data.get("text", "") for i in await self.rt.cases.items(self.b.case_id, kinds=("evidence", "fact"))]
        # the nonce is the platform's own argument (ledger.NONCE): a label for a deliberate repeat, not a figure
        stated = {k: v for k, v in shown["arguments"].items() if k != NONCE}
        missing = figures_missing(figures_text({"text": shown["text"], "arguments": stated}), known)
        if missing:
            return ("Not asked, the resident has seen nothing: figures not found in the evidence of the case: "
                    + ", ".join(missing[:5]) + ". Look them up first, or leave them out.")
        return None

    async def _declined(self, wf: dict, tool: str, text: str) -> bool:
        """The resident refused this very call (or let it expire) and has not written since: asking again
        would be pushing."""
        async with self.rt.db.engine.connect() as conn:
            said = (await conn.execute(select(func.max(t.messages.c.created_at)).where(
                t.messages.c.workflow_id == wf["id"], t.messages.c.sender == "user"))).scalar() or 0
            return (await conn.execute(select(t.approvals.c.id).where(
                t.approvals.c.workflow_id == wf["id"], t.approvals.c.tool_name == tool,
                t.approvals.c.arguments == text, t.approvals.c.status.in_(("rejected", "expired")),
                t.approvals.c.decided_at > said).limit(1))).first() is not None

    async def _prices(self, call: Any, args: dict) -> str | None:
        """The operation a cost consent is about: the one whose provider evidence it cites (None when it cites none or
        several, then no event withdraws it)."""
        cites = args.get("cites") if call.name == CONSENT_TOOL else None
        if not isinstance(cites, list):
            return None
        view = build_view(await self.rt.cases.items(self.b.case_id))
        seen = set()
        for ref in cites:
            if not isinstance(ref, str):
                continue
            behind = [ref] if ref in view.evidence else list(view.facts[ref].item.data.get("evidence", [])) if ref in view.facts else []
            seen.update(view.evidence[e].data["op"] for e in behind if e in view.evidence and view.evidence[e].data.get("op"))
        return seen.pop() if len(seen) == 1 else None

    async def _ask(self, agent: Any, call: Any, args: dict, text: str, digest: str, summary: dict, wf: dict) -> Any:
        quote = args.get("quote_ref") if isinstance(args.get("quote_ref"), str) else None
        priced = await self._prices(call, args)
        async with self.rt.db.engine.begin() as conn:
            await lock_conversation(conn, wf["conversation_id"])  # first lock, as for every writer
            cur = (await conn.execute(select(t.workflows).where(t.workflows.c.id == wf["id"]))).mappings().one()
            if cur["state"] == "closed":
                return deny("The workflow is closed. Nothing was asked; stop working on it.")
            if cur["state"] in BLOCKED:
                return deny("The workflow is blocked. Nothing was asked.")
            again = await find(conn, self.b.session_id, call.id, agent.state.reply_id)  # the same call asked twice: one approval
            if again is not None:
                return again
            policy = (await route_of(conn, cur))["config"].get("policy") or {}
            stamp, rev = now(), cur["revision"] + 1
            row = dict(
                id=new_id("appr"), workflow_id=cur["id"], conversation_id=cur["conversation_id"],
                client_id=cur["client_id"], external_user_id=cur["external_user_id"],
                session_id=self.b.session_id, agent_id=self.b.agent_id, tool_call_id=call.id, tool_name=call.name,
                arguments=text, arguments_hash=digest, quote_ref=quote, summary=summary, status="pending",
                workflow_revision=rev, expires_at=stamp + (policy.get("approval_ttl_seconds")
                                                           or self.rt.settings.approval_ttl_seconds),
                reply_id=agent.state.reply_id, operation_id=priced, created_at=stamp)
            await conn.execute(insert(t.approvals).values(**row))
            shown = {"approval_id": row["id"], "summary": summary, "arguments_hash": digest, "quote_ref": quote,
                     "expires_at": iso(row["expires_at"]), "expected_revision": rev}
            if cur["state"] == "awaiting_approval":  # one more approval waits: the state is the same, the set is not
                await emit(conn, cur["conversation_id"], "approval.required", shown,
                           workflow=await bump(conn, cur))
            else:
                await transition(conn, cur, "awaiting_approval", reason="approval_required",
                                 emit_after=[("approval.required", shown)])
        return row

    async def _existing(self, row: Any, digest: str) -> PermissionDecision | None:
        status = row["status"]
        if status == "pending":
            return PermissionDecision(behavior=PermissionBehavior.ASK,
                                      message=f"waiting for the resident's consent ({row['id']})")
        if status != "approved":
            return deny({"rejected": "The resident declined.", "expired": "The request for consent expired.",
                         }.get(status, "The request for consent was withdrawn."))
        if digest != row["arguments_hash"]:
            return deny("The arguments differ from the ones the resident agreed to.")
        async with self.rt.db.engine.begin() as conn:  # the row is the guard: a replayed resume finds it used
            await lock_conversation(conn, row["conversation_id"])  # first lock: a close that committed is seen below
            state = (await conn.execute(select(t.workflows.c.state).where(t.workflows.c.id == row["workflow_id"]))).scalar()
            if state == "closed" or state in BLOCKED:  # the consent outlives neither the workflow nor its authorization
                return deny("The workflow is closed or blocked. The tool was not run; stop working on it.")
            done = await conn.execute(update(t.approvals).where(
                t.approvals.c.id == row["id"], t.approvals.c.status == "approved", t.approvals.c.used_at.is_(None))
                .values(used_at=now()))
        if done.rowcount != 1:
            return deny("This consent was already used.")
        return None

    async def resumed(self, inputs: Any) -> None:
        """The agent took the event the engine sent to wake it: the engine's acknowledgement (a 200 from /chat
        alone does not say the run started)."""
        if not isinstance(inputs, (UserConfirmResultEvent, UserInterruptEvent)) or not str(inputs.id).startswith(RESUME):
            return
        try:
            async with self.rt.db.engine.begin() as conn:
                await conn.execute(update(t.approvals).where(
                    t.approvals.c.id == str(inputs.id)[len(RESUME):], t.approvals.c.session_id == self.b.session_id,
                    t.approvals.c.resumed_at.is_(None)).values(resumed_at=now()))
        except Exception:
            log.exception("could not note the resume of %s", inputs.id)
