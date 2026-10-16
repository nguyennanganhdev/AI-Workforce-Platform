"""Small reads the agent side needs: which workflow a case belongs to, its route's rules, which request a
message belongs to. The tools and middlewares of a room use these; the engine has its own queries."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select

from ..guard import PhraseRule, Rules
from . import tables as t


async def workflow_of_case(db, case_id: str) -> dict | None:
    """The workflow row of a case. Every case of the platform has one; None only for an id that is not a case."""
    async with db.engine.connect() as conn:
        row = (await conn.execute(select(t.workflows).where(t.workflows.c.case_id == case_id))).mappings().first()
    return dict(row) if row else None


# Every route: a claim that work is done or booked needs the platform's own mark on a result (jobs.verified): the
# partner's system said the work is done, in a field of its answer. The resident's words never do, and neither does any
# text inside a result (a note someone typed into a ticket, the prose of a pending answer): the mark is defused in
# everything a partner sends. A route adds its own rules to these; it cannot take them away.
DONE_CLAIMS = PhraseRule(
    phrases=(
        # the ways to say that work has been carried out. Matching is by substring and does not read negation, so the forms
        # an honest "nothing is done yet" / "nothing was booked" uses (a bare "is done", "was booked") are left out.
        "has been fixed", "is fixed", "is now fixed", "have fixed", "has been repaired", "is repaired", "have repaired",
        "has been completed", "is completed", "has completed", "have completed", "is now complete", "work is complete",
        "work is done", "job is done", "is now done", "all done", "has been done", "has finished", "have finished",
        "has been finished", "work is finished", "is now finished", "has been resolved", "is now resolved",
        "has been booked", "have booked", "has been confirmed",
        # Vietnamese, with and without the marks
        "đã sửa xong", "đã xong", "xong rồi", "đã được sửa", "đã khắc phục", "đã được khắc phục", "đã giải quyết",
        "đã được giải quyết", "đã hoàn thành", "đã được hoàn thành", "hoàn thành rồi", "đã hoàn tất", "hoàn tất rồi",
        "công việc hoàn tất", "việc hoàn tất", "công việc hoàn thành", "đã đặt xong",
        "da sua xong", "da xong", "xong roi", "da duoc sua", "da khac phuc", "da giai quyet", "da hoan thanh",
        "hoan thanh roi", "da hoan tat", "hoan tat roi", "cong viec hoan tat", "viec hoan tat", "da dat xong"),
    reason="work is not done, booked or confirmed unless a system result you cite says so",
    unless=("<platform-verified>",))


# Only the partner's close ends a workflow, and the leader cannot call it: whatever the resident is told about
# the request being closed would be untrue. There is no `unless`: no tool result can make it so.
CLOSED_CLAIMS = PhraseRule(
    phrases=("request is closed", "request has been closed", "request was closed", "ticket is closed",
             "ticket has been closed", "ticket was closed", "case is closed", "case has been closed",
             "i have closed", "i've closed", "i closed", "we have closed", "we've closed",
             "yêu cầu của bạn đã đóng", "yêu cầu đã đóng", "yêu cầu đã được đóng", "phiếu đã đóng", "đã đóng yêu cầu",
             "đã đóng phiếu", "đóng yêu cầu", "đóng phiếu", "yeu cau da dong", "da dong yeu cau"),
    reason="only the partner can close a request, and you cannot: do not tell the resident it is closed")


def rules_of(config: dict) -> Rules:
    """The route's rules (`config.rules`) as the guard wants them, after the rules of every route."""
    cfg = (config or {}).get("rules") or {}
    rules = Rules(phrase_rules=[DONE_CLAIMS, CLOSED_CLAIMS, *(PhraseRule(tuple(r["phrases"]), r["reason"], tuple(r.get("unless") or ()))
                                               for r in cfg.get("phrase_rules") or [])])
    if cfg.get("safe_reply"):
        rules.safe_reply = cfg["safe_reply"]
    return rules


_MARK = re.compile(r"<platform-verified>.*?</platform-verified>\n?", re.S)


def unmarked(text: str) -> str:
    """`text` without the platform's done mark: what evidence says once what it proved has been withdrawn."""
    return _MARK.sub("", text)


async def withdrawn(db, view: Any) -> set[str]:
    """The evidence of a case that was written about an operation (`op`) that is not `completed` now: the provider reported
    the work done and then reopened it, so the mark on that evidence no longer proves it. A pending operation never had
    its work verified, so evidence that carries the mark cannot be about it either."""
    ops = {ref: e.data["op"] for ref, e in view.evidence.items() if e.data.get("op")}
    if not ops:
        return set()
    async with db.engine.connect() as conn:
        done = set((await conn.execute(select(t.operations.c.id).where(
            t.operations.c.id.in_(set(ops.values())), t.operations.c.status == "completed"))).scalars())
    return {ref for ref, op in ops.items() if op not in done}


async def route_of(conn, workflow: Any) -> dict:
    return dict((await conn.execute(select(t.routes).where(t.routes.c.id == workflow["route_id"]))).mappings().one())


async def inflight_request(conn, workflow_id: str) -> str | None:
    """The request a message written now belongs to: that of the dispatched job, else the newest request
    still waiting, else none (a message nobody asked for, such as a report that woke the leader late)."""
    job = (await conn.execute(select(t.jobs.c.request_id).where(
        t.jobs.c.workflow_id == workflow_id, t.jobs.c.status == "dispatched"))).first()
    if job is not None and job[0]:
        return job[0]
    waiting = (await conn.execute(select(t.requests.c.id).where(
        t.requests.c.workflow_id == workflow_id, t.requests.c.status.in_(("accepted", "queued", "running")))
        .order_by(t.requests.c.accepted_at.desc()).limit(1))).first()
    return waiting[0] if waiting else None
