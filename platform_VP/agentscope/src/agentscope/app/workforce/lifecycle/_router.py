"""Manager-only router factory; Foundation injects authenticated Scope."""

from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import Field

from ..contracts import (
    AgentManifest,
    BusinessProfile,
    ReuseDecision,
    Scope,
    WorkforceModel,
    WorkforceContractError,
)
from ._models import LifecycleError, PublishSelection, new_id
from ._service import LifecycleService


class CreateDraftRequest(WorkforceModel):
    manifest: AgentManifest
    reuse_decision: ReuseDecision
    batch_id: Optional[str] = None


class EditDraftRequest(WorkforceModel):
    manifest: AgentManifest
    reuse_decision: ReuseDecision
    expected_revision: int = Field(ge=1)


class EvaluateRequest(WorkforceModel):
    expected_revision: int = Field(ge=1)
    suite_version: str


class BatchPublishRequest(WorkforceModel):
    expected_revision: int = Field(ge=1)
    selections: List[PublishSelection]


class SinglePublishRequest(WorkforceModel):
    expected_revision: int = Field(ge=1)
    evaluation_id: str
    manifest_hash: str


class RollbackRequest(WorkforceModel):
    expected_revision: int = Field(ge=1)
    version_id: str


class AvailabilityRequest(WorkforceModel):
    expected_revision: int = Field(ge=1)
    status: str


class LifecycleRoute(APIRoute):
    def get_route_handler(self) -> Callable[..., Any]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Any:
            try:
                return await original(request)
            except RequestValidationError as error:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Invalid request fields",
                            "details": {
                                "fields": [
                                    list(item["loc"])
                                    for item in error.errors()
                                ]
                            },
                            "request_id": new_id(),
                            "retryable": False,
                        }
                    },
                )
            except WorkforceContractError as error:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": {
                            "code": str(error.code),
                            "message": str(error.code),
                            "details": {},
                            "request_id": new_id(),
                            "retryable": error.retryable,
                        }
                    },
                )
            except LifecycleError as error:
                return JSONResponse(
                    status_code=error.status,
                    content={
                        "error": {
                            "code": error.code,
                            "message": error.code.replace(
                                "_", " "
                            ).capitalize(),
                            "details": error.details,
                            "request_id": new_id(),
                            "retryable": error.code
                            in ("REVISION_CONFLICT", "CONCURRENT_MUTATION"),
                        }
                    },
                )

        return handler


def create_router(
    service: LifecycleService, require_manager_scope: Callable[..., Any]
) -> APIRouter:
    """Scope dependency MUST reject machine/partner principals, not read body
    scope."""
    router = APIRouter(
        prefix="/workforce/v1",
        tags=["workforce-lifecycle"],
        route_class=LifecycleRoute,
    )

    async def owner(scope: Scope = Depends(require_manager_scope)) -> Scope:
        await service.identity.check_scope_active(scope)
        return scope

    @router.post("/drafts", status_code=201)
    async def create_draft(
        body: CreateDraftRequest, scope: Scope = Depends(owner)
    ) -> Any:
        return await service.create_draft(
            scope, body.manifest, body.reuse_decision, body.batch_id
        )

    @router.get("/drafts/{draft_id}")
    async def get_draft(draft_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.get_draft(scope, draft_id)

    @router.patch("/drafts/{draft_id}")
    async def edit_draft(
        draft_id: str, body: EditDraftRequest, scope: Scope = Depends(owner)
    ) -> Any:
        return await service.update_draft(
            scope,
            draft_id,
            body.expected_revision,
            body.manifest,
            body.reuse_decision,
        )

    @router.post("/drafts/{draft_id}/validate")
    async def validate(draft_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.validate_draft(scope, draft_id)

    @router.get("/drafts/{draft_id}/diff")
    async def diff(draft_id: str, scope: Scope = Depends(owner)) -> Any:
        return {"items": await service.diff_draft(scope, draft_id)}

    @router.post("/drafts/{draft_id}/evaluations", status_code=202)
    async def evaluate(
        draft_id: str,
        body: EvaluateRequest,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        scope: Scope = Depends(owner),
    ) -> Any:
        return await service.start_evaluation(
            scope,
            draft_id,
            body.expected_revision,
            body.suite_version,
            idempotency_key,
        )

    @router.get("/evaluations/{evaluation_id}")
    async def evaluation(
        evaluation_id: str, scope: Scope = Depends(owner)
    ) -> Any:
        return await service.get_evaluation(scope, evaluation_id)

    @router.post("/evaluations/{evaluation_id}/cancel")
    async def cancel(evaluation_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.cancel_evaluation(scope, evaluation_id)

    @router.post("/drafts/{draft_id}/publish")
    async def publish(
        draft_id: str,
        body: SinglePublishRequest,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        scope: Scope = Depends(owner),
    ) -> Any:
        selection = PublishSelection(draft_id=draft_id, **body.model_dump())
        return (
            await service.publish(
                scope, [selection], idempotency_key, scope.manager_account_id
            )
        )[0]

    @router.get("/batches/{batch_id}")
    async def batch(batch_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.get_batch(scope, batch_id)

    @router.post("/batches/{batch_id}/publish")
    async def batch_publish(
        batch_id: str, body: BatchPublishRequest, scope: Scope = Depends(owner)
    ) -> Any:
        return await service.publish_selected(
            scope,
            batch_id,
            body.expected_revision,
            [x.model_dump() for x in body.selections],
        )

    @router.post("/agents/reuse-check")
    async def reuse(
        body: BusinessProfile, scope: Scope = Depends(owner)
    ) -> Any:
        return await service.find_candidates(scope, body)

    @router.get("/agents")
    async def agents(
        cursor: Optional[str] = None,
        limit: int = 50,
        scope: Scope = Depends(owner),
    ) -> Any:
        return await service.list_agents(scope, cursor, limit)

    @router.get("/agents/{agent_id}/versions")
    async def history(agent_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.version_history(scope, agent_id)

    @router.patch("/agents/{agent_id}/availability")
    async def availability(
        agent_id: str, body: AvailabilityRequest, scope: Scope = Depends(owner)
    ) -> Any:
        return await service.set_availability(
            scope, agent_id, body.status, body.expected_revision
        )

    @router.get("/versions/{version_id}")
    async def version(version_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.get_version(scope, version_id)

    @router.post("/versions/{version_id}/fork", status_code=201)
    async def fork(version_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.fork_version(scope, version_id)

    @router.get("/versions/{version_id}/retention")
    async def retention(version_id: str, scope: Scope = Depends(owner)) -> Any:
        return await service.retention_info(scope, version_id)

    @router.get("/deployments")
    async def deployments(scope: Scope = Depends(owner)) -> Any:
        return await service.list_deployments(scope)

    @router.post("/deployments/{deployment_id}/rollback")
    async def rollback(
        deployment_id: str,
        body: RollbackRequest,
        scope: Scope = Depends(owner),
    ) -> Any:
        return await service.rollback(
            scope, deployment_id, body.version_id, body.expected_revision
        )

    return router
