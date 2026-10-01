"""Request and response DTOs for ActionRequest authorization."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints

from ..db.action_request import ActionRequest, ActionRequestStatus, RequestedByType
from ..db.approval import ActionApproval, ApprovalStatus
from ..db.rule_evaluation import RuleDecisionValue, RuleEvaluationRecord


_Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
_Hash = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]


class ActionRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_task_version: int = Field(alias="expectedTaskVersion", ge=1, strict=True)
    action_type: _Code = Field(alias="actionType")
    payload: dict[str, JsonValue]


class ActionRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    incident_id: UUID = Field(alias="incidentId")
    task_id: UUID = Field(alias="taskId")
    requested_by_type: RequestedByType = Field(alias="requestedByType")
    requested_by_id: str = Field(alias="requestedById")
    requested_by_version: int | None = Field(alias="requestedByVersion")
    action_type: str = Field(alias="actionType")
    target_type: str = Field(alias="targetType")
    target_id: str | None = Field(alias="targetId")
    payload: dict[str, JsonValue]
    payload_hash: str = Field(alias="payloadHash")
    status: ActionRequestStatus
    version: int
    correlation_id: str = Field(alias="correlationId")
    created_at: datetime = Field(alias="createdAt")


class RuleEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    action_request_id: UUID = Field(alias="actionRequestId")
    decision: RuleDecisionValue
    reason_code: str = Field(alias="reasonCode")
    rule_version: str = Field(alias="ruleVersion")
    evaluated_at: datetime = Field(alias="evaluatedAt")
    correlation_id: str = Field(alias="correlationId")


class ActionApprovalRead(BaseModel):
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


class ActionSubmissionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    action_request: ActionRequestRead = Field(alias="actionRequest")
    rule_evaluation: RuleEvaluationRead = Field(alias="ruleEvaluation")
    approval: ActionApprovalRead | None


def action_submission_read(
    action_request: ActionRequest,
    evaluation: RuleEvaluationRecord,
    approval: ActionApproval | None,
) -> ActionSubmissionRead:
    return ActionSubmissionRead(
        actionRequest=ActionRequestRead.model_validate(action_request),
        ruleEvaluation=RuleEvaluationRead.model_validate(evaluation),
        approval=(
            ActionApprovalRead.model_validate(approval) if approval is not None else None
        ),
    )
