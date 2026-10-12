"""Event retention (contract 12, spec 9): drop old public events of finished conversations.

Only a conversation whose workflows are all closed for longer than the retention window is
touched; an open workflow keeps its whole log, and so does a closed one with an operation that is
not over (sent, pending or unknown: contract 12). What is dropped leaves a tombstone, so an old
cursor answers 410 instead of "unknown", and `purged_through` records how far the log was cut.
The newest event always stays: it is the anchor `snapshot_cursor` points at.

`run` does all of it (events, provider dedupe rows, the finished jobs and turns and the images of closed workflows) and `tick` is the scheduled
call: under a lease (lease.py) it runs once per `retention_every_seconds` in the whole fleet. A period of 0 days keeps that kind
of data for ever. Everything here is safe to repeat and decides from the rows, never from what a previous run did.
"""
from __future__ import annotations

import logging
import os
import socket

from sqlalchemy import and_, delete, exists, func, insert, or_, select, update

from ..assets import StoreError
from . import lease, tables as t
from .close import OPEN_OPERATION
from .common import now

log = logging.getLogger("awp.workforce")

DAY = 86400.0
JOB = "retention"
LEASE_TTL = 600.0  # a run that dies holding the lease is taken over after this long
SETTLED = ("applied", "duplicate", "rejected", "needs_attention")  # receipts with an outcome; the rest are still being worked
MINIMUM_DAYS = {"event_retention_days": 90, "inbox_retention_days": 180}  # contract 12, "unless agreed otherwise"


async def purge_events(db, days: float, at: float | None = None) -> dict:
    """Purge what is past `days` days after close. Returns {"conversations": n, "events": n}."""
    cutoff = (at if at is not None else now()) - days * DAY
    purged = {"conversations": 0, "events": 0}
    # a workflow closed with an operation nobody has seen the end of keeps its log: it is the only record of it
    unfinished = select(t.operations.c.workflow_id).where(t.operations.c.status.in_(OPEN_OPERATION))
    async with db.engine.connect() as conn:
        open_conv = select(t.workflows.c.conversation_id).where(
            (t.workflows.c.state != "closed") | (t.workflows.c.closed_at.is_(None))
            | (t.workflows.c.closed_at >= cutoff) | t.workflows.c.id.in_(unfinished))
        ids = (await conn.execute(select(t.conversations.c.id).where(
            t.conversations.c.id.notin_(open_conv),
            t.conversations.c.id.in_(select(t.workflows.c.conversation_id))))).scalars().all()
    for cid in ids:
        async with db.engine.begin() as conn:
            conv = (await conn.execute(select(t.conversations).where(t.conversations.c.id == cid))).mappings().one()
            # Re-check inside the transaction: nothing reopened since the list was made.
            still = (await conn.execute(select(func.count()).select_from(t.workflows).where(
                t.workflows.c.conversation_id == cid,
                (t.workflows.c.state != "closed") | (t.workflows.c.closed_at >= cutoff)
                | t.workflows.c.id.in_(unfinished)))).scalar_one()
            if still:
                continue
            fresh = (await conn.execute(select(func.min(t.events.c.sequence)).where(
                t.events.c.conversation_id == cid, t.events.c.recorded_at >= cutoff))).scalar()
            through = min((fresh - 1) if fresh is not None else conv["last_sequence"],
                          conv["last_sequence"] - 1)  # the newest event stays
            if through <= conv["purged_through"]:
                continue
            old = (t.events.c.conversation_id == cid) & (t.events.c.sequence <= through)
            await conn.execute(insert(t.event_tombstones).from_select(
                ["event_id", "conversation_id", "sequence"],
                select(t.events.c.event_id, t.events.c.conversation_id, t.events.c.sequence).where(old)))
            n = (await conn.execute(delete(t.events).where(old))).rowcount
            await conn.execute(update(t.conversations).where(t.conversations.c.id == cid)
                               .values(purged_through=through))
            purged["conversations"] += 1
            purged["events"] += n
    return purged


def _closed_before(cutoff: float):
    """Workflows closed before `cutoff` that owe nothing: no operation whose end nobody has seen."""
    w, o = t.workflows.c, t.operations.c
    return and_(w.state == "closed", w.closed_at.is_not(None), w.closed_at < cutoff,
                ~exists().where(o.workflow_id == w.id, o.status.in_(OPEN_OPERATION)))


async def purge_inbox(db, days: float, at: float | None = None) -> int:
    """Provider dedupe rows older than `days` (contract 12: kept at least 180). Only receipts with an outcome, and not those
    of a workflow that is still open or of an operation that is not over."""
    cutoff = (at if at is not None else now()) - days * DAY
    i, w, o = t.provider_inbox.c, t.workflows.c, t.operations.c
    guarded = or_(
        exists().where(o.id == i.operation_id, o.status.in_(OPEN_OPERATION)),
        exists().where(w.id == i.workflow_id, w.state != "closed"))
    async with db.engine.begin() as conn:
        done = await conn.execute(delete(t.provider_inbox).where(
            i.received_at < cutoff, i.ingestion_status.in_(SETTLED), ~guarded))
    return done.rowcount


async def purge_leftovers(db, days: float, at: float | None = None) -> dict:
    """The finished jobs and turns of workflows closed more than `days` ago. Queued and dispatched jobs and running turns
    are never touched; the audit trail (messages, requests, operations, approvals) is not retention's to remove."""
    cutoff = (at if at is not None else now()) - days * DAY
    j, tu = t.jobs.c, t.turns.c
    gone = select(t.workflows.c.id).where(_closed_before(cutoff))
    async with db.engine.begin() as conn:
        jobs = await conn.execute(delete(t.jobs).where(j.status.in_(("done", "failed")), j.workflow_id.in_(gone)))
        turns = await conn.execute(delete(t.turns).where(tu.status != "running", tu.workflow_id.in_(gone)))
    return {"jobs": jobs.rowcount, "turns": turns.rowcount}


async def purge_assets(db, store, days: float, at: float | None = None) -> int:
    """The images (spec A3) of conversations whose workflows all closed more than `days` ago and owe nothing: the object
    leaves the store, then its row leaves the table. An image of an open workflow is never touched, nor one of a closed
    workflow with an operation nobody has seen the end of. An image that was uploaded and never sent in a message goes
    `days` after its upload, unless the conversation it was uploaded for has a workflow that is still open.

    A sent image: object first, row second, so a store that fails leaves the row and the next run tries again (deleting
    twice is fine). A never-sent image: its row first and only while it is still unsent, so a message that takes the
    image at that very moment either finds no asset or keeps it whole."""
    if store is None:
        return 0
    cutoff = (at if at is not None else now()) - days * DAY
    a, w, c = t.assets.c, t.workflows.c, t.conversations.c
    sent = and_(a.conversation_id.is_not(None), ~exists().where(w.conversation_id == a.conversation_id, ~_closed_before(cutoff)))
    unsent = and_(a.conversation_id.is_(None), a.created_at < cutoff, ~exists().where(
        c.client_id == a.client_id, c.external_conversation_id == a.external_conversation_id,
        w.conversation_id == c.id, w.state != "closed"))
    async with db.engine.connect() as conn:
        rows = (await conn.execute(select(a.id, a.object_key, a.conversation_id).where(or_(sent, unsent)))).all()
    gone = 0
    for asset_id, key, conversation in rows:
        try:
            if conversation is None:
                async with db.engine.begin() as conn:
                    claimed = await conn.execute(delete(t.assets).where(a.id == asset_id, a.conversation_id.is_(None)))
                if claimed.rowcount != 1:
                    continue
                gone += 1
                await store.delete(key)
            else:
                await store.delete(key)
                async with db.engine.begin() as conn:
                    gone += (await conn.execute(delete(t.assets).where(a.id == asset_id))).rowcount
        except StoreError as e:
            log.error("retention could not delete the object of asset %s: %s", asset_id, e)
    return gone


async def run(ctx, at: float | None = None) -> dict:
    """All the purges with the periods of the settings. Returns what each removed (`assets` only where there is a store)."""
    s, done = ctx.settings, {"events": 0, "inbox": 0, "jobs": 0, "turns": 0}
    store = getattr(getattr(ctx, "rt", None), "assets", None)
    if store is not None:
        done["assets"] = await purge_assets(ctx.db, store, s.closed_retention_days, at) if s.closed_retention_days > 0 else 0
    if s.event_retention_days > 0:
        done["events"] = (await purge_events(ctx.db, s.event_retention_days, at))["events"]
    if s.inbox_retention_days > 0:
        done["inbox"] = await purge_inbox(ctx.db, s.inbox_retention_days, at)
    if s.closed_retention_days > 0:
        done.update(await purge_leftovers(ctx.db, s.closed_retention_days, at))
    if any(done.values()):
        log.info("retention removed %s", done)
    return done


def warn_if_short(settings) -> None:
    for name, floor in MINIMUM_DAYS.items():
        days = getattr(settings, name)
        if 0 < days < floor:
            log.warning("AWP_%s=%s is below the contract's minimum of %s days (contract 12): keep it only if agreed with "
                        "the partner", name.upper(), days, floor)


def me() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


async def tick(ctx, owner: str | None = None, at: float | None = None) -> dict | None:
    """The scheduled call (every process makes it; one wins): the purge result when this caller ran it, else None."""
    period = ctx.settings.retention_every_seconds
    if period <= 0:
        return None
    ran, result = await lease.run_once(ctx.db, JOB, owner or me(), lambda: run(ctx, at), period=period, ttl=LEASE_TTL, at=at)
    return result if ran else None
