"""Internal, JSON-serializable checkpoint v1; not a backend wire schema."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator
from groupchat.models import Context, ContextItem, Id, Model, ParticipantSpec, RoomData, Text, TurnPolicy


class SupervisorError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SupervisorError(code)


class Cost(Model):
    amount: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    kind: Id = "estimate"


class ProposedPlan(Model):
    summary: Text
    steps: Annotated[list[Text], Field(min_length=1)]
    performer_role: Text
    expected_duration: Text
    conditions: Text
    cost: Cost | None
    result_refs: list[Id] = Field(default_factory=list)
    attachment_ids: list[Id] = Field(default_factory=list)

    def canonical_steps(self) -> list[str]:
        # DEV-3's existing request has no dedicated role/duration/conditions fields.
        # Preserve them verbatim in the approval content for BOTH stages.
        return [*self.steps, f"Vai trò: {self.performer_role}",
                f"Thời gian dự kiến: {self.expected_duration}", f"Điều kiện: {self.conditions}"]


class PlanVersion(Model):
    plan_id: Id
    version: Annotated[int, Field(ge=1)]
    proposal: ProposedPlan


class TaskSpec(Model):
    task_id: Id
    description: Text
    assignee_agent_version_id: Id
    dependencies: list[Id] = Field(default_factory=list)


class TaskMetadata(Model):
    plan_version: int
    dependencies: list[Id]


class OpenDecision(Model):
    kind: Literal["open"]
    agent_version_ids: Annotated[list[Id], Field(min_length=1)]


class AddDecision(Model):
    kind: Literal["add_agent"]
    agent_version_id: Id


class TasksDecision(Model):
    kind: Literal["tasks"]
    tasks: Annotated[list[TaskSpec], Field(min_length=1)]


class RunDecision(Model):
    kind: Literal["run"]
    task_id: Id
    agent_version_id: Id
    instruction: Text


class CompleteTaskDecision(Model):
    kind: Literal["complete_task"]
    task_id: Id
    result_refs: Annotated[list[Id], Field(min_length=1)]
    assessment: Text


class QuestionDecision(Model):
    kind: Literal["question", "supplement"]
    question: Text


class PlanDecision(Model):
    kind: Literal["plan"]
    plan: ProposedPlan


class SummaryDecision(Model):
    kind: Literal["summarize"]
    summary: Text
    evidence_file_ids: list[Id]


class PauseDecision(Model):
    kind: Literal["pause"]
    reason: Text


Decision = Annotated[OpenDecision | AddDecision | TasksDecision | RunDecision |
                     CompleteTaskDecision | QuestionDecision | PlanDecision | SummaryDecision | PauseDecision,
                     Field(discriminator="kind")]
DECISION = TypeAdapter(Decision)

Phase = Literal["planning", "waiting_information", "waiting_management",
                "waiting_resident_plan", "execution_ready", "executing",
                "waiting_result_validation", "waiting_completion",
                "waiting_backend_closure", "paused", "completed"]


class Approval(Model):
    approval_id: Id
    stage: Literal["management_plan", "resident_plan"]
    plan_id: Id
    plan_version: int
    expires_at: datetime
    decision: Literal["approve", "reject", "request_changes"] | None = None


class Question(Model):
    request_id: Id
    question_id: Id
    return_phase: Phase


class Action(Model):
    action_id: Id
    channel: Literal["room", "backend"]
    operation: Id
    wire: dict
    plan_version: int
    status: Literal["pending", "sending", "accepted", "unknown", "done", "failed"] = "pending"
    receipt: dict | None = None
    previous_action_id: Id | None = None


class SupervisorState(Model):
    checkpoint_version: Literal[1] = 1
    context: Context
    version: int = 0
    phase: Phase = "planning"
    groupchat_version_id: Id
    turn_policy: TurnPolicy
    room: RoomData | None = None  # read cache only; refresh before decisions
    facts: list[dict] = Field(default_factory=list)
    plans: list[PlanVersion] = Field(default_factory=list)
    revision: int = 1
    revision_reason: str | None = None
    needs_clarification: bool = False
    approvals: dict[str, Approval] = Field(default_factory=dict)
    question: Question | None = None
    assignment: dict | None = None
    result: dict | None = None
    result_history: list[dict] = Field(default_factory=list)
    assignment_history: list[dict] = Field(default_factory=list)
    completion: dict | None = None
    publication_draft: dict | None = None
    feedback: list[dict] = Field(default_factory=list)
    tasks: dict[str, TaskMetadata] = Field(default_factory=dict)
    task_drafts: list[TaskSpec] = Field(default_factory=list)
    context_drafts: list[ContextItem] = Field(default_factory=list)
    context_join_pending: Id | None = None
    context_fingerprints: dict[str, str] = Field(default_factory=dict)
    run_after_put: RunDecision | None = None
    terminal_results: dict[str, RoomData] = Field(default_factory=dict)
    action: Action | None = None
    journal: list[Action] = Field(default_factory=list)
    events: dict[str, str] = Field(default_factory=dict)
    aggregate_versions: dict[str, int] = Field(default_factory=dict)
    pause_reason: str | None = None
    resume_phase: Phase | None = None

    @property
    def plan(self) -> PlanVersion | None:
        return self.plans[-1] if self.plans and self.plans[-1].version == self.revision else None


class CatalogEntry(Model):
    participant: ParticipantSpec
    # Trusted ACL for NEW tasks. Empty is forbidden: DEV-2 empty means public.
    task_readers: Annotated[list[Id], Field(min_length=1)]


class Publication(Model):
    """Backend verified QC + authorized immutable publication, not model output."""
    result_id: Id
    result_version: int
    plan_id: Id
    plan_version: int
    summary: Text
    evidence_file_ids: list[Id]
    final_cost: Cost | None
    status: Id


class AuthorityView(Model):
    """Trusted current backend projection scoped to the exact checkpoint."""
    context: Context
    state_version: int
    catalog: dict[str, CatalogEntry] = Field(default_factory=dict)
    ticket_context: list[ContextItem] = Field(default_factory=list)
    plan_id: Id | None = None
    management_recipient: Id | None = None
    resident_recipient: Id | None = None
    approval_expires_at: datetime | None = None
    assignment_id: Id | None = None
    assignment_version: int = 1
    execution_allowed: bool = False
    publication: Publication | None = None
    closure_confirmed: bool = False
    # Backend decides whether a changed plan may proceed after earlier execution.
    revision_reconciled: bool = False

    @model_validator(mode="after")
    def catalog_pins(self):
        require(all(k == v.participant.agent_version_id for k, v in self.catalog.items()),
                "catalog_pin_mismatch")
        return self


class Reconciliation(Model):
    outcome: Literal["unknown", "not_applied", "receipt"]
    receipt: dict | None = None
