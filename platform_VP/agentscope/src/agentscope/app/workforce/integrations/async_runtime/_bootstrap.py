# -*- coding: utf-8 -*-
"""Phase-C composition root for Foundation-owned Workforce services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Self

from ...foundation._database import WorkforceDatabase
from ...foundation._identity import (
    ManagementVerificationService,
    SqlIdentityPort,
)
from ...foundation._job_repository import SqlDurableJobRepository
from ...foundation._partner_routing import SqlPartnerRoutingPort
from ...foundation._provider_auth import (
    HmacProviderAuth,
    SqlProviderCredentialRepository,
)
from ...foundation._route_grants import PartnerRouteGrantService
from ...foundation.event_delivery import (
    DurableJobService,
    MessageBusPublicEventSignal,
    MessageBusRequestCompletionSignal,
)


@dataclass(frozen=True, slots=True)
class WorkforceFoundation:
    """Services that downstream Phase-C composition may depend on."""

    database: WorkforceDatabase
    identity: SqlIdentityPort
    management_verification: ManagementVerificationService
    partner_routing: SqlPartnerRoutingPort
    route_grants: PartnerRouteGrantService
    jobs: DurableJobService
    public_event_signal: MessageBusPublicEventSignal
    request_completion_signal: MessageBusRequestCompletionSignal
    provider_auth: HmacProviderAuth | None


class WorkforceBootstrap(AbstractAsyncContextManager):
    """Open Foundation resources and publish one immutable service bundle."""

    def __init__(
        self,
        *,
        database_url: str,
        message_bus: Any,
        authenticate_provider_api_key: (
            Callable[[str], Awaitable[object]] | None
        ) = None,
        resolve_provider_signing_secret: (
            Callable[[str], bytes | Awaitable[bytes]] | None
        ) = None,
        provider_clock_skew: timedelta = timedelta(minutes=5),
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if (authenticate_provider_api_key is None) != (
            resolve_provider_signing_secret is None
        ):
            raise ValueError(
                "provider API-key auth and signing resolver must be "
                "configured together",
            )
        self.database = WorkforceDatabase(
            database_url,
            engine_kwargs=engine_kwargs,
        )
        self.message_bus = message_bus
        self._api_key_authenticator = authenticate_provider_api_key
        self._secret_resolver = resolve_provider_signing_secret
        self._provider_clock_skew = provider_clock_skew
        self._components: WorkforceFoundation | None = None

    async def __aenter__(self) -> Self:
        await self.database.__aenter__()
        try:
            uows = self.database.uows
            credential_repository = SqlProviderCredentialRepository(uows)
            provider_auth = None
            if self._api_key_authenticator is not None:
                provider_auth = HmacProviderAuth(
                    credential_repository,
                    self._api_key_authenticator,
                    self._secret_resolver,
                    allowed_clock_skew=self._provider_clock_skew,
                )
            job_repository = SqlDurableJobRepository(uows)
            self._components = WorkforceFoundation(
                database=self.database,
                identity=SqlIdentityPort(uows),
                management_verification=ManagementVerificationService(uows),
                partner_routing=SqlPartnerRoutingPort(uows),
                route_grants=PartnerRouteGrantService(uows),
                jobs=DurableJobService(job_repository),
                public_event_signal=MessageBusPublicEventSignal(
                    self.message_bus,
                ),
                request_completion_signal=MessageBusRequestCompletionSignal(
                    self.message_bus,
                ),
                provider_auth=provider_auth,
            )
        except BaseException:
            await self.database.__aexit__(None, None, None)
            raise
        return self

    async def __aexit__(self, *args: Any) -> None:
        self._components = None
        await self.database.__aexit__(*args)

    @property
    def components(self) -> WorkforceFoundation:
        if self._components is None:
            raise RuntimeError(
                "WorkforceBootstrap has not entered its lifespan",
            )
        return self._components


__all__ = ["WorkforceBootstrap", "WorkforceFoundation"]
