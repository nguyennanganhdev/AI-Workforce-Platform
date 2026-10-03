import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.backend.authority_client import BackendAuthority
from adapters.backend.business_client import BusinessClient, BusinessOperation
from adapters.backend.contract_validator import PinnedContractValidator, SchemaPin
from adapters.backend.credentials import BearerCredentials
from adapters.backend.errors import AdapterError
from adapters.backend.event_verifier import BackendEventVerifier
from adapters.backend.messages import fingerprint
from adapters.backend.routes import load_operation_routes, operation_routes
from backend.production_support import authentication, contract_client, ContractTransport, proof
from backend.support import CONTEXT, event, Validator


class ValidatorTests(unittest.TestCase):
    def pins(self, folder, schemas):
        result = {}
        for kind, schema in schemas.items():
            path = Path(folder) / (kind + ".json")
            path.write_text(json.dumps(schema), encoding="utf-8")
            result[kind] = SchemaPin(path, hashlib.sha256(path.read_bytes()).hexdigest())
        return result

    def test_pinned_offline_refs_and_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            pins = self.pins(folder, {
                "base": {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:test:base",
                         "type": "string", "format": "date-time"},
                "input": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
                          "properties": {"sent_at": {"$ref": "urn:test:base"}},
                          "required": ["sent_at"], "additionalProperties": False}})
            validator = PinnedContractValidator(pins, required={"input"})
            validator.validate("input", {"sent_at": "2026-10-02T00:00:00Z"})
            for value in ({"sent_at": "yesterday"}, {"sent_at": "2026-10-02T00:00:00Z", "extra": 1}, {}):
                with self.assertRaises(AdapterError):
                    validator.validate("input", value)
            with self.assertRaises(AdapterError):
                validator.validate("missing", {})
            pins["input"].path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "digest"):
                PinnedContractValidator(pins, required={"input"})

    def test_external_reference_cannot_fetch_network(self):
        with tempfile.TemporaryDirectory() as folder:
            pins = self.pins(folder, {"input": {"$schema": "https://json-schema.org/draft/2020-12/schema",
                                               "$ref": "https://test.invalid/remote"}})
            validator = PinnedContractValidator(pins, required={"input"})
            with self.assertRaises(AdapterError):
                validator.validate("input", {})

    def test_format_named_field_and_examples_are_data_not_schema_keywords(self):
        with tempfile.TemporaryDirectory() as folder:
            pins = self.pins(folder, {"input": {
                "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
                "properties": {"format": {"type": "string"}}, "examples": [{"format": "business-label"}]}})
            PinnedContractValidator(pins, required={"input"}).validate("input", {"format": "business-label"})

    def test_missing_pins_or_unsupported_format_cannot_silently_pass(self):
        with self.assertRaises(ValueError):
            PinnedContractValidator({}, required={"input"})
        with tempfile.TemporaryDirectory() as folder:
            pins = self.pins(folder, {"input": {
                "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "string",
                "format": "not-a-supported-format"}})
            with self.assertRaises(ValueError):
                PinnedContractValidator(pins, required={"input"})

    def test_route_mapping_requires_real_configuration(self):
        self.assertEqual(operation_routes({"reception.verify": "/verify"}, required={"reception.verify"}),
                         {"reception.verify": "/verify"})
        for routes in ({}, {"reception.verify": "https://other/verify"}, {"reception.verify": "/a/../b"}):
            with self.assertRaises(ValueError):
                operation_routes(routes, required={"reception.verify"})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "routes.json"
            path.write_text('{"reception.verify":"/verify"}')
            self.assertEqual(load_operation_routes(path, required={"reception.verify"}),
                             {"reception.verify": "/verify"})

    def test_bundle_fails_startup_without_required_peer_contracts(self):
        from adapters.backend.composition import build_adapters
        from backend.support import Headers
        with self.assertRaisesRegex(ValueError, "missing required"):
            build_adapters(origin="https://test.invalid", routes={}, schema_pins={}, credentials=Headers(),
                           reception_authentication=authentication(), event_authentication=authentication())


class ProductionAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_credentials_rotate_and_fail_closed(self):
        token = ["first"]
        provider = BearerCredentials(lambda: token[0])
        self.assertEqual(await provider.headers(), {"Authorization": "Bearer first"})
        token[0] = "second"
        self.assertEqual(await provider.headers(), {"Authorization": "Bearer second"})
        for bad in ("", "two words", "secret\r\nheader"):
            token[0] = bad
            with self.assertRaisesRegex(AdapterError, "credentials_unavailable"):
                await provider.headers()

    async def test_event_requires_committed_exact_snapshot_and_scope(self):
        wire = event()
        data = dict(context=dict(CONTEXT), event_fingerprint=fingerprint(wire), committed=True)
        transport = ContractTransport(lambda _: data)
        verifier = BackendEventVerifier(contract_client(transport), authentication=authentication())
        resolved = await verifier.resolve(wire, proof(wire, purpose="event"))
        self.assertEqual(resolved.context, CONTEXT)
        for changes in ({"committed": False}, {"event_fingerprint": "changed"},
                        {"context": {**CONTEXT, "tenant_id": "other"}}):
            transport.response = lambda _, changes=changes: {**data, **changes}
            with self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
                await verifier.resolve(wire, proof(wire, purpose="event"))

    async def test_contract_schema_guard_runs_before_network_and_trace_excludes_secrets(self):
        validator = Validator()
        transport = ContractTransport(lambda _: {})
        logs = []
        client = contract_client(transport, validator=validator, observer=logs.append)
        wire = dict(request_id="id", context=dict(CONTEXT), input={"private": "secret"})
        validator.reject = "custom"
        with self.assertRaises(AdapterError):
            await client.call_contract("tool.execute", wire, request_schema="custom", response_schema="response")
        self.assertFalse(transport.calls)
        validator.reject = None
        await client.call_contract("tool.execute", wire, request_schema="custom", response_schema="response")
        self.assertEqual(logs[0]["request_id"], "id")
        self.assertEqual(logs[1]["phase"], "receipt")
        self.assertEqual(logs[1]["status"], "completed")
        self.assertNotIn("secret", json.dumps(logs))
        client._observer = lambda _: (_ for _ in ()).throw(ValueError("sink unavailable"))
        await client.call_contract("tool.execute", wire, request_schema="custom", response_schema="response")

    async def test_unknown_operation_cannot_send_and_lost_ack_does_not_retry(self):
        transport = ContractTransport(lambda _: {})
        client = contract_client(transport)
        wire = dict(request_id="saved-id", idempotency_key="saved-key", context=dict(CONTEXT))
        with self.assertRaisesRegex(AdapterError, "operation_not_configured"):
            await client.call_contract("unknown", wire, request_schema="custom", response_schema="response")
        self.assertFalse(transport.calls)
        transport.failure = TimeoutError()
        with self.assertRaises(AdapterError) as caught:
            await client.call_contract("tool.execute", wire, request_schema="custom", response_schema="response")
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][2], wire)

    async def test_business_hooks_require_configured_contract_and_context(self):
        transport = ContractTransport(lambda _: {"review_status": "pending"})
        business = BusinessClient(contract_client(transport), operations={"submit_contribution":
            BusinessOperation("business.contribution", "contribution_request", "contribution_response")})
        wire = dict(request_id="contribution-1", idempotency_key="contribution-1", context=dict(CONTEXT),
                    procedure="inspected", actual_cost=None)
        self.assertEqual((await business.call("submit_contribution", wire))["review_status"], "pending")
        self.assertEqual(transport.calls[0][2], wire)
        with self.assertRaises(AdapterError):
            await business.call("unconfigured", wire)


class AuthorityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from reception.test_supervisor_v2 import support
        from supervisor.models import Action
        self.rig = support.Rig()
        await self.rig.start()
        self.state = await self.rig.state()
        wire = dict(schema_version="2.0", message_id="notice", context=self.state.context.model_dump(exclude_none=True))
        self.action = Action(action_id="notice", operation="information_requested", channel="reception",
                             wire=wire, plan_version=1, status="unknown")
        self.transport = ContractTransport(lambda _: {})
        self.authority = BackendAuthority(contract_client(self.transport))

    def response(self, wire, **data):
        return dict(state_fingerprint=wire["state_fingerprint"],
                    **({"action_fingerprint": wire["action_fingerprint"]} if "action_fingerprint" in wire else {}),
                    **data)

    async def test_inspect_binds_exact_state_and_context(self):
        view = await self.rig.authority.inspect(self.state)
        self.transport.response = lambda wire: self.response(wire, view=view.model_dump(mode="json"))
        result = await self.authority.inspect(self.state)
        self.assertEqual(result.context, self.state.context)
        view.state_version += 1
        from supervisor.models import SupervisorError
        with self.assertRaisesRegex(SupervisorError, "invalid_authority_response"):
            await self.authority.inspect(self.state)

    async def test_authorization_is_explicit_and_action_bound(self):
        self.transport.response = lambda wire: self.response(wire, allowed=True)
        await self.authority.authorize_action(self.state, self.action)
        self.transport.response = lambda wire: self.response(wire, allowed=False)
        from supervisor.models import SupervisorError
        with self.assertRaises(SupervisorError):
            await self.authority.authorize_action(self.state, self.action)

    async def test_lookup_requires_remote_fence_and_exact_receipt(self):
        from supervisor.models import SupervisorError
        self.transport.response = lambda wire: self.response(wire, outcome="not_applied", fenced=False,
                                                             fenced_action_id="notice")
        with self.assertRaisesRegex(SupervisorError, "invalid_reconciliation"):
            await self.authority.reconcile(self.state, self.action)
        self.transport.response = lambda wire: self.response(wire, outcome="not_applied", fenced=True,
                                                             fenced_action_id="notice")
        self.assertEqual((await self.authority.reconcile(self.state, self.action)).outcome, "not_applied")
        receipt = dict(message_id="notice", status="accepted", data={})
        self.transport.response = lambda wire: self.response(wire, outcome="receipt", receipt=receipt,
                                                             wire_fingerprint=fingerprint(self.action.wire))
        result = await self.authority.reconcile(self.state, self.action)
        self.assertEqual(result.receipt, receipt)
        receipt["message_id"] = "other"
        with self.assertRaises(SupervisorError):
            await self.authority.reconcile(self.state, self.action)

    async def test_lost_lookup_response_stays_unknown_and_preserves_action(self):
        saved = self.action.model_dump_json()
        self.transport.failure = TimeoutError()
        self.assertEqual((await self.authority.reconcile(self.state, self.action)).outcome, "unknown")
        self.assertEqual(self.action.model_dump_json(), saved)
