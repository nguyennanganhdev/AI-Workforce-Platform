"""Internal, JSON-serializable checkpoint v1; not a backend wire schema."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Dict, List, Literal, Optional, Union

from groupchat.reception import ReceptionError, ReceptionMessage, ReceptionResult

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
    steps: Annotated[List[Text], Field(min_length=1)]
    performer_role: Text
    expected_duration: Text
    conditions: Text
    cost: Optional[Cost]
    result_refs: List[Id] = Field(default_factory=list)
    attachment_ids: List[Id] = Field(default_factory=list)

    def canonical_steps(self) -> List[str]:
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
    dependencies: List[Id] = Field(default_factory=list)


class TaskMetadata(Model):
    plan_version: int
    dependencies: List[Id]


class OpenDecision(Model):
    kind: Literal["open"]
    agent_version_ids: Annotated[List[Id], Field(min_length=1)]


class AddDecision(Model):
    kind: Literal["add_agent"]
    agent_version_id: Id


class TasksDecision(Model):
    kind: Literal["tasks"]
    tasks: Annotated[List[TaskSpec], Field(min_length=1)]


class RunDecision(Model):
    kind: Literal["run"]
    task_id: Id
    agent_version_id: Id
    instruction: Text


class CompleteTaskDecision(Model):
    kind: Literal["complete_task"]
    task_id: Id
    result_refs: Annotated[List[Id], Field(min_length=1)]
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
    evidence_file_ids: List[Id]


class PauseDecision(Model):
    kind: Literal["pause"]
    reason: Text


Decision = Annotated[
    Union[
        OpenDecision,
        AddDecision,
        TasksDecision,
        RunDecision,
        CompleteTaskDecision,
        QuestionDecision,
        PlanDecision,
        SummaryDecision,
        PauseDecision,
    ],
    Field(discriminator="kind"),
]
DECISION = TypeAdapter(Decision)

Phase = Literal["planning", "waiting_information", "waiting_management",
                "waiting_resident_plan", "execution_ready", "executing",
                "waiting_result_validation", "waiting_completion",
                "waiting_backend_closure", "waiting_cancellation", "paused", "completed", "cancelled", "failed"]


class Approval(Model):
    approval_id: Id
    stage: Literal["management_plan", "resident_plan"]
    plan_id: Id
    plan_version: int
    expires_at: datetime
    decision: Optional[Literal["approve", "reject", "request_changes"]] = None


class Question(Model):
    request_id: Id
    question_id: Id
    return_phase: Phase


class Action(Model):
    action_id: Id
    channel: Literal["room", "backend", "reception"]
    operation: Id
    wire: Dict
    plan_version: int
    status: Literal["pending", "sending", "accepted", "unknown", "done", "failed"] = "pending"
    receipt: Optional[Dict] = None
    previous_action_id: Optional[Id] = None


class SupervisorState(Model):
    checkpoint_version: Literal[1] = 1
    reception: Optional[ReceptionMessage] = None
    ticket_version: Optional[Id] = None
    supervisor_run_id: Optional[Id] = None
    pending_resident: Optional[Literal["information_requested", "plan_approval_requested"]] = None
    pending_ticket_version: Optional[Id] = None
    resident_approval_required: bool = True
    cancellation_return_phase: Optional[Phase] = None
    reception_events: Dict[str, str] = Field(default_factory=dict)
    resident_decisions: Dict[str, str] = Field(default_factory=dict)
    context: Context
    version: int = 0
    phase: Phase = "planning"
    groupchat_version_id: Id
    turn_policy: TurnPolicy
    room: Optional[RoomData] = None  # read cache only; refresh before decisions
    facts: List[Dict] = Field(default_factory=list)
    plans: List[PlanVersion] = Field(default_factory=list)
    revision: int = 1
    revision_reason: Optional[str] = None
    needs_clarification: bool = False
    approvals: Dict[str, Approval] = Field(default_factory=dict)
    question: Optional[Question] = None
    assignment: Optional[Dict] = None
    result: Optional[Dict] = None
    result_history: List[Dict] = Field(default_factory=list)
    assignment_history: List[Dict] = Field(default_factory=list)
    completion: Optional[Dict] = None
    publication_draft: Optional[Dict] = None
    question_draft: Optional[Text] = None
    feedback: List[Dict] = Field(default_factory=list)
    tasks: Dict[str, TaskMetadata] = Field(default_factory=dict)
    task_drafts: List[TaskSpec] = Field(default_factory=list)
    context_drafts: List[ContextItem] = Field(default_factory=list)
    context_join_pending: Optional[Id] = None
    context_fingerprints: Dict[str, str] = Field(default_factory=dict)
    run_after_put: Optional[RunDecision] = None
    terminal_results: Dict[str, RoomData] = Field(default_factory=dict)
    action: Optional[Action] = None
    journal: List[Action] = Field(default_factory=list)
    events: Dict[str, str] = Field(default_factory=dict)
    aggregate_versions: Dict[str, int] = Field(default_factory=dict)
    pause_reason: Optional[str] = None
    resume_phase: Optional[Phase] = None

    @property
    def plan(self) -> Optional[PlanVersion]:
        return self.plans[-1] if self.plans and self.plans[-1].version == self.revision else None


class CatalogEntry(Model):
    participant: ParticipantSpec
    # Trusted ACL for NEW tasks. Empty is forbidden: DEV-2 empty means public.
    task_readers: Annotated[List[Id], Field(min_length=1)]


class Publication(Model):
    """Backend verified QC + authorized immutable publication, not model output."""
    result_id: Id
    result_version: int
    plan_id: Id
    plan_version: int
    summary: Text
    evidence_file_ids: List[Id]
    final_cost: Optional[Cost]
    status: Id


class AuthorityView(Model):
    """Trusted current backend projection scoped to the exact checkpoint."""
    context: Context
    state_version: int
    catalog: Dict[str, CatalogEntry] = Field(default_factory=dict)
    ticket_context: List[ContextItem] = Field(default_factory=list)
    plan_id: Optional[Id] = None
    management_recipient: Optional[Id] = None
    resident_recipient: Optional[Id] = None
    approval_expires_at: Optional[datetime] = None
    assignment_id: Optional[Id] = None
    assignment_version: int = 1
    execution_allowed: bool = False
    publication: Optional[Publication] = None
    closure_confirmed: bool = False
    # Backend decides whether a changed plan may proceed after earlier execution.
    revision_reconciled: bool = False
    # V2 fields come from backend; no inference from resident/model text.
    ticket_version: Optional[Id] = None
    resident_approval_required: Optional[bool] = None
    resident_request_message: Optional[Text] = None
    resident_request_type: Optional[Literal["information_requested", "plan_approval_requested"]] = None
    reception_readers: List[Id] = Field(default_factory=list)
    cancellation_confirmed: Optional[bool] = None
    cancellation_message: Optional[Text] = None
    failure_message: Optional[Text] = None
    failure_result: Optional[ReceptionResult] = None
    failure_error: Optional[ReceptionError] = None
    all_work_completed: bool = False
    work_order_ids: List[Id] = Field(default_factory=list)

    @model_validator(mode="after")
    def catalog_pins(self):
        require(all(k == v.participant.agent_version_id for k, v in self.catalog.items()),
                "catalog_pin_mismatch")
        return self


class Reconciliation(Model):
    outcome: Literal["unknown", "not_applied", "receipt"]
    receipt: Optional[Dict] = None


class VerifiedReception(Model):
    """Trusted backend resolution returned by ReceptionPort, never user JSON."""
    context: Context
    message: ReceptionMessage
    supervisor_run_id: Id
