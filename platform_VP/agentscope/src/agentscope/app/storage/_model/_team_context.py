"""Durable, ticket-scoped shared context for an agent team."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ...._utils._common import _generate_id
from ._base import _RecordBase

ContextMode = Literal["task", "references", "isolated"]
ContextResultScope = Literal["caller", "shared"]
HandoffDeliveryStatus = Literal[
    "pending",
    "delivered",
    "consumed",
    "failed",
    "cancelled",
]
SharedTaskStatus = Literal[
    "queued",
    "running",
    "blocked",
    "waiting_user",
    "waiting_approval",
    "waiting_external",
    "completed",
    "failed",
    "cancelled",
]


class SharedContextEvent(BaseModel):
    """One immutable, shareable fact in a team's event history."""

    id: str = Field(default_factory=_generate_id, min_length=1, max_length=255)
    revision: int = Field(ge=1)
    task_id: str = Field(min_length=1, max_length=255)
    kind: Literal[
        "customer_message",
        "customer_reply",
        "handoff",
        "question",
        "answer",
        "result",
        "progress",
        "requires_user_input",
        "user_input_proposal",
        "conflict",
        "error",
        "external_event",
        "context_update",
    ]
    content: str = Field(min_length=1, max_length=100_000)
    source_message_id: str | None = Field(default=None, max_length=255)
    source_agent_id: str | None = Field(default=None, max_length=255)
    source_session_id: str | None = Field(default=None, max_length=255)
    thread_id: str | None = Field(default=None, max_length=255)
    in_reply_to: str | None = Field(default=None, max_length=255)
    based_on_revision: int | None = Field(default=None, ge=0)
    source_workflow_revision: int | None = Field(default=None, ge=1)
    stale: bool = False
    artifact_refs: tuple[str, ...] = Field(default=(), max_length=50)
    hop_count: int = Field(default=1, ge=1, le=12)
    reference_event_ids: tuple[str, ...] = Field(default=(), max_length=50)
    payload_hash: str | None = Field(default=None, min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SharedContextItem(BaseModel):
    """Current structured state; summaries never become its authority."""

    id: str = Field(default_factory=_generate_id, min_length=1, max_length=255)
    task_id: str | None = Field(default=None, max_length=255)
    kind: Literal["constraint", "fact", "decision", "output"]
    text: str = Field(min_length=1, max_length=100_000)
    authority: Literal[
        "customer_confirmed",
        "tool_verified",
        "agent_reported",
        "system_event",
    ]
    source_event_ids: tuple[str, ...] = Field(min_length=1, max_length=50)
    status: Literal["active", "superseded", "rejected"] = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


AssignmentStatus = Literal[
    "queued",
    "assigned",
    "reported",
    "verified",
    "accepted",
    "challenged",
    "stopped",
    "failed",
]


class TaskAssignment(BaseModel):
    """One entry of the Leader's task ledger, owned by the runtime.

    The Leader writes the brief once (goal, expected output, done_when and
    dependencies). The runtime then tracks the status from the members'
    reports and the Leader's review decisions, and releases a queued
    assignment when every dependency has reported. Models never have to
    remember routing ids to keep this ledger correct.
    """

    agent_id: str = Field(default="", max_length=255)
    agent_name: str = Field(default="", max_length=255)
    goal: str = Field(min_length=1, max_length=20_000)
    expected_output: str = Field(default="", max_length=4_000)
    done_when: str = Field(default="", max_length=4_000)
    depends_on: tuple[str, ...] = Field(default=(), max_length=20)
    """Session ids of the assignments that must report first."""
    status: AssignmentStatus = "assigned"
    challenges: int = Field(default=0, ge=0)
    last_report_event_id: str | None = Field(default=None, max_length=255)
    last_feedback: str = Field(default="", max_length=4_000)
    pending_payload: dict[str, Any] | None = None
    """Inbox payload held back until dependencies report (never in packets)."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SharedTaskState(BaseModel):
    """Durable lifecycle of one logical task inside a ticket/group."""

    id: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1, max_length=20_000)
    status: SharedTaskStatus = "running"
    owner_agent_id: str | None = Field(default=None, max_length=255)
    reply_owner_agent_id: str | None = Field(default=None, max_length=255)
    thread_id: str | None = Field(default=None, max_length=255)
    latest_customer_revision: int = Field(default=0, ge=0)
    latest_workflow_revision: int = Field(default=0, ge=0)
    pending_question_ids: tuple[str, ...] = Field(default=(), max_length=20)
    pending_operation_ids: tuple[str, ...] = Field(default=(), max_length=50)
    collaboration: dict[str, "CollaborationBranch"] = Field(default_factory=dict)
    assignments: dict[str, TaskAssignment] = Field(default_factory=dict)
    """The Leader's task ledger keyed by the member's team session id."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CollaborationBranch(BaseModel):
    """Server-owned limits and dependencies for one assigned session/task epoch."""

    customer_revision: int = 0
    status: Literal["running", "waiting_peer", "review", "completed", "stopped"] = (
        "running"
    )
    reason: str = ""
    waiting_for: dict[str, str] = Field(default_factory=dict)
    evidence_event_ids: tuple[str, ...] = Field(default=(), max_length=100)
    """Current peer reports that satisfied this branch's dependencies.

    The runtime owns this lineage. It lets a coordinating worker publish a
    synthesis backed by peer evidence without relying on the model to copy
    opaque event IDs into its next ``TeamSay`` call.
    """
    exchanges: int = 0
    model_calls: int = 0
    measured_tokens: int = 0
    active_seconds: float = 0
    verifications: int = 0
    evidence_rejections: int = 0
    signatures: dict[str, int] = Field(default_factory=dict)
    receipts: dict[str, dict] = Field(default_factory=dict)


class SharedContextSummary(BaseModel):
    """Measured summary of old shared events, never business truth itself."""

    id: str = Field(default_factory=_generate_id, min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=50_000)
    source_event_ids: tuple[str, ...] = Field(min_length=1)
    covered_through_revision: int = Field(ge=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProviderUsage(BaseModel):
    """Provider-reported usage for one agent in a team (billing-shaped).

    Unlike the counters below, these numbers come from the provider's
    ``usage`` block, so ``cached_input_tokens`` shows how much of the prompt
    was served from the provider's prompt cache.
    """

    agent_name: str = Field(default="", max_length=255)
    model: str = Field(default="", max_length=255)
    calls: int = Field(default=0, ge=0)
    calls_with_usage: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class SharedContextMetrics(BaseModel):
    """Auditable measurements from the selected model's token counter."""

    provider_usage: dict[str, ProviderUsage] = Field(default_factory=dict)
    """Provider usage keyed by agent id."""

    packets_built: int = Field(default=0, ge=0)
    compactions: int = Field(default=0, ge=0)
    compaction_failures: int = Field(default=0, ge=0)
    last_packet_tokens: int = Field(default=0, ge=0)
    peak_packet_tokens: int = Field(default=0, ge=0)
    last_required_state_tokens: int = Field(default=0, ge=0)
    last_packet_source_events: int = Field(default=0, ge=0)
    last_packet_included_events: int = Field(default=0, ge=0)
    last_packet_dropped_events: int = Field(default=0, ge=0)
    total_packet_dropped_events: int = Field(default=0, ge=0)
    packet_budget_failures: int = Field(default=0, ge=0)
    last_history_tokens: int = Field(default=0, ge=0)
    peak_history_tokens: int = Field(default=0, ge=0)
    last_summary_input_tokens: int = Field(default=0, ge=0)
    last_summary_output_tokens: int = Field(default=0, ge=0)
    last_summary_attempts: int = Field(default=0, ge=0)
    summary_model_calls: int = Field(default=0, ge=0)
    model_calls_measured: int = Field(default=0, ge=0)
    last_total_prompt_tokens: int = Field(default=0, ge=0)
    total_measured_prompt_tokens: int = Field(default=0, ge=0)
    last_tool_schema_tokens: int = Field(default=0, ge=0)
    last_system_prompt_tokens: int = Field(default=0, ge=0)
    last_conversation_tokens: int = Field(default=0, ge=0)
    peak_total_prompt_tokens: int = Field(default=0, ge=0)
    last_model_context_size: int = Field(default=0, ge=0)
    last_reserved_output_tokens: int = Field(default=0, ge=0)
    last_preflight_margin_tokens: int = Field(default=0, ge=0)
    prompt_budget_failures: int = Field(default=0, ge=0)
    bootstrap_events: int = Field(default=0, ge=0)
    last_token_counter: str = Field(default="unknown", max_length=255)


class TeamSharedContextState(BaseModel):
    """One source of shared truth for a team/ticket."""

    revision: int = Field(default=0, ge=0)
    active_task_id: str | None = Field(default=None, max_length=255)
    tasks: dict[str, SharedTaskState] = Field(default_factory=dict)
    items: list[SharedContextItem] = Field(default_factory=list)
    events: list[SharedContextEvent] = Field(default_factory=list)
    summaries: dict[str, SharedContextSummary] = Field(default_factory=dict)
    customer_history_bootstrapped: bool = False
    metrics: SharedContextMetrics = Field(default_factory=SharedContextMetrics)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_summary(cls, value: object) -> object:
        """Load records written before summaries became task-scoped."""

        if not isinstance(value, dict):
            return value
        data = dict(value)
        legacy = data.pop("summary", None)
        task_id = data.get("active_task_id")
        if legacy is not None and task_id and not data.get("summaries"):
            data["summaries"] = {task_id: legacy}
        return data

    @model_validator(mode="after")
    def _active_task_exists(self) -> "TeamSharedContextState":
        if self.active_task_id is not None and self.active_task_id not in self.tasks:
            raise ValueError("active_task_id must reference an existing task")
        return self


class TeamSharedContextRecord(_RecordBase):
    """Storage record isolated from roster updates on :class:`TeamRecord`."""

    user_id: str
    team_id: str
    tenant_id: str | None = Field(default=None, max_length=255)
    domain_id: str | None = Field(default=None, max_length=255)
    area_id: str | None = Field(default=None, max_length=255)
    manager_account_id: str | None = Field(default=None, max_length=255)
    workflow_id: str | None = Field(default=None, max_length=255)
    state: TeamSharedContextState = Field(default_factory=TeamSharedContextState)


class TeamTurnRecord(_RecordBase):
    """Durable copy of reply ownership and the single pending question."""

    user_id: str
    team_id: str
    turn_id: str
    mode: Literal["leader", "direct_mention"] = "leader"
    reply_owner_session_id: str
    reply_owner_agent_id: str
    customer_session_id: str
    task_id: str | None = None
    status: Literal["running", "awaiting_user_input"] = "running"
    pending_question_ids: tuple[str, ...] = ()
    pending_question_keys: tuple[str, ...] = ()


class TeamHandoffRecord(_RecordBase):
    """One durable recipient delivery for an internal team handoff."""

    user_id: str
    team_id: str
    handoff_id: str
    task_id: str | None = None
    thread_id: str | None = None
    in_reply_to: str | None = None
    kind: Literal[
        "handoff",
        "question",
        "answer",
        "result",
        "progress",
        "requires_user_input",
        "user_input_proposal",
        "conflict",
        "error",
    ] = "result"
    source_agent_id: str
    source_session_id: str
    recipient_agent_id: str
    recipient_session_id: str
    context_mode: ContextMode = "task"
    result_scope: ContextResultScope = "shared"
    context_ref: str | None = Field(default=None, max_length=255)
    context_revision: int = Field(default=0, ge=0)
    reference_event_ids: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    hop_count: int = Field(default=1, ge=1, le=12)
    idempotency_key: str
    payload: dict[str, Any]
    delivery_status: HandoffDeliveryStatus = "pending"
    delivery_attempts: int = Field(default=0, ge=0)
    last_error: str | None = Field(default=None, max_length=4_000)
    delivered_at: datetime | None = None
    consumed_at: datetime | None = None
    tenant_id: str | None = None
    domain_id: str | None = None
    area_id: str | None = None
    manager_account_id: str | None = None
    workflow_id: str | None = None


class ContextDelta(BaseModel):
    """Validated, append-only state changes an agent may propose."""

    objective: str | None = Field(default=None, max_length=20_000)
    status: SharedTaskStatus | None = None
    add_constraints: tuple[str, ...] = Field(default=(), max_length=20)
    add_confirmed_facts: tuple[str, ...] = Field(default=(), max_length=20)
    add_decisions: tuple[str, ...] = Field(default=(), max_length=20)
    add_outputs: tuple[str, ...] = Field(default=(), max_length=20)
    supersede_item_ids: tuple[str, ...] = Field(default=(), max_length=50)
    add_pending_operation_ids: tuple[str, ...] = Field(
        default=(),
        max_length=50,
    )
    resolve_pending_operation_ids: tuple[str, ...] = Field(
        default=(),
        max_length=50,
    )


__all__ = [
    "ContextDelta",
    "ContextMode",
    "ContextResultScope",
    "HandoffDeliveryStatus",
    "SharedContextEvent",
    "SharedContextItem",
    "SharedContextMetrics",
    "SharedContextSummary",
    "SharedTaskState",
    "SharedTaskStatus",
    "TaskAssignment",
    "TeamHandoffRecord",
    "TeamSharedContextRecord",
    "TeamSharedContextState",
    "TeamTurnRecord",
]
