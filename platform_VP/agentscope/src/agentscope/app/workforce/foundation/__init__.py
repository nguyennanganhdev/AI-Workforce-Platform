# -*- coding: utf-8 -*-
"""Workforce identity, persistence, jobs, and transport adapters.

SQL-backed Phase-C exports are loaded lazily so importing AgentScope without
the optional ``storage-sql`` extra continues to work.
"""

from importlib import import_module

from .event_delivery import (
    ConversationSseService,
    DurableJob,
    DurableJobRepository,
    DurableJobService,
    DurableJobWorker,
    DurableWorkerSupervisor,
    InMemoryMetricSink,
    JobClaim,
    JobLeaseLostError,
    JobNamespaceError,
    JobOwnerKind,
    JobStatus,
    JobHandler,
    MessageBusPublicEventSignal,
    MessageBusRequestCompletionSignal,
    MetricSink,
    NullMetricSink,
    PROVIDER_EVENTS,
    SSE_CONNECTIONS,
    SSE_REPLAYS,
    SseFrame,
    WorkerOutcome,
    WorkerOutcomeStatus,
    WORKER_ITERATIONS,
    WORKER_RESTARTS,
)

__all__ = [
    "ConversationSseService",
    "DurableJob",
    "DurableJobRepository",
    "DurableJobService",
    "DurableJobWorker",
    "DurableWorkerSupervisor",
    "InMemoryMetricSink",
    "JobClaim",
    "JobLeaseLostError",
    "JobNamespaceError",
    "JobOwnerKind",
    "JobStatus",
    "JobHandler",
    "MessageBusPublicEventSignal",
    "MessageBusRequestCompletionSignal",
    "MetricSink",
    "NullMetricSink",
    "PROVIDER_EVENTS",
    "SSE_CONNECTIONS",
    "SSE_REPLAYS",
    "SseFrame",
    "WorkerOutcome",
    "WorkerOutcomeStatus",
    "WORKER_ITERATIONS",
    "WORKER_RESTARTS",
    "HmacProviderAuth",
    "ManagementVerificationService",
    "PartnerRouteGrantService",
    "SqlAlchemyUnitOfWork",
    "SqlAlchemyUnitOfWorkFactory",
    "SqlDurableJobRepository",
    "SqlIdentityPort",
    "SqlPartnerRoutingPort",
    "SqlProviderCredentialRepository",
    "WorkforceDatabase",
]


_LAZY_EXPORTS = {
    "HmacProviderAuth": ("._provider_auth", "HmacProviderAuth"),
    "ManagementVerificationService": (
        "._identity",
        "ManagementVerificationService",
    ),
    "PartnerRouteGrantService": ("._route_grants", "PartnerRouteGrantService"),
    "SqlAlchemyUnitOfWork": ("._database", "SqlAlchemyUnitOfWork"),
    "SqlAlchemyUnitOfWorkFactory": (
        "._database",
        "SqlAlchemyUnitOfWorkFactory",
    ),
    "SqlDurableJobRepository": (
        "._job_repository",
        "SqlDurableJobRepository",
    ),
    "SqlIdentityPort": ("._identity", "SqlIdentityPort"),
    "SqlPartnerRoutingPort": ("._partner_routing", "SqlPartnerRoutingPort"),
    "SqlProviderCredentialRepository": (
        "._provider_auth",
        "SqlProviderCredentialRepository",
    ),
    "WorkforceDatabase": ("._database", "WorkforceDatabase"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
