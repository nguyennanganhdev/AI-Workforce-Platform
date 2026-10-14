# -*- coding: utf-8 -*-
"""Authentication and session management."""

from ._models import AuthPrincipal, AuthTokens, AuthUser
from ._service import (
    AREA_MANAGER,
    DOMAIN_ADMIN,
    PLATFORM_ADMIN,
    AccountPendingError,
    AdminPermissionError,
    AreaTakenError,
    AuthError,
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    RefreshTokenReuseError,
    UserAlreadyExistsError,
)

__all__ = [
    "AREA_MANAGER",
    "DOMAIN_ADMIN",
    "PLATFORM_ADMIN",
    "AccountPendingError",
    "AdminPermissionError",
    "AreaTakenError",
    "AuthError",
    "AuthPrincipal",
    "AuthService",
    "AuthTokens",
    "AuthUser",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "RefreshTokenReuseError",
    "UserAlreadyExistsError",
]

