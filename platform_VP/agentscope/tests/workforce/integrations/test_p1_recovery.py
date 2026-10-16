"""Crash/order/expiry regressions against the production SQL and worker paths."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select, update
from tests.workforce.integrations.test_unified_partner_case import _CaseHarness, call, runner_module, signed

from agentscope.app.workforce.foundation._tables import durable_jobs
from agentscope.app.workforce.integrations.unified._tables import (
    approvals,
    operations,
    receipts,
    routes,
)


class RecoveryTest(_CaseHarness):
    async def test_timeout_after_partner_side_effect_keeps_unknown_and_never_redispatches(self):
        import asyncio

        from agentscope.tool import MCPTool

        side_effects = []

        async def uncertain(tool, **arguments):
            side_effects.append(arguments["client_reference"])
            await asyncio.sleep(1)

        async def turn(tools):
            tools["vh_work_order_dispatch"]._spec["call_timeout"] = .01
            for _ in range(2):
                await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Fix leak")
            await call(tools, "CaseSay", text="Ban quản lý đang kiểm tra kết quả giao việc.", expects="reply")

        self.leader.scripts = [turn]
        with patch.object(MCPTool, "call", uncertain):
            async with self._client() as client:
                response = await client.post("/workforce/v1/partner/requests", json=self._start())
                self.assertEqual(202, response.status_code, response.text)
                self.assertEqual("succeeded", await self._run())
        self.assertEqual(1, len(side_effects))
        self.assertEqual("unknown", (await self.runner._case.store.operation(side_effects[0]))["status"])

    async def test_reconcile_reads_durable_partner_receipt_without_dispatch(self):
        import copy
        import json

        from tests.workforce.integrations.test_unified_partner_case import TOOLS

        from agentscope.message import TextBlock, ToolResultState
        from agentscope.tool import MCPTool, ToolChunk

        configured = copy.deepcopy(TOOLS)
        configured[1]["reconcile_tool"] = "vh_operation_get"
        configured.append({"name": "vh_operation_get", "mcp_tool": "vh_operation_get", "mcp_id": "mcp-1",
            "kind": "lookup", "read_only": True, "requires_consent": False, "internal": True, "tracking": "none"})
        self.storage.mcp.discovered_tools.append({"name": "vh_operation_get", "read_only": True,
            "input_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"},
                "client_reference": {"type": "string"}}}})
        async with self.uows() as uow:
            await uow.execute(update(routes).values(tools=configured))
            await uow.commit()
        async with self._client() as client:
            started = await self._started(client)
            reference = "unknown-committed-by-partner"
            await self.runner._case.store.record_operation({"workflow_id": started["workflow_id"],
                "integration_id": "pi-1", "tool_name": "vh_work_order_dispatch", "client_reference": reference,
                "external_job_id": None, "status": "unknown"})
            read_calls = []

            async def receipt(tool, **arguments):
                read_calls.append((tool._tool.name, arguments))
                return ToolChunk(state=ToolResultState.SUCCESS, content=[TextBlock(text=json.dumps({"found": True,
                    "result": {"external_job_id": "WO-existing", "status": "pending"}}))])

            await self._due("workforce.unified.reconcile")
            with patch.object(MCPTool, "call", receipt):
                self.assertEqual("succeeded", await self._run())
            self.assertEqual([("vh_operation_get", {"ticket_id": "T-77", "client_reference": reference})], read_calls)
            recovered = await self.runner._case.store.operation(reference)
            self.assertEqual(("pending", "WO-existing"), (recovered["status"], recovered["external_job_id"]))
            self.assertEqual([], self.mcp_calls)

    async def test_startup_restores_missing_jobs_for_existing_unknown_operations(self):
        from sqlalchemy import delete

        async with self._client() as client:
            await self._started(client, dispatch=True)
            async with self.uows() as uow:
                await uow.execute(delete(durable_jobs).where(durable_jobs.c.job_type == "workforce.unified.reconcile"))
                await uow.commit()
            recovery = self.assembly.services["recovery"]
            await recovery.resume_pending()
            await recovery.resume_pending()
            async with self.uows() as uow:
                jobs = (await uow.execute(select(durable_jobs).where(
                    durable_jobs.c.job_type == "workforce.unified.reconcile"))).mappings().all()
            self.assertEqual(1, len(jobs))

    async def _started(self, client, *, dispatch=False):
        async def turn(tools):
            if dispatch:
                await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Fix leak")
            await call(tools, "CaseSay", text="Yêu cầu đang được xử lý.", expects="reply")
        self.leader.scripts = [turn]
        response = await client.post("/workforce/v1/partner/requests", json=self._start())
        self.assertEqual(202, response.status_code, response.text)
        self.assertEqual("succeeded", await self._run())
        return response.json()

    async def _event(self, client, reference, event_id="event-1", version=2):
        raw, headers = signed({"schema_version": "1", "external_event_id": event_id,
            "client_reference": reference, "external_job_id": "WO-1", "event_type": "job.accepted",
            "provider_version": version, "occurred_at": "2026-10-20T02:00:00Z",
            "data": {"staff_name": "Bình", "eta": "09:30 20/10/2026"}})
        response = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
        self.assertEqual(202, response.status_code, response.text)
        return response.json()

    async def _due(self, job_type):
        async with self.uows() as uow:
            await uow.execute(update(durable_jobs).where(durable_jobs.c.job_type == job_type).values(
                not_before=datetime.now(UTC) - timedelta(seconds=1)))
            await uow.commit()

    async def test_repeat_after_persisted_dispatch_does_not_call_partner_twice(self):
        async def turn(tools):
            await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Fix leak")
            await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Fix leak")
            await call(tools, "CaseSay", text="Yêu cầu đang được xử lý.", expects="reply")
        self.leader.scripts = [turn]
        async with self._client() as client:
            response = await client.post("/workforce/v1/partner/requests", json=self._start())
            self.assertEqual(202, response.status_code, response.text)
            self.assertEqual("succeeded", await self._run())
            self.assertEqual(1, len(self.mcp_calls))
            async with self.uows() as uow:
                rows = (await uow.execute(select(operations))).mappings().all()
            self.assertEqual(1, len(rows))
            self.assertIsNotNone(rows[0]["call_result"])

    async def test_crash_after_intent_commit_never_blindly_redispatches(self):
        async with self._client() as client:
            started = await self._started(client)
            tool = self.leader.tools["vh_work_order_dispatch"]
            reference = await tool._case.client_reference(tool.name, {"ticket_id": "T-77", "description": "Fix leak"})
            await self.runner._case.store.record_operation({"workflow_id": started["workflow_id"],
                "integration_id": "pi-1", "tool_name": tool.name, "client_reference": reference,
                "external_job_id": None, "status": "dispatching"})
            await tool.call(ticket_id="T-77", description="Fix leak")
            self.assertEqual([], [entry for entry in self.mcp_calls if entry[0] == tool.name])
            await self._due("workforce.unified.reconcile")
            self.assertEqual("succeeded", await self._run())
            self.assertEqual([], self.mcp_calls)
            self.assertFalse((await self.runner._case.store.operation(reference))["terminal"])

    async def test_event_before_operation_is_reprocessed_by_durable_worker(self):
        async with self._client() as client:
            started = await self._started(client)
            received = await self._event(client, "early-reference")
            self.assertEqual("quarantined", received["ingestion_status"])
            await self.runner._case.store.record_operation({"workflow_id": started["workflow_id"],
                "integration_id": "pi-1", "tool_name": "vh_work_order_dispatch", "client_reference": "early-reference",
                "external_job_id": None, "status": "dispatching"})
            self.assertEqual("succeeded", await self._run())
            operation = await self.runner._case.store.operation("early-reference")
            self.assertEqual(("accepted", 2), (operation["status"], operation["provider_version"]))
            async with self.uows() as uow:
                row = (await uow.execute(select(receipts))).mappings().one()
            self.assertEqual((received["receipt_id"], "applied"), (row["receipt_id"], row["ingestion_status"]))
            self.assertEqual([], self.mcp_calls)

    async def test_same_rank_stale_and_unversioned_events_cannot_regress(self):
        async with self._client() as client:
            await self._started(client, dispatch=True)
            reference = next(args["client_reference"] for name, args in self.mcp_calls if name == "vh_work_order_dispatch")
            await self._event(client, reference, "new", 8)
            for event_id, version in (("old", 7), ("same", 8), ("missing-version", None)):
                result = await self._event(client, reference, event_id, version)
                self.assertEqual("rejected", result["ingestion_status"])
            operation = await self.runner._case.store.operation(reference)
            self.assertEqual(("accepted", 8), (operation["status"], operation["provider_version"]))

    async def test_progress_projection_replays_after_failure_using_stable_id(self):
        async with self._client() as client:
            await self._started(client, dispatch=True)
            reference = next(args["client_reference"] for name, args in self.mcp_calls if name == "vh_work_order_dispatch")
            provider = self.assembly.services["provider"]
            provider._share = AsyncMock(side_effect=RuntimeError("room unavailable"))
            result = await self._event(client, reference)
            async with self.uows() as uow:
                row = (await uow.execute(select(receipts))).mappings().one()
            self.assertIsNone(row["projected_at"])
            provider._share = AsyncMock()
            await self._due("workforce.unified.projection")
            self.assertEqual("succeeded", await self._run())
            provider._share.assert_awaited_once_with((await self.runner._case.store.operation(reference))["workflow_id"],
                row["projection_text"], event_id="provider:" + result["receipt_id"])
            await provider.replay_projection(result["receipt_id"])
            self.assertEqual(1, provider._share.await_count)

    async def test_expired_approval_is_resolved_and_resumed_as_denied(self):
        from agentscope.app._chat_consent import PendingChatAction
        from agentscope.event import UserConfirmResultEvent
        from agentscope.message import ToolCallBlock

        parked = [PendingChatAction(agent_id="leader-vh", session_id="s-coordinator", reply_id="reply-1",
            tool_call=ToolCallBlock(id="expired-call", name="vh_work_order_dispatch", input='{"ticket_id":"T-77"}'))]

        async def pending(*_):
            return parked

        async def asks(_):
            return None

        async def resumed(tools):
            decision = self.leader.messages[-1]
            self.assertIsInstance(decision, UserConfirmResultEvent)
            self.assertFalse(decision.confirm_results[0].confirmed)
            parked.clear()
            await call(tools, "CaseSay", text="Đề nghị đã hết hạn, cần xác nhận lại.", expects="reply")

        self.leader.scripts = [asks, resumed]
        with patch.object(runner_module, "pending_chat_actions", pending):
            async with self._client() as client:
                started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
                self.assertEqual("succeeded", await self._run())
                async with self.uows() as uow:
                    await uow.execute(update(approvals).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
                    await uow.commit()
                await self._due("workforce.unified.approval_expiry")
                self.assertEqual("succeeded", await self._run())
                self.assertEqual("succeeded", await self._run())
                async with self.uows() as uow:
                    row = (await uow.execute(select(approvals))).mappings().one()
                self.assertEqual("expired", row["status"])
                snapshot = await client.get(f"/workforce/v1/partner/conversations/{started['conversation_id']}",
                                            params={"external_user_id": "resident-1"})
                self.assertEqual([], snapshot.json()["pending_approvals"])
                self.assertEqual([], self.mcp_calls)
