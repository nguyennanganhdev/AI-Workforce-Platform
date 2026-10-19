"""Partner API in unified mode: the console runtime behind ``/workforce/v1``.

Decided 14/10/2026: instead of a second agent world (release manifests, a
separate tool registry and execution engine), partner tickets are answered by
the console Leader with the agents published in Agent Studio. This module
assembles only the production pieces that unified mode needs:

* the durable partner workflow engine (requests, bindings, checkpoints,
  public events/SSE, close) — unchanged team code over the Workforce SQL DB;
* partner authentication with the existing partner API keys; the end
  customer is the ``external_user_id`` of the query (GET) or body (POST),
  as in the partner contract;
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

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
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
from ._approvals import ApprovalError, CaseApprovals, DecisionBody
from ._case import CaseRuntime, CaseStore
from ._close import guard_case_close
from ._contract import ContractPinnedBootstrap
from ._partner_setup import OnboardingError, OnboardingRequest, PartnerOnboarding
from ._provider import ProviderError, UnifiedProviderEvents
from ._runner import LEADER_VERSION_ID, ChatLeaderTurnRunner
from ._recovery import UnifiedRecovery

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
    """FastAPI dependency: partner API key + the asserted end user.

    As the partner contract says, GET calls carry ``external_user_id`` in the
    query and POST calls in the JSON body. The value only names the end user
    the partner backend vouches for; access still comes from the API key and
    the route grant.
    """

    from ...._router._business import get_partner_principal

    async def dependency(
        request: Request,
        principal: Any = Depends(get_partner_principal),
    ) -> ActorContext:
        external_user_id = request.query_params.get("external_user_id")
        if external_user_id is None and request.method == "POST":
            try:
                body = json.loads(await request.body() or b"{}")
            except ValueError:
                body = None
            if isinstance(body, dict) and isinstance(body.get("external_user_id"), str):
                external_user_id = body["external_user_id"]
        if not external_user_id or len(external_user_id) > 200:
            raise HTTPException(status_code=422, detail="external_user_id is required")
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


class AreaRequest(BaseModel):
    domain_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    area_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=255)


def onboarding_router(foundation: WorkforceFoundation) -> APIRouter:
    """Three-party route grant: admin verifies, manager grants, partner confirms."""

    from ...._router._business import get_partner_principal
    from ....deps import (
        get_business_service,
        get_current_principal,
        get_storage,
        get_workspace_manager,
    )

    router = APIRouter(prefix="/workforce/v1", tags=["workforce-onboarding"])

    @router.post("/admin/areas", status_code=status.HTTP_201_CREATED)
    async def create_area(
        body: AreaRequest,
        x_provisioning_secret: str | None = Header(default=None, alias="X-Provisioning-Secret"),
        business: Any = Depends(get_business_service),
    ) -> dict:
        """Operator tooling: add an area to an existing domain (provisioning secret)."""

        try:
            business.verify_provisioning_secret(x_provisioning_secret)
        except Exception as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        async with foundation.uows() as uow:
            owner = (await uow.execute(text("SELECT domain_id FROM areas WHERE id = :a"), {"a": body.area_id})).scalar()
            if owner is not None and owner != body.domain_id:
                raise HTTPException(status_code=409, detail="this area id belongs to another domain")
            if owner is None:
                await uow.execute(
                    text("INSERT INTO areas (id, domain_id, name, status) VALUES (:a, :d, :n, 'active')"),
                    {"a": body.area_id, "d": body.domain_id, "n": body.name},
                )
                await uow.commit()
        return {"domain_id": body.domain_id, "area_id": body.area_id, "created": owner is None}

    @router.post("/admin/memberships/verify")
    async def verify_membership(
        body: MembershipVerifyRequest,
        x_provisioning_secret: str | None = Header(default=None, alias="X-Provisioning-Secret"),
        business: Any = Depends(get_business_service),
    ) -> dict:
        """Mark a registered area manager as verified (admin, provisioning secret)."""

        try:
            business.verify_provisioning_secret(x_provisioning_secret)
        except Exception as exc:
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
        async with foundation.uows() as uow:
            # The operator's verification also approves an account waiting
            # for it (verification needs an active account).
            await uow.execute(
                text("UPDATE auth_users SET status = 'active' WHERE id = :id AND status = 'pending'"),
                {"id": row["manager_account_id"]},
            )
            try:
                revision = await foundation.management_verification.verify(
                    scope,
                    int(row["revision"]),
                    "provisioning",
                    uow,
                )
            except (ValueError, PermissionError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            await uow.commit()
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

    @router.get("/manager/partner-routes")
    async def list_routes(principal: Any = Depends(get_current_principal)) -> list[dict]:
        """Routes the signed-in area manager has granted, newest first."""

        from ...foundation._route_grants import PartnerRouteGrantService
        from ...foundation._tables import partner_manager_routes

        try:
            scope = await foundation.identity.resolve_manager(principal)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        async with foundation.uows() as uow:
            rows = (
                await uow.execute(
                    select(partner_manager_routes)
                    .where(
                        partner_manager_routes.c.manager_account_id
                        == scope.manager_account_id,
                    )
                    .order_by(partner_manager_routes.c.created_at.desc()),
                )
            ).mappings().all()
        return [PartnerRouteGrantService._model(row).model_dump(mode="json") for row in rows]

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

    @router.post("/admin/partner-onboarding")
    async def partner_onboarding(
        body: OnboardingRequest,
        x_provisioning_secret: str | None = Header(default=None, alias="X-Provisioning-Secret"),
        business: Any = Depends(get_business_service),
        storage: Any = Depends(get_storage),
        workspace_manager: Any = Depends(get_workspace_manager),
    ) -> Any:
        """Create/update a partner from its declaration (keys shown once)."""

        from ...._router._mcp import _discover_tools

        try:
            business.verify_provisioning_secret(x_provisioning_secret)
        except Exception as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        onboarding = PartnerOnboarding(
            foundation,
            lambda client: _discover_tools(client, float(client.mcp_config.timeout or 30.0)),
        )
        try:
            return await onboarding.run(body, business, storage, workspace_manager)
        except OnboardingError as exc:
            return JSONResponse(
                {"error": {"code": exc.code, "details": exc.details}},
                status_code=exc.status,
            )

    from ._team_routes import team_routes_router
    router.include_router(team_routes_router(foundation))
    return router


def partner_case_router(
    ingress: Any,
    workflow_service: Any,
    approvals: CaseApprovals,
    provider: UnifiedProviderEvents,
    customer: Any,
    ids: Callable[[], str],
) -> APIRouter:
    """Approval decisions (contract 9.8) and provider events (section 10)."""

    from ...orchestration.workflows._models import parse_aggregate

    router = APIRouter(prefix="/workforce/v1", tags=["workforce-partner-case"])

    def error(status_code: int, code: str, details: Any = None) -> JSONResponse:
        body: dict = {"code": code, "retryable": status_code >= 500}
        if details:
            body["details"] = details
        return JSONResponse({"error": body}, status_code=status_code)

    @router.post("/partner/approvals/{approval_id}/decision", status_code=202)
    async def decide(approval_id: str, request: Request, principal: Any = Depends(customer)) -> Any:
        try:
            body = DecisionBody.model_validate(await request.json())
        except ValueError:
            return error(422, "REQUEST_BODY_INVALID")
        actor = principal
        try:
            original = await ingress.requests.resolve_workflow_request(
                actor, body.workflow_id, body.external_user_id
            )
            aggregate = parse_aggregate(
                await workflow_service.repository.load(original.scope, body.workflow_id)
            )
            answer = await approvals.decide(
                approval_id,
                body,
                actor,
                workflow=aggregate.workflow,
                requests=ingress.requests,
                workflows=workflow_service,
                trigger_ids=lambda: "approval-" + ids(),
            )
        except ApprovalError as exc:
            return error(exc.status, exc.code, exc.details)
        except PermissionError:
            return error(403, "AUTHORIZATION_DENIED")
        except KeyError:
            return error(404, "RESOURCE_NOT_FOUND")
        return JSONResponse(answer, status_code=202)

    @router.post("/provider/job-events", status_code=202)
    async def job_events(request: Request) -> Any:
        raw = await request.body()
        if len(raw) > 262_144:
            return error(413, "PAYLOAD_TOO_LARGE")
        try:
            status_code, body = await provider.accept(raw, dict(request.headers))
        except ProviderError as exc:
            return error(exc.status, exc.code, exc.details)
        return JSONResponse(body, status_code=status_code)

    @router.get("/provider/event-receipts/{receipt_id}")
    async def event_receipt(receipt_id: str, request: Request) -> Any:
        try:
            return await provider.receipt(receipt_id, dict(request.headers))
        except ProviderError as exc:
            return error(exc.status, exc.code, exc.details)

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
    asset_store: Any = None,
) -> WorkforceRuntimeAssembly:
    """Production graph for unified mode (see the module docstring).

    ``asset_store`` (the S3/MinIO blob store): partners upload the end user's
    photos (``/partner/assets``), attach them to a message, and the route
    leader sees them.
    """

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
    store = CaseStore(uows, foundation.jobs)
    approvals = CaseApprovals(uows, jobs=foundation.jobs)
    case_runtime = CaseRuntime(store)
    runner.attach_case(case_runtime, approvals)
    workflow_service = WorkflowService(
        workflows,
        ContractPinnedBootstrap(LeaderWorkflowBootstrap(UnifiedBootstrapResolver(ids), clock=clock, ids=ids),
                                storage_provider=lambda: runner._state().storage),
        authorization,
        ExecutionOperationReader(create_execution_repository(uow_factory=uows)),
        foundation.jobs,
        PublicEventWriter(event_service, clock, ids),
        SqlRuntimeContinuation(workflows, checkpoints, runner),
        uows,
        clock,
        ids,
        completion_close_guard=guard_case_close,
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
    asset_service = None
    if asset_store is not None:
        from ...assets import SqlAssetRepository, WorkforceAssetService

        asset_service = WorkforceAssetService(
            SqlAssetRepository(uows),
            asset_store,
            foundation.partner_routing,
            foundation.identity,
            None,  # provider uploads are not offered in unified mode
            clock=clock,
        )
        runner.attach_images(asset_store)
    ingress = PartnerIngressService(
        workflow_service,
        requests,
        requests,
        foundation.partner_routing,
        foundation.identity,
        event_service,
        foundation.request_completion_signal,
        clock=clock,
        assets=asset_service,
    )
    ingress.closed_hooks.append(runner.workflow_closed)
    writer = PublicEventWriter(event_service, clock, ids)
    approvals.attach_events(writer)
    provider = UnifiedProviderEvents(
        uows,
        getattr(foundation, "provider_auth", None),
        store,
        workflow_service,
        writer,
        ids,
        requests=requests,
        share=case_runtime.share_progress,
        jobs=foundation.jobs,
    )
    recovery = UnifiedRecovery(store, case_runtime, provider, approvals, workflow_service,
                               requests, foundation.jobs, foundation.identity)
    customer = partner_customer_dependency()
    router = create_router(
        ingress,
        event_service,
        customer,
        bounded_wait_seconds=bounded_wait_seconds,
    )
    if asset_service is not None:
        from ...assets import create_customer_asset_router

        router.include_router(create_customer_asset_router(asset_service, customer))
    return WorkforceRuntimeAssembly(
        services={
            "workflow_service": workflow_service,
            "ingress": ingress,
            "event_service": event_service,
            "runner": runner,
            "recovery": recovery,
            "provider": provider,
            "approvals": approvals,
        },
        routers=(
            router,
            onboarding_router(foundation),
            partner_case_router(ingress, workflow_service, approvals, provider, customer, ids),
        ),
        job_handlers={handler.job_type: handler, **recovery.handlers()},
        worker_id=UNIFIED_JOB_WORKER,
        startup=(recovery.resume_pending,),
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
