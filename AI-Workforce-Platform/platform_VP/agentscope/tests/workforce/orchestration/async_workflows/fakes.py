"""In-memory ports for PHH Phase-B orchestration tests only."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from agentscope.app.workforce.contracts import (
    ActorContext,
    AssistantMessage,
    AsyncProtocolSnapshotRef,
    ConversationSnapshot,
    EventHistoryPage,
    ExternalCreationStatus,
    ExternalOperation,
    InboundRequest,
    PartnerAudience,
    PartnerOperation,
    RequestResult,
    RequestStatus,
    ResolvedPartnerRoute,
    Scope,
    WorkflowProjection,
    WorkflowRecord,
    WorkflowState,
)
from agentscope.app.workforce.orchestration._ingress import RequestView
from agentscope.app.workforce.orchestration.partner_events import (
    ConversationAccess,
    ConversationEventService,
    EventCursorExpired,
    PublicEventWriter,
)
from agentscope.app.workforce.orchestration.workflows import (
    TurnDecision,
    WorkflowAggregate,
    WorkflowConflict,
    WorkflowContinuation,
    WorkflowLease,
    WorkflowPattern,
    WorkflowReservation,
    WorkflowService,
)
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    AgentVersionPin,
    CommandClaimResult,
    PinnedRuntimeContext,
    RuntimeTurnResult,
    UsedBudget,
    WorkflowCheckpoint,
)

NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)
SCOPE = Scope(
    tenant_id="tenant-1",
    domain_id="domain-1",
    area_id="area-1",
    manager_account_id="manager-1",
)


def customer_actor(user: str = "resident-1") -> ActorContext:
    return ActorContext(
        kind="partner",
        actor_id=f"customer-{user}",
        partner_client_id="partner-1",
        credential_id="credential-customer",
        credential_purpose="customer_api",
        external_user_id=user,
        authentication_source="phase-b-test",
    )


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int = 1) -> None:
        self.value += timedelta(seconds=seconds)


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"generated-{self.value}"


@dataclass
class Store:
    workflows: dict[str, WorkflowAggregate] = field(default_factory=dict)
    bindings: dict[tuple[str, ...], str] = field(default_factory=dict)
    inputs: dict[tuple[str, str, str], str] = field(default_factory=dict)
    jobs: dict[str, dict] = field(default_factory=dict)
    events: dict[str, list] = field(default_factory=lambda: defaultdict(list))
    checkpoints: dict[str, PinnedRuntimeContext] = field(default_factory=dict)
    command_ledger: dict[tuple[str, str], dict] = field(default_factory=dict)
    requests: dict[str, InboundRequest] = field(default_factory=dict)
    results: dict[str, RequestResult] = field(default_factory=dict)
    operations: dict[str, ExternalOperation] = field(default_factory=dict)
    leases: dict[str, WorkflowLease] = field(default_factory=dict)
    lease_fences: dict[str, int] = field(default_factory=dict)


class FakeUnitOfWork:
    def __init__(self, factory: FakeUnitOfWorkFactory) -> None:
        self.factory = factory
        self.state = deepcopy(factory.store)
        self.callbacks = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is not None or not self.committed:
            await self.rollback()
        return False

    async def commit(self) -> None:
        if self.committed:
            raise RuntimeError("unit of work already committed")
        self.factory.store = self.state
        self.committed = True
        for callback in self.callbacks:
            result = callback()
            if hasattr(result, "__await__"):
                await result

    async def rollback(self) -> None:
        self.callbacks.clear()

    def add_after_commit(self, callback) -> None:
        self.callbacks.append(callback)


class FakeUnitOfWorkFactory:
    def __init__(self) -> None:
        self.store = Store()

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self)


def state_for(factory: FakeUnitOfWorkFactory, uow=None) -> Store:
    return uow.state if uow is not None else factory.store


def binding_keys(
    scope: Scope, audience: PartnerAudience
) -> tuple[tuple[str, ...], ...]:
    prefix = (
        scope.tenant_id,
        scope.domain_id,
        scope.area_id,
        scope.manager_account_id,
        audience.partner_client_id,
        audience.external_user_id,
    )
    conversation = prefix + (
        "conversation",
        audience.external_conversation_id,
    )
    if audience.external_ticket_id is None:
        return (conversation,)
    return (
        conversation,
        prefix + ("ticket", audience.external_ticket_id),
    )


class FakeWorkflowRepository:
    def __init__(self, factory: FakeUnitOfWorkFactory, clock: Clock) -> None:
        self.factory = factory
        self.clock = clock

    async def reserve(self, aggregate, uow):
        state = state_for(self.factory, uow)
        keys = binding_keys(
            aggregate.workflow.scope,
            aggregate.workflow.audience,
        )
        existing_ids = {
            state.bindings[key]
            for key in keys
            if key in state.bindings
        }
        if existing_ids:
            if len(existing_ids) != 1:
                raise WorkflowConflict("binding indexes disagree")
            existing = existing_ids.pop()
            return WorkflowReservation(
                aggregate=state.workflows[existing], created=False
            )
        for key in keys:
            state.bindings[key] = aggregate.workflow.workflow_id
        state.workflows[aggregate.workflow.workflow_id] = aggregate
        return WorkflowReservation(aggregate=aggregate, created=True)

    async def load(self, scope, workflow_id, uow=None):
        aggregate = state_for(self.factory, uow).workflows[workflow_id]
        if aggregate.workflow.scope != scope:
            raise PermissionError("workflow scope mismatch")
        return aggregate

    async def save(self, aggregate, expected_revision, uow, lease=None):
        state = state_for(self.factory, uow)
        current = state.workflows.get(aggregate.workflow.workflow_id)
        if current is None or current.workflow.revision != expected_revision:
            return False
        if lease is not None and not await self.lease_is_current(
            aggregate.workflow.scope, lease
        ):
            return False
        state.workflows[aggregate.workflow.workflow_id] = aggregate
        return True

    async def record_input(self, scope, workflow_id, cause, text, uow):
        state = state_for(self.factory, uow)
        await self.load(scope, workflow_id, uow)
        key = (workflow_id, cause[0], cause[1])
        if key in state.inputs:
            return False
        state.inputs[key] = text
        return True

    async def acquire_lease(self, scope, workflow_id, worker_id, duration):
        state = self.factory.store
        await self.load(scope, workflow_id)
        existing = state.leases.get(workflow_id)
        if existing is not None and existing.expires_at > self.clock():
            return None
        fence = state.lease_fences.get(workflow_id, 0) + 1
        state.lease_fences[workflow_id] = fence
        lease = WorkflowLease(
            workflow_id=workflow_id,
            owner=worker_id,
            fencing_token=fence,
            expires_at=self.clock() + duration,
        )
        state.leases[workflow_id] = lease
        return lease

    async def lease_is_current(self, scope, lease, uow=None):
        await self.load(scope, lease.workflow_id, uow)
        current = self.factory.store.leases.get(lease.workflow_id)
        return current == lease and lease.expires_at > self.clock()

    async def release_lease(self, scope, lease):
        await self.load(scope, lease.workflow_id)
        if self.factory.store.leases.get(lease.workflow_id) == lease:
            self.factory.store.leases.pop(lease.workflow_id, None)


class FakeBootstrap:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.pattern = WorkflowPattern.INTERACTIVE
        self.published_read_only = False
        self.operation_refs: tuple[str, ...] = ()
        self.protocol_pins: tuple[AsyncProtocolSnapshotRef, ...] = ()
        self.count = 0

    async def prepare(self, scope, actor, audience, message, uow):
        self.count += 1
        suffix = str(self.count)
        workflow_id = f"workflow-{suffix}"
        workflow = WorkflowRecord(
            workflow_id=workflow_id,
            scope=scope,
            audience=audience,
            conversation_id=f"conversation-{suffix}",
            ticket_id=f"ticket-{suffix}",
            route_id="route-1",
            route_revision=1,
            state=WorkflowState.ACCEPTED,
            revision=1,
            group_id=f"group-{suffix}",
            version_pins=("agent-version-1",),
            created_at=self.clock(),
            updated_at=self.clock(),
        )
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            state_revision=1,
            session_refs=(f"session-{suffix}",),
            agent_version_pins=(
                AgentVersionPin(
                    agent_id="agent-1", version_id="agent-version-1"
                ),
            ),
            protocol_pins=self.protocol_pins,
            shared_state_ref=f"shared-state-{suffix}",
            operation_refs=self.operation_refs,
            used_budget=UsedBudget(
                model_turns=0, tool_calls=0, input_tokens=0, output_tokens=0
            ),
        )
        return WorkflowAggregate(
            workflow=workflow,
            checkpoint=checkpoint,
            pattern=self.pattern,
            published_read_only=self.published_read_only,
        )


class FakeAuthorization:
    def __init__(self) -> None:
        self.delivery_allowed = True
        self.revoked = False

    async def authorize(self, scope, actor, audience, operation, uow=None):
        if self.revoked:
            raise PermissionError("grant revoked")
        if actor is not None and (
            actor.partner_client_id != audience.partner_client_id
            or actor.external_user_id != audience.external_user_id
        ):
            raise PermissionError("actor audience mismatch")

    async def authorize_trigger(self, aggregate, trigger, uow=None):
        if self.revoked:
            raise PermissionError("grant revoked")
        if aggregate.workflow.workflow_id != trigger.workflow_id:
            raise PermissionError("trigger workflow mismatch")

    async def can_publish_external_event(self, aggregate, event, uow):
        return self.delivery_allowed and not self.revoked


class FakeJobs:
    def __init__(self, factory: FakeUnitOfWorkFactory) -> None:
        self.factory = factory

    async def enqueue(
        self,
        scope,
        job_type,
        payload,
        idempotency_key,
        uow=None,
        not_before=None,
    ):
        state = state_for(self.factory, uow)
        if idempotency_key not in state.jobs:
            state.jobs[idempotency_key] = {
                "job_id": f"job-{len(state.jobs) + 1}",
                "scope": scope,
                "job_type": job_type,
                "payload": deepcopy(payload),
            }
        return state.jobs[idempotency_key]["job_id"]


class FakeOperationReader:
    def __init__(self, factory: FakeUnitOfWorkFactory) -> None:
        self.factory = factory

    async def get(self, scope, operation_id, uow=None):
        operation = state_for(self.factory, uow).operations[operation_id]
        if operation.scope != scope:
            raise PermissionError("operation scope mismatch")
        return operation

    async def is_pending(self, operation, uow=None):
        return operation.job_status in {None, "pending", "assigned", "moving"}


class FakeRuntime:
    def __init__(self, factory: FakeUnitOfWorkFactory, clock: Clock) -> None:
        self.factory = factory
        self.clock = clock
        self.next_state = WorkflowState.AWAITING_CONFIRMATION
        self.message_text = "Đã xử lý yêu cầu"
        self.before_decision = None
        self.invocations = 0

    async def persist_checkpoint(
        self, scope, workflow_id, checkpoint, uow=None
    ):
        if checkpoint.workflow_id != workflow_id:
            raise PermissionError("checkpoint workflow mismatch")
        state = state_for(self.factory, uow)
        ref = f"checkpoint-{workflow_id}-{checkpoint.state_revision}"
        workflow = state.workflows.get(workflow_id)
        if workflow is None:
            # Initial save happens before replacing checkpoint_ref.
            workflow = next(
                item for item in state.workflows.values()
                if item.workflow.workflow_id == workflow_id
            )
        state.checkpoints[ref] = PinnedRuntimeContext(
            workflow=workflow.workflow.model_copy(
                update={
                    "checkpoint_ref": ref,
                    "revision": checkpoint.state_revision,
                }
            ),
            checkpoint=checkpoint,
        )
        return ref

    async def load_pinned_context(self, scope, checkpoint):
        context = self.factory.store.checkpoints[checkpoint]
        aggregate = self.factory.store.workflows[context.workflow.workflow_id]
        return PinnedRuntimeContext(
            workflow=aggregate.workflow,
            checkpoint=aggregate.checkpoint,
        )

    async def invoke_turn(self, scope, trigger, context, guard):
        self.invocations += 1
        if self.before_decision is not None:
            await self.before_decision(context, guard)
        await guard.check("read")
        checkpoint = context.checkpoint.model_copy(
            update={
                "state_revision": context.workflow.revision + 1,
                "pending_task_ids": (),
                "pending_question_ids": (),
                "used_budget": context.checkpoint.used_budget.model_copy(
                    update={
                        "model_turns": (
                            context.checkpoint.used_budget.model_turns + 1
                        )
                    }
                ),
            }
        )
        result = RequestResult(
            messages=(
                AssistantMessage(
                    message_id=f"message-{self.invocations}",
                    workflow_id=context.workflow.workflow_id,
                    text=self.message_text,
                    created_at=self.clock(),
                ),
            )
        )
        candidate = RuntimeTurnResult(
            trigger_id=trigger["trigger_id"],
            expected_state_revision=context.workflow.revision,
            checkpoint=checkpoint,
            result=result,
        )
        return TurnDecision(candidate=candidate, next_state=self.next_state)


class FakeEventSignals:
    def __init__(self) -> None:
        self.notifications: list[tuple] = []
        self.waiters: dict[tuple, asyncio.Event] = defaultdict(asyncio.Event)

    async def notify_after_commit(self, scope, conversation_id, sequence):
        self.notifications.append((scope, conversation_id, sequence))
        self.waiters[(scope, conversation_id)].set()

    async def wait_for_signal(self, scope, conversation_id, timeout):
        event = self.waiters[(scope, conversation_id)]
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except TimeoutError:
            return None
        event.clear()
        values = [
            item[2]
            for item in self.notifications
            if item[0] == scope and item[1] == conversation_id
        ]
        return values[-1] if values else None

    async def health(self):
        return True


class FakeEventRepository:
    def __init__(self, factory: FakeUnitOfWorkFactory) -> None:
        self.factory = factory

    async def access(self, conversation_id, uow=None):
        state = state_for(self.factory, uow)
        matches = [
            item.workflow
            for item in state.workflows.values()
            if item.workflow.conversation_id == conversation_id
        ]
        if len(matches) != 1:
            raise KeyError("conversation is not uniquely bound")
        workflow = matches[0]
        return ConversationAccess(
            scope=workflow.scope,
            audience=workflow.audience,
            conversation_id=workflow.conversation_id,
            workflow_id=workflow.workflow_id,
            ticket_id=workflow.ticket_id,
        )

    async def append(self, access, event, uow):
        state = state_for(self.factory, uow)
        events = state.events[access.conversation_id]
        duplicate = next(
            (item for item in events if item.event_id == event.event_id), None
        )
        if duplicate is not None:
            if duplicate.model_dump(exclude={"sequence"}) != event.model_dump(
                exclude={"sequence"}
            ):
                raise WorkflowConflict("event id conflict")
            return duplicate
        stored = event.model_copy(update={"sequence": len(events) + 1})
        events.append(stored)
        return stored

    async def list_after(self, access, cursor, limit):
        events = self.factory.store.events[access.conversation_id]
        start = 0
        if cursor is not None:
            indexes = [
                index
                for index, item in enumerate(events)
                if item.event_id == cursor
            ]
            if not indexes:
                raise EventCursorExpired(cursor)
            start = indexes[0] + 1
        items = tuple(events[start : start + limit])
        return EventHistoryPage(
            items=items,
            next_cursor=items[-1].event_id if items else cursor,
            has_more=start + len(items) < len(events),
        )

    async def snapshot(self, access):
        state = self.factory.store
        aggregate = state.workflows[access.workflow_id]
        workflow = aggregate.workflow
        events = state.events[access.conversation_id]
        messages = tuple(
            AssistantMessage(
                message_id=item.payload["message_id"],
                workflow_id=workflow.workflow_id,
                text=item.payload["text"],
                created_at=item.occurred_at,
            )
            for item in events
            if item.event_type == "assistant.message"
        )
        return ConversationSnapshot(
            conversation_id=workflow.conversation_id,
            external_conversation_id=(
                workflow.audience.external_conversation_id
            ),
            external_user_id=workflow.audience.external_user_id,
            workflows=(
                WorkflowProjection(
                    workflow_id=workflow.workflow_id,
                    external_ticket_id=workflow.audience.external_ticket_id,
                    ticket_id=workflow.ticket_id,
                    state=workflow.state,
                    next_action={
                        "accepted": "watch_request",
                        "active": "watch_request",
                        "waiting_external_event": "watch_events",
                        "awaiting_user": "submit_reply",
                        "awaiting_approval": "submit_approval",
                        "awaiting_confirmation": "confirm_close",
                        "needs_attention": "resolve_attention",
                        "blocked_authorization": "resolve_attention",
                        "blocked_route_changed": "resolve_attention",
                        "closed": "none",
                    }[workflow.state.value],
                    revision=workflow.revision,
                ),
            ),
            messages=messages,
            pending_approvals=tuple(
                {
                    "workflow_id": workflow.workflow_id,
                    "approval_id": approval_id,
                    "status": "pending",
                }
                for approval_id in aggregate.checkpoint.pending_approval_ids
            ),
            snapshot_cursor=events[-1].event_id if events else None,
        )


class FakeCommands:
    def __init__(self, factory: FakeUnitOfWorkFactory, clock: Clock) -> None:
        self.factory = factory
        self.clock = clock

    async def read_existing(
        self,
        actor,
        external_request_id,
        command_kind,
        target_ref,
        payload_hash,
    ):
        entry = self.factory.store.command_ledger.get(
            (actor.partner_client_id, external_request_id)
        )
        if entry is None:
            return None
        if entry["fingerprint"] != (command_kind, target_ref, payload_hash):
            raise WorkflowConflict(
                "idempotency key reused with other content"
            )
        return CommandClaimResult(
            request_id=entry["request_id"],
            is_new=False,
            status=entry["status"],
            result=self.factory.store.results.get(entry["request_id"]),
        )

    async def claim_or_read(
        self,
        actor,
        external_request_id,
        command_kind,
        target_ref,
        payload_hash,
        uow=None,
    ):
        state = state_for(self.factory, uow)
        key = (actor.partner_client_id, external_request_id)
        existing = state.command_ledger.get(key)
        if existing is not None:
            if existing["fingerprint"] != (
                command_kind,
                target_ref,
                payload_hash,
            ):
                raise WorkflowConflict(
                    "idempotency key reused with other content"
                )
            return CommandClaimResult(
                request_id=existing["request_id"],
                is_new=False,
                status=existing["status"],
                result=state.results.get(existing["request_id"]),
            )
        request_id = f"request-{external_request_id}"
        state.command_ledger[key] = {
            "request_id": request_id,
            "fingerprint": (command_kind, target_ref, payload_hash),
            "status": RequestStatus.ACCEPTED,
        }
        return CommandClaimResult(
            request_id=request_id,
            is_new=True,
            status=RequestStatus.ACCEPTED,
        )

    async def record_result(self, request_id, result, uow=None):
        state = state_for(self.factory, uow)
        state.results[request_id] = result
        request = state.requests.get(request_id)
        if request is not None:
            state.requests[request_id] = request.model_copy(
                update={
                    "status": RequestStatus.COMPLETED,
                    "completed_at": self.clock(),
                }
            )
        for entry in state.command_ledger.values():
            if entry["request_id"] == request_id:
                entry["status"] = RequestStatus.COMPLETED


class FakeRequests:
    def __init__(self, factory: FakeUnitOfWorkFactory) -> None:
        self.factory = factory

    async def attach(self, request, uow):
        state_for(self.factory, uow).requests[request.request_id] = request

    async def read(self, actor, request_id, external_user_id, uow=None):
        state = state_for(self.factory, uow)
        request = state.requests[request_id]
        if request.audience.external_user_id != external_user_id:
            raise PermissionError("request user mismatch")
        return RequestView(
            request=request,
            result=state.results.get(request_id),
        )

    async def resolve_workflow_request(
        self, actor, workflow_id, external_user_id, uow=None
    ):
        matches = [
            item
            for item in state_for(self.factory, uow).requests.values()
            if item.workflow_id == workflow_id
            and item.audience.external_user_id == external_user_id
        ]
        if not matches:
            raise KeyError("workflow request not found")
        return sorted(matches, key=lambda item: item.accepted_at)[0]


class FakeRouting:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.revoked = False

    def route(self):
        return ResolvedPartnerRoute(
            scope=SCOPE,
            route_id="route-1",
            route_revision=1,
            grant_operations=tuple(PartnerOperation),
            membership_revision=1,
            resolved_at=self.clock(),
        )

    async def resolve(self, actor, routing_input):
        if (
            self.revoked
            or routing_input["external_management_ref"] != "tower-a"
        ):
            raise PermissionError("route not active")
        return self.route()

    async def revalidate(
        self,
        scope,
        route_id,
        expected_revision,
        actor,
        audience,
        operation,
        uow=None,
    ):
        if (
            self.revoked
            or scope != SCOPE
            or route_id != "route-1"
            or expected_revision != 1
            or actor.partner_client_id != audience.partner_client_id
            or actor.external_user_id != audience.external_user_id
        ):
            raise PermissionError("route revalidation failed")
        return self.route()


class FakeIdentity:
    async def check_scope_active(self, scope, uow=None):
        if scope != SCOPE:
            raise PermissionError("scope inactive")


class FakeCompletionSignals:
    def __init__(self) -> None:
        self.notifications = []

    async def notify_after_commit(self, scope, request_id):
        self.notifications.append((scope, request_id))

    async def wait_for_completion(self, scope, request_id, timeout):
        return (scope, request_id) in self.notifications

    async def health(self):
        return True


class Harness:
    def __init__(self) -> None:
        self.clock = Clock()
        self.ids = Ids()
        self.uows = FakeUnitOfWorkFactory()
        self.repository = FakeWorkflowRepository(self.uows, self.clock)
        self.bootstrap = FakeBootstrap(self.clock)
        self.authorization = FakeAuthorization()
        self.jobs = FakeJobs(self.uows)
        self.operations = FakeOperationReader(self.uows)
        self.runtime = FakeRuntime(self.uows, self.clock)
        self.event_signals = FakeEventSignals()
        self.event_repository = FakeEventRepository(self.uows)
        self.event_service = ConversationEventService(
            self.event_repository,
            self.authorization,
            self.event_signals,
            self.uows,
            heartbeat_seconds=0.01,
        )
        self.events = PublicEventWriter(
            self.event_service, self.clock, self.ids
        )
        self.commands = FakeCommands(self.uows, self.clock)
        self.requests = FakeRequests(self.uows)
        self.routing = FakeRouting(self.clock)
        self.identity = FakeIdentity()
        self.completion_signals = FakeCompletionSignals()
        self.workflows = WorkflowService(
            self.repository,
            self.bootstrap,
            self.authorization,
            self.operations,
            self.jobs,
            self.events,
            self.runtime,
            self.uows,
            self.clock,
            self.ids,
        )
        self.continuation = WorkflowContinuation(
            self.workflows, self.commands, self.completion_signals
        )

    def audience(self, ticket: str, conversation: str) -> PartnerAudience:
        return PartnerAudience(
            partner_client_id="partner-1",
            external_user_id="resident-1",
            external_ticket_id=ticket,
            external_conversation_id=conversation,
            residence_id="residence-1",
        )

    def add_operation(
        self, workflow_id: str, operation_id: str = "operation-1"
    ):
        aggregate = self.uows.store.workflows[workflow_id]
        protocol = AsyncProtocolSnapshotRef(
            protocol_id="repair-status",
            protocol_version="1",
            schema_hash="schema-hash-1",
            tool_version_id="repair-tool-v1",
            provider_integration_id="provider-1",
            capabilities=("receive_status",),
        )
        operation = ExternalOperation(
            operation_id=operation_id,
            scope=SCOPE,
            audience=aggregate.workflow.audience,
            workflow_id=workflow_id,
            ticket_id=aggregate.workflow.ticket_id,
            conversation_id=aggregate.workflow.conversation_id,
            call_id="call-1",
            provider_integration_id="provider-1",
            protocol_snapshot=protocol,
            correlation_id="correlation-1",
            external_job_id="external-job-1",
            creation_status=ExternalCreationStatus.SUCCEEDED,
            job_status="assigned",
            revision=1,
        )
        checkpoint = aggregate.checkpoint.model_copy(
            update={
                "operation_refs": (operation_id,),
                "protocol_pins": (protocol,),
            }
        )
        updated = aggregate.model_copy(update={"checkpoint": checkpoint})
        self.uows.store.workflows[workflow_id] = updated
        self.uows.store.operations[operation_id] = operation
        return operation

