"""G3 ticket ingress/idempotency/rollback/isolation with test-only ports."""

import asyncio
import unittest
from copy import deepcopy

from _support import FakeRepository, SCOPE
from wf_orchestration_under_test._models import OrchestrationError
from wf_orchestration_under_test.workflows._ingress import TicketIngress


class FakePartnerGuard:
    def __init__(self):
        self.scope, self.revision = dict(SCOPE), 1
        self.revoked = False

    async def authorize(self, actor, envelope, operation, uow):
        if self.revoked:
            raise OrchestrationError("AUTHORIZATION_REVOKED")
        if actor != "authenticated-test-actor":
            raise OrchestrationError("AUTHENTICATION_REQUIRED")
        return {"scope": self.scope, "route_id": "route", "route_revision": self.revision,
                "timezone": "Asia/Ho_Chi_Minh", "audience": {
                    "partner_client_id": "partner", **{key: envelope[key] for key in (
                        "external_user_id", "external_ticket_id", "external_conversation_id")}}}


class FakeJobs:
    def __init__(self, repository):
        self.repository, self.fail = repository, False

    async def enqueue(self, scope, kind, payload, idempotency_key, *, uow):
        assert uow is self.repository and self.repository.in_transaction
        self.repository.rows[("job", (), idempotency_key)] = deepcopy(payload)
        if self.fail:
            raise RuntimeError("test crash before commit")


class IngressTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repository, self.guard = FakeRepository(), FakePartnerGuard()
        self.jobs = FakeJobs(self.repository)
        self.ingress = TicketIngress(self.repository, self.guard, self.jobs)
        self.actor = "authenticated-test-actor"

    def envelope(self, request="req-A", ticket="ticket-A", chat="chat-A"):
        return {"schema_version": "1", "command_type": "start_workflow", "external_request_id": request,
                "external_management_ref": "management", "external_user_id": "user",
                "external_ticket_id": ticket, "external_conversation_id": chat,
                "message": {"type": "text", "text": "hello"}}

    async def test_G3_T03_retry_same_receipt_and_payload_conflict(self):
        envelope = self.envelope()
        first = await self.ingress.accept(self.actor, envelope)
        retry = await self.ingress.accept(self.actor, envelope)
        self.assertEqual(first, retry)
        self.assertEqual(first["http_status"], 202)
        self.assertEqual(first["next_action"], "watch_request")
        self.assertNotIn("group_id", first)
        self.assertEqual(len([key for key in self.repository.rows if key[0] == "job"]), 1)
        with self.assertRaisesRegex(OrchestrationError, "REQUEST_ID_CONFLICT"):
            await self.ingress.accept(self.actor, {**envelope, "message": {"type": "text", "text": "changed"}})

    async def test_G3_T04_concurrent_same_ticket_one_binding(self):
        results = await asyncio.gather(
            self.ingress.accept(self.actor, self.envelope()),
            self.ingress.accept(self.actor, self.envelope()),
        )
        self.assertEqual(results[0], results[1])
        self.assertEqual(len([key for key in self.repository.rows if key[0] == "workflow"]), 1)
        with self.assertRaisesRegex(OrchestrationError, "TICKET_ALREADY_BOUND"):
            await self.ingress.accept(self.actor, self.envelope(request="new-request"))

    async def test_G3_T05_two_ticket_replies_dispatch_to_bound_groups(self):
        first = await self.ingress.accept(self.actor, self.envelope())
        second = await self.ingress.accept(self.actor, self.envelope("req-B", "ticket-B", "chat-B"))
        for request_id, receipt, ticket, chat in (("A2", first, "ticket-A", "chat-A"), ("B2", second, "ticket-B", "chat-B")):
            envelope = self.envelope(request_id, ticket, chat)
            envelope.update(command_type="workflow_reply", workflow_id=receipt["workflow_id"])
            reply = await self.ingress.accept(self.actor, envelope)
            self.assertEqual(reply["conversation_id"], receipt["conversation_id"])
        jobs = [value for (kind, _, _), value in self.repository.rows.items() if kind == "job"]
        self.assertEqual(jobs[0]["group_id"], jobs[2]["group_id"])
        self.assertEqual(jobs[1]["group_id"], jobs[3]["group_id"])
        self.assertNotEqual(jobs[0]["group_id"], jobs[1]["group_id"])

    async def test_G3_T06_mismatched_tuple_missing_workflow_closed_and_forbidden_fields(self):
        first = await self.ingress.accept(self.actor, self.envelope())
        before = len(self.repository.rows)
        bad = self.envelope("reply", "ticket-B", "chat-A")
        bad.update(command_type="workflow_reply", workflow_id=first["workflow_id"])
        with self.assertRaisesRegex(OrchestrationError, "WORKFLOW_BINDING_MISMATCH"):
            await self.ingress.accept(self.actor, bad)
        self.assertEqual(len(self.repository.rows), before)
        with self.assertRaisesRegex(OrchestrationError, "WORKFLOW_REFERENCE_REQUIRED"):
            await self.ingress.accept(self.actor, {**self.envelope("reply"), "command_type": "workflow_reply"})
        with self.assertRaisesRegex(OrchestrationError, "AUTHORITY_FIELD_FORBIDDEN"):
            await self.ingress.accept(self.actor, {**self.envelope("spoof"), "tenant_id": "spoof"})
        for (kind, _, _), value in self.repository.rows.items():
            if kind == "workflow":
                value.state = "closed"
        valid_reply = {**self.envelope("reply"), "command_type": "workflow_reply", "workflow_id": first["workflow_id"]}
        with self.assertRaisesRegex(OrchestrationError, "WORKFLOW_CLOSED"):
            await self.ingress.accept(self.actor, valid_reply)

    async def test_G3_T07_retry_after_remap_never_changes_owner(self):
        await self.ingress.accept(self.actor, self.envelope())
        self.guard.scope = {**SCOPE, "manager_account_id": "new-owner"}
        with self.assertRaisesRegex(OrchestrationError, "REQUEST_ROUTE_CHANGED"):
            await self.ingress.accept(self.actor, self.envelope())
        self.assertEqual(len([key for key in self.repository.rows if key[0] == "command"]), 1)

    async def test_G3_T09_enqueue_failure_rolls_back_entire_ingress(self):
        self.jobs.fail = True
        with self.assertRaises(RuntimeError):
            await self.ingress.accept(self.actor, self.envelope())
        self.assertEqual(self.repository.rows, {})

    async def test_contract_text_object_timezone_and_authentication_required(self):
        with self.assertRaisesRegex(OrchestrationError, "MESSAGE_INVALID"):
            await self.ingress.accept(self.actor, {**self.envelope(), "message": "plain string"})
        with self.assertRaisesRegex(OrchestrationError, "TIMEZONE_INVALID"):
            await self.ingress.accept(self.actor, {**self.envelope(), "timezone": "invalid/timezone"})
        with self.assertRaisesRegex(OrchestrationError, "AUTHENTICATION_REQUIRED"):
            await self.ingress.accept("unverified", self.envelope())
        self.assertEqual(self.repository.rows, {})
