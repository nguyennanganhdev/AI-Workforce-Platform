"""Production composition adapters for the Lifecycle D4 release seam."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from pydantic import Field
from sqlalchemy import select

from ...contracts import (
    AgentManifest,
    Scope,
    ToolDescriptor,
    ToolEffect,
    WorkforceModel,
)
from ...execution._tables import tool_calls
from ...lifecycle import ValidationReport
from ...lifecycle.async_evaluation import FrozenEvaluation, validate_async_draft
from ...lifecycle.releases import (
    ReleaseContext,
    ReleaseSelection,
    SqlReleaseService,
)
from ...orchestration._tables import workflow_checkpoints, workflows
from ...orchestration.workflows import WorkflowAggregate
from ...orchestration.workflows.phase_a import WorkflowCheckpoint
from ...registry.event_protocols import AsyncToolProtocol
from ...registry.event_protocols._sql_repository import (
    SqlAsyncProtocolRepository,
)

ToolResolver = Callable[[Scope, str, Any], Awaitable[ToolDescriptor]]
PolicyResolver = Callable[
    [Scope, str, Any],
    Awaitable[tuple[Scope, str, str, Mapping[str, Any]]],
]
ContextResolver = Callable[[Scope], ReleaseContext | Awaitable[ReleaseContext]]


def _scope_where(table: Any, scope: Scope) -> tuple[Any, ...]:
    return tuple(
        table.c[name] == value
        for name, value in scope.model_dump(mode="python").items()
    )


class TransactionalReleaseValidator:
    """Resolve mutable release dependencies inside the publish transaction.

    The tool and policy resolvers are deployment adapters because the current
    platform has no canonical Workforce SQL catalog for either resource yet.
    They must read and lock/CAS their owner rows through the supplied UOW.  The
    protocol repository is concrete and locks its current head until commit.
    """

    def __init__(
        self,
        protocols: SqlAsyncProtocolRepository,
        tools: ToolResolver,
        policies: PolicyResolver,
    ) -> None:
        if not callable(tools) or not callable(policies):
            raise TypeError("transactional release resolvers are required")
        self.protocols = protocols
        self.tools = tools
        self.policies = policies

    async def validate(
        self, scope: Scope, manifest: AgentManifest, uow: Any
    ) -> tuple[ValidationReport, dict[str, Any]]:
        scope = Scope.model_validate(scope)
        manifest = AgentManifest.model_validate(manifest)
        tools: list[ToolDescriptor] = []
        protocols: list[AsyncToolProtocol] = []
        for binding in manifest.spec.tool_bindings:
            tool = ToolDescriptor.model_validate(
                await self.tools(scope, binding.tool_version_id, uow)
            )
            if tool.tool_version_id != binding.tool_version_id:
                raise ValueError("TOOL_VERSION_IDENTITY_DRIFT")
            tools.append(tool)
            if tool.effect == ToolEffect.EXTERNAL_OPERATION:
                protocol, enabled = await self.protocols.get_current(
                    scope,
                    tool.tool_version_id,
                    uow,
                    for_update=True,
                )
                if not enabled:
                    raise PermissionError("PROTOCOL_DISABLED")
                protocols.append(protocol)

        policy: Mapping[str, Any] | None = None
        policy_scope: Scope | None = None
        policy_ref: str | None = None
        policy_schema = "pta-phase-a-1"
        if manifest.async_policy_ref is not None:
            resolved = await self.policies(scope, manifest.async_policy_ref, uow)
            policy_scope = Scope.model_validate(resolved[0])
            policy_ref = resolved[1]
            policy_schema = resolved[2]
            policy = resolved[3]

        return validate_async_draft(
            scope,
            manifest,
            tools,
            protocols,
            policy,
            policy_scope,
            policy_ref,
            policy_schema,
        )


class ReleaseAwareEvaluationJobService:
    """Register evaluation, release candidate and durable job atomically."""

    job_type = "workforce.lifecycle.evaluate"

    def __init__(self, repository: Any, jobs: Any, releases: SqlReleaseService) -> None:
        self.repository = repository
        self.jobs = jobs
        self.releases = releases

    async def enqueue(
        self,
        scope: Scope,
        evaluation_id: str,
        frozen: FrozenEvaluation,
        *,
        expected_candidate_revision: int | None = None,
    ) -> str:
        async with self.repository.uows() as uow:
            await self.repository.register(scope, evaluation_id, frozen, uow)
            await self.releases.stage_candidate(
                scope,
                frozen,
                expected_candidate_revision,
                uow,
            )
            job_id = await self.jobs.enqueue(
                scope,
                self.job_type,
                {"evaluation_id": evaluation_id},
                "evaluation:" + evaluation_id,
                uow,
            )
            await uow.commit()
            return job_id


class PublishedLeaderBootstrapResolver:
    """Reject bootstrap seeds that are not the current published deployment."""

    def __init__(self, delegate: Any, releases: SqlReleaseService) -> None:
        self.delegate = delegate
        self.releases = releases

    async def resolve(
        self,
        scope: Scope,
        actor: Any,
        audience: Any,
        uow: Any,
    ) -> Any:
        seed = await self.delegate.resolve(scope, actor, audience, uow)
        agent_id = getattr(seed, "leader_agent_id", None)
        version_id = getattr(seed, "leader_version_id", None)
        if isinstance(seed, Mapping):
            agent_id = seed.get("leader_agent_id")
            version_id = seed.get("leader_version_id")
        if not isinstance(agent_id, str) or not isinstance(version_id, str):
            raise TypeError("LEADER_RELEASE_PIN_REQUIRED")
        deployment = await self.releases.get_deployment(scope, agent_id, uow)
        if (
            deployment["active_version_id"] != version_id
            or deployment["archived"]
            or not deployment["enabled"]
        ):
            raise PermissionError("LEADER_RELEASE_NOT_CURRENT")
        version = await self.releases.get_version(scope, version_id, uow)
        if version.agent_id != agent_id:
            raise ValueError("LEADER_RELEASE_IDENTITY_DRIFT")
        return seed


class SqlWorkflowVersionUsageReader:
    """Read exact persisted workflow/checkpoint references within one Scope."""

    def __init__(self, uows: Any) -> None:
        self.uows = uows

    async def references(self, scope: Scope, version_id: str) -> Sequence[str]:
        scope = Scope.model_validate(scope)
        references: set[str] = set()
        async with self.uows() as uow:
            workflow_rows = (
                (
                    await uow.execute(
                        select(workflows.c.id, workflows.c.payload).where(
                            *_scope_where(workflows, scope)
                        )
                    )
                )
                .mappings()
                .all()
            )
            for row in workflow_rows:
                aggregate = WorkflowAggregate.model_validate(row["payload"])
                if version_id in aggregate.workflow.version_pins:
                    references.add("workflow:" + row["id"])

            checkpoint_rows = (
                (
                    await uow.execute(
                        select(
                            workflow_checkpoints.c.id,
                            workflow_checkpoints.c.payload,
                        ).where(*_scope_where(workflow_checkpoints, scope))
                    )
                )
                .mappings()
                .all()
            )
            for row in checkpoint_rows:
                checkpoint = WorkflowCheckpoint.model_validate(row["payload"])
                if any(
                    pin.version_id == version_id
                    for pin in checkpoint.agent_version_pins
                ):
                    references.add("checkpoint:" + row["id"])

            call_rows = (
                (
                    await uow.execute(
                        select(tool_calls.c.id, tool_calls.c.payload).where(
                            *_scope_where(tool_calls, scope)
                        )
                    )
                )
                .mappings()
                .all()
            )
            for row in call_rows:
                payload = row["payload"]
                request = (
                    payload.get("request") if isinstance(payload, Mapping) else None
                )
                if (
                    isinstance(request, Mapping)
                    and request.get("version_id") == version_id
                ):
                    references.add("tool_call:" + row["id"])
        return tuple(sorted(references))


class PublishReleaseRequest(WorkforceModel):
    command_id: str = Field(min_length=1, max_length=200)
    selections: tuple[ReleaseSelection, ...] = Field(min_length=1)


class RollbackReleaseRequest(WorkforceModel):
    command_id: str = Field(min_length=1, max_length=200)
    version_id: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=0, strict=True)


class AvailabilityRequest(WorkforceModel):
    expected_revision: int = Field(ge=0, strict=True)
    archived: bool = Field(strict=True)
    enabled: bool = Field(strict=True)


async def _resolve_context(resolver: ContextResolver, scope: Scope) -> ReleaseContext:
    value = resolver(scope)
    if inspect.isawaitable(value):
        value = await value
    return ReleaseContext.model_validate(value)


def create_release_router(
    releases: SqlReleaseService,
    identity: Any,
    manager_dependency: Any,
    context_resolver: ContextResolver,
    usage: SqlWorkflowVersionUsageReader,
) -> Any:
    """Expose manager-only release actions without client-supplied Scope/context."""
    from fastapi import APIRouter, Depends, Query, Request
    from fastapi.responses import JSONResponse

    globals()["Request"] = Request
    router = APIRouter(
        prefix="/workforce/v1/manager/agent-releases",
        tags=["workforce-agent-releases"],
    )
    manager_principal = Depends(manager_dependency)
    capability_query = Query(default=[])

    async def respond(action: Any) -> Any:
        try:
            return await action()
        except PermissionError:
            return JSONResponse(
                {"error": {"code": "AUTHORIZATION_DENIED"}},
                status_code=403,
            )
        except KeyError:
            return JSONResponse(
                {"error": {"code": "RESOURCE_NOT_FOUND"}},
                status_code=404,
            )
        except (TypeError, ValueError) as error:
            code = str(error) if str(error).isupper() else "REQUEST_BODY_INVALID"
            status = 409 if "CONFLICT" in code or "STALE" in code else 422
            return JSONResponse({"error": {"code": code}}, status_code=status)

    async def manager_scope(principal: Any) -> Scope:
        return await identity.resolve_manager(principal)

    @router.post("/publish")
    async def publish(
        request: Request,
        principal: Any = manager_principal,
    ) -> Any:
        async def action() -> Any:
            body = PublishReleaseRequest.model_validate(await request.json())
            scope = await manager_scope(principal)
            context = await _resolve_context(context_resolver, scope)
            version_ids = await releases.publish_selected(
                scope, body.selections, context, body.command_id
            )
            return {"version_ids": list(version_ids)}

        return await respond(action)

    @router.post("/{agent_id}/rollback")
    async def rollback(
        agent_id: str,
        request: Request,
        principal: Any = manager_principal,
    ) -> Any:
        async def action() -> Any:
            body = RollbackReleaseRequest.model_validate(await request.json())
            scope = await manager_scope(principal)
            context = await _resolve_context(context_resolver, scope)
            version_id = await releases.rollback(
                scope,
                agent_id,
                body.version_id,
                body.expected_revision,
                context,
                body.command_id,
            )
            return {"version_id": version_id}

        return await respond(action)

    @router.patch("/{agent_id}/availability")
    async def availability(
        agent_id: str,
        request: Request,
        principal: Any = manager_principal,
    ) -> Any:
        async def action() -> Any:
            body = AvailabilityRequest.model_validate(await request.json())
            scope = await manager_scope(principal)
            revision = await releases.set_availability(
                scope,
                agent_id,
                body.expected_revision,
                archived=body.archived,
                enabled=body.enabled,
            )
            return {"agent_id": agent_id, "revision": revision}

        return await respond(action)

    @router.get("")
    async def catalog(
        capability: list[str] = capability_query,
        principal: Any = manager_principal,
    ) -> Any:
        async def action() -> Any:
            scope = await manager_scope(principal)
            versions = await releases.list_candidates(scope, capability)
            return {"items": [item.model_dump(mode="json") for item in versions]}

        return await respond(action)

    @router.get("/versions/{version_id}")
    async def version(
        version_id: str,
        principal: Any = manager_principal,
    ) -> Any:
        async def action() -> Any:
            scope = await manager_scope(principal)
            item = await releases.get_version(scope, version_id)
            return item.model_dump(mode="json")

        return await respond(action)

    @router.get("/deployments/{agent_id}")
    async def deployment(
        agent_id: str,
        principal: Any = manager_principal,
    ) -> Any:
        async def action() -> Any:
            scope = await manager_scope(principal)
            return await releases.get_deployment(scope, agent_id)

        return await respond(action)

    @router.get("/versions/{version_id}/references")
    async def references(
        version_id: str,
        principal: Any = manager_principal,
    ) -> Any:
        async def action() -> Any:
            scope = await manager_scope(principal)
            refs = await releases.retention_references(scope, version_id, usage)
            return {"version_id": version_id, "references": list(refs)}

        return await respond(action)

    return router


__all__ = [
    "AvailabilityRequest",
    "ContextResolver",
    "PolicyResolver",
    "PublishReleaseRequest",
    "PublishedLeaderBootstrapResolver",
    "ReleaseAwareEvaluationJobService",
    "RollbackReleaseRequest",
    "SqlWorkflowVersionUsageReader",
    "ToolResolver",
    "TransactionalReleaseValidator",
    "create_release_router",
]
