import copy
import unittest

from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from adapters.tools.grants import GrantedToolClient, RemoteToolGrantResolver
from backend.production_support import authentication, callback, contract_client, ContractTransport, proof


class ToolGrantTests(unittest.IsolatedAsyncioTestCase):
    def parts(self):
        wire = callback()
        grant = dict(tool=wire["tool"], operation="tool.execute", request_schema="tool_callback_request",
                     response_schema="tool_callback_response", context=wire["context"],
                     agent_version_id=wire["agent_version_id"], task_id=wire["task_id"], run_id=wire["run_id"])
        transport = ContractTransport(lambda request: dict(request_fingerprint=fingerprint(request), grant=grant))
        backend = contract_client(transport)
        auth = authentication()
        resolver = RemoteToolGrantResolver(backend, authentication=auth)
        tools = GrantedToolClient(backend, resolver=resolver, authentication=auth,
                                  allowed_operations={"tool.execute"})
        return wire, grant, transport, tools

    async def test_callback_requires_remote_grant_and_preserves_ids(self):
        wire, grant, transport, tools = self.parts()
        saved = copy.deepcopy(wire)
        await tools.invoke(wire, authentication=proof(wire, purpose="tool"))
        self.assertEqual([call[0].rsplit("/", 1)[-1] for call in transport.calls],
                         ["tool.grant.verify", "tool.execute"])
        self.assertEqual(transport.calls[-1][2], saved)
        self.assertEqual(transport.calls[-1][1]["Idempotency-Key"], saved["idempotency_key"])

    async def test_cross_task_run_scope_or_unconfigured_operation_cannot_execute(self):
        for key, value in (("task_id", "other-task"), ("run_id", "other-run"),
                           ("agent_version_id", "other-agent"), ("operation", "unapproved"),
                           ("context", {**callback()["context"], "ticket_generation": 2})):
            wire, grant, transport, tools = self.parts()
            grant[key] = value
            with self.subTest(key=key), self.assertRaises(AdapterError):
                await tools.invoke(wire, authentication=proof(wire, purpose="tool"))
            self.assertEqual(len(transport.calls), 1)

    async def test_invalid_source_or_model_endpoint_cannot_resolve_grants(self):
        wire, grant, transport, tools = self.parts()
        source = proof(wire, purpose="tool")
        with self.assertRaises(AdapterError):
            await tools.invoke({**wire, "input": {"id": "changed"}}, authentication=source)
        with self.assertRaises(AdapterError):
            await tools.invoke({**wire, "endpoint": "https://evil"}, authentication=source)
        self.assertFalse(transport.calls)
