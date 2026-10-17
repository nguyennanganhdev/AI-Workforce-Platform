import unittest

from agentscope.app.workforce.contracts import NormalizedJobEvent
from agentscope.app.workforce.orchestration.partner_events import (
    EventCursorExpired,
)

from .fakes import Harness, SCOPE, customer_actor


class EventReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_replay_cursor_and_audience_are_conversation_scoped(self):
        h = Harness()
        actor = customer_actor()
        workflow_a = await h.workflows.start_with_binding(
            SCOPE,
            actor,
            h.audience("ticket-A", "chat-A"),
            {"request_id": "A1", "text": "A"},
        )
        workflow_b = await h.workflows.start_with_binding(
            SCOPE,
            actor,
            h.audience("ticket-B", "chat-B"),
            {"request_id": "B1", "text": "B"},
        )
        page_a = await h.event_service.list_after(
            actor, workflow_a.conversation_id, None, 100
        )
        self.assertTrue(page_a.items)
        self.assertTrue(
            all(
                item.workflow_id == workflow_a.workflow_id
                for item in page_a.items
            )
        )
        self.assertFalse(
            any(
                item.workflow_id == workflow_b.workflow_id
                for item in page_a.items
            )
        )
        with self.assertRaises(PermissionError):
            await h.event_service.list_after(
                customer_actor("resident-2"),
                workflow_a.conversation_id,
                None,
                100,
            )
        with self.assertRaises(EventCursorExpired):
            await h.event_service.list_after(
                actor, workflow_a.conversation_id, "expired-cursor", 100
            )

        stream = h.event_service.subscribe(actor, workflow_a.conversation_id)
        first = await anext(stream)
        await stream.aclose()
        self.assertEqual(page_a.items[0].event_id, first.event_id)

    async def test_revoked_or_closed_fact_is_not_public(self):
        h = Harness()
        actor = customer_actor()
        workflow = await h.workflows.start_with_binding(
            SCOPE,
            actor,
            h.audience("ticket-A", "chat-A"),
            {"request_id": "A1", "text": "repair"},
        )
        operation = h.add_operation(workflow.workflow_id)
        event = NormalizedJobEvent(
            inbox_event_id="inbox-1",
            provider_integration_id="provider-1",
            external_event_id="provider-event-1",
            external_job_id=operation.external_job_id,
            client_reference=operation.correlation_id,
            normalized_status="moving",
            protocol_schema_hash=operation.protocol_snapshot.schema_hash,
            source_hash="source-hash-1",
            occurred_at=h.clock(),
            received_at=h.clock(),
        )
        original_jobs = len(h.uows.store.jobs)
        original_events = len(h.uows.store.events[workflow.conversation_id])
        h.authorization.delivery_allowed = False
        unchanged = await h.workflows.apply_external_event(
            SCOPE, operation.operation_id, event
        )
        self.assertEqual(workflow.revision, unchanged.revision)
        self.assertEqual(original_jobs, len(h.uows.store.jobs))
        self.assertEqual(
            original_events, len(h.uows.store.events[workflow.conversation_id])
        )

        h.authorization.delivery_allowed = True
        updated = await h.workflows.apply_external_event(
            SCOPE, operation.operation_id, event
        )
        self.assertEqual(workflow.revision + 1, updated.revision)
        public = h.uows.store.events[workflow.conversation_id][-2:]
        self.assertEqual("operation.status_changed", public[0].event_type)
        self.assertEqual("1", public[0].payload["status_schema"])
        self.assertEqual("moving", public[0].payload["status"])
        self.assertEqual("workflow.status_changed", public[1].event_type)
        self.assertEqual(updated.revision, public[1].payload["revision"])

        aggregate = h.uows.store.workflows[workflow.workflow_id]
        closed = aggregate.model_copy(
            update={
                "workflow": aggregate.workflow.model_copy(
                    update={
                        "state": "closed",
                        "revision": aggregate.workflow.revision + 1,
                    }
                ),
                "checkpoint": aggregate.checkpoint.model_copy(
                    update={"state_revision": aggregate.workflow.revision + 1}
                ),
            }
        )
        h.uows.store.workflows[workflow.workflow_id] = closed
        second = event.model_copy(
            update={
                "inbox_event_id": "inbox-2",
                "external_event_id": "provider-event-2",
            }
        )
        before = len(h.uows.store.events[workflow.conversation_id])
        returned = await h.workflows.apply_external_event(
            SCOPE, operation.operation_id, second
        )
        self.assertEqual("closed", returned.state)
        self.assertEqual(
            before,
            len(h.uows.store.events[workflow.conversation_id]),
        )

    async def test_public_signal_and_event_are_visible_only_after_commit(self):
        h = Harness()
        workflow = await h.workflows.start_with_binding(
            SCOPE,
            customer_actor(),
            h.audience("ticket-A", "chat-A"),
            {"request_id": "A1", "text": "A"},
        )
        original_events = len(h.uows.store.events[workflow.conversation_id])
        original_notifications = len(h.event_signals.notifications)
        async with h.uows() as transaction:
            await h.events.write(
                workflow,
                "ticket.status_changed",
                {"status": "moving", "public_details": "on the way"},
                transaction,
                "cause-no-commit",
            )
            self.assertEqual(
                original_notifications,
                len(h.event_signals.notifications),
            )
            # Leaving without commit simulates a crash/rollback window.
        self.assertEqual(
            original_events, len(h.uows.store.events[workflow.conversation_id])
        )
        self.assertEqual(
            original_notifications,
            len(h.event_signals.notifications),
        )


if __name__ == "__main__":
    unittest.main()
