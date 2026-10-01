"""Pure transitions. Call only after current backend verification, on a copy."""
from datetime import datetime
from .models import PlanVersion, ProposedPlan, SupervisorState, require


def invalidate(state: SupervisorState, reason: str) -> None:
    state.revision = max([p.version for p in state.plans] + [state.revision]) + 1
    state.revision_reason = reason
    state.needs_clarification = not bool(reason.strip())
    state.approvals = {}
    state.completion = None
    state.publication_draft = None
    state.task_drafts = []
    state.run_after_put = None
    state.phase = "planning"
    # Preserve historical assignment/result; backend reconciles live work.


def propose(state: SupervisorState, proposal: ProposedPlan, plan_id: str) -> None:
    require(state.phase == "planning" and not state.needs_clarification, "plan_not_allowed")
    if state.plan:
        invalidate(state, "plan_changed")
    if state.plans:
        require(plan_id == state.plans[0].plan_id, "plan_identity_changed")
    state.plans.append(PlanVersion(plan_id=plan_id, version=state.revision,
                                   proposal=proposal.model_copy(deep=True)))
    state.approvals = {}


def execution_gate(state: SupervisorState) -> bool:
    plan = state.plan
    return bool(plan and all(
        (a := state.approvals.get(stage)) and a.decision == "approve"
        and a.plan_id == plan.plan_id and a.plan_version == plan.version
        for stage in ("management_plan", "resident_plan")
    ))


def approval_response(state: SupervisorState, p: dict, now: datetime) -> None:
    a = state.approvals.get(p["stage"])
    require(a is not None and state.plan is not None, "unexpected_approval")
    require((a.approval_id, a.plan_id, a.plan_version) ==
            (p["approval_id"], p["plan_id"], p["plan_version"]), "stale_approval")
    if a.decision is not None:
        require(a.decision == p["decision"], "decision_conflict")
        return
    require(now < a.expires_at, "approval_expired")
    expected = "waiting_management" if a.stage == "management_plan" else "waiting_resident_plan"
    require(state.phase == expected, "approval_out_of_order")
    if a.stage == "resident_plan":
        require(state.approvals.get("management_plan") is not None and
                state.approvals["management_plan"].decision == "approve", "management_required")
    a.decision = p["decision"]
    if a.decision != "approve":
        state.feedback.append(dict(p))
        invalidate(state, p.get("comment", ""))
    elif a.stage == "resident_plan":
        state.phase = "execution_ready"
    # Management approval schedules resident request on the next resume.


def apply_message(state: SupervisorState, kind: str, p: dict, now: datetime) -> None:
    if kind == "ticket.submitted":
        require(not state.facts, "ticket_already_started")
        state.facts.append(dict(p))
    elif kind == "resident.message":
        require(not p.get("mentioned_agent_id"), "mention_belongs_to_groupchat")
        if state.question and p.get("reply_to_request_id") == state.question.request_id:
            state.phase = state.question.return_phase
            state.question = None
            state.needs_clarification = False
            state.facts.append(dict(p))
            if state.plan:
                invalidate(state, "new_resident_information")
        else:
            # Free chat is neither an answer nor an approval. Persist for audit only.
            state.feedback.append(dict(p))
            if state.plan and state.phase in ("waiting_management", "waiting_resident_plan",
                                              "execution_ready", "executing", "waiting_result_validation"):
                # Conservative impact assessment: never execute an approved plan
                # after new, unassessed resident information. Chat is not approval.
                invalidate(state, "new_unassessed_resident_information")
    elif kind == "approval.responded":
        approval_response(state, p, now)
    elif kind in ("assignment.offered", "assignment.responded"):
        a = state.assignment
        require(a is not None and all(p[k] == a[k] for k in
                ("assignment_id", "assignment_version", "plan_id", "plan_version")),
                "stale_assignment")
        require(execution_gate(state), "approvals_required")
        if kind == "assignment.responded":
            prior = a.get("decision")
            require(prior in (None, p["decision"]), "decision_conflict")
            a.update(p)
            if p["decision"] == "decline":
                state.feedback.append(dict(p))
                state.phase, state.pause_reason = "paused", "assignment_declined"
            else:
                require(state.phase in ("executing", "execution_ready"), "assignment_out_of_order")
                state.phase = "executing"
    elif kind == "work.completed":
        a = state.assignment
        require(a is not None and a.get("decision") == "accept" and
                all(p[k] == a[k] for k in ("assignment_id", "assignment_version")) and
                a["plan_version"] == state.revision, "stale_work_result")
        require(state.phase in ("executing", "waiting_result_validation"), "work_out_of_order")
        if state.result:
            require(p["result_id"] == state.result["result_id"] and
                    p["result_version"] > state.result["result_version"], "stale_result")
            state.result_history.append(dict(state.result))
        state.result = dict(p)
        state.publication_draft = None
        state.phase = "waiting_result_validation"
    elif kind == "completion.responded":
        c = state.completion
        require(c is not None and all(p[k] == c[k] for k in
                ("confirmation_id", "result_id", "result_version")), "stale_completion")
        if c.get("decision"):
            require(c["decision"] == p["decision"], "decision_conflict")
            return
        require(state.phase == "waiting_completion", "completion_out_of_order")
        c.update(p)
        if p["decision"] == "not_satisfied":
            state.feedback.append(dict(p))
            state.phase, state.pause_reason = "paused", "not_satisfied"
        else:
            state.phase = "waiting_backend_closure"
    else:
        require(False, "unsupported_message")
