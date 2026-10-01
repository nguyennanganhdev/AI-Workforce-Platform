"""Resolve identity server side and apply V3 tenant RLS for every business query."""

from collections.abc import AsyncIterator

import httpx
from fastapi import Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_config import V3Settings


async def _actor_id(request: Request, settings: V3Settings) -> str:
    if settings.demo_mode:
        if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
            raise HTTPException(403, "Database demo is only available on loopback")
        actors = {"resident": "local-v3-resident", "management": "local-v3-management",
                  "technical": "local-v3-technical", "security": "local-v3-security",
                  "admin": "local-v3-admin"}
        role = request.headers.get("X-Demo-Actor", "resident")
        if role not in actors:
            raise HTTPException(422, "Unknown seeded demo actor")
        return actors[role]
    if settings.dev_user_id:
        if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
            raise HTTPException(403, "Development identity is only available on loopback")
        return settings.dev_user_id
    if not settings.auth_url:
        raise HTTPException(503, "VINHOMES_API_AUTH_URL is not configured")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                settings.auth_url,
                headers={"cookie": request.headers.get("cookie", "")},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Authentication server is unavailable") from exc
    if response.status_code in {401, 403}:
        raise HTTPException(response.status_code, "Sign in with an active platform account")
    if response.status_code != 200:
        raise HTTPException(503, "Authentication server is unavailable")
    try:
        actor_id = response.json()["user"]["id"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Authentication server returned an invalid identity") from exc
    if not isinstance(actor_id, str) or not actor_id:
        raise HTTPException(503, "Authentication server returned an invalid identity")
    return actor_id


async def scoped_connection(request: Request, x_demo_actor: str | None = Header(default=None)) -> AsyncIterator[tuple[AsyncConnection, str, bool]]:
    settings: V3Settings = request.app.state.settings
    engine = request.app.state.engine
    if not engine or not settings.tenant_id:
        raise HTTPException(503, "V3 database or tenant is not configured")
    actor_id = await _actor_id(request, settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("select set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
                {"user_id": actor_id, "tenant_id": str(settings.tenant_id)},
            )
            user = await connection.execute(
                text("select id from users where id=:user_id and status='active'"),
                {"user_id": actor_id},
            )
            if user.first() is None:
                raise HTTPException(403, "Active platform user required")
            admin = await connection.execute(
                text("select 1 from platform_admins where user_id=:user_id limit 1"),
                {"user_id": actor_id},
            )
            is_admin = admin.first() is not None
            if not is_admin:
                grant = await connection.execute(
                    text("""
                        select 1 from scoped_user_roles r
                        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
                        where m.user_id=:user_id and m.status='active'
                          and r.tenant_id=cast(:tenant_id as uuid)
                          and r.role_code in ('management','staff')
                          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
                        limit 1
                    """),
                    {"user_id": actor_id, "tenant_id": str(settings.tenant_id)},
                )
                if grant.first() is None:
                    raise HTTPException(403, "Operations role required")
            yield connection, actor_id, is_admin
    except IntegrityError as exc:
        raise HTTPException(409, "V3 constraint conflict; reload the resource and retry") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "V3 database is unavailable or missing required tables") from exc


async def resident_connection(request: Request, x_demo_actor: str | None = Header(default=None)) -> AsyncIterator[tuple[AsyncConnection, str]]:
    """Active tenant member identity for resident-owned resources."""
    settings: V3Settings = request.app.state.settings
    engine = request.app.state.engine
    if not engine or not settings.tenant_id:
        raise HTTPException(503, "V3 database or tenant is not configured")
    actor_id = await _actor_id(request, settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("select set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
                {"user_id": actor_id, "tenant_id": str(settings.tenant_id)},
            )
            membership = await connection.execute(text("""
                select 1 from users u join tenant_memberships m on m.user_id=u.id
                where u.id=:user_id and u.status='active' and m.status='active'
                  and m.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
                limit 1
            """), {"user_id": actor_id})
            if membership.first() is None:
                raise HTTPException(403, "Active tenant membership required")
            yield connection, actor_id
    except IntegrityError as exc:
        raise HTTPException(409, "V3 constraint conflict; reload the resource and retry") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "V3 database is unavailable or missing required tables") from exc


TICKET_VISIBILITY = """
    t.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    and (:is_admin or exists (
        select 1 from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where m.user_id=:user_id and m.status='active'
          and (r.role_code='management' or (r.role_code='staff' and exists (
            select 1 from work_orders own_work
            join work_assignments own_assignment on own_assignment.work_order_id=own_work.id and own_assignment.tenant_id=own_work.tenant_id
            join staff_profiles own_staff on own_staff.id=own_assignment.staff_id and own_staff.tenant_id=own_assignment.tenant_id
            where own_work.ticket_id=t.id and own_work.tenant_id=t.tenant_id
              and own_staff.user_id=:user_id and own_staff.active
              and own_assignment.status in ('offered','accepted','completed')
        )))
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and r.tenant_id=t.tenant_id
          and (s.kind='tenant'
            or (s.kind='management' and s.management_unit_id=t.management_unit_id)
            or (s.kind='site' and s.site_id=t.site_id)
            or (s.kind='zone' and s.zone_id=t.zone_id)
            or (s.kind='building' and s.building_id=t.building_id))
    ))
"""
