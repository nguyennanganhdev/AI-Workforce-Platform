"""Management accounts (M6): a client's managers, and the operator keys that act for one of them.

A route belongs to exactly one manager. A manager key (`Bearer mk_<id>.<secret>`, stored hashed like a partner's key)
sees and operates only what hangs off its own routes: workflows, operations, approvals, receipts, `resolve`, the tool
store, and the profiles those routes use. The tenant's admin key stays the superuser, and only it makes managers,
their keys and routes. `ManagerKeys` is what SecurityMiddleware asks; the scoping itself is in adminkit (`scope_of`).
"""
from __future__ import annotations

import re
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select, update

from ..security import MANAGER_PREFIX, Principal
from . import crypto, tables as t
from .adminkit import first, tenant_clients, tenant_of
from .common import iso, now
from .schemas import ManagerIn, ManagerKeyIn
from .tables import new_id

_KEY = re.compile(r"^mk_([A-Za-z0-9_-]{6,64})\.([A-Za-z0-9_-]{16,128})$")


class ManagerKeys:
    """Resolves a manager's Bearer key to its principal, or to nobody. A key that is unknown, revoked or expired, or whose
    manager or client is switched off, is the same nobody, and an unknown id costs the same comparison as a known one."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def __call__(self, token: str) -> Principal | None:
        m = _KEY.match(token)
        key_id, secret = m.groups() if m else ("", token)
        async with self.db.engine.connect() as conn:
            row = (await conn.execute(select(
                t.manager_keys.c.secret_hash, t.manager_keys.c.status, t.manager_keys.c.expires_at,
                t.managers.c.id, t.managers.c.tenant, t.managers.c.status.label("manager_status"),
                t.clients.c.status.label("client_status")).select_from(
                t.manager_keys.join(t.managers, t.managers.c.id == t.manager_keys.c.manager_id)
                .join(t.clients, t.clients.c.id == t.managers.c.client_id)).where(
                t.manager_keys.c.key_id == key_id))).mappings().first()
        if not crypto.verify_secret(secret, row["secret_hash"] if row else None):
            return None
        live = (row["status"] == "active" and row["manager_status"] == "active" and row["client_status"] == "active"
                and (row["expires_at"] is None or row["expires_at"] > now()))
        return Principal(row["tenant"], manager_id=row["id"]) if live else None


def manager_out(m: Any) -> dict:
    return {"manager_id": m["id"], "client_id": m["client_id"], "name": m["name"], "status": m["status"],
            "created_at": iso(m["created_at"])}


def key_out(k: Any) -> dict:
    return {"key_id": k["key_id"], "manager_id": k["manager_id"], "status": k["status"],
            "expires_at": iso(k["expires_at"]), "created_at": iso(k["created_at"]), "revoked_at": iso(k["revoked_at"])}


async def get_manager(conn, tenant: str, manager_id: str) -> Any:
    return await first(conn, select(t.managers).where(
        t.managers.c.id == manager_id, t.managers.c.tenant == tenant), "manager")


def build_admin_managers(r: APIRouter, ctx: Any) -> None:
    """Only the tenant admin: every handler asks `tenant_of`, which refuses a manager's key."""
    db = ctx.db

    @r.post("/clients/{client_id}/managers", status_code=201)
    async def create_manager(client_id: str, body: ManagerIn, request: Request):
        tenant = tenant_of(request)
        row = dict(id=new_id("mgr"), tenant=tenant, client_id=client_id, name=body.name, status="active", created_at=now())
        async with db.engine.begin() as conn:
            await first(conn, select(t.clients).where(t.clients.c.id == client_id, t.clients.c.id.in_(tenant_clients(tenant))), "client")
            await conn.execute(insert(t.managers).values(**row))
        return manager_out(row)

    @r.get("/managers")
    async def list_managers(request: Request, client_id: str | None = None):
        tenant = tenant_of(request)
        q = select(t.managers).where(t.managers.c.tenant == tenant, t.managers.c.client_id.in_(tenant_clients(tenant)))
        if client_id:
            q = q.where(t.managers.c.client_id == client_id)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(q.order_by(t.managers.c.created_at))).mappings().all()
        return {"managers": [manager_out(m) for m in rows]}

    @r.get("/managers/{manager_id}")
    async def read_manager(manager_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.connect() as conn:
            return manager_out(await get_manager(conn, tenant, manager_id))

    async def set_status(request: Request, manager_id: str, status: str) -> dict:
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            await get_manager(conn, tenant, manager_id)
            await conn.execute(update(t.managers).where(t.managers.c.id == manager_id).values(status=status))
            return manager_out(await get_manager(conn, tenant, manager_id))

    @r.post("/managers/{manager_id}/disable")
    async def disable_manager(manager_id: str, request: Request):
        """Its keys stop working at once; its routes and their workflows go on (the admin still operates them)."""
        return await set_status(request, manager_id, "disabled")

    @r.post("/managers/{manager_id}/enable")
    async def enable_manager(manager_id: str, request: Request):
        return await set_status(request, manager_id, "active")

    @r.post("/managers/{manager_id}/keys", status_code=201)
    async def create_key(manager_id: str, request: Request, body: ManagerKeyIn | None = None):
        tenant = tenant_of(request)
        key_id, secret = secrets.token_hex(8), secrets.token_urlsafe(32)
        expires = body.expires_at if body else None
        row = dict(key_id=key_id, manager_id=manager_id, secret_hash=crypto.hash_secret(secret), status="active",
                   expires_at=expires.timestamp() if expires else None, created_at=now(), revoked_at=None)
        async with db.engine.begin() as conn:
            if (await get_manager(conn, tenant, manager_id))["status"] != "active":
                raise HTTPException(409, "manager is not active")
            await conn.execute(insert(t.manager_keys).values(**row))
        return JSONResponse({**key_out(row), "api_key": f"{MANAGER_PREFIX}{key_id}.{secret}"}, status_code=201,
                            headers={"Cache-Control": "no-store"})  # shown once; only its hash is kept

    @r.get("/managers/{manager_id}/keys")
    async def list_keys(manager_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.connect() as conn:
            await get_manager(conn, tenant, manager_id)
            rows = (await conn.execute(select(t.manager_keys).where(t.manager_keys.c.manager_id == manager_id)
                                       .order_by(t.manager_keys.c.created_at))).mappings().all()
        return {"keys": [key_out(k) for k in rows]}

    @r.post("/managers/{manager_id}/keys/{key_id}/revoke")
    async def revoke_key(manager_id: str, key_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            await get_manager(conn, tenant, manager_id)
            mine = (t.manager_keys.c.key_id == key_id) & (t.manager_keys.c.manager_id == manager_id)
            await first(conn, select(t.manager_keys).where(mine), "key")
            await conn.execute(update(t.manager_keys).where(mine, t.manager_keys.c.status == "active")
                               .values(status="revoked", revoked_at=now()))
            return key_out(await first(conn, select(t.manager_keys).where(mine), "key"))
