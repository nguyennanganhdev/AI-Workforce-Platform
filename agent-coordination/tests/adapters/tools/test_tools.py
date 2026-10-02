import unittest

from adapters.backend.client import HttpResponse
from adapters.backend.errors import AdapterError
from adapters.tools.tool_client import ToolClient
from tests.adapters.backend.support import Transport, client, request


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_assignment_and_evidence_are_preserved(self):
        transport = Transport()
        tools = ToolClient(client(transport))
        for method, kind in ((tools.offer_assignment, "assignment.offered"),
                             (tools.respond_assignment, "assignment.responded"),
                             (tools.report_work, "work.completed")):
            wire = request(kind)
            result = await method(wire)
            self.assertEqual(result.status, "accepted")
            self.assertEqual(transport.calls[-1][2], wire)

    async def test_decline_requires_reason(self):
        transport = Transport()
        tools = ToolClient(client(transport))
        wire = request("assignment.responded")
        wire["payload"]["decision"] = "decline"
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await tools.respond_assignment(wire)
        self.assertFalse(transport.calls)
        wire["payload"]["reason"] = "Không trong ca trực"
        await tools.respond_assignment(wire)
        self.assertEqual(transport.calls[0][2]["payload"]["decision"], "decline")

    async def test_model_cannot_supply_arbitrary_tool_or_url(self):
        transport = Transport()
        tools = ToolClient(client(transport), operations={
            "offer": ("assignment.offer", "assignment.offered"),
        })
        for name in ("sql", "https://external.example", "close_ticket"):
            with self.assertRaisesRegex(AdapterError, "tool_not_allowed"):
                await tools.invoke(name, request("assignment.offered"))
        self.assertFalse(transport.calls)
        await tools.invoke("offer", request("assignment.offered"))
        self.assertEqual(len(transport.calls), 1)

    async def test_allowlisted_tool_still_checks_message_type(self):
        tools = ToolClient(client(), operations={"offer": ("assignment.offer", "assignment.offered")})
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await tools.invoke("offer", request("work.completed"))

    async def test_invalid_evidence_from_backend_is_not_success(self):
        transport = Transport()
        transport.response = HttpResponse(422, b"evidence failed")
        with self.assertRaisesRegex(AdapterError, "validation_error"):
            await ToolClient(client(transport)).report_work(request("work.completed"))
