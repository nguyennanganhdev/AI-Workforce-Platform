"""Callers that are not people: integration clients, delegations and the tool catalog.

The contract is docs/domain/HOP_DONG_TICH_HOP.md. Three rules shape this module:
  * deny by default: a delegated call works only for an operation named in TOOLS;
  * act on behalf, not instead: the person's own authority checks still run on every call;
  * leave a trail: what a delegation does is recorded as an agent action on that person's behalf.
"""

import contextvars
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .v3_audit import audit

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
LEVELS = ("read", "draft", "act_small", "propose")
TOKEN_PREFIX = "dg1_"
MAX_TTL_SECONDS = 600
MAX_CALLS = 120
# What each purpose may ever hold; a client's own levels can only narrow it further.
PURPOSES = {
    "resident_assistant": ("resident", ("read", "draft", "act_small")),
    "staff_assistant": ("staff", ("read", "draft", "propose")),
}

# The delegation behind the request being served, for the audit trail. Set when a delegated call is accepted.
CURRENT: contextvars.ContextVar[dict | None] = contextvars.ContextVar("integration_delegation", default=None)


@dataclass(frozen=True)
class Tool:
    name: str
    persona: Literal["resident", "staff"]
    level: Literal["read", "draft", "act_small", "propose"]
    method: str
    path: str
    description: str


def _r(name, level, method, path, description):
    return Tool(name, "resident", level, method, path, description)


def _s(name, level, method, path, description):
    return Tool(name, "staff", level, method, path, description)


# The allow-list. Anything not here is invisible to a delegated caller (404). Nothing here approves,
# pays, closes, dispatches or changes who may do what: those stay with people (contract section 3.3).
TOOLS: list[Tool] = [
    _r("resident.me", "read", "GET", "/resident/me", "Who the resident is and which homes they are linked to"),
    _r("resident.context", "read", "GET", "/resident/context", "Verified homes of the resident, to choose one"),
    _r("resident.tickets.list", "read", "GET", "/resident/tickets", "The resident's requests"),
    _r("resident.tickets.get", "read", "GET", "/resident/tickets/{ticket_id}", "One request of the resident"),
    _r("resident.tickets.progress", "read", "GET", "/resident/tickets/{ticket_id}/progress", "Where a request stands"),
    _r("resident.plans.list", "read", "GET", "/resident/plans", "Plans waiting for the resident's own decision"),
    _r("resident.notifications.list", "read", "GET", "/my/notifications", "The resident's notifications"),
    _s("staff.me", "read", "GET", "/operations/me", "Who the staff member is and what they may do"),
    _s("staff.tickets.list", "read", "GET", "/tickets", "Requests visible to the staff member"),
    _s("staff.tickets.get", "read", "GET", "/tickets/{ticket_id}", "One request"),
    _s("staff.tickets.timeline", "read", "GET", "/tickets/{ticket_id}/timeline", "Events of a request"),
    _s("staff.tickets.plans", "read", "GET", "/tickets/{ticket_id}/plans", "Plans of a request"),
    _s("staff.work_orders.mine", "read", "GET", "/my-work-orders", "The staff member's own jobs"),
    _s("staff.work_orders.list", "read", "GET", "/work-orders", "Jobs visible to the staff member"),
    _s("staff.work_orders.get", "read", "GET", "/work-orders/{work_order_id}", "One job"),
    _s("staff.available", "read", "GET", "/staff/available", "Staff free for a job"),
    _s("staff.plans.queue", "read", "GET", "/plans", "Plans waiting for management"),
    _s("staff.catalogs", "read", "GET", "/catalogs", "Service categories and places"),
    _s("staff.reports.incident_frequency", "read", "GET", "/reports/incident-frequency", "Incidents by building and month"),
    _s("staff.reports.incident_summary", "read", "GET", "/reports/incident-frequency-summary", "Incident totals"),
    _s("staff.reports.repair_revenue", "read", "GET", "/reports/repair-revenue", "Repair revenue"),
    _s("staff.reports.filter_options", "read", "GET", "/reports/filter-options", "Choices for a report"),
]


def register(*tools: Tool) -> None:
    """Add operations other modules own (their routes exist where they are defined)."""
    known = {(t.method, t.path) for t in TOOLS}
    for tool in tools:
        if (tool.method, tool.path) not in known:
            TOOLS.append(tool)


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_secret() -> str:
    return "ics_" + secrets.token_urlsafe(32)


def _find_tool(method: str, path: str) -> Tool | None:
    return next((t for t in TOOLS if t.method == method and t.path == path), None)


async def _tenant_db(request: Request):
    settings = request.app.state.settings
    engine = request.app.state.engine
    if engine is None or not settings.tenant_id:
        raise HTTPException(503, "Database or tenant is not configured")
    return engine, str(settings.tenant_id)


async def resolve_delegation(request: Request, token: str) -> str:
    """Accept a delegated call and return the person it acts for, or refuse. Used by the sign-in layer."""
    engine, tenant = await _tenant_db(request)
    route = request.scope.get("route")
    path = getattr(route, "path_format", None) or getattr(route, "path", None)
    tool = _find_tool(request.method, path) if path else None
    if tool is None:
        # Not in the catalog: indistinguishable from a route that does not exist.
        raise HTTPException(404, "Not found")
    if request.method not in ("GET", "HEAD") and not 1 <= len(request.headers.get("idempotency-key", "")) <= 160:
        raise HTTPException(400, "Idempotency-Key header is required for changes")
    refusal: HTTPException | None = None
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": tenant})
            row = (await db.execute(text(f"""
                select d.id,d.client_id,d.user_id,d.persona,d.levels,d.calls,d.status,d.expires_at,d.correlation_id,
                       c.status as client_status, u.status as user_status,
                       exists(select 1 from tenant_memberships m where m.tenant_id=d.tenant_id and m.user_id=d.user_id and m.status='active') as member
                from delegations d
                join integration_clients c on c.tenant_id=d.tenant_id and c.id=d.client_id
                join users u on u.id=d.user_id
                where d.tenant_id={TENANT} and d.token_hash=:hash
            """), {"hash": digest(token)})).mappings().first()
            # A refusal that also closes the delegation must commit that change, so it is raised after this block.
            if row is None or row["status"] != "active":
                refusal = HTTPException(401, "Delegation is not valid")
            elif row["expires_at"] <= datetime.now(timezone.utc):
                await db.execute(text("update delegations set status='failed',error_code='expired',finished_at=now() where id=:id"), {"id": row["id"]})
                refusal = HTTPException(401, "Delegation has expired")
            elif row["client_status"] != "active" or row["user_status"] != "active" or not row["member"]:
                await db.execute(text("update delegations set status='revoked',finished_at=now() where id=:id"), {"id": row["id"]})
                refusal = HTTPException(403, "Delegation was revoked")
            elif tool.persona != row["persona"] or tool.level not in row["levels"]:
                refusal = HTTPException(403, "This delegation does not allow that operation")
            else:
                counted = await db.execute(text("update delegations set calls=calls+1 where id=:id and calls<:max returning calls"),
                                           {"id": row["id"], "max": MAX_CALLS})
                if counted.first() is None:
                    refusal = HTTPException(429, "Too many calls for this delegation", headers={"Retry-After": "60"})
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "Database is unavailable") from exc
    if refusal is not None:
        raise refusal
    CURRENT.set({"delegation_id": str(row["id"]), "client_id": row["client_id"], "user_id": row["user_id"],
                 "correlation_id": request.headers.get("x-correlation-id") or row["correlation_id"],
                 "idempotency_key": request.headers.get("idempotency-key"), "tool": tool.name, "level": tool.level})
    return row["user_id"]


# ---------- errors in the shape the contract promises (section 9.1) ----------

ERROR_CODES = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT",
               422: "VALIDATION_FAILED", 429: "RATE_LIMITED", 503: "UNAVAILABLE"}


def integration_error(request: Request, status: int, message: str, details=None, headers=None):
    from fastapi.responses import JSONResponse
    correlation = request.headers.get("x-correlation-id") or str(uuid4())
    body: dict = {"code": ERROR_CODES.get(status, "BAD_REQUEST"), "message": message, "retryable": status in (429, 503), "correlation_id": correlation}
    if details is not None:
        body["details"] = details
    return JSONResponse({"error": body}, status, headers={**(headers or {}), "X-Correlation-Id": correlation})


# ---------- the integration API ----------

router = APIRouter(prefix="/integration/v1", tags=["Integration v1"])


@dataclass
class Caller:
    kind: Literal["client", "delegation"]
    client_id: str
    levels: dict[str, list[str]]
    delegation: dict | None = None


async def caller(request: Request, x_client_id: Annotated[str | None, Header()] = None) -> Caller:
    """A client holding its secret, or a person's delegation token."""
    engine, tenant = await _tenant_db(request)
    value = request.headers.get("authorization", "")
    if not value.startswith("Bearer ") or len(value) > 300:
        raise HTTPException(401, "Authentication required")
    secret = value[7:]
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": tenant})
            if secret.startswith(TOKEN_PREFIX):
                row = (await db.execute(text(f"""
                    select d.id,d.client_id,d.user_id,d.persona,d.levels,d.status,d.expires_at,c.levels as client_levels,c.status as client_status
                    from delegations d join integration_clients c on c.tenant_id=d.tenant_id and c.id=d.client_id
                    where d.tenant_id={TENANT} and d.token_hash=:hash
                """), {"hash": digest(secret)})).mappings().first()
                if (row is None or row["status"] != "active" or row["expires_at"] <= datetime.now(timezone.utc)
                        or row["client_status"] != "active"):
                    raise HTTPException(401, "Delegation is not valid")
                return Caller("delegation", row["client_id"], dict(row["client_levels"]),
                              {"id": row["id"], "user_id": row["user_id"], "persona": row["persona"], "levels": list(row["levels"]),
                               "expires_at": row["expires_at"]})
            if not x_client_id:
                raise HTTPException(401, "X-Client-Id is required")
            row = (await db.execute(text(f"""
                select id,status,levels,secret_hash,secret_hash_next from integration_clients where tenant_id={TENANT} and id=:id
            """), {"id": x_client_id})).mappings().first()
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, "Database is unavailable") from exc
    given = digest(secret)
    ok = row is not None and any(h and hmac.compare_digest(h, given) for h in (row["secret_hash"], row["secret_hash_next"]))
    if not ok:
        raise HTTPException(401, "Client credentials are not valid")
    if row["status"] != "active":
        raise HTTPException(403, "Client is disabled")
    return Caller("client", row["id"], dict(row["levels"]))


CallerDep = Annotated[Caller, Depends(caller)]


def _allowed(who: Caller, tool: Tool) -> bool:
    if tool.level not in who.levels.get(tool.persona, []):
        return False
    if who.delegation is not None:
        return tool.persona == who.delegation["persona"] and tool.level in who.delegation["levels"]
    return True


def _resolve(schema, components, depth=0):
    """Inline $ref so a platform can build a tool from the schema without the whole document."""
    if depth > 6 or not isinstance(schema, (dict, list)):
        return schema
    if isinstance(schema, list):
        return [_resolve(item, components, depth + 1) for item in schema]
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return _resolve(components.get(name, {}), components, depth + 1)
    return {key: _resolve(value, components, depth + 1) for key, value in schema.items()}


@router.get("/tools")
async def tools(request: Request, who: CallerDep):
    spec = request.app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    items = []
    for tool in TOOLS:
        if not _allowed(who, tool):
            continue
        operation = spec["paths"].get(tool.path, {}).get(tool.method.lower())
        if operation is None:
            continue
        body = ((operation.get("requestBody") or {}).get("content") or {}).get("application/json", {}).get("schema")
        ok = (operation.get("responses") or {}).get("200") or (operation.get("responses") or {}).get("201") or {}
        output = ((ok.get("content") or {}).get("application/json") or {}).get("schema")
        items.append({"name": tool.name, "persona": tool.persona, "level": tool.level, "method": tool.method, "path": tool.path,
                      "description": tool.description,
                      "input_schema": {"parameters": _resolve(operation.get("parameters", []), components),
                                       "body": _resolve(body, components) if body else None},
                      "output_schema": _resolve(output, components) if output else None})
    return {"version": "1", "tools": items}


@router.get("/me")
async def me(who: CallerDep):
    return {"client_id": who.client_id, "kind": who.kind, "levels": who.levels,
            "delegation": None if who.delegation is None else {
                "id": str(who.delegation["id"]), "persona": who.delegation["persona"], "levels": who.delegation["levels"],
                "expires_at": who.delegation["expires_at"].isoformat()}}


class DelegationRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    purpose: Literal["resident_assistant", "staff_assistant"]
    ttl_seconds: int = Field(default=MAX_TTL_SECONDS, ge=30, le=MAX_TTL_SECONDS)
    channel_id: str | None = Field(default=None, max_length=200)


@router.post("/delegations/self", status_code=201)
async def delegate_self(request: Request, body: DelegationRequest, idempotency_key: Annotated[str, Header(min_length=1, max_length=160)]):
    """A signed-in person lets a client act for them for a few minutes."""
    from .v3_auth import resident_connection
    from contextlib import asynccontextmanager
    if CURRENT.get() is not None or request.headers.get("authorization", "").startswith("Bearer " + TOKEN_PREFIX):
        raise HTTPException(403, "A delegation cannot create another delegation")
    persona, ceiling = PURPOSES[body.purpose]
    async with asynccontextmanager(resident_connection)(request) as (db, user_id):
        client = (await db.execute(text(f"select id,status,levels from integration_clients where tenant_id={TENANT} and id=:id"),
                                   {"id": body.client_id})).mappings().first()
        if client is None or client["status"] != "active":
            raise HTTPException(404, "Client not found")
        granted = [level for level in LEVELS if level in ceiling and level in dict(client["levels"]).get(persona, [])]
        if not granted:
            raise HTTPException(403, "This client may not act for that kind of person")
        if persona == "staff":
            staff = (await db.execute(text(f"""
                select 1 where exists(select 1 from platform_admins where user_id=:u) or exists(
                  select 1 from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
                  where m.user_id=:u and m.status='active' and r.tenant_id={TENANT} and r.role_code in ('management','staff')
                    and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()))
            """), {"u": user_id})).first()
            if staff is None:
                raise HTTPException(403, "Staff role required")
        if body.channel_id is not None:
            owned = (await db.execute(text(f"select 1 from channel_memberships where tenant_id={TENANT} and channel_id=:c and user_id=:u"),
                                      {"c": body.channel_id, "u": user_id})).first()
            if owned is None:
                raise HTTPException(403, "Not your conversation")
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(seconds=body.ttl_seconds)
        try:
            row = (await db.execute(text(f"""
                insert into delegations(tenant_id,client_id,user_id,purpose,persona,levels,token_hash,channel_id,idempotency_key,correlation_id,expires_at)
                values({TENANT},:client,:user,:purpose,:persona,:levels,:hash,:channel,:key,:corr,:expires) returning id
            """), {"client": client["id"], "user": user_id, "purpose": body.purpose, "persona": persona, "levels": granted,
                   "hash": digest(token), "channel": body.channel_id, "key": f"self:{user_id}:{idempotency_key}",
                   "corr": request.headers.get("x-correlation-id") or str(uuid4()), "expires": expires})).first()
        except IntegrityError as exc:
            raise HTTPException(409, "That Idempotency-Key was already used; the token is shown only once") from exc
        await audit(db, user_id, "integration.delegation_issued", "delegation", str(row[0]),
                    {"clientId": client["id"], "purpose": body.purpose, "levels": granted, "expiresAt": expires.isoformat()})
    return {"delegation_id": str(row[0]), "token": token, "expires_at": expires.isoformat(), "persona": persona, "scopes": granted}


class Finish(BaseModel):
    status: Literal["finished", "failed"] = "finished"
    error_code: str | None = Field(default=None, max_length=100)
    usage: dict[str, int] | None = None


@router.post("/delegations/{delegation_id}/finish")
async def finish(delegation_id: UUID, body: Finish, request: Request, who: CallerDep):
    if who.kind != "client":
        raise HTTPException(403, "Only the client ends a delegation")
    engine, tenant = await _tenant_db(request)
    usage = body.usage or {}
    async with engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": tenant})
        done = await db.execute(text(f"""
            update delegations set status=:status,finished_at=now(),error_code=:error,input_tokens=:input,output_tokens=:output
            where tenant_id={TENANT} and id=:id and client_id=:client and status='active' returning id
        """), {"id": delegation_id, "client": who.client_id, "status": body.status, "error": body.error_code,
               "input": int(usage.get("input_tokens", 0)), "output": int(usage.get("output_tokens", 0))})
        if done.first() is None:
            raise HTTPException(404, "No active delegation of this client")
    return {"delegation_id": str(delegation_id), "status": body.status}
