"""Durable workflow commands for request, reply, external event, and close."""

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from ...contracts import (
    JobPort,
    NormalizedJobEvent,
    UnitOfWorkFactory,
    WorkflowState,
)
from ._models import (
    CloseMessage,
    OperationReader,
    ReplyMessage,
    StartMessage,
    WorkflowAggregate,
    WorkflowAuthorization,
    WorkflowBootstrap,
    WorkflowClosed,
    WorkflowConflict,
    WorkflowQueryResult,
    WorkflowRepository,
    WorkflowReservation,
    WorkflowTicketAlreadyBound,
    parse_aggregate,
    raw_value,
    require_binding,
)
from .phase_a import (
    ExternalEventCause,
    RequestCause,
    WorkflowCheckpoint,
    WorkflowTrigger,
    cause_key,
)

HUMAN_WAIT_STATES = {
    WorkflowState.AWAITING_USER,
    WorkflowState.AWAITING_APPROVAL,
    WorkflowState.AWAITING_CONFIRMATION,
}
BLOCKED_STATES = {
    WorkflowState.BLOCKED_AUTHORIZATION,
    WorkflowState.BLOCKED_ROUTE_CHANGED,
}


def next_action(state: WorkflowState | str) -> str:
    return {
        WorkflowState.ACCEPTED: "watch_request",
        WorkflowState.ACTIVE: "watch_request",
        WorkflowState.WAITING_EXTERNAL_EVENT: "watch_events",
        WorkflowState.AWAITING_USER: "submit_reply",
        WorkflowState.AWAITING_APPROVAL: "submit_approval",
        WorkflowState.AWAITING_CONFIRMATION: "confirm_close",
        WorkflowState.NEEDS_ATTENTION: "resolve_attention",
        WorkflowState.BLOCKED_AUTHORIZATION: "resolve_attention",
        WorkflowState.BLOCKED_ROUTE_CHANGED: "resolve_attention",
        WorkflowState.CLOSED: "none",
    }[WorkflowState(state)]


def advance(
    aggregate: WorkflowAggregate,
    clock: Callable[[], datetime],
    **workflow_changes: object,
) -> WorkflowAggregate:
    revision = aggregate.workflow.revision + 1
    workflow = aggregate.workflow.model_copy(
        update={
            "revision": revision,
            "updated_at": clock(),
            **workflow_changes,
        }
    )
    checkpoint = aggregate.checkpoint.model_copy(update={"state_revision": revision})
    return parse_aggregate(
        aggregate.model_copy(update={"workflow": workflow, "checkpoint": checkpoint})
    )


class WorkflowService:
    def __init__(
        self,
        repository: WorkflowRepository,
        bootstrap: WorkflowBootstrap,
        authorization: WorkflowAuthorization,
        operations: OperationReader,
        jobs: JobPort,
        events: object,
        runtime: object,
        uows: UnitOfWorkFactory,
        clock: Callable[[], datetime],
        ids: Callable[[], str] = lambda: uuid4().hex,
        shared_context_projection: bool = False,
    ) -> None:
        self.repository = repository
        self.bootstrap = bootstrap
        self.authorization = authorization
        self.operations = operations
        self.jobs = jobs
        self.events = events
        self.runtime = runtime
        self.uows = uows
        self.clock = clock
        self.ids = ids
        self.shared_context_projection = shared_context_projection

    async def project_shared_context(
        self,
        scope,
        workflow,
        *,
        event_id: str,
        kind: str,
        content: str,
        artifact_refs: tuple[str, ...] = (),
        continuation: Mapping[str, object] | None = None,
        uow,
    ) -> bool:
        """Write a retryable projection job in the caller's transaction."""

        if not self.shared_context_projection:
            return False
        from ._shared_context import projection_payload

        await self.jobs.enqueue(
            scope,
            "workforce.shared_context.project",
            {
                **projection_payload(
                    workflow,
                    event_id=event_id,
                    kind=kind,
                    content=content,
                    artifact_refs=artifact_refs,
                ),
                **(
                    {"continuation": dict(continuation)}
                    if continuation is not None
                    else {}
                ),
            },
            f"shared-context:{workflow.workflow_id}:{kind}:{event_id}",
            uow,
        )
        return True

    async def _in_transaction(self, uow, callback):
        if uow is not None:
            return await callback(uow)
        async with self.uows() as owned:
            result = await callback(owned)
            await owned.commit()
            return result

    async def start_with_binding(self, scope, actor, audience, message, uow=None):
        command = StartMessage.model_validate(dict(message))

        async def execute(tx):
            await self.authorization.authorize(scope, actor, audience, "start", tx)
            proposal = parse_aggregate(
                await self.bootstrap.prepare(scope, actor, audience, command, tx)
            )
            record = require_binding(proposal, scope, audience)
            if record.revision != 1 or record.state != WorkflowState.ACCEPTED:
                raise WorkflowConflict("bootstrap must create accepted revision one")
            reservation = WorkflowReservation.model_validate(
                raw_value(await self.repository.reserve(proposal, tx))
            )
            aggregate = reservation.aggregate
            if not reservation.created:
                raise WorkflowTicketAlreadyBound(
                    "ticket or conversation already bound; use workflow_reply"
                )
            record = require_binding(aggregate, scope, audience)
            if aggregate != proposal:
                raise WorkflowConflict("repository changed the proposed binding")
            inserted = await self.repository.record_input(
                scope,
                record.workflow_id,
                ("request", command.request_id),
                command.text,
                tx,
            )
            if inserted is not True:
                raise WorkflowConflict("new workflow input was not inserted")
            checkpoint_ref = await self.runtime.persist_checkpoint(
                scope, record.workflow_id, aggregate.checkpoint, tx
            )
            aggregate = parse_aggregate(
                aggregate.model_copy(
                    update={
                        "workflow": record.model_copy(
                            update={"checkpoint_ref": checkpoint_ref}
                        )
                    }
                )
            )
            if not await self.repository.save(aggregate, record.revision, tx):
                raise WorkflowConflict("initial workflow checkpoint was not saved")
            await self.events.write(
                aggregate.workflow,
                "request.accepted",
                {"request_id": command.request_id},
                tx,
                command.request_id,
            )
            trigger = WorkflowTrigger(
                trigger_id=self.ids(),
                workflow_id=record.workflow_id,
                cause=RequestCause(
                    kind="request",
                    request_id=command.request_id,
                    asset_ids=command.asset_ids,
                ),
            ).model_dump(mode="json")
            deferred = await self.project_shared_context(
                scope,
                aggregate.workflow,
                event_id=command.request_id,
                kind="customer_message",
                content=command.text,
                artifact_refs=command.asset_ids,
                continuation=trigger,
                uow=tx,
            )
            if not deferred:
                await self.enqueue_trigger(scope, trigger, tx)
            return aggregate.workflow

        return await self._in_transaction(uow, execute)

    async def accept_reply(
        self,
        scope,
        actor,
        audience,
        workflow_id,
        message: Mapping[str, object],
        uow=None,
    ):
        command = ReplyMessage.model_validate(dict(message))

        async def execute(tx):
            aggregate = parse_aggregate(
                await self.repository.load(scope, workflow_id, tx)
            )
            record = require_binding(aggregate, scope, audience)
            await self.authorization.authorize(scope, actor, audience, "reply", tx)
            if record.state == WorkflowState.CLOSED:
                raise WorkflowClosed("workflow is closed")
            if record.state in BLOCKED_STATES:
                raise WorkflowConflict("workflow requires authorization resolution")
            if record.revision != command.expected_revision:
                raise WorkflowConflict("reply revision conflict")
            inserted = await self.repository.record_input(
                scope,
                workflow_id,
                ("request", command.request_id),
                command.text,
                tx,
            )
            if inserted is not True:
                raise WorkflowConflict("reply cause already exists")
            candidate = advance(
                aggregate,
                self.clock,
                state=WorkflowState.ACTIVE,
                pending_waits=(),
            )
            checkpoint_ref = await self.runtime.persist_checkpoint(
                scope, workflow_id, candidate.checkpoint, tx
            )
            candidate = parse_aggregate(
                candidate.model_copy(
                    update={
                        "workflow": candidate.workflow.model_copy(
                            update={"checkpoint_ref": checkpoint_ref}
                        )
                    }
                )
            )
            if not await self.repository.save(candidate, record.revision, tx):
                raise WorkflowConflict("reply revision conflict")
            await self.events.write(
                candidate.workflow,
                "workflow.status_changed",
                {
                    "state": WorkflowState.ACTIVE.value,
                    "revision": candidate.workflow.revision,
                },
                tx,
                command.request_id,
            )
            trigger = WorkflowTrigger(
                trigger_id=self.ids(),
                workflow_id=workflow_id,
                cause=RequestCause(
                    kind="request",
                    request_id=command.request_id,
                    asset_ids=command.asset_ids,
                ),
            ).model_dump(mode="json")
            deferred = await self.project_shared_context(
                scope,
                candidate.workflow,
                event_id=command.request_id,
                kind="customer_message",
                content=command.text,
                artifact_refs=command.asset_ids,
                continuation=trigger,
                uow=tx,
            )
            if not deferred:
                await self.enqueue_trigger(scope, trigger, tx)
            return candidate.workflow

        return await self._in_transaction(uow, execute)

    async def enqueue_trigger(self, scope, trigger, uow=None):
        parsed = WorkflowTrigger.model_validate(dict(trigger))

        async def execute(tx):
            aggregate = parse_aggregate(
                await self.repository.load(scope, parsed.workflow_id, tx)
            )
            if aggregate.workflow.state == WorkflowState.CLOSED:
                raise WorkflowClosed("closed workflows cannot be scheduled")
            await self.authorization.authorize_trigger(aggregate, parsed, tx)
            key = cause_key(parsed.cause)
            digest = sha256(
                json.dumps(
                    [parsed.workflow_id, key[0], key[1]], separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            return await self.jobs.enqueue(
                scope,
                "workforce.workflow.continue",
                parsed.model_dump(mode="json"),
                f"workflow:{digest}",
                tx,
            )

        return await self._in_transaction(uow, execute)

    async def project_workflow_event(
        self,
        scope,
        workflow_id: str,
        *,
        event_id: str,
        kind: str,
        content: str,
        artifact_refs: tuple[str, ...] = (),
        continuation: Mapping[str, object] | None = None,
        uow=None,
    ) -> bool:
        """Project any authenticated partner command before its continuation."""

        async def execute(tx):
            aggregate = parse_aggregate(
                await self.repository.load(scope, workflow_id, tx),
            )
            deferred = await self.project_shared_context(
                scope,
                aggregate.workflow,
                event_id=event_id,
                kind=kind,
                content=content,
                artifact_refs=artifact_refs,
                continuation=continuation,
                uow=tx,
            )
            if continuation is not None and not deferred:
                await self.enqueue_trigger(scope, continuation, tx)
            return deferred

        return await self._in_transaction(uow, execute)

    async def apply_external_event(
        self,
        scope,
        operation_ref,
        normalized_event: NormalizedJobEvent,
        uow=None,
    ):
        """Project an Execution fact; Execution already persisted the fact.

        A closed or revoked workflow suppresses public delivery and runtime
        continuation without raising. This lets the caller commit the real
        provider operation/inbox state in its surrounding UOW.
        """
        event = NormalizedJobEvent.model_validate(raw_value(normalized_event))

        async def execute(tx):
            operation = await self.operations.get(scope, operation_ref, tx)
            aggregate = parse_aggregate(
                await self.repository.load(scope, operation.workflow_id, tx)
            )
            record = require_binding(aggregate, scope, operation.audience)
            if (
                operation.operation_id != operation_ref
                or operation.scope != scope
                or operation.workflow_id != record.workflow_id
                or operation.conversation_id != record.conversation_id
                or operation.ticket_id != record.ticket_id
                or operation.operation_id not in aggregate.checkpoint.operation_refs
                or operation.protocol_snapshot not in aggregate.checkpoint.protocol_pins
                or event.provider_integration_id != operation.provider_integration_id
                or event.protocol_schema_hash != operation.protocol_snapshot.schema_hash
            ):
                raise PermissionError("external operation is not pinned to workflow")
            if event.external_job_id is None and event.client_reference is None:
                raise PermissionError("event has no operation correlation")
            if (
                event.external_job_id is not None
                and event.external_job_id != operation.external_job_id
            ):
                raise PermissionError("external job correlation mismatch")
            if (
                event.client_reference is not None
                and event.client_reference != operation.correlation_id
            ):
                raise PermissionError("client correlation mismatch")
            if record.state == WorkflowState.CLOSED:
                return record
            if not await self.authorization.can_publish_external_event(
                aggregate, event, tx
            ):
                return record
            if event.inbox_event_id in aggregate.applied_external_events:
                return record
            candidate = advance(
                aggregate,
                self.clock,
                last_applied_event_id=event.inbox_event_id,
            )
            candidate = parse_aggregate(
                candidate.model_copy(
                    update={
                        "applied_external_events": (
                            aggregate.applied_external_events + (event.inbox_event_id,)
                        )
                    }
                )
            )
            checkpoint_ref = await self.runtime.persist_checkpoint(
                scope, record.workflow_id, candidate.checkpoint, tx
            )
            candidate = parse_aggregate(
                candidate.model_copy(
                    update={
                        "workflow": candidate.workflow.model_copy(
                            update={"checkpoint_ref": checkpoint_ref}
                        )
                    }
                )
            )
            if not await self.repository.save(candidate, record.revision, tx):
                raise WorkflowConflict("external event revision conflict")
            await self.events.write(
                candidate.workflow,
                "operation.status_changed",
                {
                    "operation_type": operation.protocol_snapshot.protocol_id,
                    "status_schema": (operation.protocol_snapshot.protocol_version),
                    "status": event.normalized_status,
                    "external_reference": operation.external_job_id,
                    "attachments": event.facts.get("attachments", []),
                },
                tx,
                event.inbox_event_id,
            )
            trigger = WorkflowTrigger(
                trigger_id=self.ids(),
                workflow_id=record.workflow_id,
                cause=ExternalEventCause(
                    kind="external_event",
                    cause_event_id=event.inbox_event_id,
                    operation_id=operation_ref,
                ),
            ).model_dump(mode="json")
            deferred = await self.project_shared_context(
                scope,
                candidate.workflow,
                event_id=event.inbox_event_id,
                kind="external_event",
                content=json.dumps(
                    event.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                artifact_refs=tuple(
                    item
                    for item in event.facts.get("attachments", [])
                    if isinstance(item, str)
                ),
                continuation=trigger,
                uow=tx,
            )
            await self.events.write(
                candidate.workflow,
                "workflow.status_changed",
                {
                    "state": candidate.workflow.state.value,
                    "revision": candidate.workflow.revision,
                },
                tx,
                event.inbox_event_id,
            )
            if not deferred:
                await self.enqueue_trigger(scope, trigger, tx)
            return candidate.workflow

        return await self._in_transaction(uow, execute)

    async def apply_query_result(
        self,
        scope,
        operation_ref,
        query_result,
        uow=None,
    ):
        """Apply a verified status-query fact without fabricating an inbox event."""
        result = WorkflowQueryResult.model_validate(raw_value(query_result))

        async def execute(tx):
            operation = await self.operations.get(scope, operation_ref, tx)
            aggregate = parse_aggregate(
                await self.repository.load(scope, operation.workflow_id, tx)
            )
            record = require_binding(aggregate, scope, operation.audience)
            if (
                operation.operation_id != operation_ref
                or operation.workflow_id != record.workflow_id
                or operation.conversation_id != record.conversation_id
                or operation.ticket_id != record.ticket_id
                or operation.operation_id not in aggregate.checkpoint.operation_refs
                or operation.protocol_snapshot not in aggregate.checkpoint.protocol_pins
                or result.protocol_schema_hash
                != operation.protocol_snapshot.schema_hash
            ):
                raise PermissionError("query operation is not pinned to workflow")
            previous_hash = aggregate.applied_query_results.get(result.timer_id)
            if previous_hash is not None:
                if previous_hash != result.source_hash:
                    raise WorkflowConflict(
                        "timer result was reused with different content"
                    )
                return record
            if record.state == WorkflowState.CLOSED:
                return record
            trigger = WorkflowTrigger(
                trigger_id=self.ids(),
                workflow_id=record.workflow_id,
                cause={"kind": "timer", "timer_id": result.timer_id},
            )
            # The caller has already verified and stored the operation fact.
            # Revocation suppresses workflow publication, not that fact's commit.
            try:
                await self.authorization.authorize_trigger(aggregate, trigger, tx)
            except PermissionError:
                return record
            candidate = advance(aggregate, self.clock)
            candidate = parse_aggregate(
                candidate.model_copy(
                    update={
                        "applied_query_results": {
                            **aggregate.applied_query_results,
                            result.timer_id: result.source_hash,
                        }
                    }
                )
            )
            checkpoint_ref = await self.runtime.persist_checkpoint(
                scope, record.workflow_id, candidate.checkpoint, tx
            )
            candidate = parse_aggregate(
                candidate.model_copy(
                    update={
                        "workflow": candidate.workflow.model_copy(
                            update={"checkpoint_ref": checkpoint_ref}
                        )
                    }
                )
            )
            if not await self.repository.save(candidate, record.revision, tx):
                raise WorkflowConflict("query result revision conflict")
            await self.events.write(
                candidate.workflow,
                "operation.status_changed",
                {
                    "operation_type": operation.protocol_snapshot.protocol_id,
                    "status_schema": (operation.protocol_snapshot.protocol_version),
                    "status": result.status,
                    "external_reference": operation.external_job_id,
                },
                tx,
                result.timer_id,
            )
            deferred = await self.project_shared_context(
                scope,
                candidate.workflow,
                event_id=result.timer_id,
                kind="external_event",
                content=json.dumps(
                    result.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                continuation=trigger.model_dump(mode="json"),
                uow=tx,
            )
            await self.events.write(
                candidate.workflow,
                "workflow.status_changed",
                {
                    "state": candidate.workflow.state.value,
                    "revision": candidate.workflow.revision,
                },
                tx,
                result.timer_id,
            )
            if not deferred:
                await self.enqueue_trigger(scope, trigger.model_dump(mode="json"), tx)
            return candidate.workflow

        return await self._in_transaction(uow, execute)

    async def close(self, scope, actor, audience, command, uow=None):
        raw = dict(command)
        if type(raw.get("expected_revision")) is not int:
            raise ValueError("close expected_revision must be a strict integer")
        if type(raw.get("stop_tracking_only", False)) is not bool:
            raise ValueError("close stop_tracking_only must be a strict boolean")
        parsed = CloseMessage.model_validate(raw)
        if (
            parsed.external_user_id != audience.external_user_id
            or parsed.external_ticket_id != audience.external_ticket_id
            or parsed.external_conversation_id != audience.external_conversation_id
        ):
            raise PermissionError("close audience mismatch")

        async def execute(tx):
            aggregate = parse_aggregate(
                await self.repository.load(scope, parsed.workflow_id, tx)
            )
            record = require_binding(aggregate, scope, audience)
            await self.authorization.authorize(scope, actor, audience, "close", tx)
            if record.revision != parsed.expected_revision:
                raise WorkflowConflict("close revision conflict")
            if record.state == WorkflowState.CLOSED:
                return record
            checkpoint = aggregate.checkpoint
            if checkpoint.pending_approval_ids and not parsed.stop_tracking_only:
                raise WorkflowConflict("pending approval prevents completion close")
            pending_operations = []
            for ref in checkpoint.operation_refs:
                operation = await self.operations.get(scope, ref, tx)
                if await self.operations.is_pending(operation, tx):
                    pending_operations.append(ref)
            if pending_operations and not parsed.stop_tracking_only:
                raise WorkflowConflict("pending operation requires stop_tracking_only")
            if (
                record.state != WorkflowState.AWAITING_CONFIRMATION
                and not parsed.stop_tracking_only
            ):
                raise WorkflowConflict("workflow is not ready for completion close")
            candidate = advance(
                aggregate,
                self.clock,
                state=WorkflowState.CLOSED,
                pending_waits=(),
            )
            checkpoint_data = candidate.checkpoint.model_dump()
            checkpoint_data.update(pending_task_ids=(), pending_question_ids=())
            closed_checkpoint = WorkflowCheckpoint.model_validate(checkpoint_data)
            checkpoint_ref = await self.runtime.persist_checkpoint(
                scope, record.workflow_id, closed_checkpoint, tx
            )
            candidate = parse_aggregate(
                candidate.model_copy(
                    update={
                        "checkpoint": closed_checkpoint,
                        "workflow": candidate.workflow.model_copy(
                            update={"checkpoint_ref": checkpoint_ref}
                        ),
                    }
                )
            )
            if not await self.repository.save(candidate, record.revision, tx):
                raise WorkflowConflict("close lost revision race")
            await self.events.write(
                candidate.workflow,
                "workflow.closed",
                {
                    "state": "closed",
                    "revision": candidate.workflow.revision,
                    "reason": parsed.reason,
                    "closed_at": self.clock().isoformat(),
                },
                tx,
                parsed.external_request_id,
            )
            await self.project_shared_context(
                scope,
                candidate.workflow,
                event_id=parsed.external_request_id,
                kind="context_update",
                content=json.dumps(
                    {
                        "action": "workflow_closed",
                        "reason": parsed.reason,
                        "stop_tracking_only": parsed.stop_tracking_only,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                uow=tx,
            )
            return candidate.workflow

        return await self._in_transaction(uow, execute)
