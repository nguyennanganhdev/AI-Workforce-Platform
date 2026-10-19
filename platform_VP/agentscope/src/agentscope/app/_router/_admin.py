# -*- coding: utf-8 -*-
"""Platform administration: accounts, integrated domains and their areas.

PLATFORM_ADMIN manages everything; DOMAIN_ADMIN manages its domain's areas and
the management board (BQL) accounts in them. Each area has one BQL account,
which waits for an administrator after registering.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import (
    AdminPermissionError,
    AreaTakenError,
    AuthPrincipal,
    AuthService,
    UserAlreadyExistsError,
)
from ..deps import get_auth_service, get_current_principal

admin_router = APIRouter(prefix="/admin", tags=["admin"])


class AccountView(BaseModel):
    id: str
    email: str
    username: str
    status: str
    role: str
    domain_id: str | None = None
    area_id: str | None = None
    created_at: datetime
    last_login_at: datetime | None = None


class NameBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    active: bool = True


class DomainAdminBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=1024)
    domain_id: str = Field(min_length=1, max_length=64)


async def _guard(call):
    try:
        return await call
    except AdminPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (AreaTakenError, UserAlreadyExistsError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _view(user) -> AccountView:
    return AccountView.model_validate(user, from_attributes=True)


@admin_router.get("/accounts", response_model=list[AccountView])
async def list_accounts(
    status_filter: str | None = None,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> list[AccountView]:
    """Accounts this admin manages (``status_filter=pending`` for the queue)."""
    return [_view(user) for user in await _guard(service.list_accounts(principal, status_filter))]


@admin_router.post("/accounts/{user_id}/approve", response_model=AccountView)
async def approve(
    user_id: str,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> AccountView:
    return _view(await _guard(service.decide_account(principal, user_id, approve=True)))


@admin_router.post("/accounts/{user_id}/reject", response_model=AccountView)
async def reject(
    user_id: str,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> AccountView:
    return _view(await _guard(service.decide_account(principal, user_id, approve=False)))


@admin_router.get("/directory")
async def directory(
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> list[dict]:
    """Domains, their areas and each area's BQL account."""
    return await _guard(service.directory(principal))


@admin_router.put("/domains/{domain_id}")
async def save_domain(
    domain_id: str,
    body: NameBody,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    return await _guard(service.save_domain(principal, domain_id, body.name, body.active))


@admin_router.put("/domains/{domain_id}/areas/{area_id}")
async def save_area(
    domain_id: str,
    area_id: str,
    body: NameBody,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    return await _guard(service.save_area(principal, domain_id, area_id, body.name, body.active))


@admin_router.post("/domain-admins", response_model=AccountView, status_code=status.HTTP_201_CREATED)
async def create_domain_admin(
    body: DomainAdminBody,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> AccountView:
    return _view(
        await _guard(
            service.create_admin(
                tenant_id=principal.tenant_id,
                email=body.email,
                username=body.username,
                password=body.password,
                role="DOMAIN_ADMIN",
                domain_id=body.domain_id,
                principal=principal,
            ),
        ),
    )
