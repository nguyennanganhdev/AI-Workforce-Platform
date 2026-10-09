# -*- coding: utf-8 -*-
"""Argon2 password authentication and rotating refresh-token sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from typing import Any, Self
from uuid import UUID, uuid4

from ._models import AuthPrincipal, AuthTokens, AuthUser

_USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,63}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthError(Exception):
    """Base class for expected authentication failures."""


class InvalidCredentialsError(AuthError):
    """The login identifier or password is invalid."""


class InvalidTokenError(AuthError):
    """An access or refresh token is invalid or expired."""


class RefreshTokenReuseError(InvalidTokenError):
    """A rotated refresh token was presented again."""


class UserAlreadyExistsError(AuthError):
    """Email or username is already registered in the tenant."""


class AuthService(AbstractAsyncContextManager):
    """Own the auth database engine and token policy."""

    def __init__(
        self,
        *,
        database_url: str,
        jwt_secret: str,
        refresh_pepper: str,
        issuer: str = "agentscope",
        audience: str = "agentscope-api",
        default_tenant_id: str = "default",
        access_ttl: timedelta = timedelta(minutes=15),
        refresh_ttl: timedelta = timedelta(days=30),
        cookie_name: str = "agentscope_refresh",
        cookie_secure: bool = True,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if len(jwt_secret.encode()) < 32:
            raise ValueError("jwt_secret must contain at least 32 bytes")
        if len(refresh_pepper.encode()) < 32:
            raise ValueError("refresh_pepper must contain at least 32 bytes")
        if access_ttl <= timedelta(0) or refresh_ttl <= timedelta(0):
            raise ValueError("token TTLs must be positive")
        self._database_url = database_url
        self._jwt_secret = jwt_secret
        self._refresh_pepper = refresh_pepper.encode()
        self._issuer = issuer
        self._audience = audience
        self.default_tenant_id = default_tenant_id.strip()
        if not self.default_tenant_id or len(self.default_tenant_id) > 255:
            raise ValueError("default_tenant_id must be 1-255 characters")
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self.cookie_name = cookie_name
        self.cookie_secure = cookie_secure
        self._engine_kwargs = engine_kwargs or {}
        self._engine: Any | None = None

        from argon2 import PasswordHasher

        self._password_hasher = PasswordHasher()
        self._dummy_hash = self._password_hasher.hash(
            "not-a-real-password-" + secrets.token_urlsafe(32),
        )

    async def __aenter__(self) -> Self:
        """Create the async connection pool."""
        from sqlalchemy.ext.asyncio import create_async_engine

        self._engine = create_async_engine(
            self._database_url,
            **self._engine_kwargs,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Dispose the connection pool."""
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None

    @property
    def refresh_ttl_seconds(self) -> int:
        """Lifetime used by the refresh-token cookie."""
        return int(self._refresh_ttl.total_seconds())

    def _require_engine(self) -> Any:
        if self._engine is None:
            raise RuntimeError("AuthService has not entered its lifespan")
        return self._engine

    @staticmethod
    def _normalise_identity(value: str) -> str:
        return value.strip().lower()

    @classmethod
    def _validate_registration(
        cls,
        tenant_id: str,
        email: str,
        username: str,
        password: str,
    ) -> tuple[str, str, str]:
        tenant_id = tenant_id.strip()
        email = cls._normalise_identity(email)
        username = cls._normalise_identity(username)
        if not tenant_id or len(tenant_id) > 255:
            raise ValueError("tenant_id is required and must be <= 255 characters")
        if not _EMAIL.fullmatch(email) or len(email) > 320:
            raise ValueError("invalid email address")
        if not _USERNAME.fullmatch(username):
            raise ValueError(
                "username must be 3-64 lowercase letters, numbers, ., _, or -",
            )
        if len(password) < 12 or len(password.encode()) > 1024:
            raise ValueError("password must be 12-1024 bytes")
        return tenant_id, email, username

    def _refresh_hash(self, token: str) -> str:
        return hmac.new(
            self._refresh_pepper,
            token.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _parse_refresh_token(token: str) -> str:
        session_id, separator, secret = token.partition(".")
        if not separator or len(secret) < 32:
            raise InvalidTokenError("invalid refresh token")
        try:
            UUID(session_id)
        except ValueError as exc:
            raise InvalidTokenError("invalid refresh token") from exc
        return session_id

    def _new_refresh_token(self, session_id: str) -> str:
        return f"{session_id}.{secrets.token_urlsafe(48)}"

    def _access_token(
        self,
        *,
        user_id: str,
        tenant_id: str,
        session_id: str,
        role: str = "AREA_MANAGER",
        domain_id: str | None = None,
        area_id: str | None = None,
    ) -> str:
        import jwt

        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": user_id,
                "tid": tenant_id,
                "sid": session_id,
                "role": role,
                "did": domain_id,
                "aid": area_id,
                "jti": str(uuid4()),
                "type": "access",
                "iss": self._issuer,
                "aud": self._audience,
                "iat": now,
                "nbf": now,
                "exp": now + self._access_ttl,
            },
            self._jwt_secret,
            algorithm="HS256",
        )

    def verify_access_token(self, token: str) -> AuthPrincipal:
        """Verify signature and all security-relevant registered claims."""
        import jwt

        try:
            claims = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=["HS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={
                    "require": [
                        "sub",
                        "tid",
                        "sid",
                        "role",
                        "did",
                        "aid",
                        "jti",
                        "type",
                        "iss",
                        "aud",
                        "iat",
                        "nbf",
                        "exp",
                    ],
                },
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("invalid or expired access token") from exc
        if claims.get("type") != "access":
            raise InvalidTokenError("invalid access token type")
        if (
            claims.get("role") != "AREA_MANAGER"
            or not claims.get("did")
            or not claims.get("aid")
        ):
            raise InvalidTokenError("access token has no valid area scope")
        return AuthPrincipal(
            user_id=str(claims["sub"]),
            tenant_id=str(claims["tid"]),
            session_id=str(claims["sid"]),
            token_id=str(claims["jti"]),
            role=str(claims["role"]),
            domain_id=(str(claims["did"]) if claims["did"] else None),
            area_id=(str(claims["aid"]) if claims["aid"] else None),
        )

    async def register(
        self,
        *,
        tenant_id: str,
        email: str,
        username: str,
        password: str,
        domain_id: str,
        area_id: str,
    ) -> AuthUser:
        """Create one active account with an Argon2id password hash."""
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        tenant_id, email, username = self._validate_registration(
            tenant_id,
            email,
            username,
            password,
        )
        domain_id = domain_id.strip().lower()
        area_id = area_id.strip().lower()
        if not domain_id or not area_id:
            raise ValueError("domain_id and area_id are required")
        now = datetime.now(timezone.utc)
        user = AuthUser(
            id=str(uuid4()),
            tenant_id=tenant_id,
            email=email,
            username=username,
            status="active",
            role="AREA_MANAGER",
            domain_id=domain_id,
            area_id=area_id,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self._require_engine().begin() as connection:
                valid_scope = await connection.scalar(
                    text(
                        """
                        SELECT 1
                        FROM areas a
                        JOIN business_domains d ON d.id = a.domain_id
                        WHERE d.tenant_id = :tenant_id
                          AND d.id = :domain_id
                          AND a.id = :area_id
                          AND d.status = 'active'
                          AND a.status = 'active'
                        """,
                    ),
                    {
                        "tenant_id": tenant_id,
                        "domain_id": domain_id,
                        "area_id": area_id,
                    },
                )
                if valid_scope is None:
                    raise ValueError("area does not belong to the selected domain")
                await connection.execute(
                    text(
                        """
                        INSERT INTO auth_users (
                            id, tenant_id, email, username, password_hash,
                            status, role, domain_id, area_id,
                            created_at, updated_at
                        ) VALUES (
                            :id, :tenant_id, :email, :username, :password_hash,
                            'active', 'AREA_MANAGER', :domain_id, :area_id,
                            :created_at, :updated_at
                        )
                        """,
                    ),
                    {
                        "id": user.id,
                        "tenant_id": tenant_id,
                        "email": email,
                        "username": username,
                        "password_hash": self._password_hasher.hash(password),
                        "domain_id": domain_id,
                        "area_id": area_id,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
        except IntegrityError as exc:
            raise UserAlreadyExistsError(
                "email or username already exists",
            ) from exc
        return user

    async def login(
        self,
        *,
        tenant_id: str,
        identity: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokens:
        """Verify credentials and create a new refresh-token family."""
        from argon2.exceptions import VerificationError
        from sqlalchemy import text

        identity = self._normalise_identity(identity)
        engine = self._require_engine()
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT * FROM auth_users
                        WHERE tenant_id = :tenant_id
                          AND (email = :identity OR username = :identity)
                        """,
                        ),
                        {"tenant_id": tenant_id, "identity": identity},
                    )
                )
                .mappings()
                .first()
            )
        stored_hash = row["password_hash"] if row else self._dummy_hash
        try:
            valid = self._password_hasher.verify(stored_hash, password)
        except VerificationError:
            valid = False
        if not row or not valid or row["status"] != "active":
            raise InvalidCredentialsError("invalid credentials")

        if self._password_hasher.check_needs_rehash(stored_hash):
            password_hash = self._password_hasher.hash(password)
        else:
            password_hash = stored_hash
        session_id = str(uuid4())
        family_id = str(uuid4())
        refresh_token = self._new_refresh_token(session_id)
        now = datetime.now(timezone.utc)
        refresh_expires_at = now + self._refresh_ttl
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE auth_users
                    SET password_hash = :password_hash,
                        last_login_at = :now, updated_at = :now
                    WHERE id = :user_id
                    """,
                ),
                {"password_hash": password_hash, "now": now, "user_id": row["id"]},
            )
            await self._insert_session(
                connection,
                session_id=session_id,
                family_id=family_id,
                user_id=row["id"],
                tenant_id=row["tenant_id"],
                refresh_token=refresh_token,
                expires_at=refresh_expires_at,
                now=now,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        return self._tokens(
            user_id=row["id"],
            tenant_id=row["tenant_id"],
            session_id=session_id,
            role=row["role"],
            domain_id=row["domain_id"],
            area_id=row["area_id"],
            refresh_token=refresh_token,
            refresh_expires_at=refresh_expires_at,
        )

    async def _insert_session(
        self,
        connection: Any,
        *,
        session_id: str,
        family_id: str,
        user_id: str,
        tenant_id: str,
        refresh_token: str,
        expires_at: datetime,
        now: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> None:
        from sqlalchemy import text

        await connection.execute(
            text(
                """
                INSERT INTO auth_sessions (
                    id, user_id, tenant_id, family_id, refresh_token_hash,
                    expires_at, created_at, user_agent, ip_address
                ) VALUES (
                    :id, :user_id, :tenant_id, :family_id, :token_hash,
                    :expires_at, :created_at, :user_agent, :ip_address
                )
                """,
            ),
            {
                "id": session_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "family_id": family_id,
                "token_hash": self._refresh_hash(refresh_token),
                "expires_at": expires_at,
                "created_at": now,
                "user_agent": (user_agent or "")[:512] or None,
                "ip_address": (ip_address or "")[:64] or None,
            },
        )

    def _tokens(
        self,
        *,
        user_id: str,
        tenant_id: str,
        session_id: str,
        refresh_token: str,
        refresh_expires_at: datetime,
        role: str,
        domain_id: str | None,
        area_id: str | None,
    ) -> AuthTokens:
        return AuthTokens(
            access_token=self._access_token(
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=session_id,
                role=role,
                domain_id=domain_id,
                area_id=area_id,
            ),
            refresh_token=refresh_token,
            access_expires_in=int(self._access_ttl.total_seconds()),
            refresh_expires_at=refresh_expires_at,
        )

    async def refresh(
        self,
        refresh_token: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokens:
        """Rotate a refresh token and revoke its family on reuse."""
        from sqlalchemy import text

        old_session_id = self._parse_refresh_token(refresh_token)
        supplied_hash = self._refresh_hash(refresh_token)
        now = datetime.now(timezone.utc)
        engine = self._require_engine()
        reuse_detected = False
        result: AuthTokens | None = None
        async with engine.begin() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT s.*, u.status AS user_status,
                               u.role, u.domain_id, u.area_id
                        FROM auth_sessions s
                        JOIN auth_users u ON u.id = s.user_id
                        WHERE s.id = :id
                        FOR UPDATE OF s
                        """,
                        ),
                        {"id": old_session_id},
                    )
                )
                .mappings()
                .first()
            )
            if row is None or not hmac.compare_digest(
                row["refresh_token_hash"],
                supplied_hash,
            ):
                raise InvalidTokenError("invalid refresh token")
            if row["revoked_at"] is not None:
                if row["revoked_reason"] == "rotated":
                    await connection.execute(
                        text(
                            """
                            UPDATE auth_sessions
                            SET revoked_at = COALESCE(revoked_at, :now),
                                revoked_reason = 'reuse_detected'
                            WHERE family_id = :family_id
                            """,
                        ),
                        {"now": now, "family_id": row["family_id"]},
                    )
                    reuse_detected = True
                else:
                    raise InvalidTokenError("refresh token has been revoked")
            elif row["expires_at"] <= now or row["user_status"] != "active":
                raise InvalidTokenError("refresh token is expired or user is inactive")
            else:
                new_session_id = str(uuid4())
                new_refresh = self._new_refresh_token(new_session_id)
                new_expiry = now + self._refresh_ttl
                await self._insert_session(
                    connection,
                    session_id=new_session_id,
                    family_id=row["family_id"],
                    user_id=row["user_id"],
                    tenant_id=row["tenant_id"],
                    refresh_token=new_refresh,
                    expires_at=new_expiry,
                    now=now,
                    user_agent=user_agent,
                    ip_address=ip_address,
                )
                await connection.execute(
                    text(
                        """
                        UPDATE auth_sessions
                        SET revoked_at = :now, revoked_reason = 'rotated',
                            replaced_by = :new_id, last_used_at = :now
                        WHERE id = :old_id
                        """,
                    ),
                    {"now": now, "new_id": new_session_id, "old_id": old_session_id},
                )
                result = self._tokens(
                    user_id=row["user_id"],
                    tenant_id=row["tenant_id"],
                    session_id=new_session_id,
                    refresh_token=new_refresh,
                    refresh_expires_at=new_expiry,
                    role=row["role"],
                    domain_id=row["domain_id"],
                    area_id=row["area_id"],
                )
        if reuse_detected:
            raise RefreshTokenReuseError(
                "refresh token reuse detected; session family revoked",
            )
        assert result is not None
        return result

    async def logout(self, refresh_token: str) -> None:
        """Revoke the presented refresh session if the secret matches."""
        from sqlalchemy import text

        session_id = self._parse_refresh_token(refresh_token)
        token_hash = self._refresh_hash(refresh_token)
        async with self._require_engine().begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = COALESCE(revoked_at, :now),
                        revoked_reason = COALESCE(revoked_reason, 'logout')
                    WHERE id = :id AND refresh_token_hash = :token_hash
                    """,
                ),
                {
                    "now": datetime.now(timezone.utc),
                    "id": session_id,
                    "token_hash": token_hash,
                },
            )

    async def revoke_all(self, principal: AuthPrincipal) -> int:
        """Revoke every active refresh session owned by the principal."""
        from sqlalchemy import text

        async with self._require_engine().begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = :now, revoked_reason = 'logout_all'
                    WHERE user_id = :user_id AND tenant_id = :tenant_id
                      AND revoked_at IS NULL
                    """,
                ),
                {
                    "now": datetime.now(timezone.utc),
                    "user_id": principal.user_id,
                    "tenant_id": principal.tenant_id,
                },
            )
        return int(result.rowcount or 0)

    async def get_user(self, principal: AuthPrincipal) -> AuthUser | None:
        """Load the account associated with a verified principal."""
        from sqlalchemy import text

        async with self._require_engine().connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT id, tenant_id, email, username, status,
                               role, domain_id, area_id,
                               created_at, updated_at, last_login_at
                        FROM auth_users
                        WHERE id = :id AND tenant_id = :tenant_id
                        """,
                        ),
                        {"id": principal.user_id, "tenant_id": principal.tenant_id},
                    )
                )
                .mappings()
                .first()
            )
        return AuthUser(**row) if row else None
