"""C4 integration tests over real SQL repositories and Foundation jobs."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.workforce.contracts import (
    ActorContext,
    AssistantMessage,
    AsyncProtocolSnapshotRef,
    PartnerOperation,
    PartnerRequestEnvelope,
    RequestResult,
    ResolvedPartnerRoute,
    Scope,
    WorkflowState,
)
from agentscope.app.workforce.execution import (
    create_repository as create_execution_repository,
)
from agentscope.app.workforce.execution import (
    get_metadata as get_execution_metadata,
)
from agentscope.app.workforce.execution.external_operations._protocol import (
    protocol_hash,
)
from agentscope.app.workforce.execution.provider_events import (
    WorkflowEventAdapter,
)
from agentscope.app.workforce.foundation import (
    DurableJobService,
    DurableJobWorker,
    MessageBusPublicEventSignal,
    MessageBusRequestCompletionSignal,
    SqlAlchemyUnitOfWorkFactory,
    SqlDurableJobRepository,
)
from agentscope.app.workforce.foundation._tables import (
    metadata as foundation_metadata,
)
from agentscope.app.workforce.orchestration import (
    ExecutionOperationReader,
    LeaderBootstrapSeed,
    LeaderWorkflowBootstrap,
    PartnerIngressService,
    SqlCheckpointRepository,
    SqlEventRepository,
    SqlPartnerRequestRepository,
    SqlRuntimeContinuation,
    SqlWorkflowRepository,
    WorkflowContinuationJobHandler,
    create_router,
    get_metadata,
    receipt_http_status,
)
from agentscope.app.workforce.orchestration.partner_events import (
    ConversationEventService,
    PublicEventWriter,
)
from agentscope.app.workforce.orchestration.workflows import (
    TurnDecision,
    WorkflowContinuation,
    WorkflowService,
    advance,
)
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    RuntimeTurnResult,
)
from agentscope.app.workforce.registry.event_protocols import AsyncToolProtocol

NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)
SCOPE = Scope(
    tenant_id="tenant-1",
    domain_id="domain-1",
    area_id="area-1",
    manager_account_id="manager-1",
)


class _Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"c4-{self.value}"


class _Authorization:
    async def authorize(self, scope, actor, audience, operation, uow=None):
        if scope != SCOPE or actor.external_user_id != audience.external_user_id:
            raise PermissionError

    async def authorize_trigger(self, aggregate, trigger, uow=None):
        if aggregate.workflow.workflow_id != trigger.workflow_id:
            raise PermissionError

    async def can_publish_external_event(self, aggregate, event, uow):
        return True


class _Identity:
    async def check_scope_active(self, scope, uow=None):
        if scope != SCOPE:
            raise PermissionError


class _Routing:
    def route(self):
        return ResolvedPartnerRoute(
            scope=SCOPE,
            route_id="route-1",
            route_revision=1,
            grant_operations=tuple(PartnerOperation),
            membership_revision=1,
            resolved_at=NOW,
        )

    async def resolve(self, actor, routing_input):
        if routing_input["external_management_ref"] != "tower-a":
            raise PermissionError
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
            scope != SCOPE
            or route_id != "route-1"
            or expected_revision != 1
            or actor.external_user_id != audience.external_user_id
        ):
            raise PermissionError
        return self.route()


class _BootstrapResolver:
    def __init__(self, ids):
        self.ids = ids

    async def resolve(self, scope, actor, audience, uow):
        return LeaderBootstrapSeed(
            leader_agent_id="platform-leader",
            leader_version_id="leader-v1",
            group_id=self.ids(),
            session_ref=self.ids(),
            shared_state_ref=self.ids(),
            pattern="interactive",
            published_read_only=False,
        )


class _Leader:
    def __init__(self, clock):
        self.clock = clock
        self.calls = 0

    async def invoke_turn(self, scope, trigger, context, execution_guard):
        await execution_guard.check("read")
        self.calls += 1
        checkpoint = context.checkpoint.model_copy(
            update={
                "state_revision": context.workflow.revision + 1,
                "used_budget": context.checkpoint.used_budget.model_copy(
                    update={
                        "model_turns": (
                            context.checkpoint.used_budget.model_turns + 1
                        )
                    }
                ),
            }
        )
        return TurnDecision(
            candidate=RuntimeTurnResult(
                trigger_id=trigger["trigger_id"],
                expected_state_revision=context.workflow.revision,
                checkpoint=checkpoint,
                result=RequestResult(
                    messages=(
                        AssistantMessage(
                            message_id=f"message-{self.calls}",
                            workflow_id=context.workflow.workflow_id,
                            text="Đã tiếp nhận và xử lý yêu cầu",
                            created_at=self.clock(),
                        ),
                    )
                ),
            ),
            next_state=WorkflowState.AWAITING_USER,
        )


class _Evidence:
    def __init__(self):
        self.items = []

    async def record(self, evidence, uow):
        self.items.append(evidence)


class C4SqlSliceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database = Path(self.temp.name) / "c4.sqlite3"
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{database.as_posix()}"
        )
        sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.uows = SqlAlchemyUnitOfWorkFactory(sessions)
        async with self.engine.begin() as connection:
            await connection.run_sync(foundation_metadata.create_all)
            await connection.run_sync(get_execution_metadata().create_all)
            await connection.run_sync(get_metadata().create_all)

        self.ids = _Ids()
        self.clock = lambda: NOW
        self.workflows_repo = SqlWorkflowRepository(
            self.uows, clock=self.clock, ids=self.ids
        )
        async def tenant_resolver(actor, uow):
            if actor.partner_client_id != "partner-1":
                raise PermissionError
            return SCOPE.tenant_id

        self.requests = SqlPartnerRequestRepository(
            self.uows,
            tenant_resolver,
            clock=self.clock,
            ids=self.ids,
        )
        self.checkpoints = SqlCheckpointRepository(
            self.uows, clock=self.clock
        )
        self.execution_repository = create_execution_repository(
            uow_factory=self.uows
        )
        bus = InMemoryMessageBus()
        event_signal = MessageBusPublicEventSignal(bus)
        completion_signal = MessageBusRequestCompletionSignal(bus)
        self.authorization = _Authorization()
        self.event_repository = SqlEventRepository(self.uows)
        self.event_service = ConversationEventService(
            self.event_repository,
            self.authorization,
            event_signal,
            self.uows,
            heartbeat_seconds=0.01,
        )
        self.events = PublicEventWriter(
            self.event_service, self.clock, self.ids
        )
        self.jobs = DurableJobService(
            SqlDurableJobRepository(self.uows),
            clock=self.clock,
            id_factory=self.ids,
        )
        bootstrap = LeaderWorkflowBootstrap(
            _BootstrapResolver(self.ids), clock=self.clock, ids=self.ids
        )
        self.leader = _Leader(self.clock)
        self.runtime = SqlRuntimeContinuation(
            self.workflows_repo, self.checkpoints, self.leader
        )
        self.workflow_service = WorkflowService(
            self.workflows_repo,
            bootstrap,
            self.authorization,
            ExecutionOperationReader(self.execution_repository),
            self.jobs,
            self.events,
            self.runtime,
            self.uows,
            self.clock,
            self.ids,
        )
        self.evidence = _Evidence()
        continuation = WorkflowContinuation(
            self.workflow_service,
            self.requests,
            completion_signal,
            evidence=self.evidence,
        )
        handler = WorkflowContinuationJobHandler(
            continuation, worker_id="workflow-worker"
        )
        self.worker = DurableJobWorker(
            self.jobs,
            {handler.job_type: handler},
            worker_id="durable-worker",
            heartbeat_interval=0.01,
        )
        self.ingress = PartnerIngressService(
            self.workflow_service,
            self.requests,
            self.requests,
            _Routing(),
            _Identity(),
            self.event_service,
            completion_signal,
            clock=self.clock,
            wait_slice_seconds=0.01,
        )
        self.actor = ActorContext(
            kind="partner",
            actor_id="customer-resident-1",
            partner_client_id="partner-1",
            credential_id="customer-key",
            credential_purpose="customer_api",
            external_user_id="resident-1",
            authentication_source="c4-test",
        )

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.temp.cleanup()

    @staticmethod
    def envelope(request_id, ticket, conversation):
        return PartnerRequestEnvelope(
            schema_version="1",
            command_type="start_workflow",
            external_request_id=request_id,
            external_management_ref="tower-a",
            external_user_id="resident-1",
            external_ticket_id=ticket,
            external_conversation_id=conversation,
            residence_id="residence-1",
            message={"type": "text", "text": "Xin hỗ trợ"},
        )

    async def test_post_job_leader_result_and_replay(self):
        receipt = await self.ingress.accept(
            self.actor, self.envelope("request-A", "ticket-A", "chat-A")
        )
        self.assertEqual(202, receipt_http_status(receipt))
        outcome = await self.worker.run_once()
        self.assertEqual("succeeded", outcome.status)

        completed = await self.ingress.read_result(
            self.actor, receipt.request_id, "resident-1"
        )
        self.assertEqual(200, receipt_http_status(completed))
        self.assertEqual("awaiting_user", completed.workflow_state)
        self.assertEqual("submit_reply", completed.next_action)
        self.assertEqual(1, self.leader.calls)
        self.assertEqual(1, len(self.evidence.items))
        self.assertEqual(
            receipt.workflow_id, self.evidence.items[0].workflow_id
        )
        self.assertEqual(("read",), self.evidence.items[0].checked_effects)

        history = await self.event_service.list_after(
            self.actor, receipt.conversation_id, None, 100
        )
        self.assertEqual(
            [
                "request.accepted",
                "assistant.message",
                "workflow.status_changed",
            ],
            [item.event_type for item in history.items],
        )

    async def test_bounded_wait_observes_committed_worker_result(self):
        receipt = await self.ingress.accept(
            self.actor, self.envelope("request-A", "ticket-A", "chat-A")
        )
        waiter = asyncio.create_task(
            self.ingress.wait_for_result(
                self.actor,
                receipt.request_id,
                "resident-1",
                NOW + timedelta(seconds=1),
            )
        )
        await asyncio.sleep(0)
        await self.worker.run_once()
        completed = await asyncio.wait_for(waiter, timeout=1)
        self.assertEqual(200, receipt_http_status(completed))
        self.assertEqual("completed", completed.request_status)

    async def test_customer_http_202_then_get_and_history(self):
        app = FastAPI()

        async def customer_dependency():
            return self.actor

        app.include_router(
            create_router(
                self.ingress,
                self.event_service,
                customer_dependency,
                bounded_wait_seconds=0,
            )
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://platform.test"
        ) as client:
            response = await client.post(
                "/workforce/v1/partner/requests",
                json=self.envelope(
                    "request-http", "ticket-http", "chat-http"
                ).model_dump(mode="json"),
            )
            self.assertEqual(202, response.status_code)
            pending = response.json()

            await self.worker.run_once()

            response = await client.get(
                pending["status_url"],
                params={"external_user_id": "resident-1"},
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual("completed", response.json()["request_status"])

            response = await client.get(
                f'{pending["conversation_url"]}/event-history',
                params={"external_user_id": "resident-1"},
            )
            self.assertEqual(200, response.status_code)
            self.assertIn("items", response.json(), response.text)
            self.assertEqual(
                [
                    "request.accepted",
                    "assistant.message",
                    "workflow.status_changed",
                ],
                [item["event_type"] for item in response.json()["items"]],
            )

            response = await client.get(
                pending["event_stream_url"],
                params={
                    "external_user_id": "resident-1",
                    "after_cursor": "expired-cursor",
                },
            )
            self.assertEqual(410, response.status_code)
            self.assertEqual(
                "EVENT_CURSOR_EXPIRED", response.json()["error"]["code"]
            )

    async def test_two_tickets_and_retry_keep_isolated_groups(self):
        envelope_a = self.envelope("request-A", "ticket-A", "chat-A")
        first = await self.ingress.accept(self.actor, envelope_a)
        second = await self.ingress.accept(
            self.actor, self.envelope("request-B", "ticket-B", "chat-B")
        )
        retried = await self.ingress.accept(self.actor, envelope_a)
        self.assertEqual(first.request_id, retried.request_id)
        self.assertNotEqual(first.workflow_id, second.workflow_id)
        workflow_a = await self.workflows_repo.load(SCOPE, first.workflow_id)
        workflow_b = await self.workflows_repo.load(SCOPE, second.workflow_id)
        self.assertNotEqual(
            workflow_a.workflow.group_id, workflow_b.workflow.group_id
        )
        self.assertNotEqual(
            workflow_a.checkpoint.session_refs,
            workflow_b.checkpoint.session_refs,
        )

    async def test_execution_query_hook_uses_timer_cause_and_same_uow(self):
        receipt = await self.ingress.accept(
            self.actor, self.envelope("request-A", "ticket-A", "chat-A")
        )
        await self.worker.run_once()
        aggregate = await self.workflows_repo.load(SCOPE, receipt.workflow_id)
        sample_path = (
            Path(__file__).resolve().parents[4]
            / "docs/workforce/handoffs/nguyen-phuong-dong/phase_a_samples.json"
        )
        raw = json.loads(sample_path.read_text(encoding="utf-8"))[
            "protocols"
        ]["query_only"]
        raw.update(
            tool_version_id="technical.create.v1",
            provider_integration_id="provider-1",
            external_job_id_field="external_job_id",
            status_query_tool_version_id="technical.status.v1",
        )
        config = AsyncToolProtocol.model_validate(raw)
        snapshot = AsyncProtocolSnapshotRef.model_validate(config.snapshot_ref)
        protocol = {
            "snapshot_ref": snapshot.model_dump(mode="json"),
            "configuration": config.model_dump(mode="json"),
        }
        operation = {
            "id": "operation-A",
            "operation_id": "operation-A",
            "scope": SCOPE.model_dump(mode="json"),
            "revision": 1,
            "call_id": "call-A",
            "workflow_id": receipt.workflow_id,
            "conversation_id": receipt.conversation_id,
            "group_id": aggregate.workflow.group_id,
            "ticket_id": aggregate.workflow.ticket_id,
            "audience_ref": aggregate.workflow.audience.model_dump(
                mode="json", exclude_none=True
            ),
            "provider_integration_id": "provider-1",
            "protocol": protocol,
            "protocol_hash": protocol_hash(protocol),
            "correlation_id": "correlation-A",
            "external_job_id": "external-job-A",
            "creation_status": "succeeded",
            "job_status": "assigned",
            "pending": True,
            "last_provider_version": 1,
            "last_source_hash": "source-before-query",
            "created_at": NOW.isoformat(),
        }
        async with self.uows() as uow:
            await self.execution_repository.insert_once(
                "operations",
                operation,
                {"call_id": "call-A"},
                uow,
                SCOPE,
            )
            candidate = advance(aggregate, self.clock)
            checkpoint = candidate.checkpoint.model_copy(
                update={
                    "operation_refs": (operation["id"],),
                    "protocol_pins": (snapshot,),
                }
            )
            checkpoint_ref = await self.runtime.persist_checkpoint(
                SCOPE, receipt.workflow_id, checkpoint, uow
            )
            candidate = candidate.model_copy(
                update={
                    "checkpoint": checkpoint,
                    "workflow": candidate.workflow.model_copy(
                        update={"checkpoint_ref": checkpoint_ref}
                    ),
                }
            )
            saved = await self.workflows_repo.save(
                candidate, aggregate.workflow.revision, uow
            )
            self.assertTrue(saved)
            await uow.commit()

        adapter = WorkflowEventAdapter(
            self.execution_repository,
            self.workflow_service,
            query_sink=self.workflow_service.apply_query_result,
        )
        async with self.uows() as uow:
            stored = await self.execution_repository.get(
                "operations", "operation-A", uow, SCOPE
            )
            applied = await adapter.apply_external_event(
                SCOPE,
                stored,
                {
                    "timer_id": "timer-A",
                    "protocol_schema_hash": snapshot.schema_hash,
                    "source_hash": "query-source-A",
                    "observed_at": NOW.isoformat(),
                    "status": "on_the_way",
                    "facts": {},
                    "provider_version": 2,
                    "terminal": False,
                },
                uow,
            )
            await uow.commit()
        self.assertEqual(receipt.workflow_id, applied.workflow_id)
        current = await self.workflows_repo.load(SCOPE, receipt.workflow_id)
        self.assertEqual(
            "query-source-A", current.applied_query_results["timer-A"]
        )


if __name__ == "__main__":
    unittest.main()
