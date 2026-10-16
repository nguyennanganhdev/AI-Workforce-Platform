"""Which operation a provider event is about (contract 10.1): by the `client_reference` the platform sent, or by the
partner's job id. Never by a name, a note or a time. An event that names both must name ONE operation.

Only operations of the integration's own client count, and when a tool says which integration follows it, only that
integration's: a provider cannot reach another partner's work, nor another integration's. A tool that names none is
followed by the client's integration only while the client has just one: with two or more, an unbound tool is nobody's
(its events wait) until an admin binds it, so no provider can move work it was never given.
"""
from __future__ import annotations

from typing import Any, NamedTuple

from sqlalchemy import func, or_, select

from . import tables as t


class Match(NamedTuple):
    op: Any  # the operation row, or None (unknown yet, or ambiguous: the event waits)
    mismatch: bool = False  # the two identifiers point at different operations


async def sole(conn, client_id: str) -> bool:
    """The client has one integration, so a tool bound to none can only mean that one."""
    n = (await conn.execute(select(func.count()).select_from(t.integrations).where(
        t.integrations.c.client_id == client_id, t.integrations.c.status == "active"))).scalar_one()
    return n <= 1


def _scope(client_id: str, integration_id: str, routes: tuple[str, ...], unbound: bool):
    ours = select(t.workflows.c.id).where(t.workflows.c.client_id == client_id)
    mine = t.operations.c.integration_id == integration_id
    where = [t.operations.c.workflow_id.in_(ours), or_(mine, t.operations.c.integration_id.is_(None)) if unbound else mine]
    if "*" not in routes:  # a key limited to some routes reaches the operations of those routes only
        where.append(t.operations.c.route_id.in_(routes))
    return where


async def find(conn, client_id: str, integration_id: str, reference: str | None, job_id: str | None,
               routes: tuple[str, ...] = ("*",)) -> Match:
    where = _scope(client_id, integration_id, routes, await sole(conn, client_id))
    by_ref = by_job = None
    if reference:
        by_ref = (await conn.execute(select(t.operations).where(
            t.operations.c.client_reference == reference, *where))).mappings().first()
    jobs = []
    if job_id:
        jobs = (await conn.execute(select(t.operations).where(
            t.operations.c.external_job_id == job_id, *where).limit(2))).mappings().all()
        by_job = jobs[0] if len(jobs) == 1 else None
    if reference and job_id:
        if by_ref is None:
            return Match(None)  # a reference we do not know yet: the event waits
        other = [j for j in jobs if j["id"] != by_ref["id"]]
        if other or (by_ref["external_job_id"] not in (None, job_id)):
            return Match(None, True)
        return Match(by_ref)
    return Match(by_ref or by_job)
