# -*- coding: utf-8 -*-
"""Authentication value objects."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class AuthUser:
    """Public account fields; password hashes never leave the service."""

    id: str
    tenant_id: str
    email: str
    username: str
    status: str
    role: str
    domain_id: str
    area_id: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class AuthPrincipal:
    """Identity derived only from a verified access token."""

    user_id: str
    tenant_id: str
    session_id: str
    token_id: str
    role: str = "AREA_MANAGER"
    domain_id: str | None = None
    area_id: str | None = None


@dataclass(slots=True, frozen=True)
class AuthTokens:
    """Newly issued access and refresh token pair."""

    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_at: datetime
    token_type: str = "bearer"
