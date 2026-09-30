import asyncio
import copy
import json
import unittest

from adapters.backend.client import BackendClient, HttpResponse
from adapters.backend.errors import AdapterError
from adapters.backend.messages import MESSAGE_TYPES, validate_request
from backend.support import Headers, Transport, Validator, client, request


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_envelope_headers_and_accepted_is_only_a_receipt(self):
        transport, validator = Transport(), Validator()
        wire = request()
        result = await client(transport, validator).call("reception.ticket", wire)
        url, headers, sent, timeout = transport.calls[0]
        self.assertEqual(url, "https://backend.test/test/reception.ticket")
        self.assertEqual(sent, wire)
        self.assertEqual(headers["Idempotency-Key"], wire["idempotency_key"])
        self.assertEqual(headers["X-Trace-Id"], wire["trace_id"])
        self.assertEqual(headers["Authorization"], "Bearer test-credential")
        self.assertEqual(result.status, "accepted")
        self.assertEqual([x[0] for x in validator.seen], ["request", "response"])

    async def test_caller_mutation_during_credential_lookup_cannot_change_command(self):
        wire = request()
        original = copy.deepcopy(wire)

        class MutatingHeaders(Headers):
            async def headers(self):
                wire["context"]["ticket_id"] = "other-ticket"
                wire["payload"]["report"] = "changed"
                return await super().headers()

        transport = Transport()
        await client(transport, headers=MutatingHeaders()).call("reception.ticket", wire)
        self.assertEqual(transport.calls[0][2], original)

    async def test_timeout_is_unknown_and_never_retried(self):
        transport = Transport()
        transport.failure = TimeoutError("secret connection detail")
        with self.assertRaises(AdapterError) as caught:
            await client(transport).call("reception.ticket", request())
        self.assertEqual(caught.exception.code, "timeout")
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(len(transport.calls), 1)
        self.assertNotIn("secret", str(caught.exception))

    async def test_total_request_deadline(self):
        class SlowTransport(Transport):
            async def post(self, *args, **kwargs):
                await asyncio.sleep(1)

        with self.assertRaisesRegex(AdapterError, "timeout"):
            await client(SlowTransport(), timeout=0.01).call("reception.ticket", request())

    async def test_network_failure_is_unknown_outcome(self):
        transport = Transport()
        transport.failure = OSError("secret")
        with self.assertRaises(AdapterError) as caught:
            await client(transport).call("reception.ticket", request())
        self.assertEqual(caught.exception.code, "unavailable")
        self.assertTrue(caught.exception.outcome_unknown)

    async def test_http_errors_never_echo_backend_body(self):
        for status, expected in [(401, "forbidden"), (403, "forbidden"), (404, "not_found"),
                                 (409, "conflict"), (422, "validation_error"),
                                 (429, "rate_limited"), (503, "unavailable"),
                                 (307, "unexpected_http_status")]:
            with self.subTest(status=status):
                transport = Transport()
                transport.response = HttpResponse(status, b"secret raw backend traceback")
                with self.assertRaises(AdapterError) as caught:
                    await client(transport).call("reception.ticket", request())
                self.assertEqual(caught.exception.code, expected)
                self.assertNotIn("secret", str(caught.exception))

    async def test_invalid_or_uncorrelated_response(self):
        bodies = [b"not json", b"[]", b'{"request_id":"wrong","status":"accepted","data":{}}',
                  b'{"request_id":"request-1","status":"resolved","data":{}}',
                  b'{"request_id":"request-1","status":"accepted","data":{"x":NaN}}']
        for body in bodies:
            with self.subTest(body=body):
                transport = Transport()
                transport.response = HttpResponse(200, body)
                with self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
                    await client(transport).call("reception.ticket", request())

    async def test_business_error_even_on_http_200(self):
        transport = Transport()
        transport.response = HttpResponse(200, json.dumps({
            "request_id": "request-1", "status": "error",
            "error": {"code": "stale_version", "message": "secret", "retryable": False},
        }).encode())
        with self.assertRaisesRegex(AdapterError, "^stale_version$"):
            await client(transport).call("reception.ticket", request())

    async def test_explicit_retry_preserves_key_and_payload(self):
        transport = Transport()
        backend = client(transport)
        wire = request()
        await backend.call("reception.ticket", wire)
        await backend.call("reception.ticket", wire)
        self.assertEqual(transport.calls[0], transport.calls[1])

    async def test_canonical_validator_can_reject_before_network(self):
        validator, transport = Validator(), Transport()
        validator.reject = "request"
        with self.assertRaisesRegex(AdapterError, "^validation_error$"):
            await client(transport, validator).call("reception.ticket", request())
        self.assertEqual(transport.calls, [])

    async def test_unconfigured_operation_fails_before_credentials_or_network(self):
        transport = Transport()
        with self.assertRaisesRegex(AdapterError, "operation_not_configured"):
            await client(transport).call("http://model-chosen.example", request())
        self.assertEqual(transport.calls, [])

    async def test_missing_credentials_and_header_injection_rejected(self):
        for values in ({}, {"Authorization": "secret\r\nInjected: yes"},
                       {"Content-Type": "text/plain"}):
            class BadHeaders:
                async def headers(self):
                    return values

            transport = Transport()
            with self.assertRaises(AdapterError):
                await client(transport, headers=BadHeaders()).call("reception.ticket", request())
            self.assertEqual(transport.calls, [])
        wire = request()
        wire["request_id"] = "id\nInjected: bad"
        with self.assertRaises(AdapterError):
            await client().call("reception.ticket", wire)

    async def test_response_limit(self):
        with self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
            await client(max_response_bytes=1).call("reception.ticket", request())


class GuardsTests(unittest.TestCase):
    def test_all_documented_message_variants(self):
        for kind in MESSAGE_TYPES:
            with self.subTest(kind=kind):
                validate_request(request(kind))

    def test_management_request_and_unknown_cost(self):
        wire = request("approval.requested")
        wire["payload"].update(stage="management_plan", delivery_channel="management_ui", cost=None)
        del wire["payload"]["depends_on_approval_id"]
        validate_request(wire)
        self.assertIsNone(wire["payload"]["cost"])

    def test_invalid_field_types_and_missing_correlations(self):
        cases = []
        for kind, field, value in [
            ("approval.requested", "depends_on_approval_id", None),
            ("approval.requested", "plan_version", True),
            ("approval.requested", "expires_at", "2026-10-01T12:00:00"),
            ("approval.responded", "decision", "yes"),
            ("completion.responded", "result_version", 0),
            ("completion.responded", "decision", "approve"),
            ("resident.message", "reply_to_request_id", ""),
            ("work.completed", "before_file_ids", "file-1"),
        ]:
            wire = request(kind)
            wire["payload"][field] = value
            cases.append(wire)
        wire = request()
        wire["context"]["ticket_generation"] = True
        cases.append(wire)
        wire = request("approval.requested")
        wire["payload"]["cost"]["amount"] = -1
        cases.append(wire)
        for wire in cases:
            with self.subTest(wire=wire), self.assertRaises(AdapterError):
                validate_request(wire)

    def test_unsafe_origins_and_routes(self):
        for origin in ("http://backend.test", "https://user:secret@backend.test", "https://a/path"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                BackendClient(base_url=origin, routes={}, transport=Transport(),
                              headers=Headers(), validator=Validator())
        for path in ("https://other.test", "//other.test", "/x/../y", "/x?token=a", "/x\ny"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                BackendClient(base_url="https://backend.test", routes={"op": path},
                              transport=Transport(), headers=Headers(), validator=Validator())
