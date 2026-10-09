# -*- coding: utf-8 -*-
"""Local account and token lifecycle endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..auth import (
    AuthPrincipal,
    AuthService,
    AuthTokens,
    InvalidCredentialsError,
    InvalidTokenError,
    RefreshTokenReuseError,
    UserAlreadyExistsError,
)
from ..deps import get_auth_service, get_current_principal

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    """Create a local account."""

    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=1024)
    domain_id: str = Field(min_length=1, max_length=64)
    area_id: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    """Authenticate by email or username inside one tenant."""

    tenant_id: str = Field(min_length=1, max_length=255)
    identity: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class UserResponse(BaseModel):
    """Safe account representation."""

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


class TokenResponse(BaseModel):
    """Access token response; refresh token stays in an HttpOnly cookie."""

    access_token: str
    token_type: str
    expires_in: int


def _set_refresh_cookie(
    response: Response,
    service: AuthService,
    token: str,
) -> None:
    response.set_cookie(
        key=service.cookie_name,
        value=token,
        max_age=service.refresh_ttl_seconds,
        httponly=True,
        secure=service.cookie_secure,
        samesite="lax",
        path="/auth",
    )


def _token_response(tokens: AuthTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        token_type=tokens.token_type,
        expires_in=tokens.access_expires_in,
    )


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Register a local account."""
    try:
        user = await service.register(
            tenant_id=service.default_tenant_id,
            **body.model_dump(),
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UserResponse.model_validate(user, from_attributes=True)


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Issue a short-lived access token and refresh-token cookie."""
    try:
        tokens = await service.login(
            **body.model_dump(),
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail="invalid credentials") from exc
    _set_refresh_cookie(response, service, tokens.refresh_token)
    return _token_response(tokens)


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Rotate the refresh token and issue a new access token."""
    token = request.cookies.get(service.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="refresh token is required")
    try:
        tokens = await service.refresh(
            token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except RefreshTokenReuseError as exc:
        response.delete_cookie(service.cookie_name, path="/auth")
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_refresh_cookie(response, service, tokens.refresh_token)
    return _token_response(tokens)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    """Revoke the current refresh session and clear its cookie."""
    token = request.cookies.get(service.cookie_name)
    if token:
        try:
            await service.logout(token)
        except InvalidTokenError:
            pass
    response.delete_cookie(service.cookie_name, path="/auth")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@auth_router.post("/logout-all")
async def logout_all(
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, int]:
    """Revoke all refresh sessions for the authenticated account."""
    return {"revoked_sessions": await service.revoke_all(principal)}


@auth_router.get("/me", response_model=UserResponse)
async def me(
    principal: AuthPrincipal = Depends(get_current_principal),
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Return the account represented by the access token."""
    user = await service.get_user(principal)
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="user is inactive or missing")
    return UserResponse.model_validate(user, from_attributes=True)
