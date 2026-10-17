# -*- coding: utf-8 -*-
"""Provider API-key plus raw-body HMAC authentication."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import inspect
import re
from typing import Any

from sqlalchemy import select

from ..contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
    PartnerOperation,
    UnitOfWork,
    VerifiedProviderContext,
)
from ._database import SqlAlchemyUnitOfWork
from ._identity import _sql_uow
from ._tables import provider_credentials, provider_integrations


_SIGNATURE = re.compile(r"^v1=([0-9a-f]{64})$")


@dataclass(frozen=True, slots=True)
class ProviderCredentialSnapshot:
    credential_id: str
    api_credential_id: str
    signing_key_id: str
    provider_integration_id: str
    tenant_id: str
    partner_client_id: str
    secret_ref: str
    purpose: str
    allowed_operations: tuple[str, ...]
    expires_at: datetime | None


class SqlProviderCredentialRepository:
    """Read active credential metadata; signing material stays external."""

    def __init__(self, uows: Callable[[], SqlAlchemyUnitOfWork]) -> None:
        self._uows = uows

    async def get_active(
        self,
        api_credential_id: str,
        signing_key_id: str,
        uow: UnitOfWork | None = None,
    ) -> ProviderCredentialSnapshot | None:
        if uow is None:
            async with self._uows() as owned:
                return await self.get_active(
                    api_credential_id,
                    signing_key_id,
                    owned,
                )
        statement = (
            select(
                provider_credentials,
                provider_integrations.c.tenant_id,
                provider_integrations.c.partner_client_id,
            )
            .join(
                provider_integrations,
                provider_integrations.c.id
                == provider_credentials.c.provider_integration_id,
            )
            .where(
                provider_credentials.c.api_credential_id
                == api_credential_id,
                provider_credentials.c.signing_key_id == signing_key_id,
                provider_credentials.c.status == "active",
                provider_credentials.c.revoked_at.is_(None),
                provider_integrations.c.status == "active",
            )
            .limit(2)
        )
        rows = (await _sql_uow(uow).execute(statement)).mappings().all()
        if len(rows) > 1:
            raise RuntimeError("provider credential mapping is ambiguous")
        if not rows:
            return None
        row = rows[0]
        return ProviderCredentialSnapshot(
            credential_id=row["id"],
            api_credential_id=row["api_credential_id"],
            signing_key_id=row["signing_key_id"],
            provider_integration_id=row["provider_integration_id"],
            tenant_id=row["tenant_id"],
            partner_client_id=row["partner_client_id"],
            secret_ref=row["secret_ref"],
            purpose=row["purpose"],
            allowed_operations=tuple(row["allowed_operations"]),
            expires_at=row["expires_at"],
        )


ApiKeyAuthenticator = Callable[[str], Awaitable[object]]
SecretResolver = Callable[[str], bytes | Awaitable[bytes]]


class HmacProviderAuth:
    """Verify the exact provider signature documented in the wire contract."""

    def __init__(
        self,
        credentials: SqlProviderCredentialRepository,
        authenticate_api_key: ApiKeyAuthenticator,
        resolve_secret: SecretResolver,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        allowed_clock_skew: timedelta = timedelta(minutes=5),
    ) -> None:
        if allowed_clock_skew <= timedelta(0):
            raise ValueError("allowed_clock_skew must be positive")
        self._credentials = credentials
        self._authenticate_api_key = authenticate_api_key
        self._resolve_secret = resolve_secret
        self._clock = clock
        self._allowed_clock_skew = allowed_clock_skew

    async def authenticate(
        self,
        raw_body: bytes,
        headers: Mapping[str, str],
    ) -> VerifiedProviderContext:
        normalized: dict[str, str] = {}
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise PermissionError("invalid provider headers")
            normalized[key.lower()] = value.strip()
        authorization = normalized.get("authorization", "")
        scheme, separator, api_key = authorization.partition(" ")
        if not separator or scheme.lower() != "apikey" or not api_key:
            raise PermissionError("provider API key required")
        timestamp_text = normalized.get("x-partner-timestamp", "")
        signing_key_id = normalized.get("x-partner-key-id", "")
        signature = normalized.get("x-partner-signature", "")
        match = _SIGNATURE.fullmatch(signature)
        if not timestamp_text.isascii() or not timestamp_text.isdecimal():
            raise PermissionError("invalid provider timestamp")
        if not signing_key_id or match is None:
            raise PermissionError("invalid provider signature headers")
        try:
            request_time = datetime.fromtimestamp(
                int(timestamp_text),
                tz=UTC,
            )
        except (OverflowError, OSError, ValueError):
            raise PermissionError("invalid provider timestamp") from None
        now = self._aware_now()
        if abs(now - request_time) > self._allowed_clock_skew:
            raise PermissionError("provider signature timestamp expired")

        api_principal = await self._authenticate_api_key(api_key)
        api_credential_id = self._field(api_principal, "key_id")
        tenant_id = self._field(api_principal, "tenant_id")
        client_id = self._field(api_principal, "client_id")
        credential = await self._credentials.get_active(
            api_credential_id,
            signing_key_id,
        )
        if credential is None:
            raise PermissionError("provider credential is inactive")
        if (
            credential.tenant_id != tenant_id
            or credential.partner_client_id != client_id
        ):
            raise PermissionError("provider credential namespace mismatch")
        if credential.expires_at is not None and credential.expires_at <= now:
            raise PermissionError("provider credential expired")
        if credential.purpose != CredentialPurpose.PROVIDER_EVENTS:
            raise PermissionError("provider_events purpose required")

        secret = self._resolve_secret(credential.secret_ref)
        if inspect.isawaitable(secret):
            secret = await secret
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise RuntimeError("provider signing secret is unavailable")
        signed = timestamp_text.encode("ascii") + b"." + raw_body
        expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, match.group(1)):
            raise PermissionError("provider signature mismatch")

        actor = ActorContext(
            kind=ActorKind.PARTNER,
            actor_id=credential.provider_integration_id,
            partner_client_id=credential.partner_client_id,
            credential_id=credential.api_credential_id,
            credential_purpose=CredentialPurpose.PROVIDER_EVENTS,
            authentication_source="provider_hmac_v1",
        )
        return VerifiedProviderContext(
            tenant_id=credential.tenant_id,
            provider_integration_id=credential.provider_integration_id,
            actor_id=credential.provider_integration_id,
            credential_id=credential.api_credential_id,
            partner_client_id=credential.partner_client_id,
            signing_key_id=credential.signing_key_id,
            authenticated_at=now,
            actor=actor,
        )

    async def authorize_integration(
        self,
        principal: VerifiedProviderContext | Mapping[str, object],
        operation: PartnerOperation | str,
        uow: UnitOfWork | None = None,
    ) -> None:
        context = VerifiedProviderContext.model_validate(principal)
        requested = (
            PartnerOperation.PUBLISH_JOB_EVENT
            if operation == "process_job_event"
            else PartnerOperation(operation)
        )
        credential = await self._credentials.get_active(
            context.credential_id,
            context.signing_key_id,
            uow,
        )
        if credential is None:
            raise PermissionError("provider credential is inactive")
        if (
            credential.tenant_id != context.tenant_id
            or credential.provider_integration_id
            != context.provider_integration_id
            or credential.partner_client_id != context.partner_client_id
        ):
            raise PermissionError("provider authorization context changed")
        if requested.value not in credential.allowed_operations:
            raise PermissionError("provider operation is not granted")
        now = self._aware_now()
        if credential.expires_at is not None and credential.expires_at <= now:
            raise PermissionError("provider credential expired")

    async def require_purpose(
        self,
        principal: VerifiedProviderContext | Mapping[str, object],
        purpose: CredentialPurpose,
    ) -> None:
        context = VerifiedProviderContext.model_validate(principal)
        if context.purpose != purpose:
            raise PermissionError(f"{purpose.value} purpose required")

    def _aware_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetime")
        return now.astimezone(UTC)

    @staticmethod
    def _field(value: object, name: str) -> str:
        result = getattr(value, name, None)
        if result is None and isinstance(value, Mapping):
            result = value.get(name)
        if not isinstance(result, str) or not result:
            raise PermissionError("invalid provider API-key principal")
        return result


__all__ = [
    "HmacProviderAuth",
    "ProviderCredentialSnapshot",
    "SqlProviderCredentialRepository",
]
