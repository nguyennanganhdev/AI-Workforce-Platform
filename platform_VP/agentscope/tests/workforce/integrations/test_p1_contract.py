"""An in-flight workflow reads its persisted route, tools and event schema."""

import copy

from sqlalchemy import select, update
from tests.workforce.integrations.test_unified_partner_case import _CaseHarness, call, signed

from agentscope.app.workforce.integrations.unified._contract import route_for_workflow
from agentscope.app.workforce.integrations.unified._tables import (
    integrations,
    routes,
)
from agentscope.app.workforce.orchestration._tables import workflows


class ContractTest(_CaseHarness):
    async def _start_case(self, client):
        async def turn(tools):
            await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Fix leak")
            await call(tools, "CaseSay", text="Đang chờ nhân viên nhận yêu cầu.", expects="reply")
        self.leader.scripts = [turn]
        response = await client.post("/workforce/v1/partner/requests", json=self._start())
        self.assertEqual(202, response.status_code, response.text)
        self.assertEqual("succeeded", await self._run())
        return response.json()

    async def test_reonboard_does_not_change_running_tool_policy_or_event_schema(self):
        async with self._client() as client:
            started = await self._start_case(client)
            self.assertEqual({"leader-vh": 3}, next(iter(self.storage.sessions.values())).state.middle_context["partner_agent_versions"])
            before = await route_for_workflow(self.runner._case.store, started["workflow_id"])
            async with self.uows() as uow:
                await uow.execute(update(routes).values(tools=[], config={"rules": {"safe_reply": "changed"}}))
                await uow.execute(update(integrations).values(event_schema={"events": {}}))
                await uow.commit()
            self.storage.mcp.discovered_tools[1]["input_schema"] = {"type": "object", "properties": {"changed": {"type": "boolean"}}}
            middlewares = await self.runner.case_middlewares("manager-1", "leader-console", next(iter(self.storage.sessions)))
            case = middlewares[0]._case
            tools = await self.runner._case._tools("manager-1", case, case.route)
            dispatch = next(t for t in tools if t.name == "vh_work_order_dispatch")
            self.assertIn("description", dispatch.input_schema["properties"])
            self.assertNotIn("changed", dispatch.input_schema["properties"])
            self.assertEqual(before, await route_for_workflow(self.runner._case.store, started["workflow_id"]))
            reference = self.mcp_calls[0][1]["client_reference"]
            raw, headers = signed({"schema_version": "1", "external_event_id": "old-contract-event",
                "client_reference": reference, "external_job_id": "WO-1", "event_type": "job.accepted",
                "provider_version": 2, "occurred_at": "2026-10-20T02:00:00Z",
                "data": {"staff_name": "Bình", "eta": "09:30 20/10/2026"}})
            response = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
            self.assertEqual("applied", response.json()["ingestion_status"], response.text)
            self.assertEqual("accepted", (await self.runner._case.store.operation(reference))["status"])

    async def test_corrupt_snapshot_fails_before_connector_execution(self):
        async with self._client() as client:
            started = await self._start_case(client)
            async with self.uows() as uow:
                payload = copy.deepcopy(await uow.scalar(select(workflows.c.payload)))
                payload["workflow"]["contract_snapshot"]["sha256"] = "corrupt"
                await uow.execute(update(workflows).values(payload=payload))
                await uow.commit()
            count = len(self.mcp_calls)
            with self.assertRaisesRegex(ValueError, "WORKFLOW_CONTRACT_CORRUPT"):
                await route_for_workflow(self.runner._case.store, started["workflow_id"])
            self.assertEqual(count, len(self.mcp_calls))
