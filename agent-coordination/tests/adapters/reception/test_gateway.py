import unittest

from adapters.backend.approval_client import ApprovalClient
from adapters.backend.client import HttpResponse
from adapters.backend.errors import AdapterError
from adapters.reception.reception_gateway import ReceptionGateway
from backend.support import Transport, client, request


class ReceptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reception_operation_matrix_and_unmodified_content(self):
        transport = Transport()
        gateway = ReceptionGateway(client(transport))
        cases = (
            (gateway.receive_ticket, "ticket.submitted", "reception.ticket"),
            (gateway.receive_message, "resident.message", "reception.message"),
            (gateway.ask_question, "resident.question", "reception.question"),
            (gateway.send_update, "resident.update", "reception.update"),
            (gateway.send_plan, "approval.requested", "approval.request"),
            (gateway.receive_plan_response, "approval.responded", "approval.respond"),
            (gateway.send_completion, "completion.requested", "completion.request"),
            (gateway.receive_completion_response, "completion.responded", "completion.respond"),
        )
        for method, kind, operation in cases:
            with self.subTest(kind=kind):
                wire = request(kind)
                result = await method(wire)
                self.assertEqual(result.status, "accepted")
                self.assertTrue(transport.calls[-1][0].endswith(operation))
                self.assertEqual(transport.calls[-1][2], wire)

    async def test_management_approval_not_misrouted_as_resident_reply(self):
        transport = Transport()
        gateway = ReceptionGateway(client(transport))
        wire = request("approval.responded")
        wire["payload"]["stage"] = "management_plan"
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await gateway.receive_plan_response(wire)
        self.assertFalse(transport.calls)
        await ApprovalClient(client(transport)).respond_plan(wire)
        self.assertEqual(len(transport.calls), 1)

    async def test_management_request_uses_approval_client(self):
        transport = Transport()
        wire = request("approval.requested")
        wire["payload"].update(stage="management_plan", delivery_channel="management_ui")
        del wire["payload"]["depends_on_approval_id"]
        await ApprovalClient(client(transport)).request_plan(wire)
        self.assertEqual(transport.calls[0][2]["payload"]["stage"], "management_plan")

    async def test_backend_forbidden_means_no_reception_delivery(self):
        transport = Transport()
        transport.response = HttpResponse(403, b"denied")
        gateway = ReceptionGateway(client(transport))
        with self.assertRaisesRegex(AdapterError, "forbidden"):
            await gateway.send_plan(request("approval.requested"))
        # Only backend is called. No direct UI send exists to bypass its denial.
        self.assertEqual(len(transport.calls), 1)

    async def test_approval_and_completion_decisions_cannot_be_interchanged(self):
        gateway = ReceptionGateway(client())
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await gateway.receive_plan_response(request("completion.responded"))
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await gateway.receive_completion_response(request("approval.responded"))

    async def test_unstructured_yes_remains_a_message(self):
        transport = Transport()
        gateway = ReceptionGateway(client(transport))
        wire = request("resident.message")
        wire["payload"] = {"text": "đồng ý"}
        await gateway.receive_message(wire)
        self.assertEqual(transport.calls[0][2]["type"], "resident.message")
        self.assertNotIn("decision", transport.calls[0][2]["payload"])

    async def test_mention_and_reply_reference_preserved(self):
        transport = Transport()
        wire = request("resident.message")
        wire["payload"]["mentioned_agent_id"] = "agent-b"
        await ReceptionGateway(client(transport)).receive_message(wire)
        self.assertEqual(transport.calls[0][2]["payload"], wire["payload"])

    async def test_malformed_payload_gives_validation_error(self):
        for malformed in (None, [], "yes"):
            wire = request("approval.responded")
            wire["payload"] = malformed
            with self.assertRaisesRegex(AdapterError, "validation_error"):
                await ReceptionGateway(client()).receive_plan_response(wire)
