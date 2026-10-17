# -*- coding: utf-8 -*-
"""Stable error codes and public error envelope."""

from enum import StrEnum

from pydantic import Field

from ._base import JsonObject, OpaqueId, WorkforceModel


class WorkforceErrorCode(StrEnum):
    ROUTE_NOT_AUTHORIZED = "ROUTE_NOT_AUTHORIZED"
    CONVERSATION_SCOPE_MISMATCH = "CONVERSATION_SCOPE_MISMATCH"
    EXTERNAL_TICKET_REQUIRED = "EXTERNAL_TICKET_REQUIRED"
    TICKET_ALREADY_BOUND = "TICKET_ALREADY_BOUND"
    CONVERSATION_ALREADY_BOUND = "CONVERSATION_ALREADY_BOUND"
    WORKFLOW_BINDING_MISMATCH = "WORKFLOW_BINDING_MISMATCH"
    WORKFLOW_REFERENCE_REQUIRED = "WORKFLOW_REFERENCE_REQUIRED"
    WORKFLOW_CLOSED = "WORKFLOW_CLOSED"
    WORKFLOW_NOT_READY_TO_CLOSE = "WORKFLOW_NOT_READY_TO_CLOSE"
    ROUTE_CONFLICT = "ROUTE_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    MISSING_REQUIRED_CAPABILITY = "MISSING_REQUIRED_CAPABILITY"
    AGENT_ALREADY_EXISTS = "AGENT_ALREADY_EXISTS"
    AGENT_BUILD_IN_PROGRESS = "AGENT_BUILD_IN_PROGRESS"
    REUSE_DECISION_STALE = "REUSE_DECISION_STALE"
    EVENT_ID_CONFLICT = "EVENT_ID_CONFLICT"
    EVENT_CURSOR_EXPIRED = "EVENT_CURSOR_EXPIRED"
    UNSUPPORTED_MESSAGE_PART = "UNSUPPORTED_MESSAGE_PART"


class PublicError(WorkforceModel):
    code: WorkforceErrorCode | str
    message: str = Field(min_length=1, max_length=2000)
    details: JsonObject = Field(default_factory=dict)
    request_id: OpaqueId
    retryable: bool = False


class ErrorResponse(WorkforceModel):
    error: PublicError


class WorkforceContractError(ValueError):
    """Internal exception carrying a stable contract error code."""

    def __init__(
        self,
        code: WorkforceErrorCode,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
