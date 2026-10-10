"""Test-only atomic store, clock, runtime, operation and advisory signal."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from agentscope.app.workforce.contracts import (
    ActorContext,
    AssistantMessage,
    ConversationSnapshot,
    EventHistoryPage,
    ExternalOperation,
    NormalizedJobEvent,
    PartnerAudience,
    Scope,
    WorkflowProjection,
    WorkflowRecord,
)
from agentscope.app.workforce.orchestration.partner_events import (
    ConversationAccess,
    ConversationEventService,
    EventCursorExpired,
    PublicEventWriter,
)
from agentscope.app.workforce.orchestration.workflows import (
    BindingReservation,
    TurnLease,
    WorkflowBundle,
    WorkflowConflict,
    WorkflowContinuation,
    WorkflowService,
    next_action,
)
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    PinnedRuntimeContext,
    WorkflowCheckpoint,
)
from fixtures import phase_a_samples


class Clock:
    now = datetime(2026, 10, 10, 9, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def tick(self, seconds):
        self.now += timedelta(seconds=seconds)


class Store:
    def __init__(self):
        self.data = dict(
            workflows={},
            inputs={},
            jobs={},
            events={},
            checkpoints={},
            results={},
            operations={},
            inbox={},
            requests={},
            claims={},
        )
        self.version = 0
        self.fail_commit = False
        self.fail_event = False
        self.leases = {}
        self.fences = {}
        self.commits = 0


class Uow:
    def __init__(self, store):
        self.store = store
        self.version = store.version
        self.data = deepcopy(store.data)
        self.callbacks = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if not self.committed:
            await self.rollback()

    def add_after_commit(self, callback):
        self.callbacks.append(callback)

    async def commit(self):
        if self.store.fail_commit or self.version != self.store.version:
            raise WorkflowConflict("fake atomic commit failed")
        self.store.data = self.data
        self.store.version += 1
        self.store.commits += 1
        self.committed = True
        for callback in self.callbacks:
            await callback()

    async def rollback(self):
        self.callbacks.clear()


def view(store, uow):
    return uow.data if uow else store.data


class Repository:
    def __init__(self, store, clock):
        self.store, self.clock = store, clock

    async def create_unique(self, bundle, uow):
        wf = bundle.workflow
        for existing in uow.data["workflows"].values():
            old = existing.workflow
            if (
                old.scope == wf.scope
                and old.audience.partner_client_id
                == wf.audience.partner_client_id
            ):
                if (
                    old.audience.external_ticket_id is not None
                    and old.audience.external_ticket_id
                    == wf.audience.external_ticket_id
                    or old.audience.external_conversation_id
                    == wf.audience.external_conversation_id
                ):
                    if old.audience != wf.audience:
                        raise WorkflowConflict("binding already reserved")
                    return BindingReservation(bundle=existing, is_new=False)
        uow.data["workflows"][wf.workflow_id] = bundle
        return BindingReservation(bundle=bundle, is_new=True)

    async def load(self, scope, workflow_id, uow=None):
        bundle = view(self.store, uow)["workflows"][workflow_id]
        if bundle.workflow.scope != scope:
            raise PermissionError("scope mismatch")
        return deepcopy(bundle)

    async def save(self, bundle, expected_revision, uow, lease=None):
        current = await self.load(
            bundle.workflow.scope, bundle.workflow.workflow_id, uow
        )
        committed = self.store.data["workflows"].get(
            bundle.workflow.workflow_id, current
        )
        if (
            current.workflow.state == "closed"
            or committed.workflow.revision != expected_revision
        ):
            return False
        if lease is not None and not await self.valid_lease(
            bundle.workflow.scope, lease
        ):
            return False
        uow.data["workflows"][bundle.workflow.workflow_id] = bundle
        return True

    async def record_input(self, scope, workflow_id, cause_key, text, uow):
        key = (repr(scope), workflow_id, cause_key)
        old = uow.data["inputs"].get(key)
        if old is not None and old != text:
            raise WorkflowConflict("idempotency content conflict")
        uow.data["inputs"][key] = text
        return old is None

    async def claim(self, scope, workflow_id, owner, duration):
        bundle = await self.load(scope, workflow_id)
        for other_id, other in self.store.leases.items():
            if other.expires_at > self.clock():
                other_bundle = self.store.data["workflows"][other_id]
                if set(other_bundle.checkpoint.session_refs) & set(
                    bundle.checkpoint.session_refs
                ):
                    return None
        fence = self.store.fences.get(workflow_id, 0) + 1
        lease = TurnLease(
            workflow_id=workflow_id,
            owner=owner,
            fence=fence,
            expires_at=self.clock() + duration,
        )
        self.store.fences[workflow_id] = fence
        self.store.leases[workflow_id] = lease
        return lease

    async def valid_lease(self, scope, lease):
        await self.load(scope, lease.workflow_id)
        return (
            self.store.leases.get(lease.workflow_id) == lease
            and lease.expires_at > self.clock()
        )

    async def release(self, scope, lease):
        if self.store.leases.get(lease.workflow_id) == lease:
            del self.store.leases[lease.workflow_id]


class Authorization:
    def __init__(self, store):
        self.store = store
        self.revoked = False
        self.calls = []

    async def authorize(self, scope, actor, audience, operation, uow=None):
        self.calls.append(operation)
        if self.revoked or scope != SCOPE:
            raise PermissionError("grant revoked")
        if actor is not None:
            if (
                actor.kind != "partner"
                or actor.partner_client_id != audience.partner_client_id
                or actor.external_user_id != audience.external_user_id
                or actor.credential_purpose != "customer_api"
            ):
                raise PermissionError("actor audience/purpose mismatch")

    async def authorize_trigger(self, bundle, trigger, uow=None):
        await self.authorize(
            bundle.workflow.scope,
            None,
            bundle.workflow.audience,
            "continue",
            uow,
        )
        data = view(self.store, uow)
        cause = trigger.cause
        if cause.kind == "request":
            if (
                repr(bundle.workflow.scope),
                trigger.workflow_id,
                ("request", cause.request_id),
            ) not in data["inputs"]:
                raise PermissionError("request not bound")
        elif cause.kind == "external_event":
            if cause.cause_event_id not in bundle.observed_events:
                raise PermissionError("event not applied")
        elif cause.kind == "approval":
            if cause.request_id != "verified-approval-request":
                raise PermissionError("approval not verified")
        elif cause.timer_id != "verified-timer":
            raise PermissionError("timer not verified")


class Bootstrap:
    def __init__(self):
        self.count = 0
        self.pattern = "interactive"

    async def prepare(self, scope, actor, audience, message, uow):
        self.count += 1
        suffix = str(self.count)
        samples = phase_a_samples()["models"]
        wf = samples["WorkflowRecord"]
        cp = samples["WorkflowCheckpoint"]
        workflow_id = "workflow-" + suffix
        wf.update(
            workflow_id=workflow_id,
            scope=scope,
            audience=audience,
            conversation_id="conversation-" + suffix,
            group_id="group-" + suffix,
            checkpoint_ref="checkpoint-" + suffix + "-1",
            state="accepted",
        )
        cp.update(
            workflow_id=workflow_id,
            session_refs=["session-" + suffix],
            operation_refs=[],
        )
        return WorkflowBundle(
            workflow=WorkflowRecord.model_validate(wf),
            checkpoint=WorkflowCheckpoint.model_validate(cp),
            pattern=self.pattern,
            published_read_only=self.pattern == "response_only",
        )


class Signals:
    def __init__(self):
        self.notifications = []
        self.drop = False
        self.hook = None

    async def notify_after_commit(self, *args):
        if self.drop:
            raise ConnectionError("signal lost")
        self.notifications.append(args)

    async def wait_for_signal(self, scope, conversation_id, timeout):
        if self.hook:
            hook, self.hook = self.hook, None
            await hook()
        return None

    async def health(self):
        return not self.drop

    async def wait_for_completion(self, scope, request_id, timeout):
        return await self.wait_for_signal(scope, request_id, timeout)


class EventRepo:
    def __init__(self, store):
        self.store = store
        self.bad_page = None
        self.bad_snapshot = None

    async def access(self, conversation_id, uow=None):
        for bundle in view(self.store, uow)["workflows"].values():
            wf = bundle.workflow
            if wf.conversation_id == conversation_id:
                return ConversationAccess(
                    scope=wf.scope,
                    audience=wf.audience,
                    conversation_id=conversation_id,
                    workflow_id=wf.workflow_id,
                    ticket_id=wf.ticket_id,
                )
        raise KeyError(conversation_id)

    async def append(self, access, event, uow):
        if self.store.fail_event:
            raise RuntimeError("fake event persistence failure")
        items = uow.data["events"].setdefault(access.conversation_id, [])
        stored = event.model_copy(update={"sequence": len(items) + 1})
        items.append(stored)
        return stored

    async def list_after(self, access, cursor, limit):
        if self.bad_page is not None:
            return self.bad_page
        items = self.store.data["events"].get(access.conversation_id, [])
        index = 0
        if cursor is not None:
            matches = [i for i, e in enumerate(items) if e.event_id == cursor]
            if not matches:
                raise EventCursorExpired(cursor)
            index = matches[0] + 1
        page = items[index : index + limit]
        return EventHistoryPage(
            items=page,
            has_more=index + limit < len(items),
            next_cursor=page[-1].event_id if page else cursor,
        )

    async def snapshot(self, access):
        if self.bad_snapshot is not None:
            return self.bad_snapshot
        bundle = next(
            b
            for b in self.store.data["workflows"].values()
            if b.workflow.conversation_id == access.conversation_id
        )
        wf = bundle.workflow
        events = self.store.data["events"].get(access.conversation_id, [])
        messages = [
            AssistantMessage(
                message_id=e.payload["message_id"],
                workflow_id=e.workflow_id,
                text=e.payload["text"],
                created_at=e.occurred_at,
            )
            for e in events
            if e.event_type == "assistant.message"
        ]
        return ConversationSnapshot(
            conversation_id=access.conversation_id,
            external_user_id=access.audience.external_user_id,
            external_conversation_id=access.audience.external_conversation_id,
            workflows=(
                WorkflowProjection(
                    workflow_id=wf.workflow_id,
                    external_ticket_id=wf.audience.external_ticket_id,
                    state=wf.state,
                    next_action=next_action(wf.state),
                    revision=wf.revision,
                ),
            ),
            messages=messages,
            snapshot_cursor=events[-1].event_id if events else None,
        )


class Operations:
    def __init__(self, store):
        self.store = store
        self.pending = True

    async def get(self, scope, operation_id, uow=None):
        op = view(self.store, uow)["operations"][operation_id]
        if op.scope != scope:
            raise PermissionError("operation scope")
        return op

    async def is_pending(self, operation):
        return self.pending

    async def accept_event(self, operation, event, uow):
        old = uow.data["inbox"].get(event.inbox_event_id)
        if old:
            if old != event.source_hash:
                raise WorkflowConflict("inbox hash conflict")
            return False
        if (
            event.provider_version is not None
            and operation.last_provider_version is not None
            and event.provider_version <= operation.last_provider_version
        ):
            return False
        uow.data["inbox"][event.inbox_event_id] = event.source_hash
        uow.data["operations"][operation.operation_id] = operation.model_copy(
            update={
                "job_status": event.normalized_status,
                "last_provider_version": event.provider_version,
            }
        )
        return True


class Jobs:
    async def enqueue(
        self,
        scope,
        job_type,
        payload,
        idempotency_key,
        uow=None,
        not_before=None,
    ):
        key = (repr(scope), idempotency_key)
        if key not in uow.data["jobs"]:
            uow.data["jobs"][key] = dict(payload)
        return idempotency_key


class Runtime:
    def __init__(self, store):
        self.store, self.calls = store, []
        self.state = "awaiting_user"
        self.hook = None
        self.mutate = None

    async def persist_checkpoint(self, scope, workflow_id, checkpoint, uow):
        ref = f"checkpoint-{workflow_id}-{checkpoint.state_revision}"
        uow.data["checkpoints"][ref] = checkpoint
        return ref

    async def load_pinned_context(self, scope, ref):
        bundle = next(
            b
            for b in self.store.data["workflows"].values()
            if b.workflow.checkpoint_ref == ref
        )
        return PinnedRuntimeContext(
            workflow=bundle.workflow, checkpoint=bundle.checkpoint
        )

    async def invoke_turn(self, scope, trigger, checkpoint, execution_guard):
        self.calls.append((trigger, checkpoint))
        if self.hook:
            await self.hook(execution_guard)
        cp = checkpoint.checkpoint.model_dump(mode="json")
        cp["state_revision"] += 1
        cp["used_budget"]["model_turns"] += 1
        if trigger["cause"]["kind"] == "approval":
            cp["pending_approval_ids"] = []
        wf = checkpoint.workflow
        result = dict(
            candidate=dict(
                trigger_id=trigger["trigger_id"],
                expected_state_revision=wf.revision,
                checkpoint=cp,
                result=dict(
                    messages=[
                        dict(
                            message_id="message-" + trigger["trigger_id"],
                            workflow_id=wf.workflow_id,
                            text="Kết quả đã xử lý",
                            created_at="2026-10-10T09:00:00Z",
                        )
                    ],
                    data={},
                ),
            ),
            next_state=self.state,
        )
        if self.mutate:
            self.mutate(result)
        return result


class Commands:
    async def claim_or_read(
        self,
        actor,
        external_request_id,
        command_kind,
        target_ref,
        payload_hash,
        uow,
    ):
        from agentscope.app.workforce.orchestration.workflows.phase_a import (
            CommandClaimResult,
        )

        key = (SCOPE.tenant_id, actor.partner_client_id, external_request_id)
        existing = uow.data["claims"].get(key)
        if existing:
            if existing[0] != (command_kind, target_ref, payload_hash):
                raise WorkflowConflict("command idempotency conflict")
            request_id = existing[1]
            result = uow.data["results"].get(request_id)
            return CommandClaimResult(
                request_id=request_id,
                is_new=False,
                status="completed" if result else "accepted",
                result=result,
            )
        request_id = "request-" + external_request_id
        uow.data["claims"][key] = (
            (command_kind, target_ref, payload_hash),
            request_id,
        )
        return CommandClaimResult(
            request_id=request_id, is_new=True, status="accepted"
        )

    async def record_result(self, request_id, result, uow):
        uow.data["results"][request_id] = result
        if request_id in uow.data["requests"]:
            request = uow.data["requests"][request_id]
            uow.data["requests"][request_id] = request.model_copy(
                update={
                    "status": "completed",
                    "completed_at": Clock.now,
                }
            )


class Requests:
    def __init__(self, store):
        self.store = store

    async def attach(self, request, uow):
        uow.data["requests"][request.request_id] = request

    async def read(self, actor, request_id, external_user_id, uow=None):
        from agentscope.app.workforce.orchestration._ingress import RequestView

        data = view(self.store, uow)
        request = data["requests"][request_id]
        if (
            request.audience.partner_client_id != actor.partner_client_id
            or request.audience.external_user_id != external_user_id
        ):
            raise PermissionError("request audience")
        return RequestView(
            request=request, result=data["results"].get(request_id)
        )


class Routing:
    def __init__(self, auth):
        self.auth = auth

    async def resolve(self, actor, routing_input):
        from agentscope.app.workforce.contracts import (
            PartnerOperation,
            ResolvedPartnerRoute,
        )

        return ResolvedPartnerRoute(
            scope=SCOPE,
            route_id="route-1",
            route_revision=1,
            grant_operations=tuple(PartnerOperation),
            membership_revision=1,
            resolved_at=Clock.now,
        )

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
        await self.auth.authorize(scope, actor, audience, operation, uow)


class Identity:
    def __init__(self, auth):
        self.auth = auth

    async def check_scope_active(self, scope, uow=None):
        if self.auth.revoked or scope != SCOPE:
            raise PermissionError("scope inactive")


SCOPE = Scope(
    tenant_id="tenant-1",
    domain_id="domain-1",
    area_id="area-1",
    manager_account_id="manager-1",
)
ACTOR = ActorContext(
    kind="partner",
    actor_id="actor-1",
    partner_client_id="partner-1",
    credential_id="credential-1",
    credential_purpose="customer_api",
    external_user_id="user-1",
    authentication_source="verified-test",
)


class Harness:
    def __init__(self):
        self.store, self.clock = Store(), Clock()
        self.repo, self.auth = Repository(
            self.store, self.clock
        ), Authorization(self.store)
        self.bootstrap, self.signals, self.completion = (
            Bootstrap(),
            Signals(),
            Signals(),
        )
        self.event_repo, self.ops, self.runtime = (
            EventRepo(self.store),
            Operations(self.store),
            Runtime(self.store),
        )
        self.uows = lambda: Uow(self.store)
        self.events = ConversationEventService(
            self.event_repo,
            self.auth,
            self.signals,
            self.uows,
            heartbeat_seconds=0.001,
        )
        self.writer = PublicEventWriter(self.events, self.clock)
        self.workflows = WorkflowService(
            self.repo,
            self.bootstrap,
            self.auth,
            self.ops,
            Jobs(),
            self.writer,
            self.runtime,
            self.uows,
            self.clock,
        )
        self.continuation = WorkflowContinuation(
            self.workflows, Commands(), self.completion
        )
        from agentscope.app.workforce.orchestration._ingress import (
            PartnerIngressService,
        )

        self.ingress = PartnerIngressService(
            self.workflows,
            Commands(),
            Requests(self.store),
            Routing(self.auth),
            Identity(self.auth),
            self.events,
            self.completion,
            clock=self.clock,
        )

    async def start(self, ticket="A", request=None):
        audience = PartnerAudience(
            partner_client_id="partner-1",
            external_user_id="user-1",
            external_conversation_id="chat-" + ticket,
            external_ticket_id="ticket-" + ticket,
        )
        return await self.workflows.start_with_binding(
            SCOPE,
            ACTOR,
            audience,
            dict(
                request_id=request or "request-" + ticket,
                text="Yêu cầu " + ticket,
            ),
        )

    def trigger(
        self, workflow_id, request="request-A", kind="request", **kwargs
    ):
        cause = dict(kind=kind)
        if kind in ("request", "approval"):
            cause["request_id"] = request
        cause.update(kwargs)
        return dict(
            trigger_id="trigger-" + request,
            workflow_id=workflow_id,
            cause=cause,
        )

    def close_command(self, record, **updates):
        command = dict(
            schema_version="1",
            workflow_id=record.workflow_id,
            external_request_id="close-A",
            external_user_id=record.audience.external_user_id,
            external_ticket_id=record.audience.external_ticket_id,
            external_conversation_id=record.audience.external_conversation_id,
            expected_revision=record.revision,
            reason="Đã hoàn tất",
            stop_tracking_only=True,
        )
        command.update(updates)
        return command

    def configure(self, record, **changes):
        bundle = self.store.data["workflows"][record.workflow_id]
        data = bundle.model_dump()
        if "checkpoint" in changes:
            data["checkpoint"].update(changes.pop("checkpoint"))
        if "state" in changes:
            data["workflow"]["state"] = changes.pop("state")
        data.update(changes)
        bundle = WorkflowBundle.model_validate(data)
        self.store.data["workflows"][record.workflow_id] = bundle
        return bundle

    def add_operation(self, record):
        bundle = self.configure(
            record,
            pattern="external_tracking",
            checkpoint=dict(operation_refs=["operation-A"]),
        )
        op = ExternalOperation(
            operation_id="operation-A",
            scope=SCOPE,
            audience=record.audience,
            workflow_id=record.workflow_id,
            conversation_id=record.conversation_id,
            call_id="call-A",
            provider_integration_id="provider-1",
            protocol_snapshot=bundle.checkpoint.protocol_pins[0],
            correlation_id="correlation-A",
            external_job_id="job-A",
            creation_status="succeeded",
            revision=1,
        )
        self.store.data["operations"][op.operation_id] = op
        return op

    def event(self, **updates):
        data = dict(
            inbox_event_id="inbox-A",
            provider_integration_id="provider-1",
            external_event_id="provider-event-A",
            external_job_id="job-A",
            normalized_status="assigned",
            facts={"secret": "never publish"},
            provider_version=1,
            protocol_schema_hash="sha256:fixture",
            source_hash="hash-A",
            occurred_at=self.clock(),
            received_at=self.clock(),
        )
        data.update(updates)
        return NormalizedJobEvent.model_validate(data)
