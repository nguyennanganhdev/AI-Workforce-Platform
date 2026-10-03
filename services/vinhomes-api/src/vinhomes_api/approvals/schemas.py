"""Approval inbox and decision DTOs."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ..db.action_request import ActionRequest, ActionRequestStatus
from ..db.approval import ActionApproval, ApprovalStatus
from ..db.rule_evaluation import RuleEvaluationRecord
from ..actions.schemas import ActionRequestRead, RuleEvaluationRead


_Hash = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]


class ApprovalDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_version: int = Field(alias="expectedVersion", ge=1, strict=True)
    action_payload_hash: _Hash = Field(alias="actionPayloadHash")


class ApprovalRejectInput(ApprovalDecisionInput):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    action_request_id: UUID = Field(alias="actionRequestId")
    action_payload_hash: str = Field(alias="actionPayloadHash")
    status: ApprovalStatus
    requested_by_id: str = Field(alias="requestedById")
    reviewer_id: str | None = Field(alias="reviewerId")
    expires_at: datetime = Field(alias="expiresAt")
    decided_at: datetime | None = Field(alias="decidedAt")
    reason: str | None
    version: int


class ApprovalDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    approval: ApprovalRead
    action_request: ActionRequestRead = Field(alias="actionRequest")
    action_status: ActionRequestStatus = Field(alias="actionStatus")
    rule_evaluation: RuleEvaluationRead = Field(alias="ruleEvaluation")


class ApprovalPage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[ApprovalDetailRead]
    total: int
    limit: int
    offset: int


def approval_detail_read(
    approval: ActionApproval,
    action_request: ActionRequest,
    evaluation: RuleEvaluationRecord,
) -> ApprovalDetailRead:
    return ApprovalDetailRead(
        approval=ApprovalRead.model_validate(approval),
        actionRequest=ActionRequestRead.model_validate(action_request),
        actionStatus=action_request.status,
        ruleEvaluation=RuleEvaluationRead.model_validate(evaluation),
    )
