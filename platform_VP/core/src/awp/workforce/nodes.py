"""Which processes of the fleet are alive, and what is done about one that died (spec 9 and 13.25, slice P5b).

Every process ("node") keeps a row in `wf_leases` named `node:<id>` and moves its `lease_until` on every quarter of
`wf_lease_seconds`; in the same step it renews the lease of the jobs its own dispatchers hold. A node is alive while that
row is in the future. Everything another process does about a node waits for the row to run out:

  its jobs            are found by the sweep with an expired lease and given another attempt (runner._recover)
  its session locks   Redis keeps the lock of a killed process for up to 600 s; the locks whose value names the dead
                      node are deleted, each by compare-and-delete (bus.FleetBus.release_of). A live node's lock is
                      never deleted: its row is in the future, and the value of a lock taken since is another one.
  its approvals       an approval whose agent never got to park, and a decided one whose agent died before it took the
                      answer in, are put right (recover.py)
  its operations      an operation it was sending is taken over by reconcile.py (the answer it may have had in hand
                      died with it)

and then the row is deleted. Burying is safe to repeat and safe to do from two survivors at once.

Without Redis the session locks live in the memory of one process, so a second process on the same database would run
the same session twice: `enter` refuses to start next to a node that is alive, and waits out the lease of one that died.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import delete, insert, select, update

from ..bus import new_node  # noqa: F401  (the engine names its process with it)
from . import tables as t
from .common import now

log = logging.getLogger("awp.workforce")

PREFIX = "node:"


def name_of(node: str) -> str:
    return PREFIX + node


async def enter(db, node: str, ttl: float, shared_bus: bool) -> None:
    """Register this process. With a bus that lives in this process's memory (`shared_bus` false) it may be the only
    one: a node whose row moves while we wait is a running process (refuse), one whose row runs out has died."""
    if not shared_bus:
        seen: dict[str, float] = {}
        while True:
            async with db.engine.connect() as conn:
                rows = dict((await conn.execute(select(t.leases.c.name, t.leases.c.lease_until).where(
                    t.leases.c.name.like(PREFIX + "%"), t.leases.c.name != name_of(node),
                    t.leases.c.lease_until >= now()))).all())
            moved = [n for n, until in rows.items() if n in seen and until > seen[n]]
            if moved:
                raise RuntimeError(
                    f"another platform process is running on this database ({moved[0]}). Several processes need a "
                    "shared message bus: set AWP_REDIS_URL for all of them, or run one process.")
            if not rows:
                break
            if not seen:
                log.warning("a platform process left its mark on this database (%s): waiting up to %.0f s to see whether "
                            "it still runs (set AWP_REDIS_URL to run several processes)", ", ".join(rows), ttl)
            seen.update(rows)
            await asyncio.sleep(min(0.5, ttl / 8))
    async with db.engine.begin() as conn:
        await conn.execute(delete(t.leases).where(t.leases.c.name == name_of(node)))  # (an engine started twice)
        await conn.execute(insert(t.leases).values(name=name_of(node), owner=node, lease_until=now() + ttl, last_run_at=now()))


async def beat(db, node: str, ttl: float, workflows: list[str]) -> bool:
    """This process lives: its row and the leases of the jobs its dispatchers hold move on. False when the row was gone
    (the others took this process for dead after it was silent for a whole lease) and had to be written again."""
    until = now() + ttl
    async with db.engine.begin() as conn:
        mine = await conn.execute(update(t.leases).where(t.leases.c.name == name_of(node), t.leases.c.owner == node)
                                  .values(lease_until=until))
        if mine.rowcount != 1:
            await conn.execute(delete(t.leases).where(t.leases.c.name == name_of(node)))
            await conn.execute(insert(t.leases).values(name=name_of(node), owner=node, lease_until=until, last_run_at=now()))
        if workflows:
            await conn.execute(update(t.jobs).where(
                t.jobs.c.status == "dispatched", t.jobs.c.lease_owner == node, t.jobs.c.workflow_id.in_(workflows))
                .values(lease_until=until))
    return mine.rowcount == 1


async def heartbeat(eng: Any) -> None:
    """The task of a running engine: say that this process lives, every quarter of the lease."""
    while True:
        try:
            held = [wid for wid, task in list(eng._tasks.items()) if not task.done()]
            if not await beat(eng.ctx.db, eng.node, eng.lease, held):
                log.error("this process (%s) was silent for a whole lease and the others took its work over; it goes on "
                          "as a live process again", eng.node)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("could not renew the lease of this process")
        await asyncio.sleep(eng.lease / 4)


async def leave(db, node: str) -> None:
    """A clean stop: nothing of this process is left to wait for."""
    async with db.engine.begin() as conn:
        await conn.execute(delete(t.leases).where(t.leases.c.name == name_of(node)))


async def alive(db, node: str | None) -> bool:
    """Does the process `node` still say it lives? (None, a row written before nodes had names, is nobody's.)"""
    if not node:
        return False
    async with db.engine.connect() as conn:
        return (await conn.execute(select(t.leases.c.name).where(
            t.leases.c.name == name_of(node), t.leases.c.owner == node, t.leases.c.lease_until >= now()))).first() is not None


async def living(db) -> set[str]:
    async with db.engine.connect() as conn:
        return set((await conn.execute(select(t.leases.c.owner).where(
            t.leases.c.name.like(PREFIX + "%"), t.leases.c.owner.like("n%"), t.leases.c.lease_until >= now()))).scalars())


async def dead(db) -> list[str]:
    async with db.engine.connect() as conn:
        names = (await conn.execute(select(t.leases.c.name).where(
            t.leases.c.name.like(PREFIX + "%"), t.leases.c.lease_until < now()))).scalars().all()
    return [n[len(PREFIX):] for n in names]


async def bury(eng: Any) -> list[str]:
    """Put right what the dead nodes left (see the module's text), then forget them. Returns the nodes buried."""
    from .recover import orphan_approvals, orphan_parks

    gone = [n for n in await dead(eng.ctx.db) if n != eng.node]
    if not gone:
        return []
    done = []
    for node in gone:
        try:
            release = getattr(eng.rt.bus, "release_of", None)  # only a bus other processes share has locks of theirs
            freed = await release(node) if release is not None else []
            if freed:
                log.warning("node %s is gone: released %s session lock(s) it left", node, len(freed))
            done.append(node)
        except Exception:
            log.exception("could not release the locks of the dead node %s", node)
    if not done:
        return []
    try:  # what it was in the middle of when it died, now that its locks do not make its sessions look busy
        await orphan_approvals(eng)
        await orphan_parks(eng)
    except Exception:
        log.exception("could not reconcile the approvals after node(s) %s died", ", ".join(done))
        return []
    async with eng.ctx.db.engine.begin() as conn:
        await conn.execute(delete(t.leases).where(t.leases.c.name.in_([name_of(n) for n in done]),
                                                  t.leases.c.lease_until < now()))
    log.warning("node(s) %s did not say they live for a whole lease and were taken over", ", ".join(done))
    return done
