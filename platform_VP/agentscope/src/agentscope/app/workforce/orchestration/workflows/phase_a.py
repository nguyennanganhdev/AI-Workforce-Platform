# -*- coding: utf-8 -*-
"""PHH Phase A proposals only; not shared contracts or runtime services."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ...contracts import (
    AsyncProtocolSnapshotRef,
    OpaqueId,
    RequestResult,
    RequestStatus,
    WorkflowRecord,
    WorkforceModel,
)


class RequestCause(WorkforceModel):
    kind: Literal["request"]
    request_id: OpaqueId


class ApprovalCause(WorkforceModel):
    kind: Literal["approval"]
    request_id: OpaqueId
    approval_id: OpaqueId


class ExternalEventCause(WorkforceModel):
    kind: Literal["external_event"]
    cause_event_id: OpaqueId
    operation_id: OpaqueId


class TimerCause(WorkforceModel):
    kind: Literal["timer"]
    timer_id: OpaqueId


WorkflowCause = Annotated[
    RequestCause | ApprovalCause | ExternalEventCause | TimerCause,
    Field(discriminator="kind"),
]


class WorkflowTrigger(WorkforceModel):
    """Internal wakeup reference. Scope/authority must be reloaded from DB."""

    trigger_id: OpaqueId
    workflow_id: OpaqueId
    cause: WorkflowCause
    expected_state_revision: int | None = Field(
        default=None, ge=1, strict=True
    )


class AgentVersionPin(WorkforceModel):
    agent_id: OpaqueId
    version_id: OpaqueId


class UsedBudget(WorkforceModel):
    model_turns: int = Field(ge=0, strict=True)
    tool_calls: int = Field(ge=0, strict=True)
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)


class WorkflowCheckpoint(WorkforceModel):
    """Durable references, not raw runtime objects, prompts or credentials."""

    schema_version: Literal["phh-phase-a-1"] = "phh-phase-a-1"
    workflow_id: OpaqueId
    state_revision: int = Field(ge=1, strict=True)
    session_refs: tuple[OpaqueId, ...] = Field(min_length=1)
    agent_version_pins: tuple[AgentVersionPin, ...] = Field(min_length=1)
    protocol_pins: tuple[AsyncProtocolSnapshotRef, ...] = ()
    shared_state_ref: OpaqueId
    pending_task_ids: tuple[OpaqueId, ...] = ()
    pending_question_ids: tuple[OpaqueId, ...] = ()
    pending_approval_ids: tuple[OpaqueId, ...] = ()
    operation_refs: tuple[OpaqueId, ...] = ()
    last_processed_causes: tuple[WorkflowCause, ...] = ()
    used_budget: UsedBudget

    @model_validator(mode="after")
    def unique_references(self) -> "WorkflowCheckpoint":
        for name in (
            "session_refs",
            "pending_task_ids",
            "pending_question_ids",
            "pending_approval_ids",
            "operation_refs",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        agents = [pin.agent_id for pin in self.agent_version_pins]
        if len(agents) != len(set(agents)):
            raise ValueError("one pinned version per agent")
        protocols = [pin.tool_version_id for pin in self.protocol_pins]
        if len(protocols) != len(set(protocols)):
            raise ValueError("one protocol snapshot per tool version")
        causes = [cause_key(cause) for cause in self.last_processed_causes]
        if len(causes) != len(set(causes)):
            raise ValueError("processed causes must be unique")
        return self


def cause_key(cause: WorkflowCause) -> tuple[str, str]:
    """Proposed dedupe key suffix; DB must also include workflow_id."""
    if isinstance(cause, (RequestCause, ApprovalCause)):
        return cause.kind, cause.request_id
    if isinstance(cause, ExternalEventCause):
        return cause.kind, cause.cause_event_id
    return cause.kind, cause.timer_id


class CommandClaimResult(WorkforceModel):
    """Shared-command return proposal; also supports non-workflow approvals."""

    request_id: OpaqueId
    is_new: bool = Field(strict=True)
    status: RequestStatus
    result: RequestResult | None = None

    @model_validator(mode="after")
    def result_shape(self) -> "CommandClaimResult":
        if self.is_new and self.status != RequestStatus.ACCEPTED:
            raise ValueError("a new claim must be accepted")
        if (self.status == RequestStatus.COMPLETED) != (
            self.result is not None
        ):
            raise ValueError("only a completed claim has a required result")
        return self


class PinnedRuntimeContext(WorkforceModel):
    """Snapshot shape only. Loading/revalidation remain Foundation work."""

    workflow: WorkflowRecord
    checkpoint: WorkflowCheckpoint

    @model_validator(mode="after")
    def matching_snapshot(self) -> "PinnedRuntimeContext":
        if self.workflow.workflow_id != self.checkpoint.workflow_id:
            raise ValueError("checkpoint belongs to a different workflow")
        if self.workflow.revision != self.checkpoint.state_revision:
            raise ValueError("checkpoint revision differs from workflow")
        versions = tuple(
            pin.version_id for pin in self.checkpoint.agent_version_pins
        )
        if len(self.workflow.version_pins) != len(
            set(self.workflow.version_pins)
        ):
            raise ValueError("workflow version pins must be unique")
        if set(self.workflow.version_pins) != set(versions):
            raise ValueError("workflow and checkpoint version pins differ")
        return self


class RuntimeTurnResult(WorkforceModel):
    """Uncommitted candidate; persistence must enforce CAS/fence and auth."""

    trigger_id: OpaqueId
    expected_state_revision: int = Field(ge=1, strict=True)
    checkpoint: WorkflowCheckpoint
    result: RequestResult

    @model_validator(mode="after")
    def matching_result(self) -> "RuntimeTurnResult":
        if self.checkpoint.state_revision != self.expected_state_revision + 1:
            raise ValueError(
                "candidate checkpoint must advance exactly one revision"
            )
        ids = [message.message_id for message in self.result.messages]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate message_id in one candidate")
        if any(
            message.workflow_id != self.checkpoint.workflow_id
            for message in self.result.messages
        ):
            raise ValueError("message belongs to a different workflow")
        return self
