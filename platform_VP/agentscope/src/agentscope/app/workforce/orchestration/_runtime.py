"""Production-facing Leader bootstrap/runtime adapters and job handler.

The concrete Leader/team engine is injected.  This module owns durability and
binding checks; it deliberately contains no test fallback and no provider call.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from pydantic import Field

from ..._workforce_policy import (
    BUSINESS_AGENT_EVIDENCE_POLICY,
    WORKFORCE_LEADER_PROMPT,
)
from ..contracts import (
    ActorContext,
    PartnerAudience,
    Scope,
    WorkflowRecord,
    WorkflowState,
    WorkforceModel,
)
from ._repository import SqlCheckpointRepository
from .workflows import (
    StartMessage,
    TurnDecision,
    WorkflowAggregate,
    WorkflowPattern,
)
from .workflows._models import raw_value
from .workflows.phase_a import (
    AgentVersionPin,
    ApprovalCause,
    PinnedRuntimeContext,
    RequestCause,
    UsedBudget,
    WorkflowCheckpoint,
    WorkflowTrigger,
)


class LeaderBootstrapSeed(WorkforceModel):
    """Published, authorized Leader pin used before the first runtime turn."""

    leader_agent_id: str = Field(min_length=1, max_length=200)
    leader_version_id: str = Field(min_length=1, max_length=200)
    group_id: str = Field(min_length=1, max_length=200)
    session_ref: str = Field(min_length=1, max_length=200)
    shared_state_ref: str = Field(min_length=1, max_length=200)
    pattern: WorkflowPattern
    published_read_only: bool = Field(strict=True)


class LeaderBootstrapResolver(Protocol):
    """Resolve only persisted catalog/team facts inside the ingress UOW."""

    async def resolve(
        self,
        scope: Scope,
        actor: ActorContext,
        audience: PartnerAudience,
        uow: Any,
    ) -> LeaderBootstrapSeed: ...


class LeaderTurnRunner(Protocol):
    """Actual Leader/team runtime consumed by production and Phase-C eval."""

    async def invoke_turn(
        self,
        scope: Scope,
        trigger: dict[str, object],
        context: PinnedRuntimeContext,
        execution_guard: object,
    ) -> TurnDecision: ...


class LeaderWorkflowBootstrap:
    """Create one durable workflow/group around a published Leader version."""

    def __init__(
        self,
        resolver: LeaderBootstrapResolver,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        ids: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._resolver = resolver
        self._clock = clock
        self._ids = ids

    async def prepare(self, scope, actor, audience, message, uow):
        scope = Scope.model_validate(scope)
        audience = PartnerAudience.model_validate(audience)
        command = StartMessage.model_validate(message)
        if command.route_id is None or command.route_revision is None:
            raise ValueError("ingress must pin the authorized route")
        seed = LeaderBootstrapSeed.model_validate(
            raw_value(await self._resolver.resolve(scope, actor, audience, uow))
        )
        if seed.pattern == WorkflowPattern.RESPONSE_ONLY:
            if not seed.published_read_only:
                raise ValueError(
                    "response-only bootstrap requires published read-only policy"
                )
        elif seed.published_read_only:
            raise ValueError(
                "interactive/tracking bootstrap cannot claim read-only policy"
            )
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return timezone-aware datetime")
        workflow_id = self._ids()
        record = WorkflowRecord(
            workflow_id=workflow_id,
            scope=scope,
            audience=audience,
            conversation_id=self._ids(),
            ticket_id=self._ids() if audience.external_ticket_id else None,
            route_id=command.route_id,
            route_revision=command.route_revision,
            state=WorkflowState.ACCEPTED,
            revision=1,
            group_id=seed.group_id,
            version_pins=(seed.leader_version_id,),
            created_at=now,
            updated_at=now,
        )
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            state_revision=1,
            session_refs=(seed.session_ref,),
            agent_version_pins=(
                AgentVersionPin(
                    agent_id=seed.leader_agent_id,
                    version_id=seed.leader_version_id,
                ),
            ),
            shared_state_ref=seed.shared_state_ref,
            used_budget=UsedBudget(
                model_turns=0,
                tool_calls=0,
                input_tokens=0,
                output_tokens=0,
            ),
        )
        return WorkflowAggregate(
            workflow=record,
            checkpoint=checkpoint,
            pattern=seed.pattern,
            published_read_only=seed.published_read_only,
        )


class SqlRuntimeContinuation:
    """RuntimeContinuationPort backed by immutable SQL checkpoints."""

    def __init__(
        self,
        workflows,
        checkpoints: SqlCheckpointRepository,
        leader: LeaderTurnRunner,
        shared_context: Any | None = None,
        shared_context_model_resolver: Any | None = None,
    ) -> None:
        self._workflows = workflows
        self._checkpoints = checkpoints
        self._leader = leader
        self._shared_context = shared_context
        self._shared_context_model_resolver = shared_context_model_resolver
        if (shared_context is None) != (shared_context_model_resolver is None):
            raise ValueError(
                "shared context and its model resolver must be configured together",
            )

    async def persist_checkpoint(self, scope, workflow_id, checkpoint, uow=None) -> str:
        return await self._checkpoints.persist(scope, workflow_id, checkpoint, uow)

    async def load_pinned_context(self, scope, checkpoint):
        scope = Scope.model_validate(scope)
        stored = await self._checkpoints.load(scope, checkpoint)
        aggregate = await self._workflows.load(scope, stored.workflow_id)
        if (
            aggregate.workflow.checkpoint_ref != checkpoint
            or aggregate.checkpoint != stored
        ):
            raise RuntimeError("workflow/checkpoint pin mismatch")
        shared_context = None
        shared_context_revision = None
        shared_context_tokens = None
        if self._shared_context is not None:
            shared_record = await self._shared_context.storage.get_team_shared_context(
                scope.manager_account_id,
                aggregate.workflow.group_id,
            )
            if shared_record is None:
                raise RuntimeError(
                    "partner workflow shared context was not projected before "
                    "Leader continuation",
                )
            expected_scope = (
                scope.tenant_id,
                scope.domain_id,
                scope.area_id,
                scope.manager_account_id,
                aggregate.workflow.workflow_id,
            )
            actual_scope = (
                shared_record.tenant_id,
                shared_record.domain_id,
                shared_record.area_id,
                shared_record.manager_account_id,
                shared_record.workflow_id,
            )
            if actual_scope != expected_scope:
                raise PermissionError(
                    "partner workflow shared context owner mismatch",
                )
            if aggregate.workflow.workflow_id not in shared_record.state.tasks:
                raise RuntimeError(
                    "partner workflow task is missing from shared context",
                )
            model = await self._shared_context_model_resolver.resolve(
                scope,
                aggregate.workflow,
                stored,
            )
            if not callable(getattr(model, "count_tokens", None)):
                raise TypeError(
                    "shared-context model resolver returned an invalid model",
                )
            packet, shared_context_tokens = await self._shared_context.prepare_packet(
                model=model,
                user_id=scope.manager_account_id,
                team_id=aggregate.workflow.group_id,
                mode="task",
                task_id=aggregate.workflow.workflow_id,
            )
            shared_context = json.loads(packet)
            shared_context_revision = shared_context.get("revision")
            if not isinstance(shared_context_revision, int):
                raise RuntimeError(
                    "shared-context packet is missing its pinned revision",
                )
        return PinnedRuntimeContext(
            workflow=aggregate.workflow,
            checkpoint=stored,
            shared_context_revision=shared_context_revision,
            shared_context_tokens=shared_context_tokens,
            shared_context=shared_context,
            leader_system_prompt=WORKFORCE_LEADER_PROMPT,
            business_agent_evidence_policy=BUSINESS_AGENT_EVIDENCE_POLICY,
        )

    async def invoke_turn(self, scope, trigger, checkpoint, execution_guard):
        context = PinnedRuntimeContext.model_validate(raw_value(checkpoint))
        # The host-provided runner receives server-owned policies on every
        # partner continuation. Persisted agent/version prompts can therefore
        # never silently restore an older or weaker runtime policy.
        context = context.model_copy(
            update={
                "leader_system_prompt": WORKFORCE_LEADER_PROMPT,
                "business_agent_evidence_policy": (BUSINESS_AGENT_EVIDENCE_POLICY),
            },
        )
        decision = TurnDecision.model_validate(
            raw_value(
                await self._leader.invoke_turn(
                    Scope.model_validate(scope),
                    dict(trigger),
                    context,
                    execution_guard,
                )
            )
        )
        return decision


class WorkflowContinuationJobHandler:
    """Foundation DurableJob handler for ``workforce.workflow.continue``."""

    job_type = "workforce.workflow.continue"

    def __init__(self, continuation, *, worker_id: str) -> None:
        if not worker_id:
            raise ValueError("worker_id is required")
        self._continuation = continuation
        self._worker_id = worker_id

    async def __call__(self, job) -> dict[str, object]:
        if job.job_type != self.job_type or job.scope is None:
            raise ValueError("workflow continuation requires a scoped job")
        trigger = WorkflowTrigger.model_validate(job.payload)
        request_id = None
        if isinstance(trigger.cause, (RequestCause, ApprovalCause)):
            request_id = trigger.cause.request_id
            mark_running = getattr(self._continuation.commands, "mark_running", None)
            if mark_running is not None:
                await mark_running(request_id)
        try:
            outcome = await self._continuation.run(
                job.scope, trigger.model_dump(mode="json"), self._worker_id
            )
        except Exception:
            if request_id is not None and job.attempt >= job.max_attempts:
                record_failure = getattr(
                    self._continuation.commands, "record_failure", None
                )
                if record_failure is not None:
                    await record_failure(request_id)
            raise
        return {
            "workflow_id": trigger.workflow_id,
            "outcome": outcome,
        }


__all__ = [
    "LeaderBootstrapResolver",
    "LeaderBootstrapSeed",
    "LeaderTurnRunner",
    "LeaderWorkflowBootstrap",
    "SqlRuntimeContinuation",
    "WorkflowContinuationJobHandler",
]
