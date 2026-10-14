"""Partner API in unified mode: the console runtime behind ``/workforce/v1``.

Decided 14/10/2026: instead of a second agent world (release manifests, a
separate tool registry and execution engine), partner tickets are answered by
the console Leader with the agents published in Agent Studio. This module
assembles only the production pieces that unified mode needs:

* the durable partner workflow engine (requests, bindings, checkpoints,
  public events/SSE, close) — unchanged team code over the Workforce SQL DB;
* partner authentication with the existing partner API keys plus an
  ``X-External-User-Id`` header naming the end customer;
* routing to exactly one verified area manager (existing SQL routing);
* :class:`ChatLeaderTurnRunner` for every turn;
* onboarding endpoints for the three-party route grant (admin verifies the
  manager, the manager grants a route, the partner confirms it).

Consent for write tools happens in the conversation (the customer replies
"xác nhận"), exactly like the web chat; the partner approval API, provider
job events and external-operation tracking of the Phase-C design are not
mounted in this mode.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from ...contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
    PartnerOperation,
    Scope,
)
from ...execution import create_repository as create_execution_repository
from ...foundation._tables import manager_memberships
from ...orchestration import (
    ExecutionOperationReader,
    LeaderBootstrapSeed,
    LeaderWorkflowBootstrap,
    PartnerIngressService,
    SqlCheckpointRepository,
    SqlEventRepository,
    SqlPartnerRequestRepository,
    SqlRuntimeContinuation,
    SqlWorkflowRepository,
    WorkflowContinuationJobHandler,
    create_router,
)
from ...orchestration.partner_events import ConversationEventService, PublicEventWriter
from ...orchestration.workflows import WorkflowContinuation, WorkflowService
from ..async_runtime._bootstrap import WorkforceFoundation, WorkforceRuntimeAssembly
from ._runner import LEADER_VERSION_ID, ChatLeaderTurnRunner

UNIFIED_JOB_WORKER = "workforce-unified"


class UnifiedWorkflowAuthorization:
    """Partner access = same partner client and same end customer, active scope."""

    def __init__(self, identity: Any) -> None:
        self._identity = identity

    async def authorize(self, scope, actor, audience, operation, uow=None) -> None:
        if actor is not None:
            if actor.kind != ActorKind.PARTNER:
                raise PermissionError("partner credential required")
            if actor.partner_client_id != audience.partner_client_id:
                raise PermissionError("partner audience client mismatch")
            if actor.external_user_id != audience.external_user_id:
                raise PermissionError("partner audience user mismatch")
        await self._identity.check_scope_active(scope, uow)

    async def authorize_trigger(self, aggregate, trigger, uow=None) -> None:
        if aggregate.workflow.workflow_id != trigger.workflow_id:
            raise PermissionError("trigger targets another workflow")
        await self._identity.check_scope_active(aggregate.workflow.scope, uow)

    async def can_publish_external_event(self, aggregate, event, uow) -> bool:
        return True


class UnifiedBootstrapResolver:
    """Every partner ticket starts a fresh Leader session and group."""

    def __init__(self, ids: Callable[[], str] = lambda: uuid4().hex) -> None:
        self._ids = ids

    async def resolve(self, scope, actor, audience, uow) -> LeaderBootstrapSeed:
        return LeaderBootstrapSeed(
            leader_agent_id="workforce-leader",
            leader_version_id=LEADER_VERSION_ID,
            group_id=self._ids(),
            session_ref=self._ids(),
            shared_state_ref=self._ids(),
            pattern="interactive",
            published_read_only=False,
        )


async def _tenant_of_client(actor: ActorContext, uow: Any) -> str:
    row = (
        await uow.execute(
            text(
                "SELECT tenant_id FROM partner_api_clients "
                "WHERE id = :id AND status = 'active'",
            ),
            {"id": actor.partner_client_id},
        )
    ).first()
    if row is None:
        raise PermissionError("partner client is not active")
    return row[0]


def partner_customer_dependency() -> Any:
    """FastAPI dependency: partner API key + ``X-External-User-Id``."""

    from ...._router._business import get_partner_principal

    async def dependency(
        principal: Any = Depends(get_partner_principal),
        external_user_id: str = Header(alias="X-External-User-Id", min_length=1, max_length=200),
    ) -> ActorContext:
        return ActorContext(
            kind=ActorKind.PARTNER,
            actor_id=f"{principal.client_id}:{external_user_id}"[:200],
            partner_client_id=principal.client_id,
            credential_id=principal.key_id,
            credential_purpose=CredentialPurpose.CUSTOMER_API,
            external_user_id=external_user_id,
            authentication_source="partner_api_key",
        )

    return dependency


# ---------------------------------------------------------------- onboarding


class RouteGrantRequest(BaseModel):
    partner_client_id: str = Field(min_length=1, max_length=255)
    external_management_ref: str = Field(min_length=1, max_length=128)
    operations: list[PartnerOperation] = Field(
        default_factory=lambda: [
            PartnerOperation.SUBMIT_REQUEST,
            PartnerOperation.REPLY,
            PartnerOperation.READ_RESULT,
            PartnerOperation.RECEIVE_EVENTS,
            PartnerOperation.CLOSE_WORKFLOW,
        ],
    )


class RouteConfirmRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class MembershipVerifyRequest(BaseModel):
    manager_account_id: str = Field(min_length=1, max_length=255)


def onboarding_router(foundation: WorkforceFoundation) -> APIRouter:
    """Three-party route grant: admin verifies, manager grants, partner confirms."""

    from ...._router._business import get_partner_principal
    from ....deps import get_business_service, get_current_principal

    router = APIRouter(prefix="/workforce/v1", tags=["workforce-onboarding"])

    @router.post("/admin/memberships/verify")
    async def verify_membership(
        body: MembershipVerifyRequest,
        x_provisioning_secret: str | None = Header(default=None, alias="X-Provisioning-Secret"),
        business: Any = Depends(get_business_service),
    ) -> dict:
        """Mark a registered area manager as verified (admin, provisioning secret)."""

        try:
            business.verify_provisioning_secret(x_provisioning_secret)
        except Exception as exc:  # noqa: BLE001 - mapped to 403
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        async with foundation.uows() as uow:
            row = (
                await uow.execute(
                    select(manager_memberships).where(
                        manager_memberships.c.manager_account_id == body.manager_account_id,
                    ),
                )
            ).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="manager membership not found")
        scope = Scope(
            tenant_id=row["tenant_id"],
            domain_id=row["domain_id"],
            area_id=row["area_id"],
            manager_account_id=row["manager_account_id"],
        )
        if row["status"] == "verified":
            return {"status": "verified", "revision": row["revision"]}
        try:
            revision = await foundation.management_verification.verify(
                scope,
                int(row["revision"]),
                "provisioning",
            )
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "verified", "revision": revision}

    @router.post("/manager/partner-routes", status_code=status.HTTP_201_CREATED)
    async def grant_route(
        body: RouteGrantRequest,
        principal: Any = Depends(get_current_principal),
    ) -> dict:
        """The signed-in area manager lets one partner route tickets to them."""

        try:
            scope = await foundation.identity.resolve_manager(principal)
            route = await foundation.route_grants.create_pending(
                scope,
                body.partner_client_id,
                body.external_management_ref,
                body.operations,
                principal.user_id,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return route.model_dump(mode="json")

    @router.post("/partner/routes/{route_id}/confirm")
    async def confirm_route(
        route_id: str,
        body: RouteConfirmRequest,
        principal: Any = Depends(get_partner_principal),
    ) -> dict:
        """The partner confirms a route granted to its client."""

        actor = ActorContext(
            kind=ActorKind.PARTNER,
            actor_id=principal.client_id,
            partner_client_id=principal.client_id,
            credential_id=principal.key_id,
            credential_purpose=CredentialPurpose.CUSTOMER_API,
            authentication_source="partner_api_key",
        )
        try:
            route = await foundation.route_grants.confirm(actor, route_id, body.expected_revision)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return route.model_dump(mode="json")

    return router


# ---------------------------------------------------------------- assembly


def build_unified_runtime(
    foundation: WorkforceFoundation,
    runner: ChatLeaderTurnRunner,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ids: Callable[[], str] = lambda: uuid4().hex,
    bounded_wait_seconds: float = 8.0,
    heartbeat_seconds: float = 15.0,
) -> WorkforceRuntimeAssembly:
    """Production graph for unified mode (see the module docstring)."""

    uows = foundation.uows
    workflows = SqlWorkflowRepository(uows, clock=clock, ids=ids)
    requests = SqlPartnerRequestRepository(uows, _tenant_of_client, clock=clock, ids=ids)
    checkpoints = SqlCheckpointRepository(uows, clock=clock)
    authorization = UnifiedWorkflowAuthorization(foundation.identity)
    event_service = ConversationEventService(
        SqlEventRepository(uows),
        authorization,
        foundation.public_event_signal,
        uows,
        heartbeat_seconds=heartbeat_seconds,
    )
    workflow_service = WorkflowService(
        workflows,
        LeaderWorkflowBootstrap(UnifiedBootstrapResolver(ids), clock=clock, ids=ids),
        authorization,
        ExecutionOperationReader(create_execution_repository(uow_factory=uows)),
        foundation.jobs,
        PublicEventWriter(event_service, clock, ids),
        SqlRuntimeContinuation(workflows, checkpoints, runner),
        uows,
        clock,
        ids,
    )
    # One Leader turn may wait for its whole team; keep the workflow lease
    # longer than that wait so another worker never takes over mid-turn.
    lease = int(runner._wait_seconds) + 180
    continuation = WorkflowContinuation(
        workflow_service,
        requests,
        foundation.request_completion_signal,
        lease_seconds=lease,
    )
    handler = WorkflowContinuationJobHandler(continuation, worker_id=UNIFIED_JOB_WORKER)
    ingress = PartnerIngressService(
        workflow_service,
        requests,
        requests,
        foundation.partner_routing,
        foundation.identity,
        event_service,
        foundation.request_completion_signal,
        clock=clock,
    )
    router = create_router(
        ingress,
        event_service,
        partner_customer_dependency(),
        bounded_wait_seconds=bounded_wait_seconds,
    )
    return WorkforceRuntimeAssembly(
        services={
            "workflow_service": workflow_service,
            "ingress": ingress,
            "event_service": event_service,
            "runner": runner,
        },
        routers=(router, onboarding_router(foundation)),
        job_handlers={handler.job_type: handler},
        worker_id=UNIFIED_JOB_WORKER,
    )


def unified_mode_enabled() -> bool:
    return os.getenv("WORKFORCE_PARTNER_API", "").strip().lower() in {"1", "true", "yes"}


__all__ = [
    "ChatLeaderTurnRunner",
    "UnifiedBootstrapResolver",
    "UnifiedWorkflowAuthorization",
    "build_unified_runtime",
    "onboarding_router",
    "partner_customer_dependency",
    "unified_mode_enabled",
]
