# -*- coding: utf-8 -*-
"""External operation, provider event, and approval contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from ._base import JsonObject, OpaqueId, WorkforceModel
from ._identity import PartnerAudience, Scope


class EventIngestionStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    APPLIED = "applied"
    REJECTED = "rejected"


class ExternalCreationStatus(StrEnum):
    PREPARED = "prepared"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ProviderEventEnvelope(WorkforceModel):
    schema_version: str = Field(pattern="^1$")
    external_event_id: OpaqueId
    external_job_id: OpaqueId | None = None
    client_reference: OpaqueId | None = None
    event_type: str = Field(min_length=1, max_length=200)
    provider_version: int | None = Field(default=None, ge=0)
    occurred_at: datetime
    data: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_correlation(self) -> "ProviderEventEnvelope":
        if self.external_job_id is None and self.client_reference is None:
            raise ValueError(
                "external_job_id or client_reference is required",
            )
        return self


class ProviderEventReceipt(WorkforceModel):
    receipt_id: OpaqueId
    ingestion_status: EventIngestionStatus
    duplicate: bool = False
    received_at: datetime


class AsyncProtocolSnapshotRef(WorkforceModel):
    """Stable reference while Registry owns detailed protocol semantics."""

    protocol_id: OpaqueId
    protocol_version: str = Field(min_length=1, max_length=100)
    schema_hash: str = Field(min_length=1, max_length=200)
    tool_version_id: OpaqueId
    provider_integration_id: OpaqueId | None = None
    capabilities: tuple[str, ...] = ()


class NormalizedJobEvent(WorkforceModel):
    inbox_event_id: OpaqueId
    provider_integration_id: OpaqueId
    external_event_id: OpaqueId
    external_job_id: OpaqueId | None = None
    client_reference: OpaqueId | None = None
    normalized_status: str = Field(min_length=1, max_length=200)
    facts: JsonObject = Field(default_factory=dict)
    provider_version: int | None = Field(default=None, ge=0)
    protocol_schema_hash: str = Field(min_length=1, max_length=200)
    source_hash: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    received_at: datetime


class ExternalOperation(WorkforceModel):
    operation_id: OpaqueId
    scope: Scope
    audience: PartnerAudience
    workflow_id: OpaqueId
    ticket_id: OpaqueId | None = None
    conversation_id: OpaqueId
    call_id: OpaqueId
    provider_integration_id: OpaqueId
    protocol_snapshot: AsyncProtocolSnapshotRef
    correlation_id: OpaqueId
    external_job_id: OpaqueId | None = None
    creation_status: ExternalCreationStatus
    job_status: str | None = Field(default=None, max_length=200)
    last_provider_version: int | None = Field(default=None, ge=0)
    revision: int = Field(ge=1)


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class PartnerApprovalDecision(WorkforceModel):
    schema_version: str = Field(pattern="^1$")
    external_request_id: OpaqueId
    external_user_id: OpaqueId
    external_ticket_id: OpaqueId | None = None
    external_conversation_id: OpaqueId
    workflow_id: OpaqueId
    decision: ApprovalDecision
    expected_revision: int = Field(ge=1)
    arguments_hash: str = Field(min_length=1, max_length=200)
    quote_ref: OpaqueId | None = None
