"""Lease-fenced continuation of one durable workflow cause."""

from datetime import timedelta

from ...contracts import WorkflowState
from ._models import (
    CommittedTurnEvidence,
    TurnDecision,
    WorkflowClosed,
    WorkflowConflict,
    WorkflowPattern,
    parse_aggregate,
    raw_value,
)
from ._service import BLOCKED_STATES, HUMAN_WAIT_STATES, next_action
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
    """Trusted guard checked immediately before each model/tool side effect."""

    def __init__(self, continuation, aggregate, trigger, lease) -> None:
        self._continuation = continuation
        self._aggregate = aggregate
        self._trigger = trigger
        self._lease = lease
        self._checked_effects: list[str] = []

    async def check(self, effect: str = "read") -> None:
        await self._check(effect, record=True)

    async def validate(self) -> None:
        await self._check("read", record=False)

    async def _check(self, effect: str, *, record: bool) -> None:
        service = self._continuation.workflows
        original = self._aggregate.workflow
        if self._aggregate.published_read_only and effect != "read":
            raise WorkflowConflict(
                "published read-only workflow forbids side effects"
            )
        current = parse_aggregate(
            await service.repository.load(original.scope, original.workflow_id)
        )
        if current.workflow.state == WorkflowState.CLOSED:
            raise WorkflowClosed("workflow closed while the turn was running")
        if current != self._aggregate:
            raise WorkflowConflict(
                "workflow binding or checkpoint changed during the turn"
            )
        if current.workflow.revision != original.revision:
            raise WorkflowConflict(
                "workflow revision changed while turn was running"
            )
        if not await service.repository.lease_is_current(
            original.scope, self._lease
        ):
            raise WorkflowConflict("workflow lease/fence is no longer current")
        await service.authorization.authorize_trigger(current, self._trigger)
        if record:
            self._checked_effects.append(effect)

    @property
    def checked_effects(self) -> tuple[str, ...]:
        return tuple(self._checked_effects)


class WorkflowContinuation:
    def __init__(
        self,
        workflows,
        commands,
        completion_signals,
        *,
        lease_seconds: int = 120,
        max_model_turns: int = 100,
        max_tool_calls: int = 1000,
        max_tokens: int = 1_000_000,
        evidence=None,
    ) -> None:
        limits = (
            lease_seconds,
            max_model_turns,
            max_tool_calls,
            max_tokens,
        )
        if min(limits) <= 0:
            raise ValueError("continuation limits must be positive")
        self.workflows = workflows
        self.commands = commands
        self.completion_signals = completion_signals
        self.lease_seconds = lease_seconds
        self.max_model_turns = max_model_turns
        self.max_tool_calls = max_tool_calls
        self.max_tokens = max_tokens
        self.evidence = evidence

    async def run(self, scope, trigger, worker_id: str) -> str:
        service = self.workflows
        parsed = WorkflowTrigger.model_validate(dict(trigger))
        aggregate = None
        lease = await service.repository.acquire_lease(
            scope,
            parsed.workflow_id,
            worker_id,
            timedelta(seconds=self.lease_seconds),
        )
        if lease is None:
            raise WorkflowConflict(
                "workflow or shared session already has an active turn"
            )
        try:
            aggregate = parse_aggregate(
                await service.repository.load(scope, parsed.workflow_id)
            )
            if aggregate.workflow.state == WorkflowState.CLOSED:
                return "closed"
            await service.authorization.authorize_trigger(aggregate, parsed)
            key = cause_key(parsed.cause)
            processed = {
                cause_key(item)
                for item in aggregate.checkpoint.last_processed_causes
            }
            if key in processed:
                return "duplicate"
            if (
                parsed.expected_state_revision is not None
                and parsed.expected_state_revision
                != aggregate.workflow.revision
            ):
                raise WorkflowConflict("trigger expected revision is stale")
            if aggregate.workflow.state in BLOCKED_STATES:
                return "blocked"
            if isinstance(parsed.cause, (ExternalEventCause, TimerCause)) and (
                aggregate.workflow.state in HUMAN_WAIT_STATES
                or aggregate.checkpoint.pending_approval_ids
                or aggregate.checkpoint.pending_question_ids
            ):
                return "deferred_human_input"
            if isinstance(parsed.cause, ApprovalCause) and (
                parsed.cause.approval_id
                not in aggregate.checkpoint.pending_approval_ids
            ):
                raise WorkflowConflict(
                    "approval is not pending in this workflow"
                )
            context = PinnedRuntimeContext.model_validate(
                raw_value(
                    await service.runtime.load_pinned_context(
                        scope, aggregate.workflow.checkpoint_ref
                    )
                )
            )
            if (
                context.workflow != aggregate.workflow
                or context.checkpoint != aggregate.checkpoint
            ):
                raise WorkflowConflict(
                    "runtime loaded a different pinned checkpoint"
                )
            guard = ExecutionGuard(self, aggregate, parsed, lease)
            await guard.validate()
            decision = TurnDecision.model_validate(
                raw_value(
                    await service.runtime.invoke_turn(
                        scope,
                        parsed.model_dump(mode="json"),
                        context,
                        guard,
                    )
                )
            )
            pending_waits = await self._validate_decision(
                aggregate, parsed, decision
            )
            async with service.uows() as tx:
                if not await service.repository.lease_is_current(
                    scope, lease, tx
                ):
                    raise WorkflowConflict(
                        "workflow lease expired before commit"
                    )
                current = parse_aggregate(
                    await service.repository.load(
                        scope, parsed.workflow_id, tx
                    )
                )
                if current.workflow.state == WorkflowState.CLOSED:
                    raise WorkflowClosed("workflow closed before turn commit")
                if current.workflow.revision != aggregate.workflow.revision:
                    raise WorkflowConflict(
                        "workflow changed before turn commit"
                    )
                await service.authorization.authorize_trigger(
                    current, parsed, tx
                )
                checkpoint_data = decision.candidate.checkpoint.model_dump()
                checkpoint_data["last_processed_causes"] = (
                    aggregate.checkpoint.last_processed_causes
                    + (parsed.cause,)
                )
                checkpoint = WorkflowCheckpoint.model_validate(checkpoint_data)
                checkpoint_ref = await service.runtime.persist_checkpoint(
                    scope, parsed.workflow_id, checkpoint, tx
                )
                workflow = aggregate.workflow.model_copy(
                    update={
                        "state": decision.next_state,
                        "revision": aggregate.workflow.revision + 1,
                        "updated_at": service.clock(),
                        "checkpoint_ref": checkpoint_ref,
                        "pending_waits": pending_waits,
                    }
                )
                updated = parse_aggregate(
                    aggregate.model_copy(
                        update={"workflow": workflow, "checkpoint": checkpoint}
                    )
                )
                if not await service.repository.save(
                    updated, aggregate.workflow.revision, tx, lease
                ):
                    raise WorkflowConflict(
                        "turn lost its revision or fencing token"
                    )
                for message in decision.candidate.result.messages:
                    await service.events.write(
                        workflow,
                        "assistant.message",
                        {
                            "message_id": message.message_id,
                            "text": message.text,
                        },
                        tx,
                        key[1],
                    )
                    await service.project_shared_context(
                        scope,
                        workflow,
                        event_id=message.message_id,
                        kind="customer_reply",
                        content=message.text,
                        artifact_refs=tuple(
                            attachment.asset_id
                            for attachment in message.attachments
                        ),
                        uow=tx,
                    )
                event_type = "workflow.status_changed"
                payload = {
                    "state": workflow.state.value,
                    "revision": workflow.revision,
                }
                if workflow.state == WorkflowState.CLOSED:
                    event_type = "workflow.closed"
                    payload.update(
                        reason="response_only_completed",
                        closed_at=service.clock().isoformat(),
                    )
                await service.events.write(
                    workflow, event_type, payload, tx, key[1]
                )
                if isinstance(parsed.cause, (RequestCause, ApprovalCause)):
                    await self.commands.record_result(
                        parsed.cause.request_id, decision.candidate.result, tx
                    )

                    async def notify_result() -> None:
                        try:
                            await self.completion_signals.notify_after_commit(
                                scope, parsed.cause.request_id
                            )
                        except Exception:
                            # Durable request state remains authoritative.
                            return

                    tx.add_after_commit(notify_result)
                if self.evidence is not None:
                    before_budget = aggregate.checkpoint.used_budget
                    after_budget = checkpoint.used_budget
                    audience = workflow.audience
                    await self.evidence.record(
                        CommittedTurnEvidence(
                            workflow_id=workflow.workflow_id,
                            trigger_id=parsed.trigger_id,
                            cause_kind=parsed.cause.kind,
                            audience_key=(
                                audience.external_ticket_id
                                or audience.external_conversation_id
                            ),
                            before_state=aggregate.workflow.state,
                            after_state=workflow.state,
                            before_revision=aggregate.workflow.revision,
                            after_revision=workflow.revision,
                            next_action=next_action(workflow.state),
                            checked_effects=guard.checked_effects,
                            model_turns=(
                                after_budget.model_turns
                                - before_budget.model_turns
                            ),
                            tool_calls=(
                                after_budget.tool_calls
                                - before_budget.tool_calls
                            ),
                            input_tokens=(
                                after_budget.input_tokens
                                - before_budget.input_tokens
                            ),
                            output_tokens=(
                                after_budget.output_tokens
                                - before_budget.output_tokens
                            ),
                            new_tracking_records=len(
                                set(checkpoint.operation_refs)
                                - set(aggregate.checkpoint.operation_refs)
                            ),
                            message_ids=tuple(
                                message.message_id
                                for message in decision.candidate.result.messages
                            ),
                            approval_cause=isinstance(
                                parsed.cause, ApprovalCause
                            ),
                            provider_cause=isinstance(
                                parsed.cause,
                                (ExternalEventCause, TimerCause),
                            ),
                        ),
                        tx,
                    )
                await tx.commit()
            return "applied"
        except PermissionError:
            if aggregate is None:
                raise
            return await self._block_authorization(
                scope, parsed, aggregate, lease
            )
        finally:
            await service.repository.release_lease(scope, lease)

    async def _block_authorization(
        self, scope, trigger, aggregate, lease
    ) -> str:
        service = self.workflows
        async with service.uows() as tx:
            if not await service.repository.lease_is_current(
                scope, lease, tx
            ):
                raise WorkflowConflict(
                    "workflow lease expired while blocking authorization"
                )
            current = parse_aggregate(
                await service.repository.load(
                    scope, trigger.workflow_id, tx
                )
            )
            if current.workflow.state == WorkflowState.CLOSED:
                return "closed"
            if current.workflow.revision != aggregate.workflow.revision:
                raise WorkflowConflict(
                    "workflow changed while authorization was revoked"
                )
            revision = current.workflow.revision + 1
            checkpoint = current.checkpoint.model_copy(
                update={"state_revision": revision}
            )
            checkpoint_ref = await service.runtime.persist_checkpoint(
                scope, trigger.workflow_id, checkpoint, tx
            )
            workflow = current.workflow.model_copy(
                update={
                    "state": WorkflowState.BLOCKED_AUTHORIZATION,
                    "revision": revision,
                    "updated_at": service.clock(),
                    "checkpoint_ref": checkpoint_ref,
                    "pending_waits": (),
                }
            )
            blocked = parse_aggregate(
                current.model_copy(
                    update={
                        "workflow": workflow,
                        "checkpoint": checkpoint,
                    }
                )
            )
            if not await service.repository.save(
                blocked, current.workflow.revision, tx, lease
            ):
                raise WorkflowConflict(
                    "authorization block lost revision or fence"
                )
            if isinstance(trigger.cause, (RequestCause, ApprovalCause)):

                async def notify_result() -> None:
                    try:
                        await self.completion_signals.notify_after_commit(
                            scope, trigger.cause.request_id
                        )
                    except Exception:
                        return

                tx.add_after_commit(notify_result)
            await tx.commit()
        return "blocked_authorization"

    async def _validate_decision(
        self, aggregate, trigger, decision
    ) -> tuple[str, ...]:
        if decision.next_state in {
            WorkflowState.ACCEPTED,
            WorkflowState.ACTIVE,
        }:
            raise WorkflowConflict(
                "a completed turn must choose a wait/final state"
            )
        candidate = decision.candidate
        before = aggregate.checkpoint
        after = candidate.checkpoint
        if (
            candidate.trigger_id != trigger.trigger_id
            or candidate.expected_state_revision != aggregate.workflow.revision
            or after.workflow_id != aggregate.workflow.workflow_id
        ):
            raise WorkflowConflict(
                "runtime candidate targets another trigger/revision"
            )
        if any(
            message.created_at.tzinfo is None
            for message in candidate.result.messages
        ):
            raise WorkflowConflict(
                "assistant message timestamps must be aware"
            )
        for field in ("session_refs", "agent_version_pins", "protocol_pins"):
            if getattr(after, field) != getattr(before, field):
                raise WorkflowConflict(f"runtime changed immutable {field}")
        if after.last_processed_causes not in (
            before.last_processed_causes,
            before.last_processed_causes + (trigger.cause,),
        ):
            raise WorkflowConflict("runtime rewrote processed causes")
        if before.pending_approval_ids and not isinstance(
            trigger.cause, ApprovalCause
        ):
            if after.pending_approval_ids != before.pending_approval_ids:
                raise WorkflowConflict(
                    "only an approval cause may resolve an approval"
                )
        if isinstance(trigger.cause, ApprovalCause):
            unrelated = set(before.pending_approval_ids) - {
                trigger.cause.approval_id
            }
            if not unrelated.issubset(after.pending_approval_ids):
                raise WorkflowConflict(
                    "approval cause removed another approval"
                )
        if after.pending_approval_ids and decision.next_state not in {
            WorkflowState.AWAITING_APPROVAL,
            WorkflowState.NEEDS_ATTENTION,
            WorkflowState.BLOCKED_AUTHORIZATION,
            WorkflowState.BLOCKED_ROUTE_CHANGED,
        }:
            raise WorkflowConflict("pending approvals must remain visible")
        if not set(before.operation_refs).issubset(after.operation_refs):
            raise WorkflowConflict(
                "runtime discarded tracked operation history"
            )
        operations = []
        for operation_id in after.operation_refs:
            operation = await self.workflows.operations.get(
                aggregate.workflow.scope, operation_id
            )
            if (
                operation.operation_id != operation_id
                or operation.workflow_id != aggregate.workflow.workflow_id
                or operation.scope != aggregate.workflow.scope
                or operation.audience != aggregate.workflow.audience
                or operation.conversation_id
                != aggregate.workflow.conversation_id
                or operation.protocol_snapshot not in after.protocol_pins
            ):
                raise WorkflowConflict(
                    "runtime referenced a foreign operation"
                )
            operations.append(operation)
        for field in (
            "model_turns",
            "tool_calls",
            "input_tokens",
            "output_tokens",
        ):
            if getattr(after.used_budget, field) < getattr(
                before.used_budget, field
            ):
                raise WorkflowConflict(
                    "runtime decreased durable usage counters"
                )
        used = after.used_budget
        if (
            used.model_turns > self.max_model_turns
            or used.tool_calls > self.max_tool_calls
            or used.input_tokens + used.output_tokens > self.max_tokens
        ):
            raise WorkflowConflict("workflow execution budget exceeded")
        if decision.next_state == WorkflowState.CLOSED:
            if (
                aggregate.pattern != WorkflowPattern.RESPONSE_ONLY
                or not aggregate.published_read_only
                or after.pending_task_ids
                or after.pending_question_ids
                or after.pending_approval_ids
                or after.operation_refs
            ):
                raise WorkflowConflict(
                    "only a finished read-only response may auto-close"
                )
        if (
            aggregate.pattern == WorkflowPattern.RESPONSE_ONLY
            and decision.next_state != WorkflowState.CLOSED
        ):
            raise WorkflowConflict(
                "response-only workflow must finish in one turn"
            )
        if (
            decision.next_state == WorkflowState.AWAITING_APPROVAL
            and not after.pending_approval_ids
        ):
            raise WorkflowConflict(
                "awaiting approval requires a durable approval id"
            )
        pending: list[str] = []
        if decision.next_state == WorkflowState.WAITING_EXTERNAL_EVENT:
            if (
                aggregate.pattern != WorkflowPattern.EXTERNAL_TRACKING
                or not operations
            ):
                raise WorkflowConflict(
                    "external wait requires tracking policy and operation"
                )
            for operation in operations:
                if not await self.workflows.operations.is_pending(operation):
                    continue
                if operation.creation_status.value != "succeeded" or not {
                    "receive_status",
                    "status_query",
                }.intersection(operation.protocol_snapshot.capabilities):
                    raise WorkflowConflict(
                        "pending operation has no tracking capability"
                    )
                pending.append(operation.operation_id)
            if not pending:
                raise WorkflowConflict(
                    "external wait requires a pending operation"
                )
        if decision.next_state == WorkflowState.AWAITING_CONFIRMATION:
            if after.pending_task_ids or after.pending_question_ids:
                raise WorkflowConflict(
                    "unfinished work cannot request close confirmation"
                )
            pending_operations = [
                await self.workflows.operations.is_pending(operation)
                for operation in operations
            ]
            if any(pending_operations):
                raise WorkflowConflict(
                    "pending operation prevents close confirmation"
                )
        return tuple(pending)

