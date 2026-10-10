# -*- coding: utf-8 -*-
"""Regression cases derived from the independent Phase B critique."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import unittest

from agentscope.app.workforce.contracts import (
    PartnerRequestEnvelope,
    PublicError,
)
from agentscope.app.workforce.orchestration import receipt_http_status
from agentscope.app.workforce.orchestration.workflows import WorkflowConflict
from fakes import ACTOR, SCOPE, Harness


class CriticPhaseB(unittest.IsolatedAsyncioTestCase):
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

    async def replay(self, subscribe=False):
        record = await self.h.start()
        async with self.h.uows() as tx:
            await self.h.writer.write(
                record,
                "workflow.status_changed",
                {"state": "awaiting_user", "revision": 2},
                tx,
            )
            await tx.commit()
        method = self.h.events.subscribe if subscribe else self.h.events.stream
        return record, method(ACTOR, record.conversation_id)

    def terminal(self, receipt, status="failed"):
        request = self.h.store.data["requests"][receipt.request_id]
        self.h.store.data["requests"][receipt.request_id] = request.model_copy(
            update={"status": status, "completed_at": self.h.clock()}
        )
        error = PublicError.model_validate(
            dict(
                code="RUNTIME_FAILED",
                message="The request could not be completed.",
                request_id=receipt.request_id,
                retryable=True,
            )
        )
        self.h.store.data.setdefault("errors", {})[receipt.request_id] = error
        return error

    async def test_B131_slow_replay_revalidates_before_each_sse_frame(self):
        """A revoked reader cannot consume the next cached page item."""
        _, stream = await self.replay()
        try:
            self.assertIn(b"request.accepted", await anext(stream))
            self.h.clock.tick(61)
            self.h.auth.revoked = True
            with self.assertRaises(PermissionError):
                await anext(stream)
        finally:
            await stream.aclose()

    async def test_B132_subscription_rechecks_revocation_within_one_page(self):
        """Semantic subscription must use the same per-frame guard."""
        _, stream = await self.replay(subscribe=True)
        try:
            self.assertEqual((await anext(stream)).sequence, 1)
            self.h.auth.revoked = True
            with self.assertRaises(PermissionError):
                await anext(stream)
        finally:
            await stream.aclose()

    async def test_B133_idle_revocation_blocks_the_next_heartbeat(self):
        """Revoked clients do not retain a successful idle stream."""
        record = await self.h.start()
        stream = self.h.events.stream(ACTOR, record.conversation_id)
        try:
            await anext(stream)
            self.h.auth.revoked = True
            with self.assertRaises(PermissionError):
                await asyncio.wait_for(anext(stream), 1)
        finally:
            await stream.aclose()

    async def test_B134_binding_change_invalidates_an_already_loaded_page(
        self,
    ):
        """A stored binding cannot change between streamed frames."""
        _, stream = await self.replay()
        try:
            await anext(stream)
            access = self.h.event_repo.access

            async def changed(*args, **kwargs):
                original = await access(*args, **kwargs)
                return original.model_copy(update={"workflow_id": "other"})

            self.h.event_repo.access = changed
            with self.assertRaises(PermissionError):
                await anext(stream)
        finally:
            await stream.aclose()

    async def test_B135_failed_result_preserves_persisted_public_error(self):
        """GET result exposes the original safe terminal failure."""
        receipt = await self.accept()
        error = self.terminal(receipt)
        result = await self.h.ingress.read_result(
            ACTOR, receipt.request_id, "user-1"
        )
        self.assertEqual(result.error, error)
        self.assertEqual(result.next_action, "resolve_attention")
        self.assertEqual(receipt_http_status(result), 200)

    async def test_B136_blocked_result_preserves_public_error(self):
        """Blocked is also a terminal result with a public cause."""
        receipt = await self.accept()
        error = self.terminal(receipt, status="blocked")
        result = await self.h.ingress.read_result(
            ACTOR, receipt.request_id, "user-1"
        )
        self.assertEqual(result.error, error)
        self.assertEqual(result.request_status, "blocked")

    async def test_B137_foreign_public_error_is_rejected(self):
        """A failure from another request must never be returned."""
        receipt = await self.accept()
        error = self.terminal(receipt)
        self.h.store.data["errors"][receipt.request_id] = error.model_copy(
            update={"request_id": "request-B"}
        )
        with self.assertRaises(PermissionError):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B138_completed_request_cannot_include_failure(self):
        """Result, status and error form one consistent projection."""
        receipt = await self.accept()
        await self.h.continuation.run(
            SCOPE,
            self.h.trigger(receipt.workflow_id, receipt.request_id),
            "worker-A",
        )
        error = PublicError(
            code="RUNTIME_FAILED",
            message="Failed",
            request_id=receipt.request_id,
        )
        self.h.store.data.setdefault("errors", {})[receipt.request_id] = error
        with self.assertRaises(WorkflowConflict):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B139_pending_request_cannot_include_terminal_error(self):
        """A pending result must not be mixed with a previous failure."""
        receipt = await self.accept()
        error = PublicError(
            code="RUNTIME_FAILED",
            message="Failed",
            request_id=receipt.request_id,
        )
        self.h.store.data.setdefault("errors", {})[receipt.request_id] = error
        with self.assertRaises(WorkflowConflict):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B140_failed_request_requires_a_persisted_error(self):
        """Repositories cannot silently discard terminal error details."""
        receipt = await self.accept()
        self.terminal(receipt)
        del self.h.store.data["errors"][receipt.request_id]
        with self.assertRaises(WorkflowConflict):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B141_failed_retry_and_bounded_wait_keep_the_same_error(
        self,
    ):
        """Retry reads the old failure without another group/turn."""
        first = await self.accept()
        error = self.terminal(first)
        before = deepcopy(self.h.store.data)
        retry = await self.accept()
        waited = await self.h.ingress.wait_for_result(
            ACTOR,
            first.request_id,
            "user-1",
            self.h.clock() + timedelta(seconds=5),
        )
        self.assertEqual(retry.error, error)
        self.assertEqual(waited.error, error)
        self.assertEqual(self.h.store.data, before)
        self.assertEqual(self.h.bootstrap.count, 1)

    async def test_B142_stop_tracking_can_close_a_pending_approval(self):
        """Stop tracking never means approving or consuming consent."""
        record = await self.h.start()
        self.h.configure(
            record,
            state="awaiting_approval",
            checkpoint={"pending_approval_ids": ["approval-A"]},
        )
        closed = await self.h.workflows.close(
            SCOPE, ACTOR, record.audience, self.h.close_command(record)
        )
        self.assertEqual(closed.state, "closed")
        bundle = await self.h.repo.load(SCOPE, record.workflow_id)
        self.assertEqual(
            bundle.checkpoint.pending_approval_ids, ("approval-A",)
        )
        self.assertFalse(self.h.runtime.calls)
        self.assertFalse(self.h.store.data["results"])

    async def test_B143_normal_close_still_requires_resolving_approval(self):
        """A completion close cannot claim pending approval is resolved."""
        record = await self.h.start()
        self.h.configure(
            record, checkpoint={"pending_approval_ids": ["approval-A"]}
        )
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.close(
                SCOPE,
                ACTOR,
                record.audience,
                self.h.close_command(record, stop_tracking_only=False),
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B144_late_approval_cannot_resume_a_stopped_workflow(self):
        """Retained consent refs do not authorize a closed workflow turn."""
        record = await self.h.start()
        self.h.configure(
            record, checkpoint={"pending_approval_ids": ["approval-A"]}
        )
        await self.h.workflows.close(
            SCOPE, ACTOR, record.audience, self.h.close_command(record)
        )
        result = await self.h.continuation.run(
            SCOPE,
            self.h.trigger(
                record.workflow_id, kind="approval", approval_id="approval-A"
            ),
            "worker-A",
        )
        self.assertEqual(result, "closed")
        self.assertFalse(self.h.runtime.calls)
        self.assertFalse(self.h.store.data["results"])

    async def test_B145_stop_tracking_with_approval_preserves_other_ticket(
        self,
    ):
        """Closing A cannot change B or manufacture operation cancellation."""
        record = await self.h.start()
        other = await self.h.start("B")
        operation = self.h.add_operation(record)
        self.h.configure(
            record, checkpoint={"pending_approval_ids": ["approval-A"]}
        )
        before_b = await self.h.repo.load(SCOPE, other.workflow_id)
        await self.h.workflows.close(
            SCOPE, ACTOR, record.audience, self.h.close_command(record)
        )
        self.assertEqual(
            await self.h.repo.load(SCOPE, other.workflow_id), before_b
        )
        self.assertEqual(
            self.h.store.data["operations"][operation.operation_id], operation
        )

    async def test_B146_stop_tracking_still_rejects_revoked_permission(self):
        """The open-state exception never bypasses close authorization."""
        record = await self.h.start()
        self.h.configure(
            record, checkpoint={"pending_approval_ids": ["approval-A"]}
        )
        before = deepcopy(self.h.store.data)
        self.h.auth.revoked = True
        with self.assertRaises(PermissionError):
            await self.h.workflows.close(
                SCOPE, ACTOR, record.audience, self.h.close_command(record)
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B147_pending_request_closed_projection_has_public_error(
        self,
    ):
        """A queued request blocked by close has an explicit public cause."""
        receipt = await self.accept()
        record = (await self.h.repo.load(SCOPE, receipt.workflow_id)).workflow
        await self.h.workflows.close(
            SCOPE, ACTOR, record.audience, self.h.close_command(record)
        )
        result = await self.h.ingress.read_result(
            ACTOR, receipt.request_id, "user-1"
        )
        self.assertEqual(result.request_status, "blocked")
        self.assertEqual(result.error.code, "WORKFLOW_CLOSED")
        self.assertEqual(result.error.request_id, receipt.request_id)
        self.assertFalse(result.error.retryable)
        self.assertEqual(result.next_action, "none")

    async def test_B148_repository_cannot_relabel_another_request(self):
        """Matching user scope does not make a different request valid."""
        receipt = await self.accept()
        read = self.h.ingress.requests.read

        async def foreign(*args, **kwargs):
            original = await read(*args, **kwargs)
            return original.model_copy(
                update={
                    "request": original.request.model_copy(
                        update={"request_id": "request-B"}
                    )
                }
            )

        self.h.ingress.requests.read = foreign
        with self.assertRaises(PermissionError):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B149_stop_tracking_approval_still_enforces_revision(self):
        """The stop-tracking exception keeps the close CAS guard."""
        record = await self.h.start()
        self.h.configure(
            record, checkpoint={"pending_approval_ids": ["approval-A"]}
        )
        before = deepcopy(self.h.store.data)
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.close(
                SCOPE,
                ACTOR,
                record.audience,
                self.h.close_command(record, expected_revision=2),
            )
        self.assertEqual(self.h.store.data, before)

    async def test_B150_revoked_actor_cannot_read_a_public_failure(self):
        """Public errors remain protected by request audience authorization."""
        receipt = await self.accept()
        self.terminal(receipt)
        self.h.auth.revoked = True
        with self.assertRaises(PermissionError):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B151_closing_public_stream_closes_the_replay_iterator(self):
        """A disconnected consumer immediately releases its nested reader."""
        record = await self.h.start()
        original_frames = self.h.events.sse.frames
        closed = []

        async def observed(*args, **kwargs):
            frames = original_frames(*args, **kwargs)
            try:
                async for frame in frames:
                    yield frame
            finally:
                await frames.aclose()
                closed.append(True)

        self.h.events.sse.frames = observed
        stream = self.h.events.stream(ACTOR, record.conversation_id)
        await anext(stream)
        await stream.aclose()
        self.assertEqual(closed, [True])
