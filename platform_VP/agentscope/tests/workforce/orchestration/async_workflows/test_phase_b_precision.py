# -*- coding: utf-8 -*-
"""Regression controls for defects found when rebuilding Phase B."""

import asyncio
from copy import deepcopy
import unittest

from agentscope.app.workforce.contracts import (
    ConversationSnapshot,
    PartnerRequestEnvelope,
)
from agentscope.app.workforce.orchestration._ingress import RequestView
from agentscope.app.workforce.orchestration.partner_events import (
    ConversationEventService,
)
from agentscope.app.workforce.orchestration.workflows import WorkflowConflict
from fakes import ACTOR, SCOPE, Harness


class PrecisionPhaseB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.h = Harness()
        self.body = dict(
            schema_version="1",
            command_type="start_workflow",
            external_request_id="post-A",
            external_management_ref="management-1",
            external_user_id="user-1",
            external_ticket_id="ticket-A",
            external_conversation_id="chat-A",
            message=dict(type="text", text="Request A"),
        )

    async def accept(self):
        return await self.h.ingress.accept(
            ACTOR, PartnerRequestEnvelope.model_validate(self.body)
        )

    async def test_B113_reply_reuses_original_route_without_resolving_again(
        self,
    ):
        """Reply A after remapping must use A's saved route and group."""
        first = await self.accept()

        async def forbidden_resolve(*args):
            raise AssertionError("reply must not resolve a new manager route")

        self.h.ingress.routing.resolve = forbidden_resolve
        self.body.update(
            command_type="workflow_reply",
            workflow_id=first.workflow_id,
            external_request_id="reply-A",
        )
        reply = await self.accept()
        self.assertEqual(reply.workflow_id, first.workflow_id)
        self.assertEqual(self.h.bootstrap.count, 1)

    async def test_B114_reply_changed_management_ref_is_rejected_atomically(
        self,
    ):
        """A new management ref cannot move an existing workflow."""
        first = await self.accept()
        before = deepcopy(self.h.store.data)
        self.body.update(
            command_type="workflow_reply",
            workflow_id=first.workflow_id,
            external_request_id="reply-A",
            external_management_ref="other-manager",
        )
        with self.assertRaises((PermissionError, WorkflowConflict)):
            await self.accept()
        self.assertEqual(self.h.store.data, before)

    async def test_B115_lost_signal_reader_still_catches_up_from_durable_log(
        self,
    ):
        """Signal outage yields a heartbeat then reloads committed events."""
        record = await self.h.start()
        cursor = self.h.store.data["events"][record.conversation_id][
            -1
        ].event_id
        calls = 0

        async def broken_signal(*args):
            nonlocal calls
            calls += 1
            async with self.h.uows() as tx:
                await self.h.writer.write(
                    record,
                    "workflow.status_changed",
                    {"state": "awaiting_user", "revision": 2},
                    tx,
                )
                await tx.commit()
            raise ConnectionError("test-only Redis outage")

        self.h.signals.wait_for_signal = broken_signal
        frames = self.h.events.sse.frames(
            ACTOR, SCOPE, record.conversation_id, cursor
        )
        try:
            heartbeat = await asyncio.wait_for(anext(frames), 1)
            self.assertEqual(heartbeat.comment, "heartbeat")
            frame = await asyncio.wait_for(anext(frames), 1)
            self.assertEqual(frame.event_type, "workflow.status_changed")
            self.assertEqual(calls, 1)
        finally:
            await frames.aclose()

    async def test_B116_auth_recheck_cannot_be_delayed_over_sixty_seconds(
        self,
    ):
        """Reject heartbeat configuration beyond the revocation bound."""
        with self.assertRaises(ValueError):
            ConversationEventService(
                self.h.event_repo,
                self.h.auth,
                self.h.signals,
                self.h.uows,
                heartbeat_seconds=61,
            )

    async def test_B117_snapshot_rejects_private_approval_fields(self):
        """Public snapshots never serialize a copied credential field."""
        record = await self.h.start()
        access = await self.h.event_repo.access(record.conversation_id)
        control = await self.h.event_repo.snapshot(access)
        self.assertEqual(
            (await self.h.events.snapshot(ACTOR, record.conversation_id))[
                "pending_approvals"
            ],
            [],
        )
        data = control.model_dump()
        data["pending_approvals"] = [
            {
                "workflow_id": record.workflow_id,
                "approval_id": "approval-A",
                "credential_ref": "private-test-reference",
            }
        ]
        self.h.event_repo.bad_snapshot = ConversationSnapshot.model_validate(
            data
        )
        with self.assertRaises((PermissionError, ValueError)):
            await self.h.events.snapshot(ACTOR, record.conversation_id)

    async def test_B118_pending_operation_cannot_claim_completion_confirmation(
        self,
    ):
        """An unfinished operation cannot produce confirm_close."""
        record = await self.h.start()
        self.h.add_operation(record)
        self.h.runtime.state = "awaiting_confirmation"
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.h.continuation.run(
                SCOPE, self.h.trigger(record.workflow_id), "worker-A"
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B119_terminal_operation_allows_completion_confirmation(
        self,
    ):
        """Valid terminal control reaches confirm_close."""
        record = await self.h.start()
        self.h.add_operation(record)
        self.h.ops.pending = False
        self.h.runtime.state = "awaiting_confirmation"
        self.assertEqual(
            await self.h.continuation.run(
                SCOPE, self.h.trigger(record.workflow_id), "worker-A"
            ),
            "applied",
        )

    async def test_B120_history_rejects_copied_extra_envelope_field(self):
        """model_copy cannot bypass closed history envelope validation."""
        record = await self.h.start()
        control = await self.h.events.list_after(
            ACTOR, record.conversation_id, None, 10
        )
        self.assertEqual(len(control.items), 1)
        self.h.event_repo.bad_page = control.model_copy(
            update={"internal_trace": "private-test-data"}
        )
        with self.assertRaises(ValueError):
            await self.h.events.list_after(
                ACTOR, record.conversation_id, None, 10
            )

    async def test_B121_snapshot_rejects_copied_extra_envelope_field(self):
        """Snapshots revalidate models instead of trusting model_copy."""
        record = await self.h.start()
        access = await self.h.event_repo.access(record.conversation_id)
        control = await self.h.event_repo.snapshot(access)
        self.h.event_repo.bad_snapshot = control.model_copy(
            update={"internal_trace": "private-test-data"}
        )
        with self.assertRaises(ValueError):
            await self.h.events.snapshot(ACTOR, record.conversation_id)

    async def test_B122_non_finite_heartbeat_is_rejected(self):
        """NaN cannot disable periodic authorization/catch-up checks."""
        with self.assertRaises(ValueError):
            ConversationEventService(
                self.h.event_repo,
                self.h.auth,
                self.h.signals,
                self.h.uows,
                heartbeat_seconds=float("nan"),
            )

    async def test_B123_close_boolean_revision_is_rejected_before_claim(self):
        """True must not become revision 1 through canonical DTO coercion."""
        receipt = await self.accept()
        record = (await self.h.repo.load(SCOPE, receipt.workflow_id)).workflow
        command = self.h.close_command(record, expected_revision=True)
        command.pop("workflow_id")
        before = deepcopy(self.h.store.data)
        with self.assertRaises(ValueError):
            await self.h.ingress.close_workflow(
                ACTOR, SCOPE, record.workflow_id, command
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B124_close_string_flag_is_rejected_before_claim(self):
        """The string false cannot enable a stop-tracking close."""
        receipt = await self.accept()
        record = (await self.h.repo.load(SCOPE, receipt.workflow_id)).workflow
        command = self.h.close_command(record, stop_tracking_only="false")
        command.pop("workflow_id")
        before = deepcopy(self.h.store.data)
        with self.assertRaises(ValueError):
            await self.h.ingress.close_workflow(
                ACTOR, SCOPE, record.workflow_id, command
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B125_copied_nested_message_cannot_add_scope(self):
        """Nested model_copy extras cannot enter the command ledger."""
        control = PartnerRequestEnvelope.model_validate(self.body)
        forged = control.model_copy(
            update={
                "message": control.message.model_copy(
                    update={"scope": SCOPE.model_dump()}
                )
            }
        )
        with self.assertRaises(ValueError):
            await self.h.ingress.accept(ACTOR, forged)
        self.assertFalse(self.h.store.data["claims"])

    async def test_B126_copied_request_view_extras_cannot_be_serialized(self):
        """Persisted read views are revalidated before public projection."""
        receipt = await self.accept()
        read = self.h.ingress.requests.read

        async def corrupted(*args, **kwargs):
            control = await read(*args, **kwargs)
            self.assertIsInstance(control, RequestView)
            return control.model_copy(update={"internal_trace": "private"})

        self.h.ingress.requests.read = corrupted
        with self.assertRaises(ValueError):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B127_sse_signal_cancellation_is_not_swallowed(self):
        """Cancellation propagates rather than opening another stream read."""
        record = await self.h.start()
        cursor = self.h.store.data["events"][record.conversation_id][
            -1
        ].event_id

        async def cancelled(*args):
            raise asyncio.CancelledError()

        self.h.signals.wait_for_signal = cancelled
        frames = self.h.events.sse.frames(
            ACTOR, SCOPE, record.conversation_id, cursor
        )
        try:
            with self.assertRaises(asyncio.CancelledError):
                await anext(frames)
        finally:
            await frames.aclose()

    async def test_B128_hung_signal_is_bounded_and_rechecks_revocation(self):
        """A hung notification cannot prevent the next authorization read."""
        record = await self.h.start()
        cursor = self.h.store.data["events"][record.conversation_id][
            -1
        ].event_id

        async def hung(*args):
            await asyncio.Future()

        self.h.signals.wait_for_signal = hung
        frames = self.h.events.sse.frames(
            ACTOR, SCOPE, record.conversation_id, cursor
        )
        try:
            self.assertEqual(
                (await asyncio.wait_for(anext(frames), 1)).comment, "heartbeat"
            )
            self.h.auth.revoked = True
            with self.assertRaises(PermissionError):
                await asyncio.wait_for(anext(frames), 1)
        finally:
            await frames.aclose()

    async def test_B129_duplicate_snapshot_approval_ids_are_rejected(self):
        """Two public approvals cannot silently share an identity."""
        record = await self.h.start()
        access = await self.h.event_repo.access(record.conversation_id)
        control = await self.h.event_repo.snapshot(access)
        approval = dict(
            workflow_id=record.workflow_id, approval_id="approval-A"
        )
        self.h.event_repo.bad_snapshot = control.model_copy(
            update={"pending_approvals": (approval, approval)}
        )
        with self.assertRaises(PermissionError):
            await self.h.events.snapshot(ACTOR, record.conversation_id)

    async def test_B130_boolean_history_sequence_is_not_coerced(self):
        """A forged bool sequence cannot become integer sequence 1."""
        record = await self.h.start()
        control = await self.h.events.list_after(
            ACTOR, record.conversation_id, None, 10
        )
        self.h.event_repo.bad_page = control.model_copy(
            update={
                "items": (
                    control.items[0].model_copy(update={"sequence": True}),
                )
            }
        )
        with self.assertRaises(ValueError):
            await self.h.events.list_after(
                ACTOR, record.conversation_id, None, 10
            )
