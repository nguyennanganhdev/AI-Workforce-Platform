# -*- coding: utf-8 -*-
"""Phase-B tests for jobs, scoped signals and replay-first SSE."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import unittest

from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.workforce.contracts import (
    ActorContext,
    ActorKind,
    ConversationEvent,
    CredentialPurpose,
    Scope,
)
from agentscope.app.workforce.foundation.event_delivery import (
    ConversationSseService,
    DurableJobService,
    DurableJobWorker,
    JobLeaseLostError,
    JobNamespaceError,
    JobStatus,
    MessageBusPublicEventSignal,
    MessageBusRequestCompletionSignal,
    SseFrame,
    WorkerOutcomeStatus,
)

from .fakes import (
    FakeConversationEventPort,
    FakeDurableJobRepository,
    ImmediateTimeoutSignal,
)


NOW = datetime(2026, 10, 10, 4, 0, tzinfo=UTC)


def scope(manager: str = "manager-1") -> Scope:
    return Scope(
        tenant_id="tenant-1",
        domain_id="property",
        area_id="ha-long",
        manager_account_id=manager,
    )


def partner_actor() -> ActorContext:
    return ActorContext(
        kind=ActorKind.PARTNER,
        actor_id="partner-1",
        partner_client_id="partner-1",
        credential_id="credential-1",
        credential_purpose=CredentialPurpose.CUSTOMER_API,
        external_user_id="resident-1",
        authentication_source="api_key",
    )


def event(number: int, conversation_id: str = "conversation-1") -> ConversationEvent:
    return ConversationEvent(
        event_id=f"event-{number}",
        sequence=number,
        event_type="operation.status_changed",
        occurred_at=NOW,
        recorded_at=NOW,
        conversation_id=conversation_id,
        external_ticket_id="ticket-1",
        external_conversation_id="chat-1",
        external_user_id="resident-1",
        workflow_id="workflow-1",
        payload={"status": f"step-{number}"},
    )


class MutableClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class DurableJobTests(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_is_idempotent_inside_owner_namespace(self) -> None:
        repository = FakeDurableJobRepository()
        next_id = 0

        def id_factory() -> str:
            nonlocal next_id
            next_id += 1
            return f"job-{next_id}"

        service = DurableJobService(
            repository,
            clock=lambda: NOW,
            id_factory=id_factory,
        )
        first = await service.enqueue(
            scope(),
            "operation_reconcile",
            {"operation_id": "operation-1"},
            "timer-1",
        )
        replay = await service.enqueue(
            scope(),
            "operation_reconcile",
            {"operation_id": "operation-1"},
            "timer-1",
        )
        self.assertEqual(first, replay)
        self.assertEqual(len(repository.jobs), 1)

        with self.assertRaisesRegex(ValueError, "idempotency key"):
            await service.enqueue(
                scope(),
                "operation_reconcile",
                {"operation_id": "changed"},
                "timer-1",
            )

    async def test_provider_job_uses_verified_namespace_not_public_body(self) -> None:
        repository = FakeDurableJobRepository()
        service = DurableJobService(
            repository,
            clock=lambda: NOW,
            id_factory=lambda: "provider-job-1",
        )
        job_id = await service.enqueue_provider(
            {
                "tenant_id": "tenant-1",
                "provider_integration_id": "provider-integration-1",
                "actor_id": "provider-1",
            },
            "provider_event",
            {"receipt_id": "receipt-1"},
            "receipt-1",
        )
        stored = repository.jobs[job_id]
        self.assertIsNone(stored.scope)
        self.assertEqual(
            stored.provider_integration_id,
            "provider-integration-1",
        )

        with self.assertRaises(JobNamespaceError):
            await service.enqueue_provider(
                {"tenant_id": "tenant-1"},
                "provider_event",
                {"receipt_id": "receipt-2"},
                "receipt-2",
            )

    async def test_expired_lease_is_reclaimed_with_new_fence(self) -> None:
        repository = FakeDurableJobRepository()
        clock = MutableClock()
        first_worker = DurableJobService(
            repository,
            clock=clock,
            id_factory=lambda: "job-1",
        )
        second_worker = DurableJobService(repository, clock=clock)
        job_id = await first_worker.enqueue(
            scope(),
            "workflow_trigger",
            {"trigger_id": "trigger-1"},
            "trigger-1",
        )
        first_claim = await first_worker.claim("worker-a", timedelta(seconds=5))
        self.assertIsNotNone(first_claim)

        clock.now += timedelta(seconds=6)
        second_claim = await second_worker.claim("worker-b", timedelta(seconds=5))
        self.assertIsNotNone(second_claim)
        assert first_claim is not None and second_claim is not None
        self.assertGreater(second_claim.fencing_token, first_claim.fencing_token)

        with self.assertRaises(JobLeaseLostError):
            await first_worker.complete(job_id, {"stale": True})
        await second_worker.complete(job_id, {"applied": True})
        self.assertEqual(repository.jobs[job_id].status, JobStatus.SUCCEEDED)

    async def test_expired_claim_cannot_borrow_new_fence_in_shared_service(
        self,
    ) -> None:
        repository = FakeDurableJobRepository()
        clock = MutableClock()
        service = DurableJobService(
            repository,
            clock=clock,
            id_factory=lambda: "job-1",
        )
        await service.enqueue(scope(), "trigger", {}, "trigger-1")
        stale = await service.claim("worker-a", timedelta(seconds=5))
        assert stale is not None
        clock.now += timedelta(seconds=6)
        current = await service.claim("worker-b", timedelta(seconds=5))
        assert current is not None

        with self.assertRaises(JobLeaseLostError):
            await service.complete_claim(stale, {"stale": True})
        await service.complete_claim(current, {"current": True})
        self.assertEqual(repository.jobs["job-1"].result, {"current": True})

    async def test_not_before_and_retry_do_not_busy_loop(self) -> None:
        repository = FakeDurableJobRepository()
        clock = MutableClock()
        service = DurableJobService(
            repository,
            clock=clock,
            id_factory=lambda: "job-1",
            retry_base=timedelta(seconds=10),
        )
        await service.enqueue(
            scope(),
            "status_query",
            {"operation_id": "operation-1"},
            "query-1",
            not_before=NOW + timedelta(seconds=5),
        )
        self.assertIsNone(await service.claim("worker-a", timedelta(seconds=5)))
        clock.now += timedelta(seconds=5)
        claim = await service.claim("worker-a", timedelta(seconds=5))
        self.assertIsNotNone(claim)
        assert claim is not None
        await service.fail(claim.job.job_id, {"code": "TEMPORARY"})
        self.assertIsNone(await service.claim("worker-a", timedelta(seconds=5)))
        clock.now += timedelta(seconds=10)
        self.assertIsNotNone(await service.claim("worker-a", timedelta(seconds=5)))

    async def test_worker_dispatches_and_persists_sanitized_failure(self) -> None:
        repository = FakeDurableJobRepository()
        next_id = 0

        def id_factory() -> str:
            nonlocal next_id
            next_id += 1
            return f"job-{next_id}"

        service = DurableJobService(
            repository,
            clock=lambda: NOW,
            id_factory=id_factory,
        )

        async def success(job):
            return {"handled": job.job_id}

        await service.enqueue(scope(), "known", {}, "known-1")
        worker = DurableJobWorker(
            service,
            {"known": success},
            worker_id="worker-a",
            heartbeat_interval=1,
        )
        outcome = await worker.run_once()
        self.assertEqual(outcome.status, WorkerOutcomeStatus.SUCCEEDED)
        self.assertEqual(repository.jobs["job-1"].result, {"handled": "job-1"})

        await service.enqueue(scope(), "missing", {}, "missing-1")
        outcome = await worker.run_once()
        self.assertEqual(
            outcome.status,
            WorkerOutcomeStatus.RETRY_SCHEDULED,
        )
        self.assertEqual(
            repository.jobs["job-2"].error,
            {"code": "JOB_HANDLER_NOT_FOUND"},
        )


class SignalAndSseTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_signal_isolated_by_full_manager_scope(self) -> None:
        bus = InMemoryMessageBus()
        signal = MessageBusRequestCompletionSignal(bus)
        wrong = asyncio.create_task(
            signal.wait_for_completion(scope("manager-2"), "request-1", 0.02),
        )
        right = asyncio.create_task(
            signal.wait_for_completion(scope(), "request-1", 0.2),
        )
        await asyncio.sleep(0)
        await signal.notify_after_commit(scope(), "request-1")
        self.assertTrue(await right)
        self.assertFalse(await wrong)

    async def test_public_signal_returns_committed_sequence(self) -> None:
        bus = InMemoryMessageBus()
        signal = MessageBusPublicEventSignal(bus)
        waiter = asyncio.create_task(
            signal.wait_for_signal(scope(), "conversation-1", 0.2),
        )
        await asyncio.sleep(0)
        await signal.notify_after_commit(scope(), "conversation-1", 12)
        self.assertEqual(await waiter, 12)

    async def test_sse_replays_database_before_waiting_for_signal(self) -> None:
        service = ConversationSseService(
            FakeConversationEventPort([event(1), event(2)]),
            ImmediateTimeoutSignal(),
            page_size=1,
            heartbeat_seconds=0.01,
        )
        frames = service.frames(partner_actor(), scope(), "conversation-1")
        first = await anext(frames)
        second = await anext(frames)
        heartbeat = await anext(frames)
        await frames.aclose()

        self.assertIn(b'"event_id":"event-1"', first.encode())
        self.assertIn(b'"event_id":"event-2"', second.encode())
        self.assertEqual(heartbeat.encode(), b": heartbeat\n\n")

    async def test_sse_rejects_header_injection(self) -> None:
        frame = SseFrame(event_id="safe\nforged", data="{}")
        with self.assertRaisesRegex(ValueError, "newline"):
            frame.encode()


if __name__ == "__main__":
    unittest.main()
