"""Durable Workforce-job projection into the canonical team context."""

from __future__ import annotations

from typing import Any

from ...._shared_context import SharedContextService
from ....storage import ContextDelta, SharedTaskStatus
from ...contracts import Scope, WorkflowRecord, WorkflowState
from ...foundation.event_delivery import DurableJob
from ._models import raw_value
from .phase_a import WorkflowTrigger


class WorkforceSharedContextProjector:
    """Apply partner workflow events through the same service as UI chat."""

    job_type = "workforce.shared_context.project"

    def __init__(self, context: SharedContextService, scheduler: Any) -> None:
        self._context = context
        self._scheduler = scheduler

    async def __call__(self, value: Any) -> dict[str, object]:
        job = DurableJob.model_validate(value)
        if job.job_type != self.job_type or job.scope is None:
            raise ValueError("SCOPED_SHARED_CONTEXT_JOB_REQUIRED")
        payload = job.payload
        scope = Scope.model_validate(job.scope)
        workflow_id = self._required(payload, "workflow_id")
        team_id = self._required(payload, "group_id")
        event_id = self._required(payload, "event_id")
        kind = self._required(payload, "kind")
        content = self._required(payload, "content")
        if kind not in {
            "customer_message",
            "customer_reply",
            "external_event",
            "context_update",
        }:
            raise ValueError("unsupported shared-context projection kind")
        workflow_state = WorkflowState(self._required(payload, "workflow_state"))
        workflow_revision = payload.get("workflow_revision")
        if not isinstance(workflow_revision, int) or workflow_revision < 1:
            raise ValueError("shared-context projection requires workflow_revision")
        artifact_refs = tuple(payload.get("artifact_refs", ()))
        if not all(isinstance(item, str) and item for item in artifact_refs):
            raise ValueError("artifact_refs must contain non-empty strings")
        continuation = payload.get("continuation")
        trigger = None
        if continuation is not None:
            if not isinstance(continuation, dict):
                raise ValueError("shared-context continuation must be an object")
            trigger = WorkflowTrigger.model_validate(continuation)
            if trigger.workflow_id != workflow_id:
                raise ValueError("shared-context continuation workflow mismatch")

        projected_kind = (
            "requires_user_input"
            if kind == "customer_reply"
            and workflow_state == WorkflowState.AWAITING_USER
            else kind
        )
        task_status = self._task_status(workflow_state)
        delta = None
        if projected_kind == "customer_reply":
            delta = ContextDelta(status=task_status, add_outputs=(content,))
        elif projected_kind == "external_event":
            delta = ContextDelta(
                status=task_status,
                add_confirmed_facts=(content,),
            )
        elif projected_kind == "context_update":
            delta = ContextDelta(
                status=task_status,
                add_decisions=(content,),
            )
        elif projected_kind == "requires_user_input":
            delta = ContextDelta(status="waiting_user")
        user_id = scope.manager_account_id
        await self._context.bind_scope(
            user_id,
            team_id,
            tenant_id=scope.tenant_id,
            domain_id=scope.domain_id,
            area_id=scope.area_id,
            manager_account_id=scope.manager_account_id,
            workflow_id=workflow_id,
        )
        event = await self._context.append_event(
            user_id=user_id,
            team_id=team_id,
            task_id=workflow_id,
            event_id=event_id,
            kind=projected_kind,
            content=content,
            source_message_id=(
                event_id
                if projected_kind
                in {"customer_message", "customer_reply", "requires_user_input"}
                else None
            ),
            source_session_id=self._optional(payload, "conversation_id"),
            thread_id=workflow_id,
            artifact_refs=artifact_refs,
            source_workflow_revision=workflow_revision,
            delta=delta,
        )
        if trigger is not None and not event.stale:
            # Re-enter the authoritative scheduler so route/release/trigger
            # authorization is revalidated after asynchronous projection.
            await self._scheduler.enqueue_trigger(
                scope,
                trigger.model_dump(mode="json"),
            )
        return {
            "team_id": team_id,
            "task_id": event.task_id,
            "event_id": event.id,
            "revision": event.revision,
            "stale": event.stale,
        }

    @staticmethod
    def _required(payload: dict[str, object], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"shared-context projection requires {field}")
        return value

    @staticmethod
    def _optional(payload: dict[str, object], field: str) -> str | None:
        value = payload.get(field)
        if value is not None and (not isinstance(value, str) or not value):
            raise ValueError(f"shared-context projection has invalid {field}")
        return value

    @staticmethod
    def _task_status(state: WorkflowState) -> SharedTaskStatus:
        return {
            WorkflowState.ACCEPTED: "queued",
            WorkflowState.ACTIVE: "running",
            WorkflowState.WAITING_EXTERNAL_EVENT: "waiting_external",
            WorkflowState.AWAITING_USER: "waiting_user",
            WorkflowState.AWAITING_APPROVAL: "waiting_approval",
            WorkflowState.AWAITING_CONFIRMATION: "waiting_user",
            WorkflowState.NEEDS_ATTENTION: "blocked",
            WorkflowState.BLOCKED_AUTHORIZATION: "blocked",
            WorkflowState.BLOCKED_ROUTE_CHANGED: "blocked",
            WorkflowState.CLOSED: "completed",
        }[state]


def projection_payload(
    workflow: Any,
    *,
    event_id: str,
    kind: str,
    content: str,
    artifact_refs: tuple[str, ...] = (),
) -> dict[str, object]:
    """Create the small domain-neutral payload stored in the job outbox."""

    record = WorkflowRecord.model_validate(raw_value(workflow))
    return {
        "workflow_id": record.workflow_id,
        "group_id": record.group_id,
        "event_id": event_id,
        "kind": kind,
        "content": content,
        "artifact_refs": list(artifact_refs),
        "workflow_state": record.state.value,
        "workflow_revision": record.revision,
        "conversation_id": record.conversation_id,
    }


__all__ = ["WorkforceSharedContextProjector", "projection_payload"]
