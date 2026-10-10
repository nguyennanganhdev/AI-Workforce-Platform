"""PHH persistence seams with mandatory atomic storage guarantees."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field, model_validator

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
    pass


class WorkflowClosed(WorkflowConflict):
    pass


class WorkflowPattern(StrEnum):
    RESPONSE_ONLY = "response_only"
    INTERACTIVE = "interactive"
    EXTERNAL_TRACKING = "external_tracking"


class WorkflowBundle(PinnedRuntimeContext):
    pattern: WorkflowPattern
    published_read_only: bool = False
    observed_events: tuple[str, ...] = ()

    @model_validator(mode="after")
    def policy_shape(self):
        record = self.workflow
        if (
            type(record.revision) is not int
            or type(record.route_revision) is not int
            or record.created_at.tzinfo is None
            or record.updated_at.tzinfo is None
        ):
            raise ValueError(
                "workflow requires strict revisions and aware timestamps"
            )
        if self.pattern == WorkflowPattern.RESPONSE_ONLY:
            if not self.published_read_only:
                raise ValueError(
                    "response-only requires published read-only policy"
                )
        return self


class TurnPlan(WorkforceModel):
    candidate: RuntimeTurnResult
    next_state: WorkflowState


class BindingReservation(WorkforceModel):
    bundle: WorkflowBundle
    is_new: bool = Field(strict=True)


class TurnLease(WorkforceModel):
    workflow_id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    fence: int = Field(strict=True, ge=1)
    expires_at: datetime


class StartInput(WorkforceModel):
    request_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=20_000)


class ReplyInput(StartInput):
    expected_revision: int = Field(strict=True, ge=1)


class CloseInput(CloseWorkflowCommand):
    workflow_id: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(strict=True, ge=1)


class WorkflowAuthorization(Protocol):
    """Authorize using authenticated runtime identity and current grants."""

    async def authorize(
        self,
        scope: Scope,
        actor: ActorContext | None,
        audience: PartnerAudience,
        operation: str,
        uow: UnitOfWork | None = None,
    ) -> None:
        ...

    async def authorize_trigger(
        self,
        bundle: WorkflowBundle,
        trigger: WorkflowTrigger,
        uow: UnitOfWork | None = None,
    ) -> None:
        """Verify durable cause authority and the current route grant."""
        ...


class WorkflowBootstrap(Protocol):
    """Select published agents/route and allocate isolated group/session."""

    async def prepare(
        self,
        scope: Scope,
        actor: ActorContext,
        audience: PartnerAudience,
        message: StartInput,
        uow: UnitOfWork,
    ) -> WorkflowBundle:
        ...


class WorkflowRepository(Protocol):
    """Scope all keys. Never commit an injected UOW.

    create_unique atomically reserves ticket AND chat binding and returns
    BindingReservation with is_new. Identical binding retries return the
    existing bundle. Initial checkpoint_ref attachment may keep revision 1
    only inside the same uncommitted creation UOW. Later saves must advance
    revision and compare revision, closed state and unexpired lease fence
    inside the write transaction.
    Claim serializes the workflow and exclusive session refs across workers.
    Input/cause/results and checkpoint/event/job writes must share one UOW.
    """

    async def create_unique(
        self, bundle: WorkflowBundle, uow: UnitOfWork
    ) -> BindingReservation:
        ...

    async def load(
        self, scope: Scope, workflow_id: str, uow: UnitOfWork | None = None
    ) -> WorkflowBundle:
        ...

    async def save(
        self,
        bundle: WorkflowBundle,
        expected_revision: int,
        uow: UnitOfWork,
        lease: TurnLease | None = None,
    ) -> bool:
        ...

    async def record_input(
        self,
        scope: Scope,
        workflow_id: str,
        cause_key: tuple[str, str],
        text: str,
        uow: UnitOfWork,
    ) -> bool:
        """Return is_new; conflicting content for the same key fails."""
        ...

    async def claim(
        self, scope: Scope, workflow_id: str, owner: str, duration: timedelta
    ) -> TurnLease | None:
        ...

    async def valid_lease(self, scope: Scope, lease: TurnLease) -> bool:
        ...

    async def release(self, scope: Scope, lease: TurnLease) -> None:
        ...


class OperationLookup(Protocol):
    """Resolve canonical operation refs and pinned protocol semantics."""

    async def get(
        self, scope: Scope, operation_id: str, uow: UnitOfWork | None = None
    ) -> ExternalOperation:
        ...

    async def is_pending(self, operation: ExternalOperation) -> bool:
        """Read terminal states from the pinned protocol."""
        ...

    async def accept_event(
        self,
        operation: ExternalOperation,
        event: NormalizedJobEvent,
        uow: UnitOfWork,
    ) -> bool:
        """CAS/version/hash/inbox dedupe + fact update, no commit or LLM."""
        ...


def raw_models(value):
    """Keep model_copy extras while revalidating nested model instances."""
    if isinstance(value, BaseModel):
        return {key: raw_models(item) for key, item in dict(value).items()}
    if isinstance(value, Mapping):
        return {key: raw_models(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [raw_models(item) for item in value]
    return value


def validated_bundle(value: object) -> WorkflowBundle:
    return WorkflowBundle.model_validate(raw_models(value))


def require_binding(
    bundle: WorkflowBundle, scope: Scope, audience: PartnerAudience
) -> WorkflowRecord:
    record = bundle.workflow
    if record.scope != scope or record.audience != audience:
        raise PermissionError("workflow binding mismatch")
    return record


def parse_model(model, value: Mapping[str, object]):
    return model.model_validate(dict(value))
