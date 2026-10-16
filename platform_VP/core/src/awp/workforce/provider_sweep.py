"""The sweep over the provider events that wait (the safety net behind the task each POST starts).

Fair by construction. The events that have an operation (accepted, or held for a version) are all gone through, oldest
first, a page at a time until none is left; only then the quarantined ones, which may match an operation by now. A flood of
events that match nothing therefore delays nothing that has an operation, whoever sent it. A quarantined event is looked at
on every pass while it is young (an early event is matched as soon as the tool's answer stores the job id) and only every
QUIET seconds after that. The number of events one integration may leave quarantined is capped at the door (provider_api.py).
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import and_, or_, select

from . import tables as t
from .common import now
from .provider_apply import apply_receipt

log = logging.getLogger("awp.workforce")

PAGE = 100
QUIET = 30.0  # seconds between two looks at a quarantined event that is older than this
_TASKS: set[asyncio.Task] = set()


async def _pages(ctx, statuses: tuple[str, ...], limit: int):
    """The receipt ids in `statuses`, oldest first, one page after the other (keyset: nothing is skipped or seen twice)."""
    p, after = t.provider_inbox.c, (0.0, "")
    while True:
        where = [p.ingestion_status.in_(statuses), or_(p.received_at > after[0], and_(p.received_at == after[0], p.receipt_id > after[1]))]
        if "quarantined" in statuses:
            soon = now() - QUIET
            where.append(or_(p.checked_at.is_(None), p.received_at > soon, p.checked_at < soon))
        async with ctx.db.engine.connect() as conn:
            page = (await conn.execute(select(p.receipt_id, p.received_at).where(*where)
                                       .order_by(p.received_at, p.receipt_id).limit(limit))).all()
        if not page:
            return
        yield [rid for rid, _ in page]
        if len(page) < limit:
            return
        after = (page[-1][1], page[-1][0])


async def apply_pending(ctx, limit: int = PAGE) -> int:
    """One pass over the events that wait. Returns how many it looked at."""
    seen = 0
    for statuses in (("accepted", "processing"), ("quarantined",)):
        async for ids in _pages(ctx, statuses, limit):
            for rid in ids:
                try:
                    await apply_receipt(ctx, rid)
                except Exception:
                    log.exception("could not apply provider event %s", rid)
            seen += len(ids)
    return seen


def schedule(ctx, receipt_id: str) -> None:
    """Apply right after the POST, without making the provider wait for it."""
    async def run() -> None:
        try:
            await apply_receipt(ctx, receipt_id)
        except Exception:
            log.exception("could not apply provider event %s", receipt_id)

    task = asyncio.get_running_loop().create_task(run())
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


async def stop() -> None:
    tasks = list(_TASKS)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
