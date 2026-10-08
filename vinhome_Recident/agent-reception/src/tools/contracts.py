"""PH16 consumer contract proposal, independent of HTTP and graph implementation.

This is not Team Chien's frozen API schema. Supervisor payloads use the agreed
V2 schema; V1 graph calls must be migrated explicitly, never relabelled as V2.
All operations are system/internal and must be selected by application code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

CONTRACT_VERSION = "ph16.draft.1"


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("TEXT_REQUIRED")
    return value


def _timestamp(value: str) -> str:
    if (
        "T" not in value
        or datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None
    ):
        raise ValueError("TIMESTAMP_TIMEZONE_REQUIRED")
    return value


def _true(value: object) -> bool:
    if value is not True:
        raise ValueError("CONFIRMATION_REQUIRED")
    return True


def _file_id(value: str) -> str:
    if "://" in value or value.lower().startswith("data:"):
        raise ValueError("FILE_ID_REQUIRED_NOT_URL")
    return value


Id = Annotated[str, Field(min_length=1, max_length=512), AfterValidator(_nonblank)]
Text = Annotated[str, Field(max_length=16384)]
RequiredText = Annotated[Text, AfterValidator(_nonblank)]
Revision = Annotated[int, Field(ge=0, le=2**53 - 1)]
Timestamp = Annotated[Id, AfterValidator(_timestamp)]
Confirmed = Annotated[Literal[True], BeforeValidator(_true)]
FileId = Annotated[Id, AfterValidator(_file_id)]
FileIds = Annotated[
    list[FileId],
    Field(max_length=256),
    AfterValidator(lambda ids: list(dict.fromkeys(ids))),
]
HandoffReason = Literal[
    "needs_staff", "self_help_declined", "self_help_failed", "emergency"
]


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        allow_inf_nan=False,
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


class VerifiedContext(ContractModel):
    """Shape only: the runtime must obtain this from authenticated resolution.

    Never construct it from model output or a browser request body. The backend
    must still authorize the service credential, principal and binding per call.
    """

    tenantId: Id
    principalId: Id
    bindingId: Id
    runId: Id
    requestId: Id


class TicketRef(ContractModel):
    ticket_id: Id
    ticket_generation: Revision
    ticket_version: Id  # Opaque backend version, never coerced to/from an integer.


class Ticket(TicketRef):
    ticket_code: Id
    aggregate_version: Revision
    created_at: Timestamp


class Fact(ContractModel):
    key: Id
    value: Text | int | float | bool | None
    source: Literal["customer_report", "staff_verified", "agent_inference"]
    source_message_id: Id


class InputFact(Fact):
    # Reception cannot confer staff verification on an LLM-extracted fact.
    source: Literal["customer_report", "agent_inference"]


Facts = Annotated[list[Fact], Field(max_length=64)]
InputFacts = Annotated[list[InputFact], Field(max_length=64)]


class ResidentMessage(ContractModel):
    id: Id
    text: Text
    fileIds: FileIds = Field(default_factory=list)

    @model_validator(mode="after")
    def has_content(self):
        if not self.text.strip() and not self.fileIds:
            raise ValueError("MESSAGE_CONTENT_REQUIRED")
        return self


class Incident(ContractModel):
    title: Annotated[str, Field(max_length=512)]
    description: Text
    facts: Facts
    file_ids: FileIds


class IncidentSubmission(Incident):
    facts: InputFacts


class DraftInput(ContractModel):
    channel_id: Id
    handoff_reason: HandoffReason


class ProfileInput(TicketRef):
    resident_response: ResidentMessage


class IncidentInput(TicketRef):
    incident: IncidentSubmission


class AssessmentInput(TicketRef):
    facts: InputFacts


class HandoffInput(TicketRef):
    correlation_id: Id
    handoff_reason: HandoffReason
    # Backend loads profile, incident, official triage and destination, then
    # constructs ReceptionToSupervisorMessage V2. No model-supplied routing.


class WaitInput(TicketRef):
    correlation_id: Id


class EventInput(TicketRef):
    event_id: Id
    aggregate_version: Revision
    correlation_id: Id


class AppendInput(TicketRef):
    source_message_id: Id
    message: Text  # An image-only follow-up is valid.
    facts: InputFacts
    file_ids: FileIds

    @model_validator(mode="after")
    def has_content(self):
        if not self.message.strip() and not self.facts and not self.file_ids:
            raise ValueError("FOLLOW_UP_CONTENT_REQUIRED")
        return self


class InteractionInput(AppendInput):
    message_type: Literal[
        "information_provided",
        "plan_approved",
        "plan_rejected",
        "plan_change_requested",
    ]
    # ticket_version remains the version the resident actually saw. Backend
    # verifies the one outstanding question/plan; no inference from message text.


class CancellationInput(TicketRef):
    reason: RequiredText
    source_message_id: Id


class SelfHelpAttempt(ContractModel):
    attempt_id: Id
    procedure_version: Id
    status: Literal["offered", "accepted"]


class SelfHelpInput(ContractModel):
    channel_id: Id
    reception_session_id: Id
    source_message: ResidentMessage
    policy_version: Id
    attempt: SelfHelpAttempt | None = None
    # Eligibility/consent come from backend policy, not a model decision object.


class EmergencyInput(ContractModel):
    channel_id: Id
    reception_session_id: Id
    source_message: ResidentMessage
    policy_version: Id
    ticket_id: Id | None = None
    ticket_generation: Revision | None = None
    ticket_version: Id | None = None

    @model_validator(mode="after")
    def complete_ticket_reference(self):
        fields = (self.ticket_id, self.ticket_generation, self.ticket_version)
        if any(v is not None for v in fields) and not all(
            v is not None for v in fields
        ):
            raise ValueError("TICKET_REFERENCE_INCOMPLETE")
        return self


class ResidentProfile(ContractModel):
    resident_id: Id
    resident_name: RequiredText
    phone_number: Id
    unit_id: Id
    unit_number: Id
    building_id: Id
    building_code: Id
    building_name: RequiredText
    domain_id: Id
    domain_name: RequiredText
    location_scope_id: Id


class VerifiedProfile(ContractModel):
    kind: Literal["verified"]
    profile: ResidentProfile


class ProfileQuestions(ContractModel):
    kind: Literal["missing", "selection_required"]
    questions: Annotated[list[RequiredText], Field(min_length=1, max_length=64)]


ProfileOutput = VerifiedProfile | ProfileQuestions


class IncidentOutput(ContractModel):
    ticket: Ticket
    incident: Incident
    missing_fields: Annotated[list[Id], Field(max_length=64)]


class Triage(ContractModel):
    status: Literal["applied"]
    policy_version: Id
    triage_decision_id: Id
    request_kind: Literal["incident", "service_request"]
    priority: Literal["low", "normal", "high", "critical"]
    severity: Literal[
        "unknown", "minor", "moderate", "major", "critical", "not_applicable"
    ]
    is_emergency: bool


class AppliedAssessment(ContractModel):
    ticket: Ticket
    triage: Triage


class AssessmentReview(ContractModel):
    status: Literal["policy_missing", "review_required"]


AssessmentOutput = AppliedAssessment | AssessmentReview


class Route(ContractModel):
    destination_id: Id
    workspace_id: Id
    team_id: Id
    route_revision: Revision
    coordination_binding_id: Id
    building_id: Id
    domain_id: Id
    ticket_version: Id


class ResolvedRoute(ContractModel):
    kind: Literal["resolved"]
    route: Route


class UnresolvedRoute(ContractModel):
    kind: Literal["unresolved"]


RouteOutput = ResolvedRoute | UnresolvedRoute


class HandoffOutput(TicketRef):
    schema_version: Literal["2.0"]
    persisted: Confirmed
    enqueued: Confirmed
    correlation_id: Id
    operation_id: Id


class SupervisorWorkResult(ContractModel):
    outcome: Literal["work_completed", "needs_human_review", "unable_to_resolve"]
    summary: RequiredText
    work_order_ids: FileIds
    evidence_ids: FileIds


class SupervisorError(ContractModel):
    code: Id
    retryable: bool
    message: Text


class SupervisorMessage(TicketRef):
    """Output direction of docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md, schema V2."""

    schema_version: Literal["2.0"]
    message_id: Id
    correlation_id: Id
    sent_at: Timestamp
    message_type: Literal[
        "accepted",
        "in_progress",
        "information_requested",
        "plan_approval_requested",
        "completed",
        "failed",
        "cancelled",
    ]
    message: RequiredText
    tenant_id: Id
    workspace_id: Id
    team_id: Id
    ticket_code: Id
    supervisor_run_id: Id
    result: SupervisorWorkResult | None = None
    error: SupervisorError | None = None

    @model_validator(mode="after")
    def completion_has_evidence(self):
        if self.message_type == "completed" and (
            self.result is None or self.result.outcome != "work_completed"
        ):
            raise ValueError("COMPLETION_RESULT_REQUIRED")
        return self


class SupervisorEvent(ContractModel):
    event_id: Id
    aggregate_version: Revision
    binding_id: Id
    payload: SupervisorMessage


class WaitOutput(TicketRef):
    registered: Confirmed
    correlation_id: Id
    buffered_event: SupervisorEvent | None = None


class AppendOutput(ContractModel):
    ticket: Ticket
    delivered: bool
    scope_changed: bool
    linked_file_ids: FileIds


class InteractionOutput(ContractModel):
    ticket: Ticket
    status: Literal["accepted", "conflict", "expired"]
    linked_file_ids: FileIds


class CancellationOutput(ContractModel):
    ticket: Ticket
    status: Literal["accepted", "rejected", "review"]


class StatusOutput(ContractModel):
    ticket: Ticket
    status: Literal["draft", "in_progress", "resolved", "closed", "cancelled"]
    completion_confirmed: bool
    scope_changed: bool


class Citation(ContractModel):
    documentId: Id
    version: Id
    chunkId: Id


class ApprovedProcedure(ContractModel):
    approved: Confirmed
    eligible: Confirmed
    policy_version: Id
    version: Id
    expires_at: Timestamp
    steps: Annotated[list[RequiredText], Field(min_length=1, max_length=64)]
    stop_conditions: Annotated[list[RequiredText], Field(min_length=1, max_length=64)]
    retrievalRunId: Id
    citations: Annotated[list[Citation], Field(min_length=1, max_length=64)]


class SelfHelpUnavailable(ContractModel):
    status: Literal["unavailable", "revoked", "expired"]
    policy_version: Id


class SelfHelpOffered(ContractModel):
    status: Literal["offered"]
    policy_version: Id
    attempt_id: Id
    procedure: ApprovedProcedure


class SelfHelpAccepted(SelfHelpOffered):
    status: Literal["accepted"]
    consent_recorded: Confirmed
    consent_source_message_id: Id


class SelfHelpRecorded(ContractModel):
    status: Literal["succeeded", "declined", "failed", "stopped"]
    policy_version: Id
    attempt_id: Id
    recorded: Confirmed
    source_message_id: Id


SelfHelpOutput = (
    SelfHelpUnavailable | SelfHelpOffered | SelfHelpAccepted | SelfHelpRecorded
)


class EmergencyOutput(ContractModel):
    persisted: Confirmed
    enqueued: Confirmed
    operation_id: Id
    policy_version: Id
    ticket: Ticket | None = None


T = TypeVar("T")


class Success(ContractModel, Generic[T]):
    kind: Literal["success"]
    value: T


class Accepted(ContractModel):
    kind: Literal["accepted"]
    operationId: Id


class Failure(ContractModel):
    kind: Literal["failure"]
    code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,127}$")]
    retryable: bool
    outcome: Literal["unknown", "not_applied"]


# Untyped transport result. Named facade methods retain Success[Output] types.
ToolResult = Success | Accepted | Failure
