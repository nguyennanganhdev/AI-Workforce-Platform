# -*- coding: utf-8 -*-
"""Proposed public payload allowlist; canonical envelope remains shared."""

from datetime import datetime
import re
from typing import Annotated, Literal

from pydantic import AwareDatetime, BeforeValidator, Field

from ...contracts import (
    ConversationEvent,
    OpaqueId,
    ShortCode,
    WorkflowState,
    WorkforceModel,
)


PUBLIC_TIMESTAMP_PATTERN = (
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


def timestamp_input(value: object) -> object:
    """Wire timestamps are strings, never implicit epoch numbers."""
    if not isinstance(value, (str, datetime)):
        raise ValueError("timestamp requires a string or aware datetime")
    if isinstance(value, str) and not re.fullmatch(
        PUBLIC_TIMESTAMP_PATTERN, value
    ):
        raise ValueError("timestamp requires RFC 3339 with timezone")
    return value


PublicTimestamp = Annotated[
    AwareDatetime,
    BeforeValidator(timestamp_input),
    Field(json_schema_extra={"pattern": PUBLIC_TIMESTAMP_PATTERN}),
]


class RequestAcceptedPayload(WorkforceModel):
    request_id: OpaqueId


class WorkflowStatusPayload(WorkforceModel):
    state: WorkflowState
    revision: int = Field(ge=1, strict=True)


class TicketCreatedPayload(WorkforceModel):
    ticket_id: OpaqueId
    status: ShortCode


class TicketStatusPayload(WorkforceModel):
    status: ShortCode
    public_details: str | None = Field(default=None, max_length=2000)


class AssistantMessagePayload(WorkforceModel):
    message_id: OpaqueId
    text: str = Field(min_length=1, max_length=20_000)


class ApprovalRequiredPayload(WorkforceModel):
    approval_id: OpaqueId
    summary: str = Field(min_length=1, max_length=2000)
    expires_at: PublicTimestamp


class ApprovalResolvedPayload(WorkforceModel):
    approval_id: OpaqueId
    status: ShortCode


class OperationStatusPayload(WorkforceModel):
    operation_type: ShortCode
    status_schema: ShortCode
    status: ShortCode
    external_reference: OpaqueId | None = None


class WorkflowAwaitingUserPayload(WorkforceModel):
    reason: str = Field(min_length=1, max_length=2000)
    revision: int = Field(ge=1, strict=True)


class WorkflowNeedsAttentionPayload(WorkforceModel):
    reason_code: ShortCode


class WorkflowClosedPayload(WorkforceModel):
    state: Literal["closed"]
    revision: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=200)
    closed_at: PublicTimestamp


PUBLIC_PAYLOAD_MODELS: dict[str, type[WorkforceModel]] = {
    "request.accepted": RequestAcceptedPayload,
    "workflow.status_changed": WorkflowStatusPayload,
    "ticket.created": TicketCreatedPayload,
    "ticket.status_changed": TicketStatusPayload,
    "assistant.message": AssistantMessagePayload,
    "approval.required": ApprovalRequiredPayload,
    "approval.resolved": ApprovalResolvedPayload,
    "operation.status_changed": OperationStatusPayload,
    "workflow.awaiting_user": WorkflowAwaitingUserPayload,
    "workflow.needs_attention": WorkflowNeedsAttentionPayload,
    "workflow.closed": WorkflowClosedPayload,
}


def validate_public_event(event: ConversationEvent) -> ConversationEvent:
    """Validate shape, not authorization or content redaction; no emission."""
    # Existing model instances and model_copy updates can bypass validation.
    # dict(event) keeps extra copied fields; model_dump would drop them.
    ConversationEvent.model_validate(dict(event))
    model = PUBLIC_PAYLOAD_MODELS.get(event.event_type)
    if model is None:
        raise ValueError(
            "event type is not in the public contract section 9.7"
        )
    model.model_validate(event.payload)
    return event
