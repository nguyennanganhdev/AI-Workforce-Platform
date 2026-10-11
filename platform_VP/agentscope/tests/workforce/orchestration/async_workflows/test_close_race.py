import unittest

from agentscope.app.workforce.contracts import WorkflowState
from agentscope.app.workforce.orchestration.workflows import WorkflowClosed

from fakes import Harness, SCOPE, customer_actor


class CloseRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_during_turn_fences_late_message_and_reopen(self):
        h = Harness()
        actor = customer_actor()
        audience = h.audience("ticket-A", "chat-A")
        workflow = await h.workflows.start_with_binding(
            SCOPE,
            actor,
            audience,
            {"request_id": "start-A", "text": "start"},
        )
        aggregate = h.uows.store.workflows[workflow.workflow_id]
        awaiting = aggregate.model_copy(
            update={
                "workflow": aggregate.workflow.model_copy(
                    update={
                        "state": WorkflowState.AWAITING_CONFIRMATION,
                        "revision": 2,
                    }
                ),
                "checkpoint": aggregate.checkpoint.model_copy(
                    update={"state_revision": 2}
                ),
            }
        )
        h.uows.store.workflows[workflow.workflow_id] = awaiting
        trigger = next(iter(h.uows.store.jobs.values()))["payload"]

        async def close_while_model_returns(context, guard):
            await h.workflows.close(
                SCOPE,
                actor,
                audience,
                {
                    "schema_version": "1",
                    "workflow_id": workflow.workflow_id,
                    "external_request_id": "close-A",
                    "external_user_id": "resident-1",
                    "external_ticket_id": "ticket-A",
                    "external_conversation_id": "chat-A",
                    "expected_revision": 2,
                    "reason": "customer_confirmed",
                    "stop_tracking_only": False,
                },
            )

        h.runtime.before_decision = close_while_model_returns
        with self.assertRaises(WorkflowClosed):
            await h.continuation.run(SCOPE, trigger, "worker-close-race")

        closed = h.uows.store.workflows[workflow.workflow_id]
        self.assertEqual(WorkflowState.CLOSED, closed.workflow.state)
        self.assertEqual(3, closed.workflow.revision)
        self.assertFalse(
            any(
                item.event_type == "assistant.message"
                for item in h.uows.store.events[workflow.conversation_id]
            )
        )
        self.assertNotIn(workflow.workflow_id, h.uows.store.leases)


if __name__ == "__main__":
    unittest.main()
