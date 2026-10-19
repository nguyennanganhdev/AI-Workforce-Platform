"""Completion barriers over unified SQL facts, in the close transaction."""

from sqlalchemy import select

from ...orchestration._tables import workflows
from ...orchestration.workflows._models import (
    WorkflowApprovalPending,
    WorkflowNotReadyToClose,
    WorkflowRevisionConflict,
)
from ._tables import approvals, operations


async def guard_case_close(aggregate, command, uow) -> bool | None:
    workflow = aggregate.workflow
    # Operation intent creation takes this same lock before it contacts MCP.
    current = (await uow.execute(select(workflows.c.revision).where(
        workflows.c.id == workflow.workflow_id,
    ).with_for_update())).scalar_one()
    if current != command.expected_revision:
        raise WorkflowRevisionConflict("close revision conflict", current)
    if command.stop_tracking_only:
        if command.reason != "resident_requested_stop_tracking" or command.domain_acceptance is not None:
            raise WorkflowNotReadyToClose("stop tracking is not completion acceptance")
        return
    pending = (await uow.execute(select(approvals.c.approval_id).where(
        approvals.c.workflow_id == workflow.workflow_id,
        approvals.c.status == "pending",
    ).with_for_update())).first()
    if pending is not None:
        # Expired-but-unresolved approvals still require an explicit resolution.
        raise WorkflowApprovalPending("unified pending approval prevents completion close")
    work = (await uow.execute(select(operations).where(
        operations.c.workflow_id == workflow.workflow_id,
    ).with_for_update())).mappings().all()
    if any(not row["terminal"] for row in work):
        raise WorkflowNotReadyToClose("unified pending or unknown operation prevents completion close")
    accepted = command.domain_acceptance
    if (command.reason != "resident_confirmed" or accepted is None
        or accepted.external_ticket_id != workflow.audience.external_ticket_id
        or accepted.external_user_id != workflow.audience.external_user_id):
        raise WorkflowNotReadyToClose("Domain resident acceptance is required")
    completed_jobs = {
        row["external_job_id"] for row in work
        if row["terminal"] and row["outcome"] == "completed" and row["external_job_id"]
    }
    if not completed_jobs or not completed_jobs.issubset(set(accepted.work_order_ids)):
        raise WorkflowNotReadyToClose("successful terminal work evidence is required")
    # Domain has already authenticated this resident's decision and tied it
    # to completed work. An LLM narration failure must not block that decision.
    return True
