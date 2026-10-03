import asyncio
import copy
import json
import unittest

from adapters.backend.errors import AdapterError
from adapters.reception.authentication import HmacSourceAuthentication, SourceProof
from adapters.reception.ingress import ReceptionIngress
from adapters.reception.reception_gateway import ReceptionGateway
from backend.production_support import authentication, proof
from backend.support import client
from reception.support import input_message, V2Transport


class ProofTransport(V2Transport):
    """Test peer validates HMAC, then delegates to existing synthetic policy."""
    async def post(self, url, *, headers, body, timeout):
        if url.endswith("reception.verify"):
            await authentication().headers_for(SourceProof(headers["X-Test-Source-Proof"]),
                                                json.loads(body), purpose="reception")
            headers = {**headers, "X-Reception-Source-Proof": "test-source-proof"}
        return await super().post(url, headers=headers, body=body, timeout=timeout)


class ProofTests(unittest.IsolatedAsyncioTestCase):
    async def test_proof_binds_body_purpose_audience_expiry_and_scope(self):
        wire = input_message()
        auth = authentication()
        source = proof(wire)
        self.assertEqual((await auth.headers_for(source, wire, purpose="reception"))["X-Test-Source-Proof"],
                         source.token)
        for changes in ({"audience": "other"}, {"expires_at": 1049}, {"issued_at": 1051},
                        {"issuer": "unknown"}, {"purpose": "tool"}, {"subject": ""},
                        {"scope": {"tenant_id": "other"}}, {"fingerprint": "changed"}):
            with self.subTest(changes=changes), self.assertRaises(AdapterError):
                await auth.headers_for(proof(wire, **changes), wire, purpose="reception")
        with self.assertRaises(AdapterError):
            await auth.headers_for(SourceProof(source.token[:-1] + "x"), wire, purpose="reception")
        with self.assertRaises(AdapterError):
            await auth.headers_for(source, {**wire, "message": "tampered"}, purpose="reception")
        self.assertNotIn(source.token, repr(source))

    async def test_reserved_proof_header_and_short_keys_are_rejected(self):
        for header, key in (("Authorization", b"x" * 32), ("X-Proof", b"short"), ("X\nProof", b"x" * 32)):
            with self.assertRaises(ValueError):
                HmacSourceAuthentication(keys={"issuer": key}, audience="coordination", header=header,
                                         purposes={"reception"})

    async def test_real_gateway_rejects_changed_proof_before_network(self):
        transport = ProofTransport()
        gateway = ReceptionGateway(client(transport), authentication=authentication())
        wire = input_message()
        verified = await gateway.verify(wire, proof(wire))
        self.assertEqual(verified.message.message_id, wire["message_id"])
        transport.calls.clear()
        with self.assertRaises(AdapterError):
            await gateway.verify({**wire, "ticket_generation": 2}, proof(wire))
        self.assertFalse(transport.calls)


class ReceptionIngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_acceptance_waits_for_commit_and_contains_no_proof(self):
        transport = ProofTransport()
        gateway = ReceptionGateway(client(transport), authentication=authentication())
        items = []
        entered, committed = asyncio.Event(), asyncio.Event()

        class Inbox:
            async def enqueue_once(self, item):
                items.append(copy.deepcopy(item))
                entered.set()
                await committed.wait()
                return True

        wire = input_message()
        ingress = ReceptionIngress(gateway, inbox=Inbox())
        task = asyncio.create_task(ingress.receive(wire, authentication=proof(wire)))
        await asyncio.wait_for(entered.wait(), 2)
        self.assertFalse(task.done())
        committed.set()
        receipt = await task
        self.assertEqual(receipt, dict(message_id=wire["message_id"], status="accepted", queued=True))
        self.assertEqual(items[0].message, wire)
        self.assertNotIn(proof(wire).token, repr(items[0]))

    async def test_inbox_failure_is_unknown_not_success(self):
        class LostAck:
            async def enqueue_once(self, item):
                raise TimeoutError()
        gateway = ReceptionGateway(client(ProofTransport()), authentication=authentication())
        wire = input_message()
        with self.assertRaises(AdapterError) as caught:
            await ReceptionIngress(gateway, inbox=LostAck()).receive(wire, authentication=proof(wire))
        self.assertTrue(caught.exception.outcome_unknown)

    async def test_duplicate_receipt_still_refers_to_original_identity(self):
        class Duplicate:
            async def enqueue_once(self, item):
                return False
        gateway = ReceptionGateway(client(ProofTransport()), authentication=authentication())
        wire = input_message()
        receipt = await ReceptionIngress(gateway, inbox=Duplicate()).receive(wire, authentication=proof(wire))
        self.assertFalse(receipt["queued"])
        self.assertEqual(receipt["message_id"], wire["message_id"])

    async def test_concurrent_duplicate_inputs_only_enqueue_one_pending_item(self):
        class Inbox:
            # Test-only atomic contract double, not production durable storage.
            def __init__(self):
                self.items, self.lock = {}, asyncio.Lock()

            async def enqueue_once(self, item):
                async with self.lock:
                    key = (item.tenant_id, item.message_id)
                    old = self.items.get(key)
                    if old is not None:
                        if old.fingerprint != item.fingerprint:
                            raise AdapterError("conflict")
                        return False
                    self.items[key] = copy.deepcopy(item)
                    return True

        inbox = Inbox()
        gateway = ReceptionGateway(client(ProofTransport()), authentication=authentication())
        ingress = ReceptionIngress(gateway, inbox=inbox)
        wire = input_message()
        receipts = await asyncio.gather(*(ingress.receive(wire, authentication=proof(wire)) for _ in range(10)))
        self.assertEqual(sum(r["queued"] for r in receipts), 1)
        self.assertEqual(len(inbox.items), 1)
        with self.assertRaisesRegex(AdapterError, "conflict"):
            changed = {**wire, "message": "changed content"}
            await ingress.receive(changed, authentication=proof(changed))
        self.assertEqual(len(inbox.items), 1)

    async def test_unverified_input_never_reaches_inbox(self):
        calls = []
        class Inbox:
            async def enqueue_once(self, item):
                calls.append(item)
                return True
        gateway = ReceptionGateway(client(ProofTransport()), authentication=authentication())
        wire = input_message()
        with self.assertRaises(AdapterError):
            await ReceptionIngress(gateway, inbox=Inbox()).receive(wire, authentication="untrusted")
        self.assertFalse(calls)
