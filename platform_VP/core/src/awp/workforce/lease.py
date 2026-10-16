"""Work that exactly one process does at a time, and at most once per period: a lease row per named job.

Several processes run the same lifespan sweep. Retention (and anything else that must not run in all of them) asks
`claim` for its name: one UPDATE that succeeds for one caller only, on SQLite and on PostgreSQL alike (the row is
the lock, no advisory locks, no `FOR UPDATE`). The lease runs out after `ttl` seconds, so a process that died in the
middle of the work does not hold it: the next caller after that takes it over, and since `last_run_at` moves only when
the work ends well, the work is done again from the start (jobs run under a lease must be safe to repeat).
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from sqlalchemy import insert, or_, update
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .common import now

log = logging.getLogger("awp.workforce")


async def claim(db, name: str, owner: str, *, period: float, ttl: float, at: float | None = None) -> bool:
    """True for the one caller that may run `name` now: the lease is free and the last good run was `period` ago."""
    stamp = now() if at is None else at
    async with db.engine.begin() as conn:
        try:
            async with conn.begin_nested():  # losing the race to create the row is not an error
                await conn.execute(insert(t.leases).values(name=name, owner=None, lease_until=0.0, last_run_at=None))
        except IntegrityError:
            pass
        c = t.leases.c
        done = await conn.execute(
            update(t.leases).where(
                c.name == name, c.lease_until < stamp, or_(c.last_run_at.is_(None), c.last_run_at <= stamp - period))
            .values(owner=owner, lease_until=stamp + ttl))
        return done.rowcount == 1


async def finish(db, name: str, owner: str, *, ok: bool, at: float | None = None) -> None:
    """Give the lease back; a good run also moves `last_run_at`, so the next one is a period later."""
    stamp = now() if at is None else at
    values: dict[str, Any] = {"owner": None, "lease_until": 0.0}
    if ok:
        values["last_run_at"] = stamp
    async with db.engine.begin() as conn:
        await conn.execute(update(t.leases).where(t.leases.c.name == name, t.leases.c.owner == owner).values(**values))


async def run_once(db, name: str, owner: str, work: Callable[[], Awaitable[Any]], *, period: float, ttl: float,
                   at: float | None = None) -> tuple[bool, Any]:
    """`work()` when this caller wins the lease: (True, its result), else (False, None). A failure is logged, the
    lease is released without moving `last_run_at` and the next sweep tries again."""
    if not await claim(db, name, owner, period=period, ttl=ttl, at=at):
        return False, None
    try:
        result = await work()
    except Exception:
        log.exception("scheduled job %s failed", name)
        await finish(db, name, owner, ok=False)
        return True, None
    await finish(db, name, owner, ok=True, at=at)
    return True, result
