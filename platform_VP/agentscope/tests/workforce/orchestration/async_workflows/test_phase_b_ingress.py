"""Bounded POST/result projection with fake routing and command ledger."""

from datetime import timedelta
import unittest

from agentscope.app.workforce.contracts import PartnerRequestEnvelope
from agentscope.app.workforce.orchestration import receipt_http_status
from agentscope.app.workforce.orchestration.workflows import WorkflowConflict
from fakes import ACTOR, SCOPE, Harness


class IngressPhaseB(unittest.IsolatedAsyncioTestCase):
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
            message=dict(type="text", text="Yêu cầu A"),
        )

    async def accept(self):
        return await self.h.ingress.accept(
            ACTOR, PartnerRequestEnvelope.model_validate(self.body)
        )

    async def test_B081_pending_post_has_watch_request(self):
        receipt = await self.accept()
        self.assertEqual(receipt_http_status(receipt), 202)
        self.assertEqual(receipt.next_action, "watch_request")
        self.assertEqual(len(self.h.store.data["claims"]), 1)

    async def test_B082_completed_post_same_message_as_event(self):
        receipt = await self.accept()
        await self.h.continuation.run(
            SCOPE,
            self.h.trigger(receipt.workflow_id, receipt.request_id),
            "worker-A",
        )
        result = await self.h.ingress.read_result(
            ACTOR, receipt.request_id, "user-1"
        )
        self.assertEqual(receipt_http_status(result), 200)
        self.assertEqual(result.next_action, "submit_reply")
        page = await self.h.events.list_after(
            ACTOR, result.conversation_id, None, 10
        )
        self.assertEqual(
            result.result.messages[0].message_id,
            page.items[1].payload["message_id"],
        )

    async def test_B083_retry_post_never_rebuilds(self):
        first, second = await self.accept(), await self.accept()
        self.assertEqual(first, second)
        self.assertEqual(self.h.bootstrap.count, 1)
        self.assertEqual(len(self.h.store.data["jobs"]), 1)

    async def test_B084_same_request_changed_content_conflicts(self):
        await self.accept()
        self.body["message"]["text"] = "Khác nội dung"
        with self.assertRaises(WorkflowConflict):
            await self.accept()
        self.assertEqual(self.h.bootstrap.count, 1)

    async def test_B085_actor_cannot_impersonate_user(self):
        self.body["external_user_id"] = "user-B"
        with self.assertRaises(PermissionError):
            await self.accept()
        self.assertFalse(self.h.store.data["workflows"])

    async def test_B086_other_user_cannot_read_result(self):
        receipt = await self.accept()
        with self.assertRaises(PermissionError):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-B"
            )

    async def test_B087_result_revalidates_grant(self):
        receipt = await self.accept()
        self.h.auth.revoked = True
        with self.assertRaises(PermissionError):
            await self.h.ingress.read_result(
                ACTOR, receipt.request_id, "user-1"
            )

    async def test_B088_wait_deadline_returns_pending(self):
        receipt = await self.accept()
        result = await self.h.ingress.wait_for_result(
            ACTOR, receipt.request_id, "user-1", self.h.clock()
        )
        self.assertEqual(receipt_http_status(result), 202)
        self.assertFalse(self.h.runtime.calls)

    async def test_B089_signal_wakes_and_rereads_result(self):
        receipt = await self.accept()

        async def complete():
            await self.h.continuation.run(
                SCOPE,
                self.h.trigger(receipt.workflow_id, receipt.request_id),
                "worker-A",
            )

        self.h.completion.hook = complete
        result = await self.h.ingress.wait_for_result(
            ACTOR,
            receipt.request_id,
            "user-1",
            self.h.clock() + timedelta(seconds=5),
        )
        self.assertEqual(receipt_http_status(result), 200)

    async def test_B090_atomic_post_failure_leaves_no_claim(self):
        self.h.store.fail_commit = True
        with self.assertRaises(WorkflowConflict):
            await self.accept()
        for name in ("claims", "workflows", "requests", "jobs", "events"):
            self.assertFalse(self.h.store.data[name])
        self.assertFalse(self.h.signals.notifications)

    async def test_B091_reply_keeps_group_without_bootstrap(self):
        receipt = await self.accept()
        await self.h.continuation.run(
            SCOPE,
            self.h.trigger(receipt.workflow_id, receipt.request_id),
            "worker-A",
        )
        self.body.update(
            command_type="workflow_reply",
            workflow_id=receipt.workflow_id,
            external_request_id="reply-A",
        )
        self.body["message"]["text"] = "Trả lời A"
        reply = await self.accept()
        self.assertEqual(reply.workflow_id, receipt.workflow_id)
        self.assertEqual(reply.conversation_id, receipt.conversation_id)
        self.assertEqual(self.h.bootstrap.count, 1)

    async def test_B092_interleaved_post_results_keep_own_message(self):
        a = await self.accept()
        self.body.update(
            external_request_id="post-B",
            external_ticket_id="ticket-B",
            external_conversation_id="chat-B",
        )
        b = await self.accept()
        for receipt in (a, b):
            await self.h.continuation.run(
                SCOPE,
                self.h.trigger(receipt.workflow_id, receipt.request_id),
                "worker",
            )
        ra = await self.h.ingress.read_result(ACTOR, a.request_id, "user-1")
        rb = await self.h.ingress.read_result(ACTOR, b.request_id, "user-1")
        self.assertNotEqual(
            ra.result.messages[0].message_id, rb.result.messages[0].message_id
        )
        self.assertNotEqual(ra.workflow_id, rb.workflow_id)

    async def test_B093_close_before_result_returns_none_action(self):
        receipt = await self.accept()
        wf = (await self.h.repo.load(SCOPE, receipt.workflow_id)).workflow
        await self.h.workflows.close(
            SCOPE, ACTOR, wf.audience, self.h.close_command(wf)
        )
        result = await self.h.ingress.read_result(
            ACTOR, receipt.request_id, "user-1"
        )
        self.assertEqual(result.workflow_state, "closed")
        self.assertEqual(result.next_action, "none")

    async def test_B094_naive_wait_deadline_rejected(self):
        receipt = await self.accept()
        with self.assertRaises(ValueError):
            await self.h.ingress.wait_for_result(
                ACTOR,
                receipt.request_id,
                "user-1",
                self.h.clock().replace(tzinfo=None),
            )

    async def test_B095_scope_injection_rejected(self):
        self.body["scope"] = SCOPE.model_dump()
        with self.assertRaises(ValueError):
            await self.accept()
