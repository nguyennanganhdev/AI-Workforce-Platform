"""A workflow whose route was suspended or replaced does no more work (spec 5, contract 13.9).

S2 applies the block when a command arrives. Work that starts by itself (a job the engine claims, the first
write of an action) has no command to notice it, so it asks here. Call it under the conversation's lock.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from . import tables as t
from .workflows import BLOCKED, transition

TARGET = {"suspended": ("blocked_authorization", "route_suspended"), "replaced": ("blocked_route_changed", "route_replaced")}


async def block_if_moved(conn, wf: Any) -> dict | None:
    """Move the workflow to its blocked state when its route is suspended or replaced; the new row, else None."""
    if wf["state"] == "closed" or wf["state"] in BLOCKED:
        return None
    status = (await conn.execute(select(t.routes.c.status).where(t.routes.c.id == wf["route_id"]))).scalar_one()
    if status not in TARGET:
        return None
    state, reason = TARGET[status]
    return await transition(conn, wf, state, reason=reason)
