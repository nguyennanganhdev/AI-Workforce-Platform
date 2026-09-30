"""Wire contracts for DEV-1 dispatcher.

Every TypedDict here is a data transfer boundary.  DEV-3 produces
TicketReport, DEV-1 produces DispatcherDecision, DEV-2 consumes both.

Severity/role/purpose enums are kept as Literal unions so that they
stay aligned with the DB schema CHECK constraints defined in:
  - server/src/db/schema/domains/vinhomes/sla.ts
  - server/src/db/schema/platform/collaboration.ts
"""

from __future__ import annotations

from typing import Literal, TypedDict

from contracts.runtime import JsonValue


# ---------------------------------------------------------------------------
# Enums kept as Literal unions — mirrors DB CHECK constraints exactly.
# ---------------------------------------------------------------------------

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Urgency = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Complexity = Literal["SIMPLE", "MODERATE", "COMPLEX"]
ParticipantRole = Literal["COORDINATOR", "SPECIALIST", "REVIEWER"]
SessionPurpose = Literal["TRIAGE", "PLAN", "FOLLOW_UP", "QC", "REPLAN"]
ClassificationMethod = Literal["LLM", "ML", "RULE", "HYBRID"]
TurnStrategy = Literal["ROUND_ROBIN", "COORDINATOR_LED", "ON_DEMAND"]
MessageKind = Literal["REQUEST", "FINDING", "PROPOSAL", "DECISION", "SYSTEM"]


# ---------------------------------------------------------------------------
# DEV-3 → DEV-1  (input)
# ---------------------------------------------------------------------------

class AttachmentRef(TypedDict):
    id: str
    media_type: str
    file_object_id: str


class IncidentContext(TypedDict):
    id: str
    project_id: str
    category: str
    severity: Severity | None  # May be pre-set by reception or None
    status: str
    location_type: str


class ReportContext(TypedDict):
    text: str
    facts: dict[str, JsonValue]
    attachments: list[AttachmentRef]
    resident_mentioned_agents: list[str] | None


class DomainSubjectRefPy(TypedDict):
    namespace: str
    subject_type: str
    subject_id: str


class SlaPolicyRef(TypedDict):
    policy_id: str
    code: str
    category: str
    severity: Severity
    response_minutes: int
    resolution_minutes: int
    clock_type: str  # Currently always "ELAPSED"


class EligibleAgentRef(TypedDict):
    agent_id: str
    agent_version_id: str
    role: ParticipantRole
    capabilities: list[str]
    status: str  # Must be PUBLISHED + deployment ACTIVE


class TicketReport(TypedDict):
    """What DEV-1 receives from DEV-3 (Core API / Reception gateway)."""

    version: int
    ticket_id: str          # Maps to vh_incident.id
    tenant_id: str
    correlation_id: str
    trace_id: str

    incident: IncidentContext
    report: ReportContext
    sla_policies: list[SlaPolicyRef]
    eligible_agents: list[EligibleAgentRef]
    subject: DomainSubjectRefPy


# ---------------------------------------------------------------------------
# DEV-1 → DEV-2  (output)
# ---------------------------------------------------------------------------

class TicketClassification(TypedDict):
    category: str
    severity: Severity
    urgency: Urgency
    complexity: Complexity
    confidence: float
    method: ClassificationMethod


class SelectedAgent(TypedDict):
    agent_version_id: str
    role: ParticipantRole
    capability_scope: dict[str, JsonValue]
    selection_reason: str


class TurnPolicy(TypedDict):
    """Maps to platform_session_control fields."""

    purpose: SessionPurpose
    max_turns: int
    max_tool_calls: int
    speaker_order: list[str]   # agent_version_ids in order
    strategy: TurnStrategy
    allow_resident_agent_request: bool


class SlaBind(TypedDict):
    policy_id: str
    severity: Severity
    response_minutes: int
    resolution_minutes: int
    started_at: str  # ISO 8601


class PredictionSignals(TypedDict):
    """Advisory ML predictions — NOT decisions."""

    predicted_urgency: Urgency | None
    urgency_confidence: float | None
    predicted_resolution_hours: float | None
    resolution_confidence: float | None
    predicted_complexity: Complexity | None
    sla_breach_risk: float | None  # 0.0–1.0 probability
    model_version: str | None


class DecisionReasoning(TypedDict):
    classification_evidence: list[str]
    agent_selection_evidence: list[str]
    sla_match_evidence: list[str]
    warnings: list[str]


class DispatcherDecision(TypedDict):
    """What DEV-1 returns to DEV-2 (Agent Team Service)."""

    version: int
    decision_id: str
    ticket_id: str
    correlation_id: str

    classification: TicketClassification
    selected_agents: list[SelectedAgent]
    turn_policy: TurnPolicy
    sla: SlaBind
    prediction_signals: PredictionSignals | None

    requires_approval: bool
    approval_reason: str | None
    reasoning: DecisionReasoning


# ---------------------------------------------------------------------------
# DEV-1 ↔ DEV-2  (turn-by-turn orchestration)
# ---------------------------------------------------------------------------

class NextSpeakerDecision(TypedDict):
    """DEV-1 tells DEV-2 who speaks next."""

    participant_id: str
    agent_version_id: str
    task_input: dict[str, JsonValue]
    reason: str
    remaining_turns: int
    should_checkpoint: bool


class TurnResult(TypedDict):
    """DEV-2 reports back to DEV-1 after a turn."""

    session_id: str
    participant_id: str
    message_kind: MessageKind
    has_action_proposal: bool
    turn_number: int
    total_tool_calls: int


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class DispatcherError(TypedDict):
    error_code: str
    message: str
    ticket_id: str
    correlation_id: str
    recoverable: bool
    fallback_action: str | None
