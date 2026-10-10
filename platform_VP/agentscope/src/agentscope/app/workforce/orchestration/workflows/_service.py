# -*- coding: utf-8 -*-
"""Independent workflow logic with injected durable persistence and runtime."""

from collections.abc import Callable, Mapping
from datetime import datetime
from hashlib import sha256
import json
from uuid import uuid4

from ...contracts import (
    JobPort,
    NormalizedJobEvent,
    UnitOfWorkFactory,
    WorkflowState,
)
from ._boundary import (
    BindingReservation,
    CloseInput,
    OperationLookup,
    ReplyInput,
    StartInput,
    WorkflowAuthorization,
    WorkflowBootstrap,
    WorkflowClosed,
    WorkflowConflict,
    WorkflowRepository,
    parse_model,
    raw_models,
    require_binding,
    validated_bundle,
)
from .phase_a import (
    ExternalEventCause,
    RequestCause,
    WorkflowCheckpoint,
    WorkflowTrigger,
    cause_key,
)


HITL_STATES = {
    WorkflowState.AWAITING_USER,
    WorkflowState.AWAITING_APPROVAL,
    WorkflowState.AWAITING_CONFIRMATION,
}
BLOCKED_STATES = {
    WorkflowState.BLOCKED_AUTHORIZATION,
    WorkflowState.BLOCKED_ROUTE_CHANGED,
}


def next_action(state):
    return {
        WorkflowState.CLOSED: "none",
        WorkflowState.ACCEPTED: "watch_request",
        WorkflowState.ACTIVE: "watch_request",
        WorkflowState.WAITING_EXTERNAL_EVENT: "watch_events",
        WorkflowState.AWAITING_USER: "submit_reply",
        WorkflowState.AWAITING_APPROVAL: "submit_approval",
        WorkflowState.AWAITING_CONFIRMATION: "confirm_close",
        WorkflowState.NEEDS_ATTENTION: "resolve_attention",
        WorkflowState.BLOCKED_AUTHORIZATION: "resolve_attention",
        WorkflowState.BLOCKED_ROUTE_CHANGED: "resolve_attention",
    }[state]


def advance(bundle, clock, **changes):
    record = bundle.workflow.model_copy(
        update={
            "revision": bundle.workflow.revision + 1,
            "updated_at": clock(),
            **changes,
        }
    )
    checkpoint = bundle.checkpoint.model_copy(
        update={
            "state_revision": record.revision,
        }
    )
    return validated_bundle(
        bundle.model_copy(
            update={
                "workflow": record,
                "checkpoint": checkpoint,
            }
        )
    )


class WorkflowService:
    def __init__(
        self,
        repository: WorkflowRepository,
        bootstrap: WorkflowBootstrap,
        authorization: WorkflowAuthorization,
        operations: OperationLookup,
        jobs: JobPort,
        events,
        runtime,
        uows: UnitOfWorkFactory,
        clock: Callable[[], datetime],
        ids: Callable[[], str] = lambda: uuid4().hex,
    ):
        self.repository, self.bootstrap = repository, bootstrap
        self.authorization, self.operations = authorization, operations
        self.jobs, self.events, self.runtime = jobs, events, runtime
        self.uows, self.clock, self.ids = uows, clock, ids

    async def _transaction(self, uow, action):
        if uow is not None:
            return await action(uow)
        async with self.uows() as owned:
            result = await action(owned)
            await owned.commit()
            return result

    async def start_with_binding(
        self, scope, actor, audience, message, uow=None
    ):
        command = parse_model(StartInput, message)

        async def start(tx):
            await self.authorization.authorize(
                scope, actor, audience, "start", tx
            )
            proposed = validated_bundle(
                await self.bootstrap.prepare(
                    scope, actor, audience, command, tx
                )
            )
            require_binding(proposed, scope, audience)
            if (
                proposed.workflow.revision != 1
                or proposed.workflow.state != WorkflowState.ACCEPTED
            ):
                raise ValueError(
                    "bootstrap must allocate an accepted first revision"
                )
            reservation = BindingReservation.model_validate(
                raw_models(await self.repository.create_unique(proposed, tx))
            )
            bundle = reservation.bundle
            record = require_binding(bundle, scope, audience)
            if record.state == WorkflowState.CLOSED:
                raise WorkflowClosed("closed ticket binding cannot restart")
            input_is_new = await self.repository.record_input(
                scope,
                record.workflow_id,
                ("request", command.request_id),
                command.text,
                tx,
            )
            if type(input_is_new) is not bool:
                raise TypeError(
                    "record_input must return a strict is_new flag"
                )
            if not reservation.is_new and input_is_new:
                raise WorkflowConflict(
                    "ticket/chat already bound; use workflow_reply"
                )
            if reservation.is_new:
                if bundle != proposed:
                    raise WorkflowConflict(
                        "repository changed bootstrap pins/binding"
                    )
                ref = await self.runtime.persist_checkpoint(
                    scope, record.workflow_id, bundle.checkpoint, tx
                )
                bundle = bundle.model_copy(
                    update={
                        "workflow": record.model_copy(
                            update={"checkpoint_ref": ref}
                        ),
                    }
                )
                if not await self.repository.save(bundle, record.revision, tx):
                    raise WorkflowConflict("initial checkpoint binding failed")
                record = bundle.workflow
                await self.events.write(
                    record,
                    "request.accepted",
                    {"request_id": command.request_id},
                    tx,
                    command.request_id,
                )
            trigger = WorkflowTrigger(
                trigger_id=self.ids(),
                workflow_id=record.workflow_id,
                cause=RequestCause(
                    kind="request", request_id=command.request_id
                ),
            )
            await self.enqueue_trigger(scope, trigger.model_dump(), tx)
            return record

        return await self._transaction(uow, start)

    async def accept_reply(
        self,
        scope,
        actor,
        audience,
        workflow_id,
        message: Mapping[str, object],
        uow=None,
    ):
        command = parse_model(ReplyInput, message)

        async def reply(tx):
            bundle = await self.repository.load(scope, workflow_id, tx)
            record = require_binding(bundle, scope, audience)
            await self.authorization.authorize(
                scope, actor, audience, "reply", tx
            )
            if record.state == WorkflowState.CLOSED:
                raise WorkflowClosed("workflow is closed")
            if record.state in BLOCKED_STATES:
                raise WorkflowConflict(
                    "workflow requires grant/route resolution"
                )
            if record.revision != command.expected_revision:
                raise WorkflowConflict("reply revision conflict")
            await self.repository.record_input(
                scope,
                workflow_id,
                ("request", command.request_id),
                command.text,
                tx,
            )
            trigger = WorkflowTrigger(
                trigger_id=self.ids(),
                workflow_id=workflow_id,
                cause=RequestCause(
                    kind="request", request_id=command.request_id
                ),
            )
            await self.enqueue_trigger(scope, trigger.model_dump(), tx)
            return record

        return await self._transaction(uow, reply)

    async def enqueue_trigger(self, scope, trigger, uow=None):
        trigger = parse_model(WorkflowTrigger, trigger)

        async def enqueue(tx):
            bundle = await self.repository.load(scope, trigger.workflow_id, tx)
            if bundle.workflow.scope != scope:
                raise PermissionError("trigger scope mismatch")
            if bundle.workflow.state == WorkflowState.CLOSED:
                raise WorkflowClosed("workflow is closed")
            await self.authorization.authorize_trigger(bundle, trigger, tx)
            key = cause_key(trigger.cause)
            job_key = sha256(
                json.dumps(
                    [trigger.workflow_id, *key], separators=(",", ":")
                ).encode()
            ).hexdigest()
            # Serialize causes at execution using the saved revision.
            return await self.jobs.enqueue(
                scope,
                "workforce.workflow.continue",
                trigger.model_dump(mode="json"),
                f"workflow:{job_key}",
                tx,
            )

        return await self._transaction(uow, enqueue)

    async def apply_external_event(
        self,
        scope,
        operation_ref,
        normalized_event: NormalizedJobEvent,
        uow=None,
    ):
        normalized_event = NormalizedJobEvent.model_validate(
            dict(normalized_event)
        )

        async def apply(tx):
            operation = await self.operations.get(scope, operation_ref, tx)
            bundle = await self.repository.load(
                scope, operation.workflow_id, tx
            )
            record = require_binding(bundle, scope, operation.audience)
            await self.authorization.authorize(
                scope, None, record.audience, "apply_verified_event", tx
            )
            if (
                operation.scope != scope
                or operation.conversation_id != record.conversation_id
                or operation.operation_id
                not in bundle.checkpoint.operation_refs
                or operation.protocol_snapshot
                not in bundle.checkpoint.protocol_pins
            ):
                raise PermissionError("operation is not pinned to workflow")
            event = normalized_event
            if (
                event.provider_integration_id
                != operation.provider_integration_id
                or event.protocol_schema_hash
                != operation.protocol_snapshot.schema_hash
                or (
                    event.external_job_id is None
                    and event.client_reference is None
                )
                or (
                    event.external_job_id is not None
                    and event.external_job_id != operation.external_job_id
                )
                or (
                    event.client_reference is not None
                    and event.client_reference != operation.correlation_id
                )
            ):
                raise PermissionError(
                    "event protocol/provider/correlation mismatch"
                )
            if record.state == WorkflowState.CLOSED:
                return record
            if not await self.operations.accept_event(operation, event, tx):
                return record
            if event.inbox_event_id in bundle.observed_events:
                raise WorkflowConflict(
                    "operation adapter failed durable inbox dedupe"
                )
            candidate = advance(
                bundle, self.clock, last_applied_event_id=event.inbox_event_id
            )
            candidate = candidate.model_copy(
                update={
                    "observed_events": bundle.observed_events
                    + (event.inbox_event_id,),
                }
            )
            checkpoint_ref = await self.runtime.persist_checkpoint(
                scope, record.workflow_id, candidate.checkpoint, tx
            )
            candidate = candidate.model_copy(
                update={
                    "workflow": candidate.workflow.model_copy(
                        update={
                            "checkpoint_ref": checkpoint_ref,
                        }
                    ),
                }
            )
            if not await self.repository.save(candidate, record.revision, tx):
                raise WorkflowConflict("event revision conflict")
            await self.events.write(
                candidate.workflow,
                "operation.status_changed",
                {
                    "operation_type": operation.protocol_snapshot.protocol_id,
                    "status_schema": (
                        operation.protocol_snapshot.protocol_version  # Pin.
                    ),
                    "status": event.normalized_status,
                    "external_reference": operation.external_job_id,
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
            )
            await self.enqueue_trigger(scope, trigger.model_dump(), tx)
            return candidate.workflow

        return await self._transaction(uow, apply)

    async def close(self, scope, actor, audience, command, uow=None):
        command = parse_model(CloseInput, command)
        if (
            command.external_user_id != audience.external_user_id
            or command.external_ticket_id != audience.external_ticket_id
            or command.external_conversation_id
            != audience.external_conversation_id
        ):
            raise PermissionError("close audience mismatch")

        async def close(tx):
            bundle = await self.repository.load(scope, command.workflow_id, tx)
            record = require_binding(bundle, scope, audience)
            await self.authorization.authorize(
                scope, actor, audience, "close", tx
            )
            if record.revision != command.expected_revision:
                raise WorkflowConflict("close revision conflict")
            # Ingress already resolves exact command retries from the ledger.
            # Every new command must satisfy CAS, including on closed state.
            if record.state == WorkflowState.CLOSED:
                return record
            if (
                bundle.checkpoint.pending_approval_ids
                and not command.stop_tracking_only
            ):
                raise WorkflowConflict(
                    "pending approval must be resolved before close"
                )
            pending = [
                await self.operations.is_pending(
                    await self.operations.get(scope, ref, tx)
                )
                for ref in bundle.checkpoint.operation_refs
            ]
            if any(pending) and not command.stop_tracking_only:
                raise WorkflowConflict(
                    "pending operation requires stop_tracking_only"
                )
            if (
                record.state
                not in {
                    WorkflowState.AWAITING_CONFIRMATION,
                    WorkflowState.CLOSED,
                }
                and not command.stop_tracking_only
            ):
                raise WorkflowConflict(
                    "explicit close requires completion confirmation"
                )
            candidate = advance(
                bundle,
                self.clock,
                state=WorkflowState.CLOSED,
                pending_waits=(),
            )
            checkpoint_data = candidate.checkpoint.model_dump()
            # Consent refs remain as evidence. Close grants neither approval
            # nor provider cancellation; closed-state guards block late turns.
            checkpoint_data.update(
                pending_task_ids=(), pending_question_ids=()
            )
            checkpoint = WorkflowCheckpoint.model_validate(checkpoint_data)
            ref = await self.runtime.persist_checkpoint(
                scope, record.workflow_id, checkpoint, tx
            )
            candidate = candidate.model_copy(
                update={
                    "checkpoint": checkpoint,
                    "workflow": candidate.workflow.model_copy(
                        update={"checkpoint_ref": ref}
                    ),
                }
            )
            if not await self.repository.save(candidate, record.revision, tx):
                raise WorkflowConflict("close revision conflict")
            await self.events.write(
                candidate.workflow,
                "workflow.closed",
                {
                    "state": "closed",
                    "revision": candidate.workflow.revision,
                    "reason": command.reason,
                    "closed_at": self.clock().isoformat(),
                },
                tx,
                command.external_request_id,
            )
            return candidate.workflow

        return await self._transaction(uow, close)
