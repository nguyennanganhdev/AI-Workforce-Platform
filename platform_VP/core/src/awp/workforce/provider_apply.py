"""Applying the events a provider sent (spec 7.3, contract 10): from the inbox to the operation, the public log, the
resident and, when the schema says so, the leader.

The POST only stores the event (provider_api.py). This runs afterwards, from a task the POST starts and from the sweep
(provider_sweep.py), so a lost task costs nothing: every pass is idempotent. One event is one transaction that begins with
the conversation's lock (events.lock_conversation, like every writer of a workflow) and does ALL of: the operation, its
public events, the templated message, the evidence, the wake-up job and the receipt's new state (provider_effects.py). A
crash anywhere leaves the event `accepted` and nothing else changed, and the next pass does it again.

Order: events of one operation are applied in the order they were received. The tasks of two POSTs race for the lock, so a
later event first looks for an earlier one of the same operation that is stored and not applied yet, and stands back; the
earlier one, once applied, applies the ones that stood back (`release`). An earlier event that stays unapplied for
ORDER_WAIT seconds is not waited for any longer.

An event that matches no operation yet waits as `quarantined` (the early event: it can come before the tool's own answer
stored the partner's job id), is matched again on later passes, and needs attention once it has waited too long. Events that
arrive after the workflow closed, or while its route is blocked, are kept for the audit and change nothing. An event whose
API key or signing key was revoked after it was stored is refused.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import and_, or_, select, update

from . import tables as t
from .common import now
from .events import lock_conversation
from .provider_effects import apply_effects
from .provider_match import find
from .provider_schema import Rule, Seen, mode_of, rule_of, verdict
from .routecheck import block_if_moved
from .settling import settle_waiting
from .workflows import BLOCKED, retryable, transition

log = logging.getLogger("awp.workforce")

LIVE = ("accepted", "processing", "quarantined")  # the receipts that still wait to be applied
ATTEMPTS = 3
ORDER_WAIT = 30.0  # seconds an earlier stored event of the same operation is waited for
SAID = {"STALE_EVENT": "A later event already moved the operation past this one.",
        "VERSION_CONFLICT": "An event with this provider_version and other content was already applied.",
        "VERSION_GAP": "An earlier provider_version never arrived.",
        "UNMATCHED_EVENT": "No operation matched the job id or client reference in time.",
        "JOB_CORRELATION_MISMATCH": "external_job_id and client_reference point at different operations.",
        "UNKNOWN_EVENT_TYPE": "The event type is not in the integration's event schema.",
        "KEY_REVOKED": "The key that sent this event was revoked before it was applied."}


def failure(code: str) -> dict:
    return {"code": code, "message": SAID[code]}


async def _mark(conn, receipt_id: str, status: str, *, error: str | None = None, note: str | None = None,
                op: Any = None, applied: bool = False, normalized: str | None = None) -> bool:
    """Move a receipt that still waits to its next state (compare-and-set: whoever got there first wins)."""
    values: dict[str, Any] = {"ingestion_status": status, "error": failure(error) if error else None, "note": note}
    if op is not None:
        values.update(operation_id=op["id"], workflow_id=op["workflow_id"])
    if applied:
        values["applied_at"] = now()
    if normalized:
        values["normalized_status"] = normalized
    done = await conn.execute(update(t.provider_inbox).where(
        t.provider_inbox.c.receipt_id == receipt_id, t.provider_inbox.c.ingestion_status.in_(LIVE)).values(**values))
    return done.rowcount == 1


async def _attention(conn, wf: Any, reason: str) -> None:
    if wf["state"] in ("closed", "needs_attention", "awaiting_approval", *BLOCKED):
        return  # (an approval comes first: the resident is asked something now)
    await transition(conn, wf, "needs_attention", reason=reason)
    await settle_waiting(conn, wf["id"])


async def _revoked(conn, row: Any) -> bool:
    """The API key or the signing key that sent the event was revoked since: a stolen key's queue must not run."""
    status = (await conn.execute(select(t.keys.c.status).where(t.keys.c.key_id == row["key_id"]))).scalar()
    if row["key_id"] and status != "active":
        return True
    if row["sig_key_id"]:
        signing = (await conn.execute(select(t.signing_keys.c.status).where(
            t.signing_keys.c.key_id == row["sig_key_id"], t.signing_keys.c.integration_id == row["integration_id"]))).scalar()
        return signing != "active"
    return False


# ---- one event -----------------------------------------------------------------------------------------------------
async def apply_receipt(ctx, receipt_id: str, release: bool = True) -> str | None:
    """Apply one stored event if it still waits. Returns the receipt's state afterwards (None: there is nothing to do)."""
    async with ctx.db.engine.connect() as conn:
        row = (await conn.execute(select(t.provider_inbox).where(
            t.provider_inbox.c.receipt_id == receipt_id))).mappings().first()
        if row is None or row["ingestion_status"] not in LIVE:
            return None
        integ = (await conn.execute(select(t.integrations).where(t.integrations.c.id == row["integration_id"]))).mappings().first()
        if integ is None or integ["status"] != "active":
            return row["ingestion_status"]  # nobody to apply it for
        if await _revoked(conn, row):
            return await _refuse(ctx, row, "KEY_REVOKED")
        rule = rule_of(integ["event_schema"], row["event_type"])
        ev = row["payload"]
        keyed = (await conn.execute(select(t.keys.c.routes).where(t.keys.c.key_id == row["key_id"]))).scalar()
        match = await find(conn, integ["client_id"], integ["id"], ev.get("client_reference"), ev.get("external_job_id"),
                           tuple(keyed or ("*",))) if rule is not None else None
    if rule is None or match.mismatch:
        return await _refuse(ctx, row, "UNKNOWN_EVENT_TYPE" if rule is None else "JOB_CORRELATION_MISMATCH")
    if match.op is None:
        return await _unmatched(ctx, row)
    status = ""
    for attempt in range(ATTEMPTS):
        try:
            status = await _apply(ctx, row, integ, rule, match.op["id"])
            break
        except Exception as e:
            if not retryable(e) or attempt == ATTEMPTS - 1:
                raise
            await asyncio.sleep(0.01 * (attempt + 1))
    if release and status != row["ingestion_status"]:
        await release_after(ctx, match.op["id"])  # what stood back for this event, or waited for its version, may go now
    return status


async def _refuse(ctx, row: Any, code: str) -> str:
    async with ctx.db.engine.begin() as conn:
        await _mark(conn, row["receipt_id"], "rejected", error=code)
    return "rejected"


async def _unmatched(ctx, row: Any) -> str:
    """No operation yet: wait (quarantined), and once the wait is too long a person has to look."""
    gone = now() - row["received_at"] > ctx.settings.wf_quarantine_seconds
    async with ctx.db.engine.begin() as conn:
        if gone:
            await _mark(conn, row["receipt_id"], "needs_attention", error="UNMATCHED_EVENT")
        elif row["ingestion_status"] != "quarantined":
            await _mark(conn, row["receipt_id"], "quarantined")
        await conn.execute(update(t.provider_inbox).where(t.provider_inbox.c.receipt_id == row["receipt_id"])
                           .values(checked_at=now()))
    return "needs_attention" if gone else "quarantined"


async def _apply(ctx, row: Any, integ: Any, rule: Rule, op_id: str) -> str:
    wake = None
    async with ctx.db.engine.begin() as conn:
        w = (await conn.execute(select(t.workflows.c.id, t.workflows.c.conversation_id).select_from(
            t.workflows.join(t.operations, t.operations.c.workflow_id == t.workflows.c.id))
            .where(t.operations.c.id == op_id))).one()
        await lock_conversation(conn, w[1])  # first, as for every writer of a workflow
        status, wake = await _locked(conn, ctx, row, integ, rule, op_id, w[0])
    if wake is not None:
        try:
            ctx.engine.notify(*wake)
        except Exception:
            log.exception("engine.notify failed for job %s", wake[1])
    return status


async def _behind(conn, row: Any, received: float, op_id: str) -> bool:
    """An event of the same operation that was received before this one is stored and not applied yet."""
    p = t.provider_inbox.c
    earlier = or_(p.received_at < received, and_(p.received_at == received, p.receipt_id < row["receipt_id"]))
    return (await conn.execute(select(p.receipt_id).where(
        p.operation_id == op_id, p.ingestion_status == "accepted", earlier, p.received_at > now() - ORDER_WAIT)
        .limit(1))).first() is not None


async def _same(conn, row: Any, op_id: str, version: int | None) -> bool:
    """The platform already consumed an event that says what this one says: the same version (or, without versions, the
    last one applied) with the same type and the same data."""
    p = t.provider_inbox.c
    where = [p.operation_id == op_id, p.note.is_(None), p.receipt_id != row["receipt_id"]]
    if version is not None:
        where += [p.provider_version == str(version), p.ingestion_status.in_(("applied", "rejected"))]
    else:
        where += [p.ingestion_status == "applied"]
    last = (await conn.execute(select(p.event_type, p.payload).where(*where).order_by(
        p.applied_at.desc() if version is None else p.received_at.desc()).limit(1))).first()
    return last is not None and last[0] == row["event_type"] and (last[1] or {}).get("data") == row["payload"].get("data")


async def _locked(conn, ctx, row: Any, integ: Any, rule: Rule, op_id: str, workflow_id: str) -> tuple[str, tuple | None]:
    rid, ev = row["receipt_id"], row["payload"]
    live = (await conn.execute(select(t.provider_inbox.c.ingestion_status, t.provider_inbox.c.received_at).where(
        t.provider_inbox.c.receipt_id == rid))).one()
    if live[0] not in LIVE:
        return live[0], None  # a parallel pass did it
    op = (await conn.execute(select(t.operations).where(t.operations.c.id == op_id))).mappings().one()
    wf = dict((await conn.execute(select(t.workflows).where(t.workflows.c.id == workflow_id))).mappings().one())
    note = "after_close" if wf["state"] == "closed" else None
    if note is None and wf["state"] not in BLOCKED:
        moved = await block_if_moved(conn, wf)  # a suspended or replaced route lets nothing happen by itself
        wf = moved or wf
    if note is None and wf["state"] in BLOCKED:
        note = "route_blocked"
    if note:  # kept for the audit; the workflow does not move, nobody is woken, nothing is said
        await _mark(conn, rid, "applied", note=note, op=op, applied=True, normalized=rule.status)
        return "applied", None
    if op["status"] == "intent":  # the request has not left yet: nobody can have news of it (and it must still be sent)
        await _mark(conn, rid, "quarantined")
        return "quarantined", None
    if await _behind(conn, row, live[1], op_id):
        return live[0], None  # its turn comes after the earlier event's: that one applies it when it is done

    version = ev.get("provider_version")
    held = op["provider_version"]
    seen = Seen(op["status"], op["last_rank"], int(held) if held and held.isdigit() else None)
    mode = mode_of(integ["event_schema"])
    same = await _same(conn, row, op_id, version)
    v = verdict(rule, mode, version, seen, same)
    if v.first and now() - live[1] > ctx.settings.wf_delta_first_seconds:
        v = verdict(rule, mode, version, seen, same, aged=True)  # nothing earlier came: this is where the stream starts
    if v.kind == "duplicate":
        await _mark(conn, rid, "duplicate", op=op, normalized=rule.status)
        return "duplicate", None
    if v.kind == "stale":
        if v.consume:  # old news, but it was the next version: the provider's next one is not a gap
            await conn.execute(update(t.operations).where(t.operations.c.id == op_id).values(provider_version=str(version)))
        await _mark(conn, rid, "rejected", error=v.code, op=op, normalized=rule.status)
        return "rejected", None
    if v.kind == "conflict":
        await _mark(conn, rid, "needs_attention", error=v.code, op=op, normalized=rule.status)
        return "needs_attention", None
    if v.kind == "hold":
        if not v.first and now() - live[1] > ctx.settings.wf_delta_hold_seconds:
            await _mark(conn, rid, "needs_attention", error=v.code, op=op, normalized=rule.status)
            await _attention(conn, wf, "provider_gap")
            return "needs_attention", None
        await _mark(conn, rid, "processing", op=op, normalized=rule.status)
        return "processing", None
    wake = await apply_effects(conn, ctx, row, rule, op, wf)
    await _mark(conn, rid, "applied", op=op, applied=True, normalized=rule.status)
    return "applied", wake


async def release_after(ctx, op_id: str) -> None:
    """An event of this operation was settled: the events that stood back for it, and the delta events that waited for
    its version, may follow now. Accepted ones go first, in the order received; held ones in the order of their version."""
    for _ in range(100):
        async with ctx.db.engine.connect() as conn:
            waiting = (await conn.execute(select(
                t.provider_inbox.c.receipt_id, t.provider_inbox.c.ingestion_status, t.provider_inbox.c.provider_version,
                t.provider_inbox.c.received_at).where(
                t.provider_inbox.c.operation_id == op_id,
                t.provider_inbox.c.ingestion_status.in_(("accepted", "processing"))))).all()
        waiting.sort(key=lambda r: (r[1] != "accepted", r[3] if r[1] == "accepted" else int(r[2]) if r[2] and r[2].isdigit() else 0))
        moved = False
        for rid, before, *_ in waiting:
            if await apply_receipt(ctx, rid, release=False) != before:
                moved = True
        if not moved:
            return
