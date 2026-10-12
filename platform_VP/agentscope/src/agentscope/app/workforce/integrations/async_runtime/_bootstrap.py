# -*- coding: utf-8 -*-
"""Phase-C composition root for Foundation-owned Workforce services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Self

from ...foundation._database import (
    SqlAlchemyUnitOfWorkFactory,
    WorkforceDatabase,
)
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
    DurableJobWorker,
    DurableWorkerSupervisor,
    DurableJobService,
    MetricSink,
    MessageBusPublicEventSignal,
    MessageBusRequestCompletionSignal,
)


@dataclass(frozen=True, slots=True)
class WorkforceRuntimeAssembly:
    """Owner-built runtime graph mounted and supervised by the C7 root.

    ``factory`` code receives one :class:`WorkforceFoundation`; therefore all
    SQL repositories can and must use ``foundation.uows``.  Routers and job
    handlers are collected here so API mounting and worker registration cannot
    silently diverge between deployments.
    """

    services: Mapping[str, Any]
    routers: tuple[Any, ...] = ()
    job_handlers: Mapping[str, Any] | None = None
    worker_id: str = "workforce-runtime"

    def __post_init__(self) -> None:
        if not self.worker_id:
            raise ValueError("worker_id must not be empty")
        handlers = dict(self.job_handlers or {})
        if any(
            not key or not callable(value)
            for key, value in handlers.items()
        ):
            raise ValueError(
                "job handlers require a non-empty type and callable"
            )
        object.__setattr__(self, "job_handlers", handlers)
        object.__setattr__(self, "routers", tuple(self.routers))


RuntimeFactory = Callable[["WorkforceFoundation"], WorkforceRuntimeAssembly]


@dataclass(frozen=True, slots=True)
class WorkforceFoundation:
    """Services that downstream Phase-C composition may depend on."""

    database: WorkforceDatabase
    uows: SqlAlchemyUnitOfWorkFactory
    identity: SqlIdentityPort
    management_verification: ManagementVerificationService
    partner_routing: SqlPartnerRoutingPort
    route_grants: PartnerRouteGrantService
    jobs: DurableJobService
    public_event_signal: MessageBusPublicEventSignal
    request_completion_signal: MessageBusRequestCompletionSignal
    provider_auth: HmacProviderAuth | None
    runtime: WorkforceRuntimeAssembly | None = None


class WorkforceBootstrap(AbstractAsyncContextManager):
    """Open one SQL foundation and its optional production runtime graph."""

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
        runtime_factory: RuntimeFactory | None = None,
        worker_metrics: MetricSink | None = None,
        worker_idle_seconds: float = 0.25,
        worker_restart_seconds: float = 0.5,
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
        self._worker_metrics = worker_metrics
        self._worker_idle_seconds = worker_idle_seconds
        self._worker_restart_seconds = worker_restart_seconds
        self._components: WorkforceFoundation | None = None
        self._supervisor: DurableWorkerSupervisor | None = None

        # Repositories are assembled before the database connects so FastAPI
        # can mount their routers deterministically during create_app().  The
        # factory is lazy at call time and raises if used outside the lifespan.
        uows = SqlAlchemyUnitOfWorkFactory(
            lambda: self.database.session_factory(),
        )
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
        foundation = WorkforceFoundation(
            database=self.database,
            uows=uows,
            identity=SqlIdentityPort(uows),
            management_verification=ManagementVerificationService(uows),
            partner_routing=SqlPartnerRoutingPort(uows),
            route_grants=PartnerRouteGrantService(uows),
            jobs=DurableJobService(job_repository),
            public_event_signal=MessageBusPublicEventSignal(self.message_bus),
            request_completion_signal=MessageBusRequestCompletionSignal(
                self.message_bus,
            ),
            provider_auth=provider_auth,
        )
        runtime = runtime_factory(foundation) if runtime_factory else None
        self._prepared = WorkforceFoundation(
            database=foundation.database,
            uows=foundation.uows,
            identity=foundation.identity,
            management_verification=foundation.management_verification,
            partner_routing=foundation.partner_routing,
            route_grants=foundation.route_grants,
            jobs=foundation.jobs,
            public_event_signal=foundation.public_event_signal,
            request_completion_signal=foundation.request_completion_signal,
            provider_auth=foundation.provider_auth,
            runtime=runtime,
        )

    async def __aenter__(self) -> Self:
        await self.database.__aenter__()
        try:
            self._components = self._prepared
            runtime = self._prepared.runtime
            if runtime is not None and runtime.job_handlers:
                worker = DurableJobWorker(
                    self._prepared.jobs,
                    runtime.job_handlers,
                    worker_id=runtime.worker_id,
                )
                self._supervisor = DurableWorkerSupervisor(
                    worker,
                    idle_seconds=self._worker_idle_seconds,
                    restart_seconds=self._worker_restart_seconds,
                    metrics=self._worker_metrics,
                )
                await self._supervisor.__aenter__()
        except BaseException:
            self._components = None
            await self.database.__aexit__(None, None, None)
            raise
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._supervisor is not None:
            supervisor, self._supervisor = self._supervisor, None
            await supervisor.__aexit__(*args)
        self._components = None
        await self.database.__aexit__(*args)

    @property
    def routers(self) -> tuple[Any, ...]:
        """Routers are stable before startup so OpenAPI sees them once."""
        runtime = self._prepared.runtime
        return () if runtime is None else runtime.routers

    @property
    def components(self) -> WorkforceFoundation:
        if self._components is None:
            raise RuntimeError(
                "WorkforceBootstrap has not entered its lifespan",
            )
        return self._components


__all__ = [
    "RuntimeFactory",
    "WorkforceBootstrap",
    "WorkforceFoundation",
    "WorkforceRuntimeAssembly",
]
