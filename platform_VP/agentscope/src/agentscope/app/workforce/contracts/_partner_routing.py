# -*- coding: utf-8 -*-
"""Partner-to-management-account routing contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from ._base import OpaqueId, ShortCode, WorkforceModel
from ._identity import Scope


class PartnerRouteStatus(StrEnum):
    """Lifecycle of a partner route grant."""

    PENDING_CONFIRMATION = "pending_confirmation"
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKED = "revoked"


class PartnerOperation(StrEnum):
    """Fine-grained operations granted to a machine credential."""

    SUBMIT_REQUEST = "submit_request"
    REPLY = "reply"
    READ_RESULT = "read_result"
    RECEIVE_EVENTS = "receive_events"
    SUBMIT_CONSENT = "submit_consent"
    CLOSE_WORKFLOW = "close_workflow"
    CONFIRM_ROUTE = "confirm_route"
    SYNC_RESIDENCE = "sync_residence"
    PUBLISH_JOB_EVENT = "publish_job_event"
    READ_EVENT_RECEIPT = "read_event_receipt"


class PartnerManagerRoute(WorkforceModel):
    """Persisted mapping from a partner reference to one manager account."""

    route_id: OpaqueId
    scope: Scope
    partner_client_id: OpaqueId
    external_management_ref: ShortCode
    status: PartnerRouteStatus
    revision: int = Field(ge=1)
    allowed_operations: tuple[PartnerOperation, ...]
    granted_by: OpaqueId
    confirmed_by_client_id: OpaqueId | None = None
    created_at: datetime
    updated_at: datetime


class ResolvedPartnerRoute(WorkforceModel):
    """Server-produced route snapshot pinned to an accepted request."""

    scope: Scope
    route_id: OpaqueId
    route_revision: int = Field(ge=1)
    grant_operations: tuple[PartnerOperation, ...]
    membership_revision: int = Field(ge=1)
    resolved_at: datetime


class RouteConfirmation(WorkforceModel):
    schema_version: str = Field(pattern="^1$")
    external_management_ref: ShortCode
    expected_revision: int = Field(ge=1)


class RouteConfirmationResult(WorkforceModel):
    route_id: OpaqueId
    external_management_ref: ShortCode
    status: PartnerRouteStatus
    revision: int = Field(ge=1)
    allowed_operations: tuple[PartnerOperation, ...]


class ResidenceStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ResidenceSync(WorkforceModel):
    schema_version: str = Field(pattern="^1$")
    external_user_id: OpaqueId
    external_management_ref: ShortCode
    status: ResidenceStatus
    expected_revision: int = Field(ge=0)


class ResidenceSyncResult(WorkforceModel):
    residence_id: OpaqueId
    external_user_id: OpaqueId
    external_management_ref: ShortCode
    status: ResidenceStatus
    revision: int = Field(ge=1)
    updated_at: datetime
