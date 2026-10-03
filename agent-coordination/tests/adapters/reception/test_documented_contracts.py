"""Compare executable DEV-3 boundary with checked-in documented contracts."""
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from adapters.backend.composition import FEATURES, build_adapters
from adapters.backend.documented_contracts import DocumentedContractValidator
from adapters.backend.errors import AdapterError
from backend.support import CONTEXT, Headers, Transport, request
from reception.support import Authentication, input_message, output_message, V2Transport

ROOT = Path(__file__).resolve().parents[4]


class DocumentedContractsTests(unittest.TestCase):
    def test_fields_and_enums_match_both_documented_v2_definitions(self):
        from groupchat.reception import ReceptionMessage, SupervisorMessage
        for path in ("docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md", "docs/teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md"):
            doc = (ROOT / path).read_text(encoding="utf-8").split("### schema_v2", 1)[1]
            for name, model in (("ReceptionToSupervisorMessage", ReceptionMessage),
                                ("SupervisorToReceptionResult", SupervisorMessage)):
                with self.subTest(doc=path, model=name):
                    body = re.search(r"type " + name + r" = \{(.*?)^\};", doc, re.M | re.S).group(1)
                    fields = set(re.findall(r"^  ([a-z_]+)\??:", body, re.M))
                    self.assertEqual(fields, set(model.model_fields))
                    enum = set(re.findall(r'"([a-z_]+)"', re.search(r"  message_type:(.*?);", body, re.S).group(1)))
                    self.assertEqual(enum, set(model.model_fields["message_type"].annotation.__args__))

    def test_nested_ticket_result_and_error_fields_match_document(self):
        from groupchat.reception import Fact, Location, ReceptionError, ReceptionResult, Request, Resident
        doc = (ROOT / "docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md").read_text(encoding="utf-8").split("### schema_v2", 1)[1]
        for name, model in (("resident", Resident), ("location", Location), ("request", Request),
                            ("result", ReceptionResult), ("error", ReceptionError)):
            body = re.search(r"^  " + name + r"\??: \{(.*?)^  \};", doc, re.M | re.S).group(1)
            with self.subTest(model=name):
                self.assertEqual(set(re.findall(r"^    ([a-z_]+)\??:", body, re.M)), set(model.model_fields))
        fact = re.search(r"type Fact = \{(.*?)^\};", doc, re.M | re.S).group(1)
        self.assertEqual(set(re.findall(r"^  ([a-z_]+)\??:", fact, re.M)), set(Fact.model_fields))

    def test_all_v2_enums_and_null_facts_validate_without_json_schema_files(self):
        validator = DocumentedContractValidator()
        for kind in ("ticket_submitted", "information_provided", "plan_approved", "plan_rejected",
                     "plan_change_requested", "cancel_requested"):
            wire = input_message(kind)
            validator.validate("reception_input", wire)
            self.assertIsNone(wire["facts"][0]["value"])
        for kind in ("accepted", "in_progress", "information_requested", "plan_approval_requested",
                     "completed", "failed", "cancelled"):
            validator.validate("reception_output", output_message(kind))

    def test_old_wire_missing_source_incomplete_completion_and_foreign_scope_fail(self):
        validator = DocumentedContractValidator()
        invalid = [("reception_input", request()),
                   ("reception_input", input_message("plan_approved", source_message_id=None)),
                   ("reception_input", {**input_message(), "additional_information": {}}),
                   ("reception_output", {**output_message(), "customer_message": "old"}),
                   ("reception_output", output_message("completed", result=None)),
                   ("reception_delivery", {"message": output_message(), "context": {**CONTEXT, "ticket_generation": 2}})]
        for kind, wire in invalid:
            with self.subTest(kind=kind), self.assertRaises(AdapterError):
                validator.validate(kind, wire)

    def test_internal_response_is_not_a_third_reception_message_schema(self):
        validator = DocumentedContractValidator()
        validator.validate("reception_response", dict(message_id="id", status="accepted", data={}))
        validator.validate("reception_response", dict(message_id="id", status="error",
                                                     error={"code": "forbidden", "retryable": False}))
        for wire in (dict(message_id="id", status="closed", data={}),
                     dict(message_id="id", status="error", error={"code": "forbidden", "retryable": "false"}),
                     dict(message_id="id", status="accepted", data={}, unexpected=True)):
            with self.assertRaises(AdapterError):
                validator.validate("reception_response", wire)
        with self.assertRaises(AdapterError):
            validator.validate("unconfigured_rpc", {})


class FactoryTests(unittest.IsolatedAsyncioTestCase):
    def bundle(self, *, features=frozenset({"reception", "workflow"}), transport=None, **kwargs):
        routes = {operation: "/test/" + operation for feature in features
                  for operation in FEATURES.get(feature, (set(), set()))[0]}
        return build_adapters(origin="https://test.invalid", routes=routes, credentials=Headers(),
            reception_authentication=Authentication(), features=features,
            transport=transport or V2Transport(), **kwargs)

    async def test_standard_flow_needs_no_proposed_contracts_or_event_provider(self):
        transport = V2Transport()
        bundle = self.bundle(transport=transport)
        self.assertIsNone(bundle.authority)
        self.assertIsNone(bundle.event_verifier)
        verified = await bundle.gateway.verify(input_message(), "verified-source")
        receipt = await bundle.gateway.send(output_message(), verified.context)
        self.assertEqual(receipt, {"message_id": "output-1", "status": "accepted"})
        self.assertEqual(transport.calls[0][2], input_message())

    async def test_workflow_and_v1_bridge_remain_available(self):
        bundle = self.bundle(features=frozenset({"reception", "workflow", "legacy"}), transport=Transport())
        await bundle.approvals.request_plan(request("approval.requested"))
        result = await bundle.gateway.ask_question(request("resident.question"))
        self.assertEqual(result.status, "accepted")
        result = await bundle.gateway.send_completion(request("completion.requested"))
        self.assertEqual(result.request_id, "request-1")

    async def test_only_two_pinned_reception_schemas_augment_existing_guards(self):
        from adapters.backend.contract_validator import SchemaPin
        with tempfile.TemporaryDirectory() as folder:
            pins = {}
            for kind in ("reception_input", "reception_output"):
                path = Path(folder) / (kind + ".json")
                # Test-only schemas demonstrate augmentation, not publication of
                # the canonical peer schema. The documented boundary still runs.
                path.write_text(json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object", "properties": {"message": {"type": "string", "minLength": 5}}}))
                pins[kind] = SchemaPin(path, hashlib.sha256(path.read_bytes()).hexdigest())
            bundle = self.bundle(schema_pins=pins)
            await bundle.gateway.verify(input_message(), "verified-source")
            with self.assertRaises(AdapterError):
                await bundle.gateway.verify(input_message(message="x"), "verified-source")
            with self.assertRaises(AdapterError):
                await bundle.gateway.verify(request(), "verified-source")

    async def test_explicit_optional_feature_still_requires_its_validator_and_auth(self):
        with self.assertRaisesRegex(ValueError, "missing validators"):
            self.bundle(features=frozenset({"reception", "authority"}))
        with self.assertRaisesRegex(ValueError, "event source authentication"):
            self.bundle(features=frozenset({"reception", "events"}))
        with self.assertRaisesRegex(ValueError, "unknown or empty"):
            self.bundle(features=frozenset({"unknown"}))

    async def test_disabling_reception_does_not_require_its_authentication(self):
        routes = {op: "/test/" + op for op in FEATURES["workflow"][0]}
        bundle = build_adapters(origin="https://test.invalid", routes=routes, credentials=Headers(),
                                features=frozenset({"workflow"}), transport=Transport())
        self.assertIsNone(bundle.gateway)
        await bundle.tools.offer_assignment(request("assignment.offered"))
