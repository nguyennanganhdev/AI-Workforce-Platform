import asyncio
import copy
import unittest

from adapters.backend.errors import AdapterError
from adapters.backend.events import EventIngress, INBOUND_TYPES
from backend.support import CONTEXT, Inbox, Validator, Verifier, event, request


class EventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.verifier = Verifier()
        self.inbox = Inbox()
        self.validator = Validator()
        self.ingress = EventIngress(
            verifier=self.verifier, inbox=self.inbox, validator=self.validator,
            event_types={f"backend.{kind}": kind for kind in INBOUND_TYPES},
        )

    async def receive(self, value):
        return await self.ingress.receive(value, authentication="test-backend-signature")

    async def test_all_supported_events_reach_durable_pending_queue(self):
        for kind in INBOUND_TYPES:
            with self.subTest(kind=kind):
                receipt = await self.receive(event(kind, event_id=kind))
                self.assertTrue(receipt.queued)
                item = self.inbox.items[("tenant-a", kind)]
                self.assertEqual(item.context, CONTEXT)
                self.assertEqual(item.message_type, kind)
                self.assertEqual(item.target, "supervisor")

    async def test_raw_request_is_not_an_authorized_backend_event(self):
        with self.assertRaises(AdapterError):
            await self.receive(request("approval.responded"))
        self.assertFalse(self.inbox.items)

    async def test_bad_auth_never_queues(self):
        with self.assertRaisesRegex(AdapterError, "event_not_authorized"):
            await self.ingress.receive(event(), authentication="client-asserted-identity")
        self.assertFalse(self.inbox.items)

    async def test_backend_rejected_decisions_never_advance_room(self):
        for failure in ("forbidden", "stale_version", "conflict", "approval_expired"):
            with self.subTest(failure=failure):
                self.verifier.failure = failure
                with self.assertRaisesRegex(AdapterError, failure):
                    await self.receive(event("approval.responded"))
                self.assertFalse(self.inbox.items)

    async def test_tenant_mismatch_after_resolution_fails_closed(self):
        with self.assertRaisesRegex(AdapterError, "event_not_authorized"):
            await self.receive(event(tenant="another-tenant"))
        self.assertFalse(self.inbox.items)

    async def test_generation_is_taken_from_verified_binding(self):
        self.verifier.contexts["ticket-1"]["ticket_generation"] = 2
        await self.receive(event())
        self.assertEqual(self.inbox.items[("tenant-a", "event-1")].context["ticket_generation"], 2)
        # An old generation must instead be rejected by the resolver/inbox fence.
        self.verifier.failure = "stale_version"
        with self.assertRaisesRegex(AdapterError, "stale_version"):
            await self.receive(event(event_id="old-generation"))
        self.assertEqual(len(self.inbox.items), 1)

    async def test_concurrent_duplicate_callbacks_only_enqueue_once(self):
        receipts = await asyncio.gather(*(self.receive(event()) for _ in range(20)))
        self.assertEqual(sum(item.queued for item in receipts), 1)
        self.assertEqual(len(self.inbox.items), 1)

    async def test_same_event_id_with_changed_content_conflicts(self):
        await self.receive(event("approval.responded"))
        changed = event("approval.responded")
        changed["payload"]["decision"] = "reject"
        with self.assertRaisesRegex(AdapterError, "conflict"):
            await self.receive(changed)
        self.assertEqual(len(self.inbox.items), 1)

    async def test_same_event_id_is_scoped_by_tenant(self):
        self.verifier.contexts["ticket-2"] = {
            **CONTEXT, "tenant_id": "tenant-b", "ticket_id": "ticket-2",
            "binding_id": "binding-2", "run_id": "run-2",
        }
        await asyncio.gather(self.receive(event()), self.receive(
            event(ticket_id="ticket-2", tenant="tenant-b")
        ))
        self.assertEqual(len(self.inbox.items), 2)

    async def test_two_rooms_keep_binding_run_and_recipient_separate(self):
        self.verifier.contexts["ticket-2"] = {
            **CONTEXT, "ticket_id": "ticket-2", "binding_id": "binding-2",
            "run_id": "run-2", "initiated_by_user_id": "resident-2",
        }
        await asyncio.gather(
            self.receive(event(event_id="a")),
            self.receive(event(event_id="b", ticket_id="ticket-2")),
        )
        a, b = self.inbox.items[("tenant-a", "a")], self.inbox.items[("tenant-a", "b")]
        self.assertEqual(a.context["binding_id"], "binding-1")
        self.assertEqual(b.context["binding_id"], "binding-2")
        self.assertEqual(b.context["initiated_by_user_id"], "resident-2")

    async def test_legacy_mention_routes_only_after_event_verification(self):
        value = event("resident.message")
        value["payload"]["mentioned_agent_id"] = "agent-1"
        await self.receive(value)
        self.assertEqual(self.inbox.items[("tenant-a", "event-1")].target, "groupchat")
        self.assertEqual(len(self.verifier.calls), 1)

    async def test_unknown_event_or_bad_payload_never_calls_verifier(self):
        value = event()
        value["event_type"] = "model.approved"
        with self.assertRaisesRegex(AdapterError, "event_not_supported"):
            await self.receive(value)
        value = event("approval.responded")
        value["payload"]["decision"] = "yes"
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await self.receive(value)
        self.assertEqual(self.verifier.calls, [])

    async def test_management_decisions_are_forwarded_without_reinterpretation(self):
        for kind, decision in (("approval.responded", "reject"),
                               ("approval.responded", "request_changes")):
            value = event(kind, event_id=decision)
            value["payload"]["decision"] = decision
            await self.receive(value)
            self.assertEqual(self.inbox.items[("tenant-a", decision)].event["payload"]["decision"],
                             decision)

    async def test_lost_queue_ack_can_be_retried_without_second_pending_item(self):
        real_inbox = self.inbox

        class LostAck:
            async def enqueue_once(self, delivery):
                result = await real_inbox.enqueue_once(delivery)
                if result:
                    raise TimeoutError()
                return result

        ingress = EventIngress(verifier=self.verifier, inbox=LostAck(), validator=self.validator,
                               event_types={"backend.approval.responded": "approval.responded"})
        with self.assertRaises(AdapterError) as caught:
            await ingress.receive(event(), authentication="test-backend-signature")
        self.assertTrue(caught.exception.outcome_unknown)
        receipt = await ingress.receive(event(), authentication="test-backend-signature")
        self.assertFalse(receipt.queued)
        self.assertEqual(len(real_inbox.items), 1)

    async def test_recreated_ingress_uses_existing_inbox_dedup_state(self):
        # Tests port reuse only, not process restart durability of a real store.
        await self.receive(event())
        replacement = EventIngress(verifier=self.verifier, inbox=self.inbox, validator=self.validator,
                                   event_types={"backend.approval.responded": "approval.responded"})
        self.assertFalse((await replacement.receive(
            event(), authentication="test-backend-signature"
        )).queued)

    async def test_verifier_cannot_mutate_queued_payload(self):
        original = event()
        base_verifier = self.verifier

        class MutatingVerifier:
            async def resolve(self, value, authentication):
                value["payload"]["comment"] = "mutated"
                return await base_verifier.resolve(value, authentication)

        ingress = EventIngress(verifier=MutatingVerifier(), inbox=self.inbox, validator=self.validator,
                               event_types={"backend.approval.responded": "approval.responded"})
        await ingress.receive(original, authentication="test-backend-signature")
        self.assertEqual(self.inbox.items[("tenant-a", "event-1")].event, original)

    async def test_schema_validator_rejection_prevents_queue(self):
        self.validator.reject = "event"
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await self.receive(event())
        self.assertFalse(self.inbox.items)


if __name__ == "__main__":
    unittest.main()
