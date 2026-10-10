# -*- coding: utf-8 -*-
"""Mixed operations, notification deadlines and closed-command CAS controls."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import unittest

from agentscope.app.workforce.contracts import PartnerRequestEnvelope
from agentscope.app.workforce.orchestration import receipt_http_status
from agentscope.app.workforce.orchestration.workflows import WorkflowConflict
from fakes import ACTOR, SCOPE, Harness


class DeepReviewPhaseB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.h = Harness()

    async def accept(self):
        return await self.h.ingress.accept(
            ACTOR,
            PartnerRequestEnvelope.model_validate(
                dict(
                    schema_version="1",
                    command_type="start_workflow",
                    external_request_id="post-A",
                    external_management_ref="management-1",
                    external_user_id="user-1",
                    external_ticket_id="ticket-A",
                    external_conversation_id="chat-A",
                    message=dict(type="text", text="Request A"),
                )
            ),
        )

    async def operations(self, pending_a=False, pending_b=True):
        record = await self.h.start()
        a = self.h.add_operation(record)
        b = a.model_copy(
            update=dict(
                operation_id="operation-B",
                call_id="call-B",
                correlation_id="correlation-B",
                external_job_id="job-B",
            )
        )
        self.h.store.data["operations"][b.operation_id] = b
        self.h.configure(
            record,
            checkpoint=dict(
                operation_refs=[a.operation_id, b.operation_id],
            ),
        )
        self.h.ops.pending_by_operation.update(
            {
                a.operation_id: pending_a,
                b.operation_id: pending_b,
            }
        )
        self.h.runtime.state = "waiting_external_event"
        return record, a, b

    async def run_turn(self, record, request="request-A"):
        return await self.h.continuation.run(
            SCOPE,
            self.h.trigger(record.workflow_id, request),
            "worker-A",
        )

    async def wait(self, receipt, milliseconds=30):
        return await asyncio.wait_for(
            self.h.ingress.wait_for_result(
                ACTOR,
                receipt.request_id,
                "user-1",
                self.h.clock() + timedelta(milliseconds=milliseconds),
            ),
            0.5,
        )

    async def closed(self):
        receipt = await self.accept()
        record = (await self.h.repo.load(SCOPE, receipt.workflow_id)).workflow
        command = self.h.close_command(record)
        command.pop("workflow_id")
        result = await self.h.ingress.close_workflow(
            ACTOR,
            SCOPE,
            record.workflow_id,
            command,
        )
        return record, command, result

    async def test_B152_terminal_a_preserved_while_b_remains_pending(self):
        """Completed A remains in history, while only B is a durable wait."""
        record, a, b = await self.operations()
        self.assertEqual(await self.run_turn(record), "applied")
        bundle = await self.h.repo.load(SCOPE, record.workflow_id)
        self.assertEqual(
            bundle.checkpoint.operation_refs, (a.operation_id, b.operation_id)
        )
        self.assertEqual(bundle.workflow.pending_waits, (b.operation_id,))

    async def test_B153_terminal_b_does_not_block_waiting_for_a(self):
        """Active wait selection is independent of operation order."""
        record, a, b = await self.operations(True, False)
        self.assertEqual(await self.run_turn(record), "applied")
        bundle = await self.h.repo.load(SCOPE, record.workflow_id)
        self.assertEqual(bundle.workflow.pending_waits, (a.operation_id,))
        self.assertIn(b.operation_id, bundle.checkpoint.operation_refs)

    async def test_B154_two_pending_operations_are_both_waited_on(self):
        """The valid all-pending control retains both active waits."""
        record, a, b = await self.operations(True, True)
        await self.run_turn(record)
        bundle = await self.h.repo.load(SCOPE, record.workflow_id)
        self.assertEqual(
            bundle.workflow.pending_waits, (a.operation_id, b.operation_id)
        )

    async def test_B155_all_terminal_operations_cannot_select_external_wait(
        self,
    ):
        """No pending operation permits external wait; failure is atomic."""
        record, _, _ = await self.operations(False, False)
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.run_turn(record)
        self.assertEqual(self.h.store.data, before)

    async def test_B156_all_terminal_operations_allow_confirmation(self):
        """Completion confirmation retains terminal history and no waits."""
        record, a, b = await self.operations(False, False)
        self.h.runtime.state = "awaiting_confirmation"
        await self.run_turn(record)
        bundle = await self.h.repo.load(SCOPE, record.workflow_id)
        self.assertEqual(bundle.workflow.state, "awaiting_confirmation")
        self.assertEqual(bundle.workflow.pending_waits, ())
        self.assertEqual(
            bundle.checkpoint.operation_refs, (a.operation_id, b.operation_id)
        )

    async def test_B157_mixed_operations_cannot_claim_completion(self):
        """B still pending prevents completion even when A is terminal."""
        record, _, _ = await self.operations()
        self.h.runtime.state = "awaiting_confirmation"
        with self.assertRaises(WorkflowConflict):
            await self.run_turn(record)

    async def test_B158_terminal_history_still_requires_matching_audience(
        self,
    ):
        """Ignoring terminal waits never skips historical isolation checks."""
        record, a, _ = await self.operations()
        self.h.store.data["operations"][a.operation_id] = a.model_copy(
            update={
                "audience": a.audience.model_copy(
                    update={"external_ticket_id": "ticket-B"}
                ),
            }
        )
        with self.assertRaises(WorkflowConflict):
            await self.run_turn(record)

    async def test_B159_next_turn_can_finish_the_last_pending_operation(self):
        """Last-job completion advances mixed wait to confirmation."""
        record, a, b = await self.operations()
        await self.run_turn(record)
        current = (await self.h.repo.load(SCOPE, record.workflow_id)).workflow
        await self.h.workflows.accept_reply(
            SCOPE,
            ACTOR,
            current.audience,
            current.workflow_id,
            dict(
                request_id="reply-A",
                text="Check status",
                expected_revision=current.revision,
            ),
        )
        self.h.ops.pending_by_operation[b.operation_id] = False
        self.h.runtime.state = "awaiting_confirmation"
        await self.run_turn(current, "reply-A")
        bundle = await self.h.repo.load(SCOPE, record.workflow_id)
        self.assertEqual(bundle.workflow.pending_waits, ())
        self.assertEqual(
            bundle.checkpoint.operation_refs, (a.operation_id, b.operation_id)
        )

    async def test_B160_hung_advisory_signal_obeys_deadline_and_is_cancelled(
        self,
    ):
        """A never-returning signal cannot keep a 30ms wait open for 500ms."""
        receipt = await self.accept()
        cleaned = asyncio.Event()

        async def hung(*args):
            try:
                await asyncio.Future()
            finally:
                cleaned.set()

        self.h.completion.wait_for_completion = hung
        result = await self.wait(receipt)
        await asyncio.wait_for(cleaned.wait(), 0.2)
        self.assertEqual(receipt_http_status(result), 202)
        self.assertFalse(self.h.runtime.calls)

    async def test_B161_signal_cancellation_cleanup_cannot_extend_deadline(
        self,
    ):
        """Slow cleanup runs independently of the request's bounded wait."""
        receipt = await self.accept()
        release = asyncio.Event()
        cleaned = asyncio.Event()

        async def slow_cleanup(*args):
            try:
                await asyncio.Future()
            finally:
                await release.wait()
                cleaned.set()

        self.h.completion.wait_for_completion = slow_cleanup
        task = asyncio.create_task(
            self.h.ingress.wait_for_result(
                ACTOR,
                receipt.request_id,
                "user-1",
                self.h.clock() + timedelta(milliseconds=30),
            )
        )
        try:
            done, _ = await asyncio.wait({task}, timeout=0.5)
            self.assertIn(task, done, "signal cleanup exceeded wait deadline")
            result = task.result()
            self.assertEqual(receipt_http_status(result), 202)
            self.assertFalse(cleaned.is_set())
        finally:
            release.set()
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await asyncio.wait_for(cleaned.wait(), 0.2)

    async def test_B162_timeout_rereads_a_result_committed_without_signal(
        self,
    ):
        """A lost signal still returns the durable result after timeout."""
        receipt = await self.accept()

        async def lost(*args):
            await self.h.continuation.run(
                SCOPE,
                self.h.trigger(receipt.workflow_id, receipt.request_id),
                "worker-A",
            )
            await asyncio.Future()

        self.h.completion.wait_for_completion = lost
        result = await self.wait(receipt)
        self.assertEqual(receipt_http_status(result), 200)
        self.assertEqual(result.request_status, "completed")
        self.assertEqual(len(self.h.runtime.calls), 1)

    async def test_B163_caller_cancellation_cleans_up_signal_waiter(self):
        """Client cancellation propagates and cancels the subscription."""
        receipt = await self.accept()
        entered, cleaned = asyncio.Event(), asyncio.Event()

        async def hung(*args):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                cleaned.set()

        self.h.completion.wait_for_completion = hung
        task = asyncio.create_task(
            self.h.ingress.wait_for_result(
                ACTOR,
                receipt.request_id,
                "user-1",
                self.h.clock() + timedelta(seconds=5),
            )
        )
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(cleaned.wait(), 0.2)

    async def test_B164_timeout_revalidates_permission_before_returning(self):
        """Signal timeout never returns a cached receipt after revocation."""
        receipt = await self.accept()

        async def revoke(*args):
            self.h.auth.revoked = True
            await asyncio.Future()

        self.h.completion.wait_for_completion = revoke
        with self.assertRaises(PermissionError):
            await self.wait(receipt)

    async def test_B165_immediate_signal_failure_does_not_busy_loop(self):
        """A failed advisory port backs off for the remaining slice."""
        receipt = await self.accept()
        calls = []

        async def failed(*args):
            calls.append(args)
            raise OSError("advisory outage")

        self.h.completion.wait_for_completion = failed
        self.assertEqual(receipt_http_status(await self.wait(receipt)), 202)
        self.assertEqual(len(calls), 1)

    async def test_B166_new_close_id_with_stale_revision_conflicts(self):
        """A new command on a closed workflow still enforces revision CAS."""
        record, command, _ = await self.closed()
        before = deepcopy(self.h.store.data)
        command["external_request_id"] = "close-B"
        with self.assertRaises(WorkflowConflict):
            await self.h.ingress.close_workflow(
                ACTOR, SCOPE, record.workflow_id, command
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B167_new_close_id_with_future_revision_conflicts(self):
        """Closed state cannot turn an impossible revision into success."""
        record, command, _ = await self.closed()
        before = deepcopy(self.h.store.data)
        command.update(external_request_id="close-B", expected_revision=999)
        with self.assertRaises(WorkflowConflict):
            await self.h.ingress.close_workflow(
                ACTOR, SCOPE, record.workflow_id, command
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B168_exact_close_retry_reads_result_before_revision_check(
        self,
    ):
        """Same ID/body retry reads its result without new effects."""
        record, command, first = await self.closed()
        before = deepcopy(self.h.store.data)
        retry = await self.h.ingress.close_workflow(
            ACTOR, SCOPE, record.workflow_id, command
        )
        self.assertEqual(retry, first)
        self.assertEqual(self.h.store.data, before)

    async def test_B169_new_closed_command_current_revision_does_not_emit(
        self,
    ):
        """Valid new command on closed state does not emit another close."""
        record, command, first = await self.closed()
        before_events = deepcopy(self.h.store.data["events"])
        command.update(
            external_request_id="close-B",
            expected_revision=first.workflow_revision,
        )
        second = await self.h.ingress.close_workflow(
            ACTOR, SCOPE, record.workflow_id, command
        )
        self.assertEqual(second.workflow_revision, first.workflow_revision)
        self.assertNotEqual(second.request_id, first.request_id)
        self.assertEqual(self.h.store.data["events"], before_events)

    async def test_B170_close_retry_changed_body_still_conflicts(self):
        """Idempotency cannot conceal different content even after closure."""
        record, command, _ = await self.closed()
        before = deepcopy(self.h.store.data)
        command["reason"] = "Different reason"
        with self.assertRaises(WorkflowConflict):
            await self.h.ingress.close_workflow(
                ACTOR, SCOPE, record.workflow_id, command
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B171_direct_close_on_closed_state_checks_revision(self):
        """The workflow service itself must guard new direct close calls."""
        record, command, _ = await self.closed()
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.close(
                SCOPE,
                ACTOR,
                record.audience,
                {
                    **command,
                    "workflow_id": record.workflow_id,
                    "expected_revision": 999,
                },
            )

    def create_only_protocol(self, record, operation):
        protocol = operation.protocol_snapshot.model_copy(
            update={
                "protocol_id": "create-only",
                "tool_version_id": "tool-version-create-only",
                "capabilities": ("create",),
            }
        )
        self.h.store.data["operations"][
            operation.operation_id
        ] = operation.model_copy(
            update={"protocol_snapshot": protocol},
        )
        bundle = self.h.store.data["workflows"][record.workflow_id]
        self.h.configure(
            record,
            checkpoint={
                "protocol_pins": [*bundle.checkpoint.protocol_pins, protocol],
            },
        )

    async def test_B172_active_create_only_operation_cannot_become_wait(self):
        """Every active operation still requires tracking capability."""
        record, _, b = await self.operations(True, True)
        self.create_only_protocol(record, b)
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.run_turn(record)
        self.assertEqual(self.h.store.data, before)

    async def test_B173_terminal_create_only_history_does_not_block_wait(self):
        """Completed create-only history does not need tracking capability."""
        record, a, b = await self.operations(True, False)
        self.create_only_protocol(record, b)
        await self.run_turn(record)
        bundle = await self.h.repo.load(SCOPE, record.workflow_id)
        self.assertEqual(bundle.workflow.pending_waits, (a.operation_id,))
        self.assertIn(b.operation_id, bundle.checkpoint.operation_refs)

    async def test_B175_operation_lookup_cannot_relabel_a_historical_ref(self):
        """A terminal lookup must return the exact referenced operation ID."""
        record, a, _ = await self.operations()
        self.h.store.data["operations"][a.operation_id] = a.model_copy(
            update={"operation_id": "operation-other"}
        )
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.run_turn(record)
        self.assertEqual(self.h.store.data, before)

    async def test_B174_runtime_cannot_discard_terminal_operation_history(
        self,
    ):
        """Removing completed A to avoid mixed waits remains prohibited."""
        record, _, b = await self.operations()

        def discard(plan):
            plan["candidate"]["checkpoint"]["operation_refs"] = [
                b.operation_id
            ]

        self.h.runtime.mutate = discard
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.run_turn(record)
        self.assertEqual(self.h.store.data, before)
