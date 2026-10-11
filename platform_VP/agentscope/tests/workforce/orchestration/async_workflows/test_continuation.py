import unittest

from agentscope.app.workforce.contracts import (
    NormalizedJobEvent,
    PartnerRequestEnvelope,
    WorkflowState,
)
from agentscope.app.workforce.orchestration import (
    PartnerIngressService,
    receipt_http_status,
)
from agentscope.app.workforce.orchestration.workflows import (
    WorkflowConflict,
    WorkflowPattern,
)

from fakes import Harness, SCOPE, customer_actor


class ContinuationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.h = Harness()
        self.actor = customer_actor()
        self.ingress = PartnerIngressService(
            self.h.workflows,
            self.h.commands,
            self.h.requests,
            self.h.routing,
            self.h.identity,
            self.h.event_service,
            self.h.completion_signals,
            clock=self.h.clock,
            wait_slice_seconds=0.01,
        )

    async def test_response_only_turn_commits_once(self):
        self.h.bootstrap.pattern = WorkflowPattern.RESPONSE_ONLY
        self.h.bootstrap.published_read_only = True
        receipt = await self.ingress.accept(
            self.actor,
            PartnerRequestEnvelope(
                schema_version="1",
                command_type="start_workflow",
                external_request_id="read-only-request",
                external_management_ref="tower-a",
                external_user_id="resident-1",
                external_ticket_id="ticket-read-only",
                external_conversation_id="chat-read-only",
                residence_id="residence-1",
                message={"type": "text", "text": "show hotel options"},
            ),
        )
        job = next(iter(self.h.uows.store.jobs.values()))
        self.h.runtime.next_state = WorkflowState.CLOSED
        outcome = await self.h.continuation.run(
            self.h.uows.store.workflows[receipt.workflow_id].workflow.scope,
            job["payload"],
            "worker-1",
        )
        self.assertEqual("applied", outcome)

        completed = await self.ingress.read_result(
            self.actor, receipt.request_id, "resident-1"
        )
        self.assertEqual(200, receipt_http_status(completed))
        self.assertEqual("completed", completed.request_status)
        self.assertEqual("closed", completed.workflow_state)
        self.assertEqual("none", completed.next_action)
        self.assertEqual(1, len(completed.result.messages))
        message = completed.result.messages[0]
        events = self.h.uows.store.events[completed.conversation_id]
        assistant_events = [
            event for event in events
            if event.event_type == "assistant.message"
        ]
        self.assertEqual(
            message.message_id,
            assistant_events[0].payload["message_id"],
        )
        self.assertIn(
            (
                self.h.uows.store.workflows[
                    receipt.workflow_id
                ].workflow.scope,
                receipt.request_id,
            ),
            self.h.completion_signals.notifications,
        )

        duplicate = await self.h.continuation.run(
            self.h.uows.store.workflows[receipt.workflow_id].workflow.scope,
            job["payload"],
            "worker-2",
        )
        self.assertEqual("closed", duplicate)
        self.assertEqual(1, self.h.runtime.invocations)
        self.assertEqual(1, len(assistant_events))

    async def test_external_tracking_sleeps_without_extra_turn(self):
        self.h.bootstrap.pattern = WorkflowPattern.EXTERNAL_TRACKING
        receipt = await self.ingress.accept(
            self.actor,
            PartnerRequestEnvelope(
                schema_version="1",
                command_type="start_workflow",
                external_request_id="repair-request",
                external_management_ref="tower-a",
                external_user_id="resident-1",
                external_ticket_id="repair-ticket",
                external_conversation_id="repair-chat",
                residence_id="residence-1",
                message={"type": "text", "text": "repair the pipe"},
            ),
        )
        self.h.add_operation(receipt.workflow_id)
        job = next(iter(self.h.uows.store.jobs.values()))
        self.h.runtime.next_state = WorkflowState.WAITING_EXTERNAL_EVENT
        self.assertEqual(
            "applied",
            await self.h.continuation.run(
                self.h.uows.store.workflows[
                    receipt.workflow_id
                ].workflow.scope,
                job["payload"],
                "worker-tracking",
            ),
        )
        aggregate = self.h.uows.store.workflows[receipt.workflow_id]
        used = aggregate.checkpoint.used_budget
        self.assertEqual(
            WorkflowState.WAITING_EXTERNAL_EVENT,
            aggregate.workflow.state,
        )
        self.assertEqual(("operation-1",), aggregate.workflow.pending_waits)
        self.assertEqual(1, used.model_turns)
        self.assertEqual(0, used.tool_calls)
        self.assertEqual(1, self.h.runtime.invocations)

    async def test_invalid_decision_does_not_commit(self):
        receipt = await self.ingress.accept(
            self.actor,
            PartnerRequestEnvelope(
                schema_version="1",
                command_type="start_workflow",
                external_request_id="interactive-request",
                external_management_ref="tower-a",
                external_user_id="resident-1",
                external_ticket_id="interactive-ticket",
                external_conversation_id="interactive-chat",
                residence_id="residence-1",
                message={"type": "text", "text": "perform a side effect"},
            ),
        )
        before = self.h.uows.store.workflows[receipt.workflow_id]
        job = next(iter(self.h.uows.store.jobs.values()))
        self.h.runtime.next_state = WorkflowState.CLOSED
        with self.assertRaises(WorkflowConflict):
            await self.h.continuation.run(
                before.workflow.scope, job["payload"], "worker-invalid"
            )
        after = self.h.uows.store.workflows[receipt.workflow_id]
        self.assertEqual(before, after)
        self.assertNotIn(receipt.request_id, self.h.uows.store.results)
        self.assertFalse(
            any(
                item.event_type == "assistant.message"
                for item in self.h.uows.store.events[receipt.conversation_id]
            )
        )

    async def test_external_event_defers_while_approval_is_pending(self):
        self.h.bootstrap.pattern = WorkflowPattern.EXTERNAL_TRACKING
        workflow = await self.h.workflows.start_with_binding(
            SCOPE,
            self.actor,
            self.h.audience("ticket-A", "chat-A"),
            {"request_id": "start-A", "text": "book"},
        )
        operation = self.h.add_operation(workflow.workflow_id)
        aggregate = self.h.uows.store.workflows[workflow.workflow_id]
        awaiting = aggregate.model_copy(
            update={
                "workflow": aggregate.workflow.model_copy(
                    update={
                        "state": WorkflowState.AWAITING_APPROVAL,
                        "revision": 2,
                    }
                ),
                "checkpoint": aggregate.checkpoint.model_copy(
                    update={
                        "state_revision": 2,
                        "pending_approval_ids": ("approval-1",),
                    }
                ),
            }
        )
        self.h.uows.store.workflows[workflow.workflow_id] = awaiting
        event = NormalizedJobEvent(
            inbox_event_id="inbox-approval-wait",
            provider_integration_id="provider-1",
            external_event_id="external-approval-wait",
            external_job_id=operation.external_job_id,
            client_reference=operation.correlation_id,
            normalized_status="assigned",
            protocol_schema_hash=operation.protocol_snapshot.schema_hash,
            source_hash="source-hash",
            occurred_at=self.h.clock(),
            received_at=self.h.clock(),
        )
        updated = await self.h.workflows.apply_external_event(
            SCOPE, operation.operation_id, event
        )
        external_job = next(
            item
            for item in self.h.uows.store.jobs.values()
            if item["payload"]["cause"]["kind"] == "external_event"
        )
        outcome = await self.h.continuation.run(
            SCOPE, external_job["payload"], "worker-deferred"
        )
        self.assertEqual("deferred_human_input", outcome)
        self.assertEqual(WorkflowState.AWAITING_APPROVAL, updated.state)
        self.assertEqual(0, self.h.runtime.invocations)

    async def test_revoked_authorization_blocks_without_model_turn(self):
        receipt = await self.ingress.accept(
            self.actor,
            PartnerRequestEnvelope(
                schema_version="1",
                command_type="start_workflow",
                external_request_id="revoked-request",
                external_management_ref="tower-a",
                external_user_id="resident-1",
                external_ticket_id="revoked-ticket",
                external_conversation_id="revoked-chat",
                residence_id="residence-1",
                message={"type": "text", "text": "help"},
            ),
        )
        job = next(iter(self.h.uows.store.jobs.values()))
        self.h.authorization.revoked = True
        outcome = await self.h.continuation.run(
            SCOPE, job["payload"], "worker-revoked"
        )
        self.assertEqual("blocked_authorization", outcome)
        self.assertEqual(0, self.h.runtime.invocations)
        blocked = self.h.uows.store.workflows[receipt.workflow_id]
        self.assertEqual(
            WorkflowState.BLOCKED_AUTHORIZATION,
            blocked.workflow.state,
        )
        projected = await self.ingress.read_result(
            self.actor, receipt.request_id, "resident-1"
        )
        self.assertEqual("blocked", projected.request_status)
        self.assertEqual("resolve_attention", projected.next_action)


if __name__ == "__main__":
    unittest.main()
