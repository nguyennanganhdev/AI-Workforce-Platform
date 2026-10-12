"""Finding out what became of operations nobody is waiting on any more (spec 8, 9; P0 items 17, 24).

Two kinds of operation need it, and the sweep (every couple of seconds) looks for both:

  left half done   an `intent` or `sent` row older than `wf_op_grace_seconds` with no live call: none in this
                   process, and the process that sent it (the row's `node`) does not live any more (nodes.py). While
                   that process lives the row is its own: it has the live call, or the answer in hand that its
                   database would not take (ledger.HELD). So
                   the process died between writing the row and recording the answer. Nobody knows whether the
                   partner got it. In this order: the tool has an idempotency argument -> send it again with the
                   SAME client_reference (the partner makes it a no-op if it already has it); else the route can
                   ask (status_query) -> ask; else it is `unknown` and the workflow needs attention. Never a
                   blind resend.
  asked about      a `pending` or `unknown` row of a tool with tracking status_query is asked every
                   `wf_status_poll_seconds` what became of its client_reference, until the partner says.

The status tool is the partner's own MCP tool named in `wf_tools.status_tool`: input `client_reference`, output the
same JSON as the action (`status`, and the job id). A finished operation wakes the leader, who tells the resident.
An operation of a closed workflow, or of one whose route is suspended or replaced, is left alone (stop tracking never
calls anything at the partner): the check is part of taking the row (ledger.touch), so it holds for each row of a pass.
A resend that could not even connect says nothing of the original request, which may have reached the partner before
the crash: the row waits for the next pass.

Every process of a fleet runs this pass. Taking a row is a compare-and-set on its clock (ledger.touch `before`), so two
processes that saw the same row do not both call the partner about it.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, or_, select

from . import ledger, nodes, tables as t
from .common import now
from .ledger import HELD, INFLIGHT
from .partner_mcp import PartnerListError
from .partner_result import FAILED, KNOWN_WORDS, UNKNOWN, PartnerResult
from .partner_tools import MAX_CALL_TIMEOUT, NONCE, hidden_args
from .settling import settle_waiting
from .workflows import BLOCKED, transition

log = logging.getLogger("awp.workforce")

LIMIT = 20  # operations looked at per pass: a slow partner must not hold up the others for long


async def candidates(db: Any, grace: float, poll: float) -> list[Any]:
    op, wf, tool = t.operations, t.workflows, t.tools
    stamp = now()
    joined = op.join(wf, wf.c.id == op.c.workflow_id).join(t.routes, t.routes.c.id == wf.c.route_id).outerjoin(
        tool, and_(tool.c.route_id == op.c.route_id, tool.c.name == op.c.tool_name))
    async with db.engine.connect() as conn:
        return list((await conn.execute(
            select(op, tool.c.mcp_tool, tool.c.server, tool.c.tracking, tool.c.status_tool, tool.c.client_reference_arg,
                   tool.c.idempotency_arg, tool.c.call_timeout)
            .select_from(joined).where(
                wf.c.state.notin_(("closed", *BLOCKED)), t.routes.c.status == "active",
                or_(and_(op.c.status.in_(("intent", "sent")), op.c.updated_at < stamp - grace),
                    and_(op.c.status.in_(("pending", "unknown")), tool.c.tracking == "status_query",
                         op.c.updated_at < stamp - poll)))
            .order_by(op.c.updated_at).limit(LIMIT))).mappings().all())


def answered(res: PartnerResult) -> bool:
    """The partner said what became of the operation (a status word we know), as opposed to an error or silence."""
    return res.status in KNOWN_WORDS and res.error in (None, "rejected")


async def ask(client: Any, row: Any) -> PartnerResult:
    return await client.call(row["status_tool"], {"client_reference": row["client_reference"]}, kind="action",
                             timeout=min(float(row["call_timeout"] or 8.0), MAX_CALL_TIMEOUT), tracking="events")


async def resend(client: Any, row: Any) -> PartnerResult:
    """The same request, with the same reference in the same arguments."""
    args = {k: v for k, v in (row["arguments"] or {}).items() if k != NONCE}
    args.update({a: row["client_reference"] for a in hidden_args({"client_reference_arg": row["client_reference_arg"],
                                                                  "idempotency_arg": row["idempotency_arg"]})})
    return await client.call(row["mcp_tool"], args, kind="action",
                             timeout=min(float(row["call_timeout"] or 8.0), MAX_CALL_TIMEOUT), tracking=row["tracking"])


async def client_of(eng: Any, row: Any) -> Any:
    """The MCP client for the row's tool, or None when its configuration is gone."""
    if row["server"] is None:
        return None
    server = (await eng.rt.mcp.servers(row["route_id"])).get(row["server"])
    if server is None:
        return None
    try:
        return eng.rt.mcp.client(row["route_id"], server)
    except PartnerListError:
        return None


async def attention(db: Any, workflow_id: str) -> None:
    """An operation nobody can find out about: the workflow needs a person (public reason operation_unknown)."""
    async with db.engine.begin() as conn:
        wf = await ledger.locked(conn, workflow_id)
        if wf["state"] in ("closed", "needs_attention", "awaiting_approval", *BLOCKED):
            return  # (a pending approval comes first; the next settle finds the lost operation)
        await transition(conn, wf, "needs_attention", reason="operation_unknown")
        await settle_waiting(conn, workflow_id)


async def one(eng: Any, row: Any, before: float | None = None) -> None:
    db, left_over = eng.ctx.db, row["status"] in ("intent", "sent")
    me = getattr(eng, "node", None)
    if row["id"] in INFLIGHT:
        return  # a live call here owns it
    if left_over and row["node"] and row["node"] != me and await nodes.alive(db, row["node"]):
        return  # the process that sent it lives: the call is its, and so is the answer if it has one in hand
    if not await ledger.touch(db, row["id"], "sent" if left_over else row["status"],
                              ("intent", "sent") if left_over else (row["status"],), before=before,
                              node=me if left_over else None):
        return  # something else just changed it, or another process took it
    if (row["result"] or {}).get("reviewed"):
        return  # a person looked at it; the touch above is what keeps it from coming back at once
    client = await client_of(eng, row)
    res: PartnerResult
    if row["id"] in HELD:  # the partner answered, the database would not take it then: it is the answer
        res = HELD[row["id"]]
    elif client is None:
        res = PartnerResult(UNKNOWN, "the tool is no longer configured", error="config", sent=None)
    elif left_over and row["idempotency_arg"]:
        res = await resend(client, row)
        if res.outcome == FAILED and res.sent is False:
            return  # the resend did not get there; that says nothing of the original request. Try again after the pause.
    elif row["tracking"] == "status_query" and row["status_tool"]:
        res = await ask(client, row)
        if not answered(res):
            if res.error != "protocol" or not left_over:
                return  # the partner did not answer (or this is only a poll): ask again after the pause
            # it answered, and has no record of the request: nobody can say what became of it
            res = PartnerResult(UNKNOWN, "the partner has no record of the request", error="unanswered", sent=None)
    else:
        res = PartnerResult(UNKNOWN, "the process stopped while the request was being sent; nobody knows whether "
                                     "it was carried out", error="interrupted", sent=None)
    after = await ledger.finish(db, row["id"], res, wake=True)
    HELD.pop(row["id"], None)
    log.info("operation %s: %s -> %s", row["id"], row["status"], after["status"])
    if after["status"] == "unknown" and (row["tracking"] != "status_query" or left_over):
        await attention(db, row["workflow_id"])


async def reconcile(eng: Any, grace: float | None = None, poll: float | None = None) -> int:
    """One pass over what needs finding out. Returns how many operations were looked at. `grace` and `poll`
    replace the settings (a test, or an operator who wants it now)."""
    s = eng.settings
    grace = s.wf_op_grace_seconds if grace is None else grace
    poll = s.wf_status_poll_seconds if poll is None else poll
    rows = await candidates(eng.ctx.db, grace, poll)
    for row in rows:
        try:
            await one(eng, row, now() - (grace if row["status"] in ("intent", "sent") else poll))
        except Exception:
            log.exception("could not reconcile operation %s", row["id"])
    return len(rows)
