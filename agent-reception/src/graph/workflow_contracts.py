"""Consumer Python interfaces. DD/PH own backend bindings and runtime implementations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, NotRequired, Protocol, TypedDict

WORKFLOW_VERSION = "pd-workflow-python-2"


class VerifiedContext(TypedDict):
    principalId: str
    tenantId: str
    initiatedBy: str
    bindingId: str
    checkpoint: dict[str, str]
    runId: str
    requestId: str
    permissions: list[str]


class Ticket(TypedDict):
    ticket_id: str
    ticket_code: str
    ticket_generation: int
    ticket_version: str
    aggregate_version: int
    created_at: str


class ResidentProfile(TypedDict):
    resident_id: str
    resident_name: str
    phone_number: str
    unit_id: str
    unit_number: str
    building_id: str
    building_code: str
    building_name: str
    domain_id: str
    domain_name: str
    location_scope_id: str


class IncidentFact(TypedDict):
    key: str
    value: str | int | float | bool | None
    source: Literal["customer_report", "staff_verified", "agent_inference"]
    source_message_id: str


class Incident(TypedDict):
    title: str
    description: str
    facts: list[IncidentFact]
    file_ids: list[str]


class Triage(TypedDict):
    status: Literal["applied"]
    policy_version: str
    triage_decision_id: str
    request_kind: Literal["incident", "service_request"]
    priority: Literal["low", "normal", "high", "critical"]
    severity: Literal[
        "unknown", "minor", "moderate", "major", "critical", "not_applicable"
    ]
    is_emergency: bool


class Route(TypedDict):
    destination_id: str
    workspace_id: str
    team_id: str
    route_revision: int
    coordination_binding_id: str
    building_id: str
    domain_id: str
    ticket_version: str


class ToolPort(Protocol):
    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]: ...


class AsyncModel(Protocol):
    async def ainvoke(self, messages: list[Any]) -> Any: ...


class IntakePort(Protocol):
    async def evaluate_policy(self, request: dict) -> dict: ...
    async def search_knowledge(self, request: dict) -> dict: ...


class RequestPolicyPort(Protocol):
    """Authorized policy preflight and recheck with validated LLM proposal."""

    async def evaluate_request(self, request: dict) -> dict: ...


@dataclass(frozen=True)
class GraphDependencies:
    model: AsyncModel
    tools: ToolPort
    checkpointer: (
        Any  # LangGraph BaseCheckpointSaver; injected, never a default RAM saver.
    )


@dataclass(frozen=True)
class WorkflowOptions:
    intake: IntakePort
    resolve_session: Callable[[dict, Any], Awaitable[dict]]
    reconcile: Callable[[dict], Awaitable[dict]] | None = None
    now: Callable[[], str] | None = None
    timeout_ms: int = 10000
    max_question_attempts: int = 4
    request_policy: RequestPolicyPort | None = None


OPERATIONS = (
    "create_ticket_draft",
    "get_verified_resident_context",
    "update_ticket_incident",
    "submit_ticket_assessment",
    "resolve_management_destination",
    "handoff_ticket",
    "register_supervisor_wait",
    "get_supervisor_event",
    "append_ticket_information",
    "respond_supervisor_interaction",
    "request_ticket_cancellation",
    "get_ticket_status",
    "process_self_help",
    "escalate_emergency",
)

HandoffReason = Literal[
    "needs_staff", "self_help_declined", "self_help_failed", "emergency"
]
WorkflowOperation = Literal[
    "create_ticket_draft",
    "get_verified_resident_context",
    "update_ticket_incident",
    "submit_ticket_assessment",
    "resolve_management_destination",
    "handoff_ticket",
    "register_supervisor_wait",
    "get_supervisor_event",
    "append_ticket_information",
    "respond_supervisor_interaction",
    "request_ticket_cancellation",
    "get_ticket_status",
    "process_self_help",
    "escalate_emergency",
]


class ResidentMessage(TypedDict):
    id: str
    text: str
    fileIds: NotRequired[list[str]]


class ResumeEvent(TypedDict):
    eventId: str
    aggregateVersion: int
    ticketId: NotRequired[str]
    generation: int
    bindingId: str
    interruptId: str


class RequestedQuestion(TypedDict):
    field_id: str
    question: str
    required: bool


class RequestedInformation(TypedDict):
    interaction_id: str
    questions: list[RequestedQuestion]


class SupervisorResult(TypedDict):
    schema_version: Literal["1.0"]
    message_id: str
    correlation_id: str
    sent_at: str
    tenant_id: str
    workspace_id: str
    team_id: str
    ticket_id: str
    ticket_code: str
    ticket_generation: int
    ticket_version: str
    supervisor_run_id: str
    status: Literal[
        "accepted", "in_progress", "waiting_for_customer", "completed", "failed"
    ]
    customer_message: str
    requested_information: NotRequired[RequestedInformation]
    result: NotRequired[dict[str, Any]]
    error: NotRequired[dict[str, Any]]


class SupervisorEvent(TypedDict):
    event_id: str
    aggregate_version: int
    binding_id: str
    interaction_revision: NotRequired[int]
    payload: SupervisorResult


class Ack(TypedDict):
    persisted: Literal[True]
    enqueued: Literal[True]
    correlation_id: str
    operation_id: str


class TicketInput(TypedDict):
    ticket_id: str
    ticket_generation: int
    ticket_version: str


class DraftInput(TypedDict):
    channel_id: str
    handoff_reason: HandoffReason


class ProfileInput(TicketInput):
    resident_response: ResidentMessage


class IncidentInput(TicketInput):
    incident: Incident


class AssessmentInput(TicketInput):
    facts: list[IncidentFact]


class HandoffInput(TicketInput):
    destination_id: str
    route_revision: int
    message: dict[str, Any]  # Exact schema-v1 projection is validated by build_handoff.


class WaitInput(TicketInput):
    correlation_id: str
    workspace_id: str
    team_id: str
    coordination_binding_id: str


class EventInput(TypedDict):
    event: ResumeEvent


class AppendInput(TicketInput):
    source_message_id: str
    message: str
    facts: list[IncidentFact]
    file_ids: list[str]


class InteractionInput(TicketInput):
    interaction_id: str
    interaction_revision: int
    source_message_id: str
    answers: dict[str, str]


class CancellationInput(TicketInput):
    reason: str
    source_message_id: str


class RequestAssessment(TypedDict):
    intent: Literal["information", "incident", "service_request", "ticket_follow_up"]
    proposed_action: str
    explicit_staff_request: bool
    self_help_declined: bool
    self_help_failed: bool
    emergency_signals: list[str]
    missing_information: list[str]
    reason: str


class ReceptionDecision(RequestAssessment):
    next_action: str  # Selected by deterministic code after policy/state guards.
    policy_version: str


class RequestPolicy(TypedDict):
    policy_version: str
    emergency: bool
    staff_required: bool
    self_help_allowed: bool
    missing_information: list[str]
    handoff_reason: HandoffReason
    safety_guidance: NotRequired[dict[str, Any]]


class SelfHelpInput(TypedDict):
    channel_id: str
    reception_session_id: str
    source_message: ResidentMessage
    policy_version: str
    assessment: ReceptionDecision
    attempt: dict[str, Any] | None


class EmergencyInput(TypedDict):
    channel_id: str
    reception_session_id: str
    source_message: ResidentMessage
    policy_version: str
    ticket_id: NotRequired[str]
    ticket_generation: NotRequired[int]
    ticket_version: NotRequired[str]


class PendingOperation(TypedDict):
    operation: WorkflowOperation
    input: dict[str, Any]
    idempotencyKey: str
    after: str


class ResidentTurn(TypedDict):
    intent: Literal[
        "information", "status", "cancel", "new_incident", "interaction_answer"
    ]
    title: NotRequired[str]
    description: NotRequired[str]
    facts: list[IncidentFact]
    answers: dict[str, str]


class WorkflowState(TypedDict):
    schemaVersion: Literal[1]
    workflow_version: str
    owner: dict[str, str]
    channel_id: str
    reception_session_id: str
    reception_binding_id: str
    phase: str
    next: str
    operation_id: str
    message: ResidentMessage
    active_ticket_id: NotRequired[str]
    ticket: NotRequired[Ticket]
    verified_profile: NotRequired[ResidentProfile | None]
    incident: NotRequired[Incident]
    triage: NotRequired[Triage | None]
    route: NotRequired[Route | None]
    ack: NotRequired[Ack | None]
    intake: NotRequired[dict[str, Any]]
    handoff_reason: HandoffReason
    pending: NotRequired[PendingOperation | None]
    turn: NotRequired[ResidentTurn | None]
    wait_registered: bool
    wait_kind: NotRequired[str]
    questions: list[str]
    asked_questions: list[str]
    question_attempts: int
    pending_interaction: NotRequired[dict[str, Any] | None]
    processed_event_ids: list[str]
    last_event_version: int
    event: NotRequired[ResumeEvent | None]
    completed_operations: list[str]
    last_error: NotRequired[str | None]
    reply: str
    decision: NotRequired[ReceptionDecision | None]
    request_policy: NotRequired[RequestPolicy]
    conversation_history: NotRequired[list[dict[str, Any]]]
    self_help: NotRequired[dict[str, Any] | None]


# Semantic operation inputs, not a backend registration or HTTP route catalog.
OPERATION_INPUTS = dict(
    zip(
        OPERATIONS,
        (
            DraftInput,
            ProfileInput,
            IncidentInput,
            AssessmentInput,
            TicketInput,
            HandoffInput,
            WaitInput,
            EventInput,
            AppendInput,
            InteractionInput,
            CancellationInput,
            TicketInput,
            SelfHelpInput,
            EmergencyInput,
        ),
    )
)
