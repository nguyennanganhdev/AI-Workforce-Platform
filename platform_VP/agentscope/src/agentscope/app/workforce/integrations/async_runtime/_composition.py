# -*- coding: utf-8 -*-
"""C7 registration helpers for the owner-built Phase-C runtime graph."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from ...contracts import ActorContext, RequestResult, Scope
from ...foundation.event_delivery import DurableJob
from ._bootstrap import WorkforceFoundation, WorkforceRuntimeAssembly


PHASE_C_JOB_TYPES = frozenset(
    {
        "provider_event",
        "operation_reconcile",
        "workforce.workflow.continue",
        "workforce.lifecycle.evaluate",
    }
)


@dataclass(frozen=True, slots=True)
class PhaseCRuntimeDependencies:
    """Deployment-owned ports required to build the production SQL graph."""

    tenant_resolver: Any
    approval_authorizer: Any
    workflow_authorization: Any
    leader_bootstrap_resolver: Any
    leader: Any
    runtime_authority: Any
    tool_registry: Any
    quote_provider: Any
    hitl: Any
    mcp: Any
    operation_queries: Any
    evaluation_runner: Any
    customer_dependency: Any
    manager_dependency: Any
    release_tool_resolver: Any
    release_policy_resolver: Any
    release_context_resolver: Any
    clock: Any = lambda: datetime.now(UTC)
    call_factory: Any = None
    builtins: Mapping[str, Any] | None = None
    bounded_wait_seconds: float = 8.0
    heartbeat_seconds: float = 15.0
    worker_id: str = "workforce-phase-c"


class ApprovalContinuationCommandAdapter:
    """Atomic bridge from partner approval command to workflow wakeup."""

    def __init__(self, commands: Any, workflow_service: Any) -> None:
        self._commands = commands
        self._workflows = workflow_service

    def __getattr__(self, name: str) -> Any:
        return getattr(self._commands, name)

    async def record_approval_result(
        self,
        actor: Any,
        resolved: Mapping[str, Any],
        request_id: str,
        result: Any,
        *,
        uow: Any,
    ) -> None:
        """Persist response and separately-keyed continuation atomically."""
        actor = ActorContext.model_validate(actor)
        result = RequestResult.model_validate(result)
        scope = Scope.model_validate(resolved["scope"])
        await self._commands.record_result(request_id, result, uow=uow)
        data = result.data
        if data.get("status") != "approved":
            return
        workflow_id = data.get("workflow_id")
        approval_id = data.get("approval_id")
        if not isinstance(workflow_id, str) or not isinstance(
            approval_id, str
        ):
            raise ValueError("approved result requires workflow and approval")
        external_id = "approval-continuation-" + request_id
        payload_hash = hashlib.sha256(
            json.dumps(
                [workflow_id, approval_id, request_id],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        continuation = await self._commands.claim_or_read(
            actor,
            external_id,
            "approval_continuation",
            workflow_id,
            payload_hash,
            uow=uow,
        )
        await self._workflows.enqueue_trigger(
            scope,
            {
                "trigger_id": "approval-" + request_id,
                "workflow_id": workflow_id,
                "cause": {
                    "kind": "approval",
                    "request_id": continuation.request_id,
                    "approval_id": approval_id,
                },
            },
            uow=uow,
        )


class OperationReconcileJobHandler:
    """Translate the durable job envelope into the reconciler's scoped call."""

    job_type = "operation_reconcile"

    def __init__(self, reconciler: Any) -> None:
        self._reconciler = reconciler

    async def __call__(self, value: Any) -> dict[str, str]:
        job = DurableJob.model_validate(value)
        operation_id = job.payload.get("operation_id")
        timer_id = job.payload.get("timer_id")
        if (
            job.job_type != self.job_type
            or job.scope is None
            or not isinstance(operation_id, str)
            or not operation_id
            or not isinstance(timer_id, str)
            or not timer_id
        ):
            raise ValueError("SCOPED_OPERATION_RECONCILE_JOB_REQUIRED")
        status = await self._reconciler.reconcile(
            job.scope, operation_id, timer_id
        )
        return {"operation_id": operation_id, "status": status}


def compose_phase_c_runtime(
    foundation: WorkforceFoundation,
    *,
    services: Mapping[str, Any],
    routers: tuple[Any, ...],
    provider_event_processor: Any,
    workflow_continuation_handler: Any,
    operation_reconciler: Any,
    evaluation_handler: Any,
    worker_id: str = "workforce-phase-c",
) -> WorkforceRuntimeAssembly:
    """Register every Phase-C HTTP/job seam against one Foundation UOW.

    Domain-specific ports (Leader, MCP transport, quote provider and auth
    dependencies) are intentionally constructed by the deployer and supplied
    in ``services``.  This function owns the non-optional, easy-to-miss global
    wiring: one UOW identity, three routers and all four durable job types.
    """
    if services.get("uows") is not foundation.uows:
        raise ValueError("all Phase-C repositories must use foundation.uows")
    if len(routers) != 3 or any(router is None for router in routers):
        raise ValueError(
            "workflow, execution and release routers are all required"
        )
    handlers = {
        "provider_event": provider_event_processor.handle_job,
        "workforce.workflow.continue": workflow_continuation_handler,
        "operation_reconcile": OperationReconcileJobHandler(
            operation_reconciler
        ),
        "workforce.lifecycle.evaluate": evaluation_handler,
    }
    if set(handlers) != PHASE_C_JOB_TYPES or any(
        not callable(handler) for handler in handlers.values()
    ):
        raise ValueError("Phase-C durable handler set is incomplete")
    return WorkforceRuntimeAssembly(
        services={**services, "uows": foundation.uows},
        routers=routers,
        job_handlers=handlers,
        worker_id=worker_id,
    )


def build_phase_c_runtime(
    foundation: WorkforceFoundation,
    dependencies: PhaseCRuntimeDependencies,
) -> WorkforceRuntimeAssembly:
    """Build the complete C1–C6 production graph without test fallbacks."""
    if foundation.provider_auth is None:
        raise ValueError("provider HMAC authentication must be configured")

    # Imports remain local so the base SDK keeps its optional SQL/FastAPI
    # dependency boundary when Workforce is disabled.
    from ...execution import (
        ApprovalService,
        ExecutionGateway,
        ExecutionPolicy,
        PartnerApprovalService,
        TransactionService,
        create_repository,
        create_router as create_execution_router,
    )
    from ...execution.external_operations import (
        ExternalOperationService,
        OperationReconciler,
        RegistryExecutionProtocols,
    )
    from ...execution.provider_events import (
        ProviderEventIngress,
        ProviderEventProcessor,
        WorkflowEventAdapter,
    )
    from ...lifecycle.async_evaluation import (
        AsyncEvaluationService,
        EvaluationJobHandler,
        SqlEvaluationRepository,
    )
    from ...lifecycle.releases import (
        PinnedVersionAuthorization,
        SqlReleaseService,
    )
    from ...orchestration import (
        ExecutionOperationReader,
        LeaderWorkflowBootstrap,
        PartnerIngressService,
        SqlCheckpointRepository,
        SqlEventRepository,
        SqlPartnerRequestRepository,
        SqlRuntimeContinuation,
        SqlWorkflowRepository,
        WorkflowContinuationJobHandler,
        create_router as create_workflow_router,
    )
    from ...orchestration.partner_events import (
        ConversationEventService,
        PublicEventWriter,
    )
    from ...orchestration.workflows import (
        WorkflowContinuation,
        WorkflowService,
    )
    from ...registry.event_protocols import SqlAsyncProtocolProvider
    from ._releases import (
        PublishedLeaderBootstrapResolver,
        ReleaseAwareEvaluationJobService,
        SqlWorkflowVersionUsageReader,
        TransactionalReleaseValidator,
        create_release_router,
    )

    deps = dependencies
    uows = foundation.uows
    execution_repository = create_repository(uow_factory=uows)
    protocol_provider = SqlAsyncProtocolProvider(uows)
    release_validator = TransactionalReleaseValidator(
        protocol_provider.repository,
        deps.release_tool_resolver,
        deps.release_policy_resolver,
    )
    releases = SqlReleaseService(
        uows,
        release_validator,
        foundation.identity,
        clock=deps.clock,
    )
    release_authorization = PinnedVersionAuthorization(
        deps.workflow_authorization,
        releases,
    )
    leader_bootstrap_resolver = PublishedLeaderBootstrapResolver(
        deps.leader_bootstrap_resolver,
        releases,
    )
    operations = ExternalOperationService(
        execution_repository, deps.clock
    )
    protocols = RegistryExecutionProtocols(
        protocol_provider,
        execution_repository,
        foundation.provider_auth,
        operations,
    )
    approvals = ApprovalService(
        execution_repository,
        deps.runtime_authority,
        deps.quote_provider,
        deps.hitl,
        deps.clock,
    )
    gateway = ExecutionGateway(
        ExecutionPolicy(deps.runtime_authority, deps.tool_registry),
        TransactionService(execution_repository, approvals, deps.clock),
        deps.mcp,
        operations,
        protocols,
        builtins=deps.builtins,
        call_factory=deps.call_factory,
    )

    workflow_repository = SqlWorkflowRepository(uows, clock=deps.clock)
    checkpoint_repository = SqlCheckpointRepository(uows, clock=deps.clock)
    request_repository = SqlPartnerRequestRepository(
        uows,
        deps.tenant_resolver,
        approval_authorizer=deps.approval_authorizer,
        clock=deps.clock,
    )
    event_repository = SqlEventRepository(uows)
    event_service = ConversationEventService(
        event_repository,
        release_authorization,
        foundation.public_event_signal,
        uows,
        heartbeat_seconds=deps.heartbeat_seconds,
    )
    event_writer = PublicEventWriter(event_service, deps.clock)
    runtime = SqlRuntimeContinuation(
        workflow_repository,
        checkpoint_repository,
        deps.leader,
    )
    workflow_service = WorkflowService(
        workflow_repository,
        LeaderWorkflowBootstrap(
            leader_bootstrap_resolver,
            clock=deps.clock,
        ),
        release_authorization,
        ExecutionOperationReader(execution_repository),
        foundation.jobs,
        event_writer,
        runtime,
        uows,
        deps.clock,
    )
    continuation = WorkflowContinuation(
        workflow_service,
        request_repository,
        foundation.request_completion_signal,
    )
    continuation_handler = WorkflowContinuationJobHandler(
        continuation,
        worker_id=deps.worker_id + "-workflow",
    )
    ingress = PartnerIngressService(
        workflow_service,
        request_repository,
        request_repository,
        foundation.partner_routing,
        foundation.identity,
        event_service,
        foundation.request_completion_signal,
        clock=deps.clock,
    )

    workflow_adapter = WorkflowEventAdapter(
        execution_repository,
        workflow_service,
        query_sink=workflow_service.apply_query_result,
    )
    provider_ingress = ProviderEventIngress(
        execution_repository,
        foundation.provider_auth,
        protocols,
        foundation.jobs,
        operations,
        deps.clock,
    )
    provider_processor = ProviderEventProcessor(
        provider_ingress, workflow_adapter
    )
    reconciler = OperationReconciler(
        execution_repository,
        deps.operation_queries,
        protocols,
        workflow_adapter,
        foundation.jobs,
    )

    evaluation_repository = SqlEvaluationRepository(uows)
    evaluation_service = AsyncEvaluationService(
        deps.evaluation_runner, deps.clock
    )
    evaluation_jobs = ReleaseAwareEvaluationJobService(
        evaluation_repository,
        foundation.jobs,
        releases,
    )
    evaluation_handler = EvaluationJobHandler(
        evaluation_repository, evaluation_service
    )
    approval_commands = ApprovalContinuationCommandAdapter(
        request_repository, workflow_service
    )
    partner_approvals = PartnerApprovalService(
        approvals, approval_commands
    )

    workflow_router = create_workflow_router(
        ingress,
        event_service,
        deps.customer_dependency,
        bounded_wait_seconds=deps.bounded_wait_seconds,
    )
    execution_router = create_execution_router(
        gateway,
        approvals,
        partner_approvals,
        provider_ingress,
        deps.manager_dependency,
        deps.customer_dependency,
        foundation.provider_auth,
    )
    release_usage = SqlWorkflowVersionUsageReader(uows)
    release_router = create_release_router(
        releases,
        foundation.identity,
        deps.manager_dependency,
        deps.release_context_resolver,
        release_usage,
    )
    services = {
        "uows": uows,
        "protocol_provider": protocol_provider,
        "protocols": protocols,
        "execution_repository": execution_repository,
        "gateway": gateway,
        "approvals": approvals,
        "operations": operations,
        "workflow_repository": workflow_repository,
        "request_repository": request_repository,
        "event_service": event_service,
        "workflow_service": workflow_service,
        "ingress": ingress,
        "provider_ingress": provider_ingress,
        "provider_processor": provider_processor,
        "operation_reconciler": reconciler,
        "evaluation_repository": evaluation_repository,
        "evaluation_jobs": evaluation_jobs,
        "release_validator": release_validator,
        "releases": releases,
        "release_usage": release_usage,
        "published_catalog": releases,
    }
    return compose_phase_c_runtime(
        foundation,
        services=services,
        routers=(workflow_router, execution_router, release_router),
        provider_event_processor=provider_processor,
        workflow_continuation_handler=continuation_handler,
        operation_reconciler=reconciler,
        evaluation_handler=evaluation_handler,
        worker_id=deps.worker_id,
    )


__all__ = [
    "ApprovalContinuationCommandAdapter",
    "OperationReconcileJobHandler",
    "PhaseCRuntimeDependencies",
    "PHASE_C_JOB_TYPES",
    "compose_phase_c_runtime",
    "build_phase_c_runtime",
]
