import unittest

from agentscope.app.workforce.contracts import (
    PartnerRequestEnvelope,
    WorkflowState,
)
from agentscope.app.workforce.orchestration import (
    PartnerIngressService,
    receipt_http_status,
)
from agentscope.app.workforce.orchestration.workflows import (
    WorkflowBindingMismatch,
    WorkflowConflict,
)

from fakes import Harness, customer_actor


def envelope(
    request_id, ticket, conversation, *, workflow_id=None, text="help"
):
    return PartnerRequestEnvelope(
        schema_version="1",
        command_type="workflow_reply" if workflow_id else "start_workflow",
        external_request_id=request_id,
        external_management_ref="tower-a",
        external_user_id="resident-1",
        external_ticket_id=ticket,
        external_conversation_id=conversation,
        workflow_id=workflow_id,
        residence_id="residence-1",
        message={"type": "text", "text": text},
    )


class WorkflowIngressTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.harness = Harness()
        self.ingress = PartnerIngressService(
            self.harness.workflows,
            self.harness.commands,
            self.harness.requests,
            self.harness.routing,
            self.harness.identity,
            self.harness.event_service,
            self.harness.completion_signals,
            clock=self.harness.clock,
            wait_slice_seconds=0.01,
        )
        self.actor = customer_actor()

    async def test_two_tickets_keep_distinct_group_and_session(self):
        request_a = envelope("A1", "external-ticket-A", "external-chat-A")
        request_b = envelope("B1", "external-ticket-B", "external-chat-B")
        receipt_a = await self.ingress.accept(self.actor, request_a)
        receipt_b = await self.ingress.accept(self.actor, request_b)

        self.assertEqual(202, receipt_http_status(receipt_a))
        self.assertEqual(202, receipt_http_status(receipt_b))
        self.assertNotEqual(receipt_a.workflow_id, receipt_b.workflow_id)
        aggregate_a = self.harness.uows.store.workflows[receipt_a.workflow_id]
        aggregate_b = self.harness.uows.store.workflows[receipt_b.workflow_id]
        self.assertNotEqual(
            aggregate_a.workflow.group_id, aggregate_b.workflow.group_id
        )
        self.assertNotEqual(
            aggregate_a.checkpoint.session_refs,
            aggregate_b.checkpoint.session_refs,
        )

        retried = await self.ingress.accept(self.actor, request_a)
        self.assertEqual(receipt_a.request_id, retried.request_id)
        self.assertEqual(2, len(self.harness.uows.store.workflows))
        self.assertEqual(2, len(self.harness.uows.store.jobs))

        reply_a = envelope(
            "A2",
            "external-ticket-A",
            "external-chat-A",
            workflow_id=receipt_a.workflow_id,
            text="more details for A",
        )
        replied = await self.ingress.accept(self.actor, reply_a)
        current_a = self.harness.uows.store.workflows[receipt_a.workflow_id]
        current_b = self.harness.uows.store.workflows[receipt_b.workflow_id]
        self.assertEqual(2, replied.workflow_revision)
        self.assertEqual("active", replied.workflow_state)
        self.assertEqual(2, current_a.workflow.revision)
        self.assertEqual(1, current_b.workflow.revision)
        self.assertEqual(
            aggregate_a.workflow.group_id,
            current_a.workflow.group_id,
        )

    async def test_mismatched_ticket_reply_has_zero_dispatch(self):
        receipt_a = await self.ingress.accept(
            self.actor, envelope("A1", "external-ticket-A", "external-chat-A")
        )
        await self.ingress.accept(
            self.actor, envelope("B1", "external-ticket-B", "external-chat-B")
        )
        job_count = len(self.harness.uows.store.jobs)
        with self.assertRaises(WorkflowBindingMismatch):
            await self.ingress.accept(
                self.actor,
                envelope(
                    "bad-reply",
                    "external-ticket-B",
                    "external-chat-B",
                    workflow_id=receipt_a.workflow_id,
                ),
            )
        self.assertEqual(job_count, len(self.harness.uows.store.jobs))
        self.assertNotIn(
            ("partner-1", "bad-reply"), self.harness.uows.store.command_ledger
        )

    async def test_ticket_and_conversation_are_independently_unique(self):
        await self.ingress.accept(
            self.actor, envelope("A1", "ticket-A", "chat-A")
        )
        with self.assertRaises(WorkflowConflict):
            await self.ingress.accept(
                self.actor, envelope("A2", "ticket-A", "chat-other")
            )
        with self.assertRaises(WorkflowConflict):
            await self.ingress.accept(
                self.actor, envelope("A3", "ticket-other", "chat-A")
            )
        self.assertEqual(1, len(self.harness.uows.store.workflows))
        self.assertEqual(1, len(self.harness.uows.store.jobs))

    async def test_reply_revision_is_cas_guarded(self):
        receipt = await self.ingress.accept(
            self.actor, envelope("start", "ticket-A", "chat-A")
        )
        audience = self.harness.audience("ticket-A", "chat-A")
        first = await self.harness.workflows.accept_reply(
            self.harness.uows.store.workflows[
                receipt.workflow_id
            ].workflow.scope,
            self.actor,
            audience,
            receipt.workflow_id,
            {"request_id": "reply-1", "text": "one", "expected_revision": 1},
        )
        self.assertEqual(2, first.revision)
        with self.assertRaises(WorkflowConflict):
            await self.harness.workflows.accept_reply(
                first.scope,
                self.actor,
                audience,
                receipt.workflow_id,
                {
                    "request_id": "reply-2",
                    "text": "two",
                    "expected_revision": 1,
                },
            )

    async def test_close_ticket_a_does_not_close_or_wake_ticket_b(self):
        receipt_a = await self.ingress.accept(
            self.actor, envelope("A1", "ticket-A", "chat-A")
        )
        receipt_b = await self.ingress.accept(
            self.actor, envelope("B1", "ticket-B", "chat-B")
        )
        aggregate_a = self.harness.uows.store.workflows[
            receipt_a.workflow_id
        ]
        self.harness.uows.store.workflows[receipt_a.workflow_id] = (
            aggregate_a.model_copy(
                update={
                    "workflow": aggregate_a.workflow.model_copy(
                        update={
                            "state": WorkflowState.AWAITING_CONFIRMATION,
                            "revision": 2,
                        }
                    ),
                    "checkpoint": aggregate_a.checkpoint.model_copy(
                        update={"state_revision": 2}
                    ),
                }
            )
        )
        closed = await self.ingress.close_workflow(
            self.actor,
            self.harness.uows.store.workflows[
                receipt_a.workflow_id
            ].workflow.scope,
            receipt_a.workflow_id,
            {
                "schema_version": "1",
                "external_request_id": "close-A",
                "external_user_id": "resident-1",
                "external_ticket_id": "ticket-A",
                "external_conversation_id": "chat-A",
                "expected_revision": 2,
                "reason": "customer_confirmed",
                "stop_tracking_only": False,
            },
        )
        self.assertEqual("closed", closed.workflow_state)
        self.assertEqual("none", closed.next_action)
        workflow_b = self.harness.uows.store.workflows[
            receipt_b.workflow_id
        ].workflow
        self.assertEqual(WorkflowState.ACCEPTED, workflow_b.state)
        self.assertFalse(
            any(
                event.event_type == "workflow.closed"
                for event in self.harness.uows.store.events[
                    receipt_b.conversation_id
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
