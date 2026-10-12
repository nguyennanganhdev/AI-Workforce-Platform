"""What the admin endpoints share: who is calling, and lookups that answer 404 for rows that are not the caller's.

Two kinds of caller reach /platform/v1/wf: the tenant's admin, and an operator of one management account (M6). An
endpoint is the admin's alone unless it asks `scope_of`: `tenant_of` refuses a manager's key, so an endpoint nobody
thought about is closed to managers, not open.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import select, update

from . import tables as t


@dataclass(frozen=True)
class Scope:
    """The tenant, and for a manager's key the one manager whose routes it may touch."""

    tenant: str
    manager_id: str | None = None

    def routes(self):
        """The ids of the routes the caller may see, as a subquery."""
        q = select(t.routes.c.id).where(t.routes.c.client_id.in_(tenant_clients(self.tenant)))
        return q.where(t.routes.c.manager_id == self.manager_id) if self.manager_id else q


def scope_of(request: Request) -> Scope:
    p = getattr(request.state, "principal", None)
    if p is None:
        raise HTTPException(401, "no principal")
    return Scope(p.tenant, getattr(p, "manager_id", None))


def tenant_of(request: Request) -> str:
    who = scope_of(request)
    if who.manager_id:
        raise HTTPException(403, "this needs the tenant's admin key")
    return who.tenant


async def first(conn, query, what: str):
    row = (await conn.execute(query)).mappings().first()
    if row is None:
        raise HTTPException(404, f"no such {what}")
    return row


async def lock(conn, table, row_id: str) -> None:
    """Take the write lock of one row (a route, a client) now, before anything is read that the write depends on.
    Every writer of a route's tool store locks the route first, every writer of a client's refs the client: what
    they read afterwards cannot change under them, on PostgreSQL (row lock) and on SQLite (the file's write lock,
    which a transaction only gets with its first write)."""
    if conn.dialect.name == "postgresql":
        await conn.execute(select(table.c.id).where(table.c.id == row_id).with_for_update())
    else:
        await conn.execute(update(table).where(table.c.id == row_id).values(id=table.c.id))


def tenant_clients(tenant: str):
    """The partner clients of a tenant. Its evaluation sandbox is not one: no admin or manager view shows it or anything
    that hangs on it (routes, workflows, operations, approvals)."""
    return select(t.clients.c.id).where(t.clients.c.tenant == tenant, t.clients.c.environment != t.EVAL_ENV)


async def get_route(conn, who: str | Scope, route_id: str):
    """A route of the caller: of the tenant, and for a manager one of its own (another's answers like a missing one)."""
    scope = who if isinstance(who, Scope) else Scope(who)
    return await first(conn, select(t.routes).where(t.routes.c.id == route_id, t.routes.c.id.in_(scope.routes())), "route")
