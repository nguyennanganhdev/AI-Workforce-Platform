"""Admin API of the partner side, under /platform/v1/wf (Bearer admin key, spec 7.4).

Every id is looked up through the admin's tenant, so another tenant's rows
answer 404. No secret and no hash is ever returned except the plaintext shown
once when a key is created. A manager's key (managers.py) reads its own routes here and nothing else.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import insert, literal, select, update

from . import crypto, tables as t
from .adminkit import first, get_route, lock, scope_of, tenant_clients, tenant_of
from .admin_ops import build_admin_ops
from .admin_tools import build_admin_tools
from .auth import CUSTOMER_OPS, PROVIDER_OPS
from .common import iso, now
from .crypto import SecretKeyMissing
from .managers import build_admin_managers
from .schemas import (ClientIn, IntegrationIn, KeyIn, ProviderKeyIn, ReplaceRouteIn, RotateIn,
                      RouteConfig, RouteIn)
from .tables import new_id


def client_out(r) -> dict:
    return {"client_id": r["id"], "domain": r["domain"], "environment": r["environment"],
            "name": r["name"], "status": r["status"], "capabilities": list(r["capabilities"] or []),
            "created_at": iso(r["created_at"])}


def key_out(r) -> dict:
    return {"key_id": r["key_id"], "kind": r["kind"], "client_id": r["client_id"],
            "integration_id": r["integration_id"], "operations": list(r["operations"]),
            "routes": list(r["routes"]), "status": r["status"], "expires_at": iso(r["expires_at"]),
            "created_at": iso(r["created_at"]), "revoked_at": iso(r["revoked_at"])}


def route_out(r) -> dict:
    return {"route_id": r["id"], "client_id": r["client_id"],
            "external_management_ref": r["external_management_ref"], "status": r["status"],
            "revision": r["revision"], "leader_profile": r["leader_profile"], "manager_id": r["manager_id"],
            "config": r["config"], "created_at": iso(r["created_at"])}


def integration_out(r, signing: list | None = None) -> dict:
    out = {"integration_id": r["id"], "client_id": r["client_id"], "status": r["status"],
           "event_schema": r["event_schema"], "created_at": iso(r["created_at"])}
    if signing is not None:
        out["signing_keys"] = [{"key_id": s["key_id"], "status": s["status"],
                                "created_at": iso(s["created_at"])} for s in signing]
    return out


def _shown_once(status: int, body: dict) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def build_admin(ctx: Any) -> APIRouter:
    r = APIRouter(prefix="/platform/v1/wf", tags=["workforce-admin"])
    db, sealer = ctx.db, ctx.sealer

    def client_q(tenant: str, client_id: str):
        return select(t.clients).where(t.clients.c.id == client_id, t.clients.c.tenant == tenant,
                                       t.clients.c.environment != t.EVAL_ENV)  # the sandbox client gets no key, route or integration

    async def active_client(conn, tenant: str, client_id: str):
        c = await first(conn, client_q(tenant, client_id), "client")
        if c["status"] != "active":
            raise HTTPException(409, "client is not active")
        return c

    async def get_integration(conn, tenant: str, integration_id: str):
        return await first(conn, select(t.integrations).where(
            t.integrations.c.id == integration_id,
            t.integrations.c.client_id.in_(tenant_clients(tenant))),
            "integration")

    async def get_key(conn, tenant: str, key_id: str):
        mine = tenant_clients(tenant)
        theirs = select(t.integrations.c.id).where(t.integrations.c.client_id.in_(mine))
        return await first(conn, select(t.keys).where(
            t.keys.c.key_id == key_id,
            t.keys.c.client_id.in_(mine) | t.keys.c.integration_id.in_(theirs)), "key")

    async def check_scope(conn, client_id: str, operations: list[str], routes: list[str], allowed) -> None:
        bad = [o for o in operations if o not in allowed]
        if bad:
            raise HTTPException(422, f"unknown operations for this key kind: {bad}")
        if routes != ["*"]:
            have = {x for x in (await conn.execute(select(t.routes.c.id).where(
                t.routes.c.client_id == client_id, t.routes.c.id.in_(routes)))).scalars()}
            if set(routes) - have:
                raise HTTPException(422, "routes must be routes of this client")

    async def issue(conn, owner: dict, kind: str, operations: list[str], routes: list[str],
                    expires_at) -> tuple[dict, str]:
        key_id, _, full = crypto.new_api_key()
        secret = full.split(".", 1)[1]
        row = dict(key_id=key_id, kind=kind, secret_hash=crypto.hash_secret(secret),
                   operations=operations, routes=routes, status="active",
                   expires_at=expires_at.timestamp() if expires_at else None,
                   created_at=now(), revoked_at=None)
        row.update({"client_id": None, "integration_id": None, **owner})
        await conn.execute(insert(t.keys).values(**row))
        return row, full

    async def new_signing_key(conn, integration_id: str) -> dict:
        key_id, secret = crypto.new_signing_secret()
        try:
            sealed = sealer.seal(secret)
        except SecretKeyMissing:
            raise HTTPException(503, "AWP_SECRET_KEY is not set; signing keys cannot be stored")
        await conn.execute(insert(t.signing_keys).values(
            key_id=key_id, integration_id=integration_id, secret_enc=sealed,
            status="active", created_at=now()))
        return {"key_id": key_id, "secret": secret}

    # ---- clients -------------------------------------------------------
    @r.post("/clients", status_code=201)
    async def create_client(body: ClientIn, request: Request):
        tenant = tenant_of(request)
        row = dict(id=new_id("client"), tenant=tenant, domain=body.domain,
                   environment=body.environment, name=body.name, status="active",
                   capabilities=list(body.capabilities), created_at=now())
        async with db.engine.begin() as conn:
            await conn.execute(insert(t.clients).values(**row))
        return client_out(row)

    @r.get("/clients")
    async def list_clients(request: Request):
        tenant = tenant_of(request)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(select(t.clients).where(t.clients.c.tenant == tenant, t.clients.c.environment != t.EVAL_ENV)
                                       .order_by(t.clients.c.created_at))).mappings().all()
        return {"clients": [client_out(x) for x in rows]}

    @r.get("/clients/{client_id}")
    async def get_client(client_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.connect() as conn:
            return client_out(await first(conn, client_q(tenant, client_id), "client"))

    # ---- customer keys ---------------------------------------------------
    @r.post("/clients/{client_id}/keys", status_code=201)
    async def create_key(client_id: str, body: KeyIn, request: Request):
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            await active_client(conn, tenant, client_id)
            await check_scope(conn, client_id, body.operations, body.routes, CUSTOMER_OPS)
            row, full = await issue(conn, {"client_id": client_id}, "customer",
                                    body.operations, body.routes, body.expires_at)
        return _shown_once(201, {**key_out(row), "api_key": full})

    @r.get("/clients/{client_id}/keys")
    async def list_keys(client_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.connect() as conn:
            await first(conn, client_q(tenant, client_id), "client")
            rows = (await conn.execute(select(t.keys).where(t.keys.c.client_id == client_id)
                                       .order_by(t.keys.c.created_at))).mappings().all()
        return {"keys": [key_out(x) for x in rows]}

    @r.post("/keys/{key_id}/revoke")
    async def revoke_key(key_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            old = await get_key(conn, tenant, key_id)
            if old["status"] != "revoked":
                await conn.execute(update(t.keys).where(t.keys.c.key_id == key_id)
                                   .values(status="revoked", revoked_at=now()))
            return key_out(await first(conn, select(t.keys).where(t.keys.c.key_id == key_id), "key"))

    @r.post("/keys/{key_id}/rotate", status_code=201)
    async def rotate_key(key_id: str, request: Request, body: RotateIn | None = None):
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            old = await get_key(conn, tenant, key_id)
            if old["status"] != "active":
                raise HTTPException(409, "only an active key can be rotated")
            expires = body.expires_at if body and body.expires_at else None
            if expires is None and old["expires_at"] is not None:
                if old["expires_at"] <= now():
                    raise HTTPException(422, "key has expired: send a new expires_at")
                expires = datetime.fromtimestamp(old["expires_at"], timezone.utc)
            owner = {"client_id": old["client_id"]} if old["client_id"] else {
                "integration_id": old["integration_id"]}
            # Retire the old key first, only if it is still active: a parallel rotate or a revoke
            # that got there first leaves nothing to replace, so no second live successor appears.
            done = await conn.execute(update(t.keys).where(
                t.keys.c.key_id == key_id, t.keys.c.status == "active")
                .values(status="revoked", revoked_at=now()))
            if done.rowcount != 1:
                raise HTTPException(409, "only an active key can be rotated")
            row, full = await issue(conn, owner, old["kind"], list(old["operations"]),
                                    list(old["routes"]), expires)
        return _shown_once(201, {**key_out(row), "api_key": full, "replaces": key_id})

    # ---- routes ----------------------------------------------------------
    def normalize(cfg: RouteConfig) -> dict:
        out = cfg.model_dump()
        if out["wait_seconds"] is None:
            out["wait_seconds"] = ctx.settings.wf_wait_seconds
        if out["policy"]["approval_ttl_seconds"] is None:
            out["policy"]["approval_ttl_seconds"] = ctx.settings.approval_ttl_seconds
        return out

    async def need_leader(tenant: str, key: str) -> None:
        """A route whose leader does not exist would accept requests that no agent can ever take (M4)."""
        newest = await ctx.rt.profiles.latest(tenant, key)
        if newest is None or newest.profile.role != "leader":
            raise HTTPException(422, f"leader_profile {key!r} is not a leader profile of this tenant")

    async def own_ref(conn, client_id: str, ref: str, manager_id: str | None) -> None:
        """One ref, one manager (M6): a second account cannot take over an area by naming it, on a new route or on
        a replacement. The client's row is locked first, so two routes made at once for one ref are judged one
        after the other."""
        await lock(conn, t.clients, client_id)
        others = (await conn.execute(select(t.routes.c.manager_id).where(
            t.routes.c.client_id == client_id, t.routes.c.external_management_ref == ref,
            t.routes.c.status != "replaced"))).scalars().all()
        if any(m and m != manager_id for m in others):  # a route older than managers (null) holds no ref for anybody
            raise HTTPException(409, "this external_management_ref belongs to another manager")

    @r.post("/clients/{client_id}/routes", status_code=201)
    async def create_route(client_id: str, body: RouteIn, request: Request):
        tenant = tenant_of(request)
        row = dict(id=new_id("route"), client_id=client_id, status="pending", revision=1,
                   external_management_ref=body.external_management_ref, manager_id=body.manager_id,
                   leader_profile=body.leader_profile, config=normalize(body.config), created_at=now())
        async with db.engine.connect() as conn:
            await active_client(conn, tenant, client_id)  # first: another tenant's client is a 404 whatever the body says
        await need_leader(tenant, body.leader_profile)
        async with db.engine.begin() as conn:
            await active_client(conn, tenant, client_id)
            manager = (await conn.execute(select(t.managers.c.status).where(
                t.managers.c.id == body.manager_id, t.managers.c.client_id == client_id))).scalar()
            if manager != "active":  # another client's manager answers like a missing one
                raise HTTPException(422, "manager_id is not an active manager of this client")
            await own_ref(conn, client_id, body.external_management_ref, body.manager_id)
            await conn.execute(insert(t.routes).values(**row))
        return route_out(row)

    @r.get("/routes")
    async def list_routes(request: Request, client_id: str | None = None, status: str | None = None,
                          manager_id: str | None = None):
        who = scope_of(request)
        q = select(t.routes).where(t.routes.c.id.in_(who.routes()))
        for column, value in ((t.routes.c.client_id, client_id), (t.routes.c.status, status),
                              (t.routes.c.manager_id, manager_id)):
            if value:
                q = q.where(column == value)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(q.order_by(t.routes.c.created_at))).mappings().all()
        return {"routes": [route_out(x) for x in rows]}

    @r.get("/routes/{route_id}")
    async def read_route(route_id: str, request: Request):
        async with db.engine.connect() as conn:
            return route_out(await get_route(conn, scope_of(request), route_id))

    @r.post("/routes/{route_id}/suspend")
    async def suspend_route(route_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            await get_route(conn, tenant, route_id)
            # The transition is decided by the row itself, not by an earlier read.
            await conn.execute(update(t.routes).where(
                t.routes.c.id == route_id, t.routes.c.status.notin_(("replaced", "suspended")))
                .values(status="suspended", revision=t.routes.c.revision + 1))
            cur = await get_route(conn, tenant, route_id)
            if cur["status"] == "replaced":
                raise HTTPException(409, "route was replaced")
            return route_out(cur)

    @r.post("/routes/{route_id}/replace", status_code=201)
    async def replace_route(route_id: str, request: Request, body: ReplaceRouteIn | None = None):
        """The old route keeps its workflows; the new one starts pending and needs confirming. It belongs to the same
        manager and starts with the old one's tool store (servers, tools and their states), so replacing a route
        does not throw away what was discovered and activated."""
        tenant = tenant_of(request)
        body = body or ReplaceRouteIn()
        if body.leader_profile:
            async with db.engine.connect() as conn:
                await get_route(conn, tenant, route_id)
            await need_leader(tenant, body.leader_profile)
        async with db.engine.begin() as conn:
            old = await get_route(conn, tenant, route_id)
            await active_client(conn, tenant, old["client_id"])
            if body.external_management_ref and body.external_management_ref != old["external_management_ref"]:
                await own_ref(conn, old["client_id"], body.external_management_ref, old["manager_id"])
            # Only one replace can win the move to "replaced"; the others see zero rows.
            done = await conn.execute(update(t.routes).where(
                t.routes.c.id == route_id, t.routes.c.status != "replaced")
                .values(status="replaced", revision=t.routes.c.revision + 1))
            if done.rowcount != 1:
                raise HTTPException(409, "route was already replaced")
            new = dict(id=new_id("route"), client_id=old["client_id"], status="pending", revision=1,
                       external_management_ref=body.external_management_ref or old["external_management_ref"],
                       leader_profile=body.leader_profile or old["leader_profile"], manager_id=old["manager_id"],
                       config=normalize(body.config) if body.config else old["config"], created_at=now())
            await conn.execute(insert(t.routes).values(**new))
            for table in (t.mcp_servers, t.tools):  # sealed headers travel as they are: the same key opens them
                cols = [c for c in table.c if c.name != "route_id"]
                await conn.execute(insert(table).from_select(
                    ["route_id", *(c.name for c in cols)],
                    select(literal(new["id"]), *cols).where(table.c.route_id == route_id)))
        return {"replaced": route_id, "route": route_out(new)}

    # ---- integrations and provider keys -------------------------------------
    @r.post("/clients/{client_id}/integrations", status_code=201)
    async def create_integration(client_id: str, body: IntegrationIn, request: Request):
        tenant = tenant_of(request)
        row = dict(id=new_id("intg"), client_id=client_id, status="active",
                   event_schema=body.event_schema.model_dump(), created_at=now())
        async with db.engine.begin() as conn:
            await active_client(conn, tenant, client_id)
            await conn.execute(insert(t.integrations).values(**row))
        return integration_out(row)

    @r.get("/integrations")
    async def list_integrations(request: Request, client_id: str | None = None):
        tenant = tenant_of(request)
        q = select(t.integrations).where(t.integrations.c.client_id.in_(
            select(t.clients.c.id).where(t.clients.c.tenant == tenant)))
        if client_id:
            q = q.where(t.integrations.c.client_id == client_id)
        async with db.engine.connect() as conn:
            rows = (await conn.execute(q.order_by(t.integrations.c.created_at))).mappings().all()
        return {"integrations": [integration_out(x) for x in rows]}

    @r.get("/integrations/{integration_id}")
    async def read_integration(integration_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.connect() as conn:
            row = await get_integration(conn, tenant, integration_id)
            signing = (await conn.execute(select(t.signing_keys).where(
                t.signing_keys.c.integration_id == integration_id)
                .order_by(t.signing_keys.c.created_at))).mappings().all()
        return integration_out(row, signing)

    @r.post("/integrations/{integration_id}/keys", status_code=201)
    async def create_provider_key(integration_id: str, request: Request, body: ProviderKeyIn | None = None):
        """A provider API key and its first signing key; both secrets are shown once."""
        tenant = tenant_of(request)
        body = body or ProviderKeyIn()
        async with db.engine.begin() as conn:
            integ = await get_integration(conn, tenant, integration_id)
            if integ["status"] != "active":
                raise HTTPException(409, "integration is not active")
            await check_scope(conn, integ["client_id"], body.operations, body.routes, PROVIDER_OPS)
            row, full = await issue(conn, {"integration_id": integration_id}, "provider",
                                    body.operations, body.routes, body.expires_at)
            signing = await new_signing_key(conn, integration_id)
        return _shown_once(201, {**key_out(row), "api_key": full, "signing_key": signing})

    @r.get("/integrations/{integration_id}/keys")
    async def list_provider_keys(integration_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.connect() as conn:
            await get_integration(conn, tenant, integration_id)
            rows = (await conn.execute(select(t.keys).where(t.keys.c.integration_id == integration_id)
                                       .order_by(t.keys.c.created_at))).mappings().all()
        return {"keys": [key_out(x) for x in rows]}

    @r.post("/integrations/{integration_id}/signing-keys", status_code=201)
    async def add_signing_key(integration_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            await get_integration(conn, tenant, integration_id)
            signing = await new_signing_key(conn, integration_id)
        return _shown_once(201, {"signing_key": signing})

    @r.post("/integrations/{integration_id}/signing-keys/{key_id}/revoke")
    async def revoke_signing_key(integration_id: str, key_id: str, request: Request):
        tenant = tenant_of(request)
        async with db.engine.begin() as conn:
            await get_integration(conn, tenant, integration_id)
            await first(conn, select(t.signing_keys).where(
                t.signing_keys.c.key_id == key_id, t.signing_keys.c.integration_id == integration_id),
                "signing key")
            await conn.execute(update(t.signing_keys).where(t.signing_keys.c.key_id == key_id)
                               .values(status="revoked"))
        return {"key_id": key_id, "status": "revoked"}

    build_admin_managers(r, ctx)
    build_admin_tools(r, ctx)
    build_admin_ops(r, ctx)
    return r
