# -*- coding: utf-8 -*-
"""One cause, one pinned turn. Runtime/provider calls occur outside the UOW."""

from datetime import timedelta

from ...contracts import WorkflowState
from ._boundary import (
    TurnPlan,
    WorkflowClosed,
    WorkflowConflict,
    WorkflowPattern,
    raw_models,
    validated_bundle,
)
from ._service import BLOCKED_STATES, HITL_STATES
from .phase_a import (
    ApprovalCause,
    ExternalEventCause,
    PinnedRuntimeContext,
    RequestCause,
    TimerCause,
    WorkflowCheckpoint,
    WorkflowTrigger,
    cause_key,
)


class ExecutionGuard:
    """Runtime calls check immediately before EVERY provider/tool side effect.

    A close or expired/replaced lease invalidates this guard. A provider call
    sent needs Execution's operation reconciliation in Phase C.
    """

    def __init__(self, service, bundle, trigger, lease):
        self.service, self.bundle, self.trigger, self.lease = (
            service,
            bundle,
            trigger,
            lease,
        )

    async def check(self, effect="read"):
        record = self.bundle.workflow
        if self.bundle.published_read_only and effect != "read":
            raise PermissionError(
                "published read-only policy prohibits side effects"
            )
        current = await self.service.repository.load(
            record.scope, record.workflow_id
        )
        if current.workflow.state == WorkflowState.CLOSED:
            raise WorkflowClosed("execution guard invalidated by close")
        if (
            current.workflow.revision != record.revision
            or not await self.service.repository.valid_lease(
                record.scope, self.lease
            )
        ):
            raise WorkflowConflict("execution guard revision/fence expired")
        await self.service.authorization.authorize_trigger(
            current, self.trigger
        )


class WorkflowContinuation:
    def __init__(
        self,
        workflows,
        commands,
        completion_signals,
        *,
        lease_seconds=120,
        max_model_turns=100,
        max_tool_calls=1000,
        max_tokens=1_000_000,
    ):
        if (
            min(lease_seconds, max_model_turns, max_tool_calls, max_tokens)
            <= 0
        ):
            raise ValueError("continuation limits must be positive")
        self.workflows, self.commands, self.completion_signals = (
            workflows,
            commands,
            completion_signals,
        )
        self.lease_seconds = lease_seconds
        self.limits = (max_model_turns, max_tool_calls, max_tokens)

    async def run(self, scope, trigger, worker_id):
        service = self.workflows
        trigger = WorkflowTrigger.model_validate(dict(trigger))
        lease = await service.repository.claim(
            scope,
            trigger.workflow_id,
            worker_id,
            timedelta(seconds=self.lease_seconds),
        )
        if lease is None:
            raise WorkflowConflict("workflow/session has an active turn lease")
        try:
            bundle = validated_bundle(
                await service.repository.load(scope, trigger.workflow_id)
            )
            if bundle.workflow.scope != scope:
                raise PermissionError("continuation scope mismatch")
            if bundle.workflow.state == WorkflowState.CLOSED:
                return "closed"
            await service.authorization.authorize_trigger(bundle, trigger)
            key = cause_key(trigger.cause)
            if key in {
                cause_key(c) for c in bundle.checkpoint.last_processed_causes
            }:
                return "duplicate"
            if (
                trigger.expected_state_revision is not None
                and trigger.expected_state_revision != bundle.workflow.revision
            ):
                raise WorkflowConflict("trigger revision conflict")
            if bundle.workflow.state in BLOCKED_STATES:
                return "blocked"
            if isinstance(
                trigger.cause, (ExternalEventCause, TimerCause)
            ) and (
                bundle.workflow.state in HITL_STATES
                or bundle.checkpoint.pending_approval_ids
                or bundle.checkpoint.pending_question_ids
            ):
                # Facts are already durable. The next authorized human cause
                # loads them, without inventing an approval or user message.
                return "deferred_hitl"
            if isinstance(trigger.cause, ApprovalCause):
                if (
                    trigger.cause.approval_id
                    not in bundle.checkpoint.pending_approval_ids
                ):
                    raise WorkflowConflict(
                        "approval is not pending in this workflow"
                    )
            loaded = await service.runtime.load_pinned_context(
                scope, bundle.workflow.checkpoint_ref
            )
            context = PinnedRuntimeContext.model_validate(raw_models(loaded))
            if (
                context.workflow != bundle.workflow
                or context.checkpoint != bundle.checkpoint
            ):
                raise WorkflowConflict(
                    "runtime loaded a different pinned snapshot"
                )
            guard = ExecutionGuard(service, bundle, trigger, lease)
            await guard.check()
            plan = TurnPlan.model_validate(
                raw_models(
                    await service.runtime.invoke_turn(
                        scope, trigger.model_dump(mode="json"), context, guard
                    )
                )
            )
            pending_waits = await self._validate_plan(bundle, trigger, plan)
            async with service.uows() as tx:
                await guard.check()
                await service.authorization.authorize_trigger(
                    bundle, trigger, tx
                )
                candidate = plan.candidate
                data = candidate.checkpoint.model_dump()
                data[
                    "last_processed_causes"
                ] = bundle.checkpoint.last_processed_causes + (trigger.cause,)
                checkpoint = WorkflowCheckpoint.model_validate(data)
                ref = await service.runtime.persist_checkpoint(
                    scope, trigger.workflow_id, checkpoint, tx
                )
                record = bundle.workflow.model_copy(
                    update={
                        "state": plan.next_state,
                        "revision": candidate.expected_state_revision + 1,
                        "updated_at": service.clock(),
                        "checkpoint_ref": ref,
                        "pending_waits": pending_waits,
                    }
                )
                updated = validated_bundle(
                    bundle.model_copy(
                        update={
                            "workflow": record,
                            "checkpoint": checkpoint,
                        }
                    )
                )
                if not await service.repository.save(
                    updated, bundle.workflow.revision, tx, lease
                ):
                    raise WorkflowConflict(
                        "turn lost revision/fence; candidate discarded"
                    )
                for message in candidate.result.messages:
                    await service.events.write(
                        record,
                        "assistant.message",
                        {
                            "message_id": message.message_id,
                            "text": message.text,
                        },
                        tx,
                        key[1],
                    )
                event_type = "workflow.status_changed"
                payload = {"state": record.state, "revision": record.revision}
                if record.state == WorkflowState.CLOSED:
                    event_type = "workflow.closed"
                    payload.update(
                        reason="response_only_completed",
                        closed_at=service.clock().isoformat(),
                    )
                await service.events.write(
                    record, event_type, payload, tx, key[1]
                )
                if isinstance(trigger.cause, (RequestCause, ApprovalCause)):
                    await self.commands.record_result(
                        trigger.cause.request_id, candidate.result, tx
                    )

                    async def signal():
                        try:
                            await self.completion_signals.notify_after_commit(
                                scope, trigger.cause.request_id
                            )
                        except Exception:
                            pass

                    tx.add_after_commit(signal)
                await tx.commit()
            return "applied"
        finally:
            await service.repository.release(scope, lease)

    async def _validate_plan(self, bundle, trigger, plan):
        if plan.next_state in {WorkflowState.ACCEPTED, WorkflowState.ACTIVE}:
            raise WorkflowConflict(
                "completed turn must select a durable wait/final state"
            )
        candidate = plan.candidate
        checkpoint = candidate.checkpoint
        before = bundle.checkpoint
        candidate.result.model_dump(mode="json")
        if any(
            message.created_at.tzinfo is None
            for message in candidate.result.messages
        ):
            raise WorkflowConflict(
                "assistant messages require aware timestamps"
            )
        if (
            candidate.trigger_id != trigger.trigger_id
            or candidate.expected_state_revision != bundle.workflow.revision
            or checkpoint.workflow_id != trigger.workflow_id
        ):
            raise WorkflowConflict(
                "runtime result targets a different trigger/revision"
            )
        for name in ("session_refs", "agent_version_pins", "protocol_pins"):
            if getattr(checkpoint, name) != getattr(before, name):
                raise WorkflowConflict(
                    "runtime changed pinned identity or session"
                )
        if checkpoint.last_processed_causes not in (
            before.last_processed_causes,
            before.last_processed_causes + (trigger.cause,),
        ):
            raise WorkflowConflict("runtime rewrote processed causes")
        if before.pending_approval_ids and not isinstance(
            trigger.cause, ApprovalCause
        ):
            if checkpoint.pending_approval_ids != before.pending_approval_ids:
                raise WorkflowConflict(
                    "only a verified approval cause resolves approval"
                )
        if isinstance(trigger.cause, ApprovalCause):
            remaining = set(before.pending_approval_ids) - {
                trigger.cause.approval_id
            }
            if not remaining.issubset(checkpoint.pending_approval_ids):
                raise WorkflowConflict(
                    "approval cause cannot resolve another approval"
                )
        if checkpoint.pending_approval_ids and plan.next_state not in {
            WorkflowState.AWAITING_APPROVAL,
            WorkflowState.NEEDS_ATTENTION,
            WorkflowState.BLOCKED_AUTHORIZATION,
            WorkflowState.BLOCKED_ROUTE_CHANGED,
        }:
            raise WorkflowConflict("pending approvals must remain visible")
        if not set(before.operation_refs).issubset(checkpoint.operation_refs):
            raise WorkflowConflict("runtime cannot discard tracked operations")
        operations = []
        for ref in checkpoint.operation_refs:
            op = await self.workflows.operations.get(
                bundle.workflow.scope, ref
            )
            if (
                op.operation_id != ref
                or op.scope != bundle.workflow.scope
                or op.workflow_id != trigger.workflow_id
                or op.audience != bundle.workflow.audience
                or op.conversation_id != bundle.workflow.conversation_id
                or op.protocol_snapshot not in checkpoint.protocol_pins
            ):
                raise WorkflowConflict(
                    "runtime references a foreign or unpinned operation"
                )
            operations.append(op)
        if any(
            getattr(checkpoint.used_budget, k) < getattr(before.used_budget, k)
            for k in (
                "model_turns",
                "tool_calls",
                "input_tokens",
                "output_tokens",
            )
        ):
            raise WorkflowConflict("runtime decreased durable budget")
        budget = checkpoint.used_budget
        if (
            budget.model_turns > self.limits[0]
            or budget.tool_calls > self.limits[1]
            or budget.input_tokens + budget.output_tokens > self.limits[2]
        ):
            raise WorkflowConflict("workflow budget exceeded")
        if plan.next_state == WorkflowState.CLOSED:
            if (
                bundle.pattern != WorkflowPattern.RESPONSE_ONLY
                or not bundle.published_read_only
                or checkpoint.pending_approval_ids
                or checkpoint.pending_question_ids
                or checkpoint.pending_task_ids
                or checkpoint.operation_refs
            ):
                raise WorkflowConflict(
                    "auto-close requires a completed read-only response"
                )
        if (
            bundle.pattern == WorkflowPattern.RESPONSE_ONLY
            and plan.next_state != WorkflowState.CLOSED
        ):
            raise WorkflowConflict("response-only turn must complete")
        if (
            plan.next_state == WorkflowState.AWAITING_APPROVAL
            and not checkpoint.pending_approval_ids
        ):
            raise WorkflowConflict(
                "awaiting_approval requires durable approval refs"
            )
        pending_waits = []
        if plan.next_state == WorkflowState.WAITING_EXTERNAL_EVENT:
            if (
                bundle.pattern != WorkflowPattern.EXTERNAL_TRACKING
                or not checkpoint.operation_refs
            ):
                raise WorkflowConflict(
                    "external wait requires tracking pattern and operation"
                )
            for op in operations:
                # Terminal refs remain in checkpoint history. Only active
                # operations need a tracking capability and become waits.
                if not await self.workflows.operations.is_pending(op):
                    continue
                if op.creation_status.value != "succeeded" or not {
                    "receive_status",
                    "status_query",
                }.intersection(op.protocol_snapshot.capabilities):
                    raise WorkflowConflict(
                        "operation cannot support this external wait"
                    )
                pending_waits.append(op.operation_id)
            if not pending_waits:
                raise WorkflowConflict(
                    "external wait requires at least one pending operation"
                )
        if plan.next_state == WorkflowState.AWAITING_CONFIRMATION:
            if checkpoint.pending_task_ids or checkpoint.pending_question_ids:
                raise WorkflowConflict(
                    "unfinished work cannot request completion"
                )
            for operation in operations:
                if await self.workflows.operations.is_pending(operation):
                    raise WorkflowConflict(
                        "pending operation cannot request "
                        "completion confirmation"
                    )
        return tuple(pending_waits)
