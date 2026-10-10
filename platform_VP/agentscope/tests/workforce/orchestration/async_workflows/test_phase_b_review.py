"""Review regressions and the complete MB lifecycle using fake dependencies."""

from copy import deepcopy
import unittest

from agentscope.app.workforce.contracts import EventHistoryPage, WorkflowState
from agentscope.app.workforce.orchestration.workflows import (
    WorkflowConflict,
    next_action,
)
from fakes import ACTOR, SCOPE, Harness


class ReviewPhaseB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.h = Harness()
        self.a = await self.h.start()

    async def run_turn(self, trigger=None):
        return await self.h.continuation.run(
            SCOPE, trigger or self.h.trigger(self.a.workflow_id), "worker"
        )

    async def test_B096_start_checkpoint_ref_is_persisted(
        self,
    ):
        ref = self.a.checkpoint_ref
        self.assertIn(ref, self.h.store.data["checkpoints"])
        self.assertEqual(
            self.h.store.data["checkpoints"][ref].workflow_id,
            self.a.workflow_id,
        )

    async def test_B097_conflicting_duplicate_inbox_hash_is_rejected(self):
        self.h.add_operation(self.a)
        await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event()
        )
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.apply_external_event(
                SCOPE, "operation-A", self.h.event(source_hash="different")
            )
        self.assertEqual(before, self.h.store.data)

    async def test_B098_both_correlations_must_match(self):
        self.h.add_operation(self.a)
        with self.assertRaises(PermissionError):
            await self.h.workflows.apply_external_event(
                SCOPE,
                "operation-A",
                self.h.event(
                    external_job_id="job-B", client_reference="correlation-A"
                ),
            )

    async def test_B099_pending_approval_cannot_disappear_on_plain_reply(self):
        self.h.configure(
            self.a,
            state="awaiting_approval",
            checkpoint=dict(pending_approval_ids=["approval-A"]),
        )
        self.h.runtime.mutate = lambda p: p["candidate"]["checkpoint"].update(
            pending_approval_ids=[]
        )
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()

    async def test_B100_resolving_A_cannot_remove_pending_B(self):
        self.h.configure(
            self.a,
            state="awaiting_approval",
            checkpoint=dict(pending_approval_ids=["approval-A", "approval-B"]),
        )
        trigger = self.h.trigger(
            self.a.workflow_id,
            "verified-approval-request",
            "approval",
            approval_id="approval-A",
        )
        with self.assertRaises(WorkflowConflict):
            await self.run_turn(trigger)

    async def test_B101_runtime_cannot_discard_pending_operation(
        self,
    ):
        self.h.add_operation(self.a)
        self.h.runtime.mutate = lambda p: p["candidate"]["checkpoint"].update(
            operation_refs=[]
        )
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()

    async def test_B102_foreign_operation_is_rejected_even_when_not_waiting(
        self,
    ):
        operation = self.h.add_operation(self.a)
        self.h.store.data["operations"]["operation-A"] = operation.model_copy(
            update={"workflow_id": "workflow-B"}
        )
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()

    async def test_B103_read_only_guard_rejects_write_side_effect(self):
        self.h.configure(
            self.a, pattern="response_only", published_read_only=True
        )
        self.h.runtime.state = "closed"

        async def write(guard):
            await guard.check("write")

        self.h.runtime.hook = write
        with self.assertRaises(PermissionError):
            await self.run_turn()
        self.assertFalse(self.h.store.data["results"])

    async def test_B104_plain_close_requires_confirmation_state(self):
        command = self.h.close_command(self.a, stop_tracking_only=False)
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.close(
                SCOPE, ACTOR, self.a.audience, command
            )
        self.h.configure(self.a, state="awaiting_confirmation")
        result = await self.h.workflows.close(
            SCOPE, ACTOR, self.a.audience, command
        )
        self.assertEqual(result.state, WorkflowState.CLOSED)

    async def test_B105_same_conversation_wrong_workflow_event_is_rejected(
        self,
    ):
        event = self.h.store.data["events"][self.a.conversation_id][0]
        foreign = event.model_copy(update={"workflow_id": "workflow-B"})
        self.h.event_repo.bad_page = EventHistoryPage(
            items=(foreign,), next_cursor=foreign.event_id, has_more=False
        )
        with self.assertRaises(PermissionError):
            await self.h.events.list_after(
                ACTOR, self.a.conversation_id, None, 10
            )

    async def test_B106_full_MB_lifecycle_request_progress_confirmation_close(
        self,
    ):
        b = await self.h.start("B")
        self.h.add_operation(self.a)
        self.h.runtime.state = "waiting_external_event"
        await self.run_turn()
        original = await self.h.repo.load(SCOPE, self.a.workflow_id)
        for version, status in enumerate(
            ("assigned", "on_the_way", "arrived", "completed"), 1
        ):
            if status == "completed":
                self.h.ops.pending = False
                self.h.runtime.state = "awaiting_confirmation"
            event = self.h.event(
                inbox_event_id=f"inbox-{version}",
                external_event_id=f"provider-{version}",
                source_hash=f"hash-{version}",
                provider_version=version,
                normalized_status=status,
            )
            await self.h.workflows.apply_external_event(
                SCOPE, "operation-A", event
            )
            trigger = next(
                t
                for t in self.h.store.data["jobs"].values()
                if t["cause"].get("cause_event_id") == event.inbox_event_id
            )
            self.assertEqual(await self.run_turn(trigger), "applied")
            current = await self.h.repo.load(SCOPE, self.a.workflow_id)
            self.assertEqual(
                current.workflow.group_id, original.workflow.group_id
            )
            self.assertEqual(
                current.checkpoint.session_refs,
                original.checkpoint.session_refs,
            )
            self.assertEqual(
                current.checkpoint.protocol_pins,
                original.checkpoint.protocol_pins,
            )
        current = (await self.h.repo.load(SCOPE, self.a.workflow_id)).workflow
        self.assertEqual(current.state, "awaiting_confirmation")
        closed = await self.h.workflows.close(
            SCOPE,
            ACTOR,
            current.audience,
            self.h.close_command(current, stop_tracking_only=False),
        )
        self.assertEqual(closed.state, "closed")
        page = await self.h.events.list_after(
            ACTOR, current.conversation_id, None, 100
        )
        statuses = [
            e.payload["status"]
            for e in page.items
            if e.event_type == "operation.status_changed"
        ]
        self.assertEqual(
            statuses, ["assigned", "on_the_way", "arrived", "completed"]
        )
        self.assertEqual(page.items[-1].event_type, "workflow.closed")
        self.assertEqual(
            [e.sequence for e in page.items],
            list(range(1, len(page.items) + 1)),
        )
        self.assertEqual(
            (await self.h.repo.load(SCOPE, b.workflow_id)).workflow.state,
            "accepted",
        )
        self.assertEqual(len(self.h.runtime.calls), 5)

    async def test_B107_close_uses_shared_command_namespace(self):
        body = dict(
            schema_version="1",
            command_type="start_workflow",
            external_request_id="post-B",
            external_management_ref="management-1",
            external_user_id="user-1",
            external_ticket_id="ticket-B",
            external_conversation_id="chat-B",
            message=dict(type="text", text="B"),
        )
        from agentscope.app.workforce.contracts import PartnerRequestEnvelope

        receipt = await self.h.ingress.accept(
            ACTOR, PartnerRequestEnvelope.model_validate(body)
        )
        record = (await self.h.repo.load(SCOPE, receipt.workflow_id)).workflow
        command = self.h.close_command(record)
        command.pop("workflow_id")
        from agentscope.app.workforce.contracts import CloseWorkflowCommand

        command["external_request_id"] = "post-B"
        with self.assertRaises(WorkflowConflict):
            await self.h.ingress.close_workflow(
                ACTOR,
                SCOPE,
                record.workflow_id,
                CloseWorkflowCommand.model_validate(command),
            )

    async def test_B108_close_retry_ignores_old_revision_after_claim(self):
        from agentscope.app.workforce.contracts import CloseWorkflowCommand

        command = self.h.close_command(self.a)
        command.pop("workflow_id")
        command = CloseWorkflowCommand.model_validate(command)
        first = await self.h.ingress.close_workflow(
            ACTOR, SCOPE, self.a.workflow_id, command
        )
        second = await self.h.ingress.close_workflow(
            ACTOR, SCOPE, self.a.workflow_id, command
        )
        self.assertEqual(first, second)
        self.assertEqual(first.request_status, "completed")
        self.assertEqual(first.next_action, "none")
        self.assertEqual(
            len(self.h.store.data["events"][self.a.conversation_id]), 2
        )

    async def test_B109_all_state_projections_are_defined(self):
        for state in WorkflowState:
            self.assertTrue(next_action(state))

    async def test_B110_opaque_ids_cannot_collide_in_job_dedupe_key(self):
        original = await self.h.repo.load(SCOPE, self.a.workflow_id)
        self.h.store.data["jobs"].clear()
        for workflow_id, request_id in (
            ("A:request:B", "C"),
            ("A", "B:request:C"),
        ):
            data = original.model_dump()
            data["workflow"]["workflow_id"] = workflow_id
            data["checkpoint"]["workflow_id"] = workflow_id
            from agentscope.app.workforce.orchestration.workflows import (
                WorkflowBundle,
            )

            self.h.store.data["workflows"][
                workflow_id
            ] = WorkflowBundle.model_validate(data)
            tx = self.h.uows()
            await self.h.repo.record_input(
                SCOPE, workflow_id, ("request", request_id), "input", tx
            )
            await self.h.workflows.enqueue_trigger(
                SCOPE, self.h.trigger(workflow_id, request_id), tx
            )
            await tx.commit()
        self.assertEqual(len(self.h.store.data["jobs"]), 2)

    async def test_B111_runtime_message_naive_time_is_rejected(self):
        self.h.runtime.mutate = lambda p: p["candidate"]["result"]["messages"][
            0
        ].update(created_at="2026-10-10T09:00:00")
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()
        self.assertFalse(self.h.store.data["results"])

    async def test_B112_new_start_cannot_implicitly_reply_to_bound_ticket(
        self,
    ):
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.h.start("A", request="new-request-A")
        self.assertEqual(before, self.h.store.data)
