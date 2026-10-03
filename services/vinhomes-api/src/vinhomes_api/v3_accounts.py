"""Tenant membership administration on the canonical users owned by the platform.

Only local demo mode creates synthetic identities; real login remains in Hono.
Suspension/deletion changes this tenant's membership, not a global identity.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_auth import scoped_connection
from .v3_audit import audit

router = APIRouter(tags=["Vinhomes V3 tenant accounts"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


def admin(scope: Scope) -> None:
    if not scope[2]:
        raise HTTPException(403, "Platform admin required")


async def account(scope: Scope, user_id: str, lock: bool = False) -> dict[str, object]:
    result = await scope[0].execute(
        text(
            f"""
        select m.id as membership_id,m.status,m.updated_at,u.id,u.name,u.email,u.status as identity_status
        from tenant_memberships m join users u on u.id=m.user_id
        where m.user_id=:id and m.tenant_id={TENANT}
    """
            + (" for update of m" if lock else "")
        ),
        {"id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, "Tenant account not found")
    return dict(row)


async def review(
    scope: Scope, user_id: str, action: str, before: str | None, after: str, reason: str
) -> None:
    await scope[0].execute(
        text(f"""
        insert into account_reviews(tenant_id,user_id,action,from_status,to_status,reason,reviewer_user_id,decided_at)
        values ({TENANT},:user,:action,:before,:after,:reason,:actor,now())
    """),
        {
            "user": user_id,
            "action": action,
            "before": before,
            "after": after,
            "reason": reason,
            "actor": scope[1],
        },
    )


@router.get("/admin/accounts")
async def accounts(
    scope: Scope,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Literal["pending", "active", "suspended", "ended"] | None = None,
) -> dict[str, object]:
    admin(scope)
    result = await scope[0].execute(
        text(f"""
        select u.id,u.name,u.email,u.status as identity_status,m.status,m.updated_at,m.joined_at
        from users u join tenant_memberships m on m.user_id=u.id
        where m.tenant_id={TENANT} and (cast(:status as text) is null or m.status=:status)
        order by m.created_at desc,u.id limit :limit offset :offset
    """),
        {"status": status, "limit": limit, "offset": offset},
    )
    items = [dict(row) for row in result.mappings()]
    return {
        "items": items,
        "nextOffset": offset + len(items) if len(items) == limit else None,
    }


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(
        min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/admin/accounts", status_code=201)
async def create_account(
    body: AccountCreate, request: Request, scope: Scope
) -> dict[str, object]:
    admin(scope)
    if not request.app.state.settings.demo_mode:
        raise HTTPException(
            409,
            "Create real identities through platform registration; use tenant membership endpoint for existing users",
        )
    tenant = await scope[0].execute(text("select current_setting('app.tenant_id')"))
    user_id = "demo-account-" + str(
        uuid5(
            NAMESPACE_URL,
            f"account:{tenant.scalar_one()}:{scope[1]}:{body.idempotency_key}",
        )
    )
    # Serialize idempotent inserts without requiring a globally mutable user lock.
    await scope[0].execute(
        text("select pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": user_id}
    )
    old = await scope[0].execute(
        text("select name,email from users where id=:id"), {"id": user_id}
    )
    existing = old.mappings().first()
    if existing:
        if existing["name"] != body.name or existing["email"] != body.email.lower():
            raise HTTPException(409, "Account key already used with different content")
        return await account(scope, user_id)
    await scope[0].execute(
        text(
            "insert into users(id,name,email,status) values (:id,:name,:email,'active')"
        ),
        {"id": user_id, "name": body.name, "email": body.email.lower()},
    )
    await scope[0].execute(
        text(
            f"insert into tenant_memberships(tenant_id,user_id,status) values ({TENANT},:id,'pending')"
        ),
        {"id": user_id},
    )
    await review(
        scope,
        user_id,
        "register",
        None,
        "pending",
        "Synthetic local demo identity; no login credentials created",
    )
    return await account(scope, user_id)


class MembershipCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/admin/accounts/memberships", status_code=201)
async def add_membership(body: MembershipCreate, scope: Scope) -> dict[str, object]:
    admin(scope)
    await scope[0].execute(
        text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"membership:{body.user_id}"},
    )
    user = await scope[0].execute(
        text(
            "select 1 from users where id=:id and status='active' and deleted_at is null"
        ),
        {"id": body.user_id},
    )
    if user.first() is None:
        raise HTTPException(404, "Active platform identity required")
    previous = await scope[0].execute(
        text(
            f"select 1 from tenant_memberships where user_id=:id and tenant_id={TENANT}"
        ),
        {"id": body.user_id},
    )
    if previous.first():
        return await account(scope, body.user_id)
    await scope[0].execute(
        text(
            f"insert into tenant_memberships(tenant_id,user_id,status) values ({TENANT},:id,'pending')"
        ),
        {"id": body.user_id},
    )
    await review(scope, body.user_id, "register", None, "pending", body.reason)
    return await account(scope, body.user_id)


class AccountDecision(BaseModel):
    action: Literal["approve", "reject", "activate", "suspend", "delete"]
    reason: str = Field(min_length=1, max_length=2000)
    expected_updated_at: datetime


@router.post("/admin/accounts/{user_id}/decision")
async def account_decision(
    user_id: str, body: AccountDecision, scope: Scope
) -> dict[str, object]:
    admin(scope)
    row = await account(scope, user_id, True)
    if row["updated_at"] != body.expected_updated_at:
        raise HTTPException(409, "Account membership changed; reload")
    if body.action in {"suspend", "delete", "reject"}:
        protected = await scope[0].execute(
            text("select 1 from platform_admins where user_id=:id"), {"id": user_id}
        )
        if user_id == scope[1] or protected.first():
            raise HTTPException(
                403, "Cannot revoke yourself or a platform administrator"
            )
    transitions = {
        "approve": ("pending", "active"),
        "reject": ("pending", "ended"),
        "activate": ("suspended", "active"),
        "suspend": ("active", "suspended"),
    }
    if body.action == "delete":
        if row["status"] == "ended":
            raise HTTPException(409, "Account membership already ended")
        target = "ended"
    else:
        source, target = transitions[body.action]
        if row["status"] != source:
            raise HTTPException(409, "Account action is invalid for its current state")
    await scope[0].execute(
        text("""
        update tenant_memberships set status=:status,updated_at=now(),
          joined_at=case when :status='active' then coalesce(joined_at,now()) else joined_at end,
          ended_at=case when :status='ended' then now() else null end where id=:id
    """),
        {"status": target, "id": row["membership_id"]},
    )
    await review(scope, user_id, body.action, row["status"], target, body.reason)
    return await account(scope, user_id)


@router.get("/admin/accounts/{user_id}/history")
async def account_history(user_id: str, scope: Scope) -> dict[str, object]:
    admin(scope)
    await account(scope, user_id)
    rows = await scope[0].execute(
        text(
            "select id,action,from_status,to_status,reason,reviewer_user_id,decided_at from account_reviews where user_id=:id order by created_at desc limit 100"
        ),
        {"id": user_id},
    )
    return {"items": [dict(row) for row in rows.mappings()]}


class RoleGrant(BaseModel):
    role_code: Literal["customer", "staff", "management"]
    scope_id: UUID


@router.get("/admin/accounts/{user_id}/roles")
async def account_roles(user_id: str, scope: Scope) -> dict[str, object]:
    admin(scope)
    member = await account(scope, user_id)
    result = await scope[0].execute(
        text("""
        select r.id,r.role_code,r.scope_id,s.kind,r.valid_from,r.valid_to,r.granted_by
        from scoped_user_roles r join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where r.membership_id=:id order by r.valid_from desc
    """),
        {"id": member["membership_id"]},
    )
    return {"items": [dict(row) for row in result.mappings()]}


@router.post("/admin/accounts/{user_id}/roles", status_code=201)
async def grant_role(user_id: str, body: RoleGrant, scope: Scope) -> dict[str, object]:
    admin(scope)
    member = await account(scope, user_id, True)
    if member["status"] != "active":
        raise HTTPException(409, "Active membership required before granting role")
    target = await scope[0].execute(
        text("select 1 from access_scopes where id=:id"), {"id": body.scope_id}
    )
    if target.first() is None:
        raise HTTPException(404, "Tenant scope not found")
    existing = await scope[0].execute(
        text("""
        select id,role_code,scope_id from scoped_user_roles
        where membership_id=:member and scope_id=:scope and role_code=:role
          and valid_from<=now() and (valid_to is null or valid_to>now())
    """),
        {
            "member": member["membership_id"],
            "scope": body.scope_id,
            "role": body.role_code,
        },
    )
    old = existing.mappings().first()
    if old:
        return dict(old)
    result = await scope[0].execute(
        text(f"""
        insert into scoped_user_roles(tenant_id,membership_id,scope_id,role_code,granted_by,valid_from)
        values ({TENANT},:member,:scope,:role,:actor,now()) returning id,role_code,scope_id,granted_by,valid_from
    """),
        {
            "member": member["membership_id"],
            "scope": body.scope_id,
            "role": body.role_code,
            "actor": scope[1],
        },
    )
    role = dict(result.mappings().one())
    await audit(
        scope[0],
        scope[1],
        "account.role_granted",
        "tenant_membership",
        str(member["membership_id"]),
        {"userId": user_id, "scopeId": body.scope_id, "role": body.role_code},
    )
    return role
