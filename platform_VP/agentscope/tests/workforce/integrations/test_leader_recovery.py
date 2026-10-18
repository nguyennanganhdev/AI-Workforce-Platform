"""Real durable workflow seams; scripted models and a fake partner MCP."""

from copy import deepcopy
from types import SimpleNamespace

from sqlalchemy import select, update

from agentscope.app.workforce.integrations.unified._case import CaseEvidence
from agentscope.app.workforce.integrations.unified._tables import (
    integrations,
    operations,
)
from agentscope.app.workforce.orchestration._tables import workflows
from tests.workforce.integrations.test_unified_partner_case import (
    SCHEMA,
    _CaseHarness,
    call,
    signed,
)


class LeaderRecoveryTest(_CaseHarness):
    async def test_context_reader_resolves_only_sources_of_the_bound_ticket(self):
        from agentscope.app._shared_context import SharedContextService
        from tests.team_shared_context_test import _Storage

        async with self._client() as client:
            started, _ = await self._dispatch(client)
        shared = _Storage()
        state = self.runner._app.state
        state.shared_context_storage = shared
        session = next(iter(self.storage.sessions.values()))
        session.team_id = "owned-team"
        service = SharedContextService(shared, state.message_bus)
        await service.append_event(
            user_id="manager-1",
            team_id="owned-team",
            kind="customer_message",
            content="Original evidence",
            event_id="owned-source",
        )
        await service.append_event(
            user_id="manager-1",
            team_id="other-team",
            kind="customer_message",
            content="Other case secret",
            event_id="foreign-source",
        )
        found = await self.runner._case.context_sources(
            started["workflow_id"], ["owned-source", "foreign-source", "history:0"]
        )
        self.assertEqual("Original evidence", found["owned-source"])
        self.assertNotIn("foreign-source", found)
        self.assertIn("owned-source", found["history:0"])
        self.assertNotIn("Other case secret", found["history:0"])

    async def test_partner_cannot_ask_again_for_location_in_the_handover(self):
        async def ask(tools):
            refused = await call(
                tools, "CaseSay", text="Bạn đang ở đâu?", expects="reply"
            )
            self.assertIn("đã cung cấp", refused)
            await call(tools, "CaseSay", text="Đã ghi nhận vị trí bạn cung cấp.")

        self.leader.scripts = [ask]
        async with self._client() as client:
            await client.post(
                "/workforce/v1/partner/requests",
                json=self._start(text_value="Rò nước ở hầm B2"),
            )
            self.assertEqual("succeeded", await self._run())

    async def _dispatch(self, client):
        async def dispatch(tools):
            await call(
                tools,
                "vh_work_order_dispatch",
                ticket_id="T-77",
                description="Repair the leak",
            )
            await call(tools, "CaseSay", text="Đã gửi yêu cầu cho nhân viên.")

        self.leader.scripts = [dispatch]
        started = (
            await client.post("/workforce/v1/partner/requests", json=self._start())
        ).json()
        self.assertEqual("succeeded", await self._run())
        reference = next(
            args["client_reference"]
            for name, args in self.mcp_calls
            if name == "vh_work_order_dispatch"
        )
        return started, reference

    async def _event(self, client, reference, kind):
        raw, headers = signed(
            {
                "schema_version": "1",
                "external_event_id": "event-" + kind,
                "external_job_id": "WO-1",
                "client_reference": reference,
                "event_type": kind,
                "provider_version": 9,
                "occurred_at": "2026-10-20T02:00:00.000000Z",
                "data": {
                    "summary": "Repair completed",
                    "photo_count": 2,
                    "reported_by": "An",
                    "staff_name": "An",
                    "eta": "09:30",
                },
            }
        )
        response = await client.post(
            "/workforce/v1/provider/job-events", content=raw, headers=headers
        )
        self.assertEqual(
            "applied", response.json().get("ingestion_status"), response.text
        )

    async def test_signed_completion_opens_acceptance_without_a_second_model_turn(self):
        async with self._client() as client:
            started, reference = await self._dispatch(client)
            await self._event(client, reference, "job.result_published")
            self.assertEqual("succeeded", await self._run())
            history = await self._history(client, started["conversation_id"])
        self.assertEqual(1, len(self.leader.messages))
        states = [
            item["payload"]["state"]
            for item in history
            if item["event_type"] == "workflow.status_changed"
        ]
        self.assertEqual("awaiting_confirmation", states[-1])
        async with self.uows() as uow:
            operation = (await uow.execute(select(operations))).mappings().one()
        self.assertTrue(operation["owner_agent_id"])
        self.assertTrue(operation["owner_session_id"])
        self.assertEqual("idle", await self._run())

    async def test_provider_wake_is_system_input_not_resident_input(self):
        schema = deepcopy(SCHEMA)
        schema["events"]["job.accepted"].update(wake=True, evidence=True)
        async with self.uows() as uow:
            await uow.execute(update(integrations).values(event_schema=schema))
            await uow.commit()
        async with self._client() as client:
            _, reference = await self._dispatch(client)

            async def acknowledge(tools):
                await call(tools, "CaseSay", text="Nhân viên đã nhận việc.")

            self.leader.scripts = [acknowledge]
            await self._event(client, reference, "job.accepted")
            self.assertEqual("succeeded", await self._run())
        self.assertEqual("system", self.leader.messages[-1].metadata["actor"])

    async def test_archived_report_does_not_become_verified_external_evidence(self):
        from unittest.mock import AsyncMock

        case = SimpleNamespace(
            workflow_id="w",
            store=SimpleNamespace(labelled=AsyncMock(return_value={})),
            context_reader=AsyncMock(
                return_value={"report-1": "Agent speculated that ticket_closed=true"}
            ),
        )
        result = await CaseEvidence(case).call(event_ids=["report-1"])
        self.assertFalse(result.metadata["external_evidence"])
        result = await CaseEvidence(case).call(event_ids=["other-ticket-source"])
        self.assertEqual("error", result.state.value)

    async def test_domain_acceptance_can_close_a_workflow_after_leader_attention(self):
        async with self._client() as client:
            started, reference = await self._dispatch(client)
            await self._event(client, reference, "job.result_published")
            self.assertEqual("succeeded", await self._run())
            # Reproduce a model/context failure after the durable work completed.
            async with self.uows() as uow:
                payload = deepcopy(
                    await uow.scalar(
                        select(workflows.c.payload).where(
                            workflows.c.id == started["workflow_id"]
                        )
                    )
                )
                payload["workflow"]["state"] = "needs_attention"
                await uow.execute(
                    update(workflows)
                    .where(workflows.c.id == started["workflow_id"])
                    .values(state="needs_attention", payload=payload)
                )
                await uow.commit()
            history = await self._history(client, started["conversation_id"])
            revision = [
                i["payload"]["revision"]
                for i in history
                if i["event_type"] == "workflow.status_changed"
            ][-1]
            body = {
                "schema_version": "1",
                "external_request_id": "close-after-attention",
                "external_user_id": "resident-1",
                "external_ticket_id": "T-77",
                "external_conversation_id": "chat-9:T-77",
                "expected_revision": revision,
                "reason": "resident_confirmed",
                "domain_acceptance": self._acceptance(),
            }
            response = await client.post(
                "/workforce/v1/partner/workflows/" + started["workflow_id"] + "/close",
                json=body,
            )
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual("closed", response.json()["workflow_state"])
