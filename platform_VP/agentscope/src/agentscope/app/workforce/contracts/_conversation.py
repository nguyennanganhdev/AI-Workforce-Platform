# -*- coding: utf-8 -*-
"""Customer request, workflow, ticket binding, and result contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from ._base import JsonObject, OpaqueId, ShortCode, WorkforceModel
from ._errors import PublicError
from ._identity import PartnerAudience, Scope


class PartnerCommandType(StrEnum):
    START_WORKFLOW = "start_workflow"
    WORKFLOW_REPLY = "workflow_reply"


class RequestStatus(StrEnum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class WorkflowState(StrEnum):
    ACCEPTED = "accepted"
    ACTIVE = "active"
    WAITING_EXTERNAL_EVENT = "waiting_external_event"
    AWAITING_USER = "awaiting_user"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    NEEDS_ATTENTION = "needs_attention"
    BLOCKED_AUTHORIZATION = "blocked_authorization"
    BLOCKED_ROUTE_CHANGED = "blocked_route_changed"
    CLOSED = "closed"


class NextAction(StrEnum):
    NONE = "none"
    SUBMIT_REPLY = "submit_reply"
    SUBMIT_APPROVAL = "submit_approval"
    WATCH_REQUEST = "watch_request"
    WATCH_EVENTS = "watch_events"
    CONFIRM_CLOSE = "confirm_close"
    RESOLVE_ATTENTION = "resolve_attention"


class TextMessageInput(WorkforceModel):
    type: str = Field(pattern="^text$")
    text: str = Field(min_length=1, max_length=20_000)


class PartnerRequestEnvelope(WorkforceModel):
    """Public body; internal routing fields are intentionally absent."""

    schema_version: str = Field(pattern="^1$")
    command_type: PartnerCommandType
    external_request_id: OpaqueId
    external_management_ref: ShortCode
    external_user_id: OpaqueId
    external_ticket_id: OpaqueId | None = None
    external_conversation_id: OpaqueId
    workflow_id: OpaqueId | None = None
    residence_id: OpaqueId | None = None
    timezone: str | None = Field(default=None, max_length=100)
    message: TextMessageInput

    @model_validator(mode="after")
    def validate_command_target(self) -> "PartnerRequestEnvelope":
        """Require an explicit workflow only for replies."""
        if self.command_type == PartnerCommandType.START_WORKFLOW:
            if self.workflow_id is not None:
                raise ValueError("start_workflow must not contain workflow_id")
        elif self.workflow_id is None:
            raise ValueError("workflow_reply requires workflow_id")
        return self


class TicketConversationBinding(WorkforceModel):
    """Immutable server-side route from one partner ticket to one group."""

    scope: Scope
    partner_client_id: OpaqueId
    external_user_id: OpaqueId
    external_ticket_id: OpaqueId
    external_conversation_id: OpaqueId
    workflow_id: OpaqueId
    conversation_id: OpaqueId
    group_id: OpaqueId
    route_id: OpaqueId
    route_revision: int = Field(ge=1)
    status: str = Field(default="active", pattern="^(active|closed)$")
    created_at: datetime
    updated_at: datetime


class InboundRequest(WorkforceModel):
    request_id: OpaqueId
    scope: Scope
    audience: PartnerAudience
    external_request_id: OpaqueId
    external_management_ref: ShortCode
    payload_hash: str = Field(min_length=1, max_length=200)
    route_id: OpaqueId
    route_revision: int = Field(ge=1)
    conversation_id: OpaqueId
    workflow_id: OpaqueId
    group_id: OpaqueId
    run_id: OpaqueId | None = None
    status: RequestStatus
    accepted_at: datetime
    completed_at: datetime | None = None


class AssistantMessage(WorkforceModel):
    message_id: OpaqueId
    workflow_id: OpaqueId
    sender: str = Field(default="assistant", pattern="^assistant$")
    text: str = Field(min_length=1, max_length=20_000)
    created_at: datetime


class RequestResult(WorkforceModel):
    messages: tuple[AssistantMessage, ...] = ()
    data: JsonObject = Field(default_factory=dict)


class InboundReceipt(WorkforceModel):
    request_id: OpaqueId
    request_status: RequestStatus
    external_ticket_id: OpaqueId | None = None
    conversation_id: OpaqueId
    workflow_id: OpaqueId
    ticket_id: OpaqueId | None = None
    workflow_state: WorkflowState
    next_action: NextAction
    workflow_revision: int = Field(ge=1)
    result: RequestResult | None = None
    error: PublicError | None = None
    accepted_at: datetime
    completed_at: datetime | None = None
    status_url: str = Field(min_length=1)
    conversation_url: str = Field(min_length=1)
    event_stream_url: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_state_projection(self) -> "InboundReceipt":
        if self.workflow_state == WorkflowState.CLOSED:
            if self.next_action != NextAction.NONE:
                raise ValueError("closed workflow requires next_action=none")
        if self.request_status in {
            RequestStatus.ACCEPTED,
            RequestStatus.QUEUED,
            RequestStatus.RUNNING,
        } and self.next_action != NextAction.WATCH_REQUEST:
            raise ValueError(
                "pending request requires next_action=watch_request",
            )
        if (
            self.request_status == RequestStatus.COMPLETED
            and self.next_action == NextAction.WATCH_REQUEST
        ):
            raise ValueError("completed request cannot watch_request")
        return self


class CloseWorkflowCommand(WorkforceModel):
    """Explicit, idempotent request to close one bound workflow."""

    schema_version: str = Field(pattern="^1$")
    external_request_id: OpaqueId
    external_user_id: OpaqueId
    external_ticket_id: OpaqueId | None = None
    external_conversation_id: OpaqueId
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=200)
    stop_tracking_only: bool = False


class WorkflowProjection(WorkforceModel):
    workflow_id: OpaqueId
    external_ticket_id: OpaqueId | None = None
    ticket_id: OpaqueId | None = None
    state: WorkflowState
    next_action: NextAction
    revision: int = Field(ge=1)


class ConversationSnapshot(WorkforceModel):
    conversation_id: OpaqueId
    external_conversation_id: OpaqueId
    external_user_id: OpaqueId
    workflows: tuple[WorkflowProjection, ...]
    messages: tuple[AssistantMessage, ...] = ()
    pending_approvals: tuple[JsonObject, ...] = ()
    snapshot_cursor: OpaqueId | None = None


class WorkflowRecord(WorkforceModel):
    workflow_id: OpaqueId
    scope: Scope
    audience: PartnerAudience
    conversation_id: OpaqueId
    ticket_id: OpaqueId | None = None
    route_id: OpaqueId
    route_revision: int = Field(ge=1)
    state: WorkflowState
    revision: int = Field(ge=1)
    group_id: OpaqueId
    checkpoint_ref: OpaqueId | None = None
    version_pins: tuple[OpaqueId, ...] = ()
    pending_waits: tuple[OpaqueId, ...] = ()
    last_applied_event_id: OpaqueId | None = None
    created_at: datetime
    updated_at: datetime
