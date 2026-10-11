"""Workflow aggregates and private orchestration boundaries for Phase B."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from ...contracts import (
    ActorContext,
    CloseWorkflowCommand,
    ExternalOperation,
    NormalizedJobEvent,
    PartnerAudience,
    Scope,
    UnitOfWork,
    WorkflowRecord,
    WorkflowState,
    WorkforceModel,
)
from .phase_a import PinnedRuntimeContext, RuntimeTurnResult, WorkflowTrigger


class WorkflowConflict(RuntimeError):
    """A durable binding, revision, fence, or transition no longer matches."""


class WorkflowClosed(WorkflowConflict):
    """The requested action cannot be applied to a closed workflow."""


class WorkflowPattern(StrEnum):
    RESPONSE_ONLY = "response_only"
    INTERACTIVE = "interactive"
    EXTERNAL_TRACKING = "external_tracking"


class WorkflowAggregate(PinnedRuntimeContext):
    """Durable workflow state plus policy and processed event identities."""

    pattern: WorkflowPattern
    published_read_only: bool = False
    applied_external_events: tuple[str, ...] = ()
    applied_query_results: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy(self) -> "WorkflowAggregate":
        workflow = self.workflow
        if (
            workflow.created_at.tzinfo is None
            or workflow.updated_at.tzinfo is None
        ):
            raise ValueError("workflow timestamps must be timezone-aware")
        if (
            type(workflow.revision) is not int
            or type(workflow.route_revision) is not int
        ):
            raise ValueError("workflow revisions must be strict integers")
        if (
            self.pattern == WorkflowPattern.RESPONSE_ONLY
            and not self.published_read_only
        ):
            raise ValueError(
                "response-only workflows require published read-only policy"
            )
        if len(self.applied_external_events) != len(
            set(self.applied_external_events)
        ):
            raise ValueError("external event identities must be unique")
        if any(
            not timer_id or not source_hash
            for timer_id, source_hash in self.applied_query_results.items()
        ):
            raise ValueError("query result identities must not be empty")
        return self


class WorkflowReservation(WorkforceModel):
    aggregate: WorkflowAggregate
    created: bool = Field(strict=True)


class WorkflowLease(WorkforceModel):
    workflow_id: str = Field(min_length=1)
    owner: str = Field(min_length=1, max_length=200)
    fencing_token: int = Field(strict=True, ge=1)
    expires_at: datetime


class TurnDecision(WorkforceModel):
    candidate: RuntimeTurnResult
    next_state: WorkflowState


class StartMessage(WorkforceModel):
    request_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=20_000)
    route_id: str | None = Field(default=None, min_length=1, max_length=200)
    route_revision: int | None = Field(default=None, strict=True, ge=1)

    @model_validator(mode="after")
    def complete_route_pin(self) -> "StartMessage":
        if (self.route_id is None) != (self.route_revision is None):
            raise ValueError("route_id and route_revision must be supplied together")
        return self


class ReplyMessage(StartMessage):
    expected_revision: int = Field(strict=True, ge=1)


class CloseMessage(CloseWorkflowCommand):
    workflow_id: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(strict=True, ge=1)
    stop_tracking_only: bool = Field(default=False, strict=True)


class WorkflowRepository(Protocol):
    """Persistence contract; injected transactions are never committed here."""

    async def reserve(
        self, aggregate: WorkflowAggregate, uow: UnitOfWork
    ) -> WorkflowReservation: ...

    async def load(
        self,
        scope: Scope,
        workflow_id: str,
        uow: UnitOfWork | None = None,
    ) -> WorkflowAggregate: ...

    async def save(
        self,
        aggregate: WorkflowAggregate,
        expected_revision: int,
        uow: UnitOfWork,
        lease: WorkflowLease | None = None,
    ) -> bool: ...

    async def record_input(
        self,
        scope: Scope,
        workflow_id: str,
        cause_key: tuple[str, str],
        text: str,
        uow: UnitOfWork,
    ) -> bool: ...

    async def acquire_lease(
        self,
        scope: Scope,
        workflow_id: str,
        worker_id: str,
        duration: timedelta,
    ) -> WorkflowLease | None: ...

    async def lease_is_current(
        self,
        scope: Scope,
        lease: WorkflowLease,
        uow: UnitOfWork | None = None,
    ) -> bool: ...

    async def release_lease(
        self, scope: Scope, lease: WorkflowLease
    ) -> None: ...


class WorkflowBootstrap(Protocol):
    """Select published versions and create one isolated group/session."""

    async def prepare(
        self,
        scope: Scope,
        actor: ActorContext,
        audience: PartnerAudience,
        message: StartMessage,
        uow: UnitOfWork,
    ) -> WorkflowAggregate: ...


class WorkflowAuthorization(Protocol):
    async def authorize(
        self,
        scope: Scope,
        actor: ActorContext | None,
        audience: PartnerAudience,
        operation: str,
        uow: UnitOfWork | None = None,
    ) -> None: ...

    async def authorize_trigger(
        self,
        aggregate: WorkflowAggregate,
        trigger: WorkflowTrigger,
        uow: UnitOfWork | None = None,
    ) -> None: ...

    async def can_publish_external_event(
        self,
        aggregate: WorkflowAggregate,
        event: NormalizedJobEvent,
        uow: UnitOfWork,
    ) -> bool:
        """Suppress delivery after revoke; preserve provider facts."""
        ...


class OperationReader(Protocol):
    """Read the operation fact already updated by Execution in the same UOW."""

    async def get(
        self,
        scope: Scope,
        operation_id: str,
        uow: UnitOfWork | None = None,
    ) -> ExternalOperation: ...

    async def is_pending(
        self, operation: ExternalOperation, uow: UnitOfWork | None = None
    ) -> bool: ...


class WorkflowQueryResult(WorkforceModel):
    """Verified result of an internal status query, not a provider event."""

    timer_id: str = Field(min_length=1, max_length=200)
    protocol_schema_hash: str = Field(min_length=1, max_length=200)
    source_hash: str = Field(min_length=1, max_length=200)
    observed_at: AwareDatetime
    status: str = Field(min_length=1, max_length=200)
    facts: dict[str, object] = Field(default_factory=dict)
    provider_version: int | None = Field(default=None, ge=0, strict=True)
    terminal: bool = Field(strict=True)


class CommittedTurnEvidence(WorkforceModel):
    """Sanitized runtime evidence persisted atomically with a completed turn."""

    workflow_id: str = Field(min_length=1, max_length=200)
    trigger_id: str = Field(min_length=1, max_length=200)
    cause_kind: str = Field(min_length=1, max_length=64)
    audience_key: str = Field(min_length=1, max_length=200)
    before_state: WorkflowState
    after_state: WorkflowState
    before_revision: int = Field(ge=1, strict=True)
    after_revision: int = Field(ge=2, strict=True)
    next_action: str = Field(min_length=1, max_length=64)
    checked_effects: tuple[str, ...] = ()
    model_turns: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)
    new_tracking_records: int = Field(ge=0, strict=True)
    message_ids: tuple[str, ...] = ()
    approval_cause: bool = Field(strict=True)
    provider_cause: bool = Field(strict=True)


class RuntimeEvidenceWriter(Protocol):
    async def record(
        self, evidence: CommittedTurnEvidence, uow: UnitOfWork
    ) -> None: ...


def raw_value(value: object) -> object:
    """Revalidate copied Pydantic models without dropping injected extras."""
    if isinstance(value, BaseModel):
        return {key: raw_value(item) for key, item in dict(value).items()}
    if isinstance(value, Mapping):
        return {key: raw_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [raw_value(item) for item in value]
    return value


def parse_aggregate(value: object) -> WorkflowAggregate:
    return WorkflowAggregate.model_validate(raw_value(value))


def require_binding(
    aggregate: WorkflowAggregate,
    scope: Scope,
    audience: PartnerAudience,
) -> WorkflowRecord:
    workflow = aggregate.workflow
    if workflow.scope != scope or workflow.audience != audience:
        raise PermissionError("workflow scope or audience mismatch")
    return workflow

