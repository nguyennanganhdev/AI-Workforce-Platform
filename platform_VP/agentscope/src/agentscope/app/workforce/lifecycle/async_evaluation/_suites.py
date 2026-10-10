"""Versioned deterministic lifecycle expectations, independent of Builder."""

from typing import Any, Dict, Literal, Tuple

from pydantic import Field, model_validator

from ...contracts import NextAction, WorkflowState, WorkforceModel
from ._validation import canonical_hash


class ExpectedTurn(WorkforceModel):
    cause: str
    workflow_state: WorkflowState
    next_action: NextAction
    llm_calls: int = Field(ge=0)
    side_effect_calls: int = Field(ge=0)
    tracking_records: int = Field(ge=0)
    approval_granted: bool = False
    provider_confirmed: bool = False


class LifecycleCase(WorkforceModel):
    case_id: str
    pattern: Literal["response_only", "interactive", "external_tracking"]
    turns: Tuple[ExpectedTurn, ...] = Field(min_length=1)


class LifecycleSuite(WorkforceModel):
    suite_version: str
    cases: Tuple[LifecycleCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases(self) -> "LifecycleSuite":
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("duplicate evaluation case")
        return self

    @property
    def suite_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))

    def runner_input(self, case: LifecycleCase) -> Dict[str, Any]:
        # Expectations are intentionally withheld from the runtime runner.
        return {
            "case_id": case.case_id,
            "pattern": case.pattern,
            "suite_version": self.suite_version,
            "stimuli": [{"cause": turn.cause} for turn in case.turns],
            "clock_mode": "fixed",
            "tool_mode": "mock",
            "audience_key": "ticket-A",
            "other_audience_key": "ticket-B",
        }


def lifecycle_suite() -> LifecycleSuite:
    def turn(
        cause: str,
        state: WorkflowState,
        action: NextAction,
        llm: int = 1,
        effects: int = 0,
        tracking: int = 0,
        approval: bool = False,
        confirmed: bool = False,
    ) -> ExpectedTurn:
        return ExpectedTurn(
            cause=cause,
            workflow_state=state,
            next_action=action,
            llm_calls=llm,
            side_effect_calls=effects,
            tracking_records=tracking,
            approval_granted=approval,
            provider_confirmed=confirmed,
        )

    closed = turn("close", WorkflowState.CLOSED, NextAction.NONE, llm=0)
    waiting = WorkflowState.WAITING_EXTERNAL_EVENT
    watch = NextAction.WATCH_EVENTS
    return LifecycleSuite(
        suite_version="pta-lifecycle-1",
        cases=(
            LifecycleCase(
                case_id="response-only",
                pattern="response_only",
                turns=(turn("request", WorkflowState.CLOSED, NextAction.NONE),),
            ),
            LifecycleCase(
                case_id="interactive-booking",
                pattern="interactive",
                turns=(
                    turn("plan", WorkflowState.AWAITING_USER, NextAction.SUBMIT_REPLY),
                    turn(
                        "selection",
                        WorkflowState.AWAITING_APPROVAL,
                        NextAction.SUBMIT_APPROVAL,
                    ),
                    turn(
                        "approval",
                        WorkflowState.AWAITING_CONFIRMATION,
                        NextAction.CONFIRM_CLOSE,
                        effects=1,
                        approval=True,
                        confirmed=True,
                    ),
                    closed,
                ),
            ),
            LifecycleCase(
                case_id="external-events",
                pattern="external_tracking",
                turns=(
                    turn(
                        "create-pending",
                        waiting,
                        watch,
                        effects=1,
                        tracking=1,
                        approval=True,
                    ),
                    turn("idle-before-timer", waiting, watch, llm=0, tracking=1),
                    turn("assigned-v1", waiting, watch, tracking=1),
                    turn("on-the-way-v2", waiting, watch, tracking=1),
                    turn("duplicate-v2", waiting, watch, llm=0, tracking=1),
                    turn("arrived-v3", waiting, watch, tracking=1),
                    turn(
                        "completed-v4",
                        WorkflowState.AWAITING_CONFIRMATION,
                        NextAction.CONFIRM_CLOSE,
                        tracking=1,
                        confirmed=True,
                    ),
                    turn(
                        "late-v2",
                        WorkflowState.AWAITING_CONFIRMATION,
                        NextAction.CONFIRM_CLOSE,
                        llm=0,
                        tracking=1,
                        confirmed=True,
                    ),
                    closed,
                ),
            ),
            LifecycleCase(
                case_id="unknown-reconciliation",
                pattern="external_tracking",
                turns=(
                    turn(
                        "create-timeout",
                        WorkflowState.NEEDS_ATTENTION,
                        NextAction.RESOLVE_ATTENTION,
                        effects=1,
                        tracking=1,
                        approval=True,
                    ),
                    turn(
                        "idle-before-timer",
                        WorkflowState.NEEDS_ATTENTION,
                        NextAction.RESOLVE_ATTENTION,
                        llm=0,
                        tracking=1,
                    ),
                    turn("timer-query-pending", waiting, watch, llm=0, tracking=1),
                    turn(
                        "completed",
                        WorkflowState.AWAITING_CONFIRMATION,
                        NextAction.CONFIRM_CLOSE,
                        tracking=1,
                        confirmed=True,
                    ),
                    closed,
                ),
            ),
            LifecycleCase(
                case_id="audience-isolation",
                pattern="external_tracking",
                turns=(
                    turn(
                        "create-pending",
                        waiting,
                        watch,
                        effects=1,
                        tracking=1,
                        approval=True,
                    ),
                    turn("ticket-B-event", waiting, watch, llm=0, tracking=1),
                    turn("ticket-B-approval", waiting, watch, llm=0, tracking=1),
                ),
            ),
        ),
    )
