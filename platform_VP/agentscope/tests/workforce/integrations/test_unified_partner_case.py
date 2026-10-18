"""Partner case runtime of unified mode, driven the way the Vinhomes bridge does.

Real Workforce SQL repositories, durable jobs, routers, HMAC provider auth and
the case middleware/tools; the model is a script that calls the same tools
the room would (the Leader's case tools and the coordinator's partner tools,
under the same ticket), and the partner MCP server is a fake.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentscope.app.business import PartnerPrincipal
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.workforce.contracts import (
    PartnerOperation,
    PartnerRequestEnvelope,
    ResolvedPartnerRoute,
    Scope,
)
from agentscope.app.workforce.execution import get_metadata as get_execution_metadata
from agentscope.app.workforce.foundation import (
    DurableJobService,
    DurableJobWorker,
    MessageBusPublicEventSignal,
    MessageBusRequestCompletionSignal,
    SqlAlchemyUnitOfWorkFactory,
    SqlDurableJobRepository,
)
from agentscope.app.workforce.foundation._provider_auth import (
    HmacProviderAuth,
    SqlProviderCredentialRepository,
)
from agentscope.app.workforce.foundation._tables import metadata as foundation_metadata
from agentscope.app.workforce.foundation._tables import (
    partner_manager_routes,
    provider_credentials,
    provider_integrations,
)
from agentscope.app.workforce.integrations.unified import (
    ChatLeaderTurnRunner,
    build_unified_runtime,
)
from agentscope.app.workforce.integrations.unified import _runner as runner_module
from agentscope.app.workforce.integrations.unified import get_metadata as unified_metadata
from agentscope.app.workforce.integrations.unified._case import check_say
from agentscope.app.workforce.integrations.unified._secrets import (
    resolve_signing_secret,
    seal,
)
from agentscope.app.workforce.integrations.unified._tables import (
    approvals,
    integrations,
    operations,
    routes,
)
from agentscope.app.workforce.orchestration import get_metadata
from agentscope.app.workforce.orchestration._tables import workflow_checkpoints
from agentscope.mcp import HttpMCPConfig, MCPClient
from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import MCPTool, ToolChunk

PEPPER = "p" * 40
SIGNING_SECRET = "s" * 43
SCOPE = Scope(tenant_id="tenant-1", domain_id="domain-1", area_id="area-1", manager_account_id="manager-1")
NOW = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
RULES = {
    "safe_reply": "Tôi chưa xác minh được thông tin này. Bạn vui lòng liên hệ quầy lễ tân.",
    "phrase_rules": [
        {"phrases": ["sẽ đến trong", "sẽ có mặt ngay"], "reason": "không hứa khoảng thời gian"},
        {
            "phrases": ["được miễn phí", "không tính phí"],
            "reason": "chỉ nói miễn phí khi tài liệu ghi như vậy",
            "unless": ["miễn phí"],
        },
    ],
}
SCHEMA = {
    "version": "1",
    "version_mode": "snapshot",
    "events": {
        "job.offered": {"status": "offered", "rank": 10, "public_status": "offered"},
        "job.accepted": {
            "status": "accepted",
            "rank": 20,
            "public_status": "accepted",
            "public_fields": ["staff_name", "eta"],
            "message": "Nhân viên {staff_name} đã nhận yêu cầu của bạn, dự kiến đến lúc {eta}.",
        },
        "job.en_route": {
            "status": "en_route",
            "rank": 30,
            "public_status": "en_route",
            "public_fields": ["staff_name"],
            "message": "Nhân viên {staff_name} đang trên đường đến nhà bạn.",
        },
        "job.result_published": {
            "status": "result_published",
            "rank": 90,
            "terminal": True,
            "outcome": "completed",
            "public_status": "result_published",
            "public_fields": ["summary", "photo_count", "reported_by"],
            "field_types": {"photo_count": "count"},
            "wake": True,
            "evidence": True,
        },
    },
}
TOOLS = [
    {
        "name": "vh_ticket_get",
        "mcp_tool": "vh_ticket_get",
        "mcp_id": "mcp-1",
        "kind": "lookup",
        "read_only": True,
        "requires_consent": False,
        "tracking": "none",
        "description_override": "Where the request stands NOW.",
    },
    {
        "name": "vh_work_order_dispatch",
        "mcp_tool": "vh_work_order_dispatch",
        "mcp_id": "mcp-1",
        "kind": "action",
        "read_only": False,
        "requires_consent": False,
        "tracking": "events",
        "client_reference_arg": "client_reference",
        "description_override": "Create the work and offer it to staff.",
    },
]
COORDINATOR = {"name": "DieuPhoiVinhomes", "tools": [t["name"] for t in TOOLS], "coordinator": True}
HANDOVER = "ticket_id: T-77\nhandover_version: v1.1\nCư dân: An\nMô tả của cư dân: Rò nước bồn rửa\nCăn: S1-1205"


class _Routing:
    def route(self):
        return ResolvedPartnerRoute(
            scope=SCOPE,
            route_id="route-1",
            route_revision=1,
            grant_operations=tuple(PartnerOperation),
            membership_revision=1,
            resolved_at=NOW,
        )

    async def resolve(self, actor, routing_input):
        return self.route()

    async def revalidate(self, scope, route_id, expected_revision, actor, audience, operation, uow=None):
        return self.route()


class _Identity:
    async def check_scope_active(self, scope, uow=None):
        if scope != SCOPE:
            raise PermissionError


class _Session(SimpleNamespace):
    pass


class _Storage:
    """Just enough of StorageBase for the case runner and middleware."""

    def __init__(self):
        self.sessions = {}
        self.messages = []  # every session's messages; enough for token counting

        self.mcp = SimpleNamespace(
            id="mcp-1",
            enabled=True,
            client=MCPClient(
                name="vinhomes",
                is_stateful=False,
                mcp_config=HttpMCPConfig(url="https://partner.test/mcp"),
            ),
            discovered_tools=[
                {
                    "name": "vh_ticket_get",
                    "description": "Read the ticket.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"ticket_id": {"type": "string"}},
                        "required": ["ticket_id"],
                    },
                },
                {
                    "name": "vh_work_order_dispatch",
                    "description": "Dispatch.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string"},
                            "description": {"type": "string"},
                            "client_reference": {"type": "string", "minLength": 8},
                        },
                        "required": ["ticket_id", "description", "client_reference"],
                    },
                },
            ],
        )

    async def list_model_calls(self, *_args, **_kwargs):
        return getattr(self, "model_calls", [])

    async def get_agent(self, user_id, agent_id):
        from agentscope.agent import ContextConfig, ReActConfig
        from agentscope.app._agent_spec import AgentSpec
        from agentscope.app.storage import AgentData, AgentRecord

        return AgentRecord(id=agent_id, user_id=user_id, data=AgentData(
            name=agent_id, context_config=ContextConfig(), react_config=ReActConfig(), published_version=3, versions=[{
                "version": 3, "system_prompt": "Scripted test agent",
                "spec": AgentSpec(name=agent_id).model_dump(mode="json"), "evaluation": {},
            }],
        ))

    async def list_sessions(self, user_id, agent_id):
        return [SimpleNamespace(config=SimpleNamespace(chat_model_config=None))]

    async def get_session(self, user_id, agent_id, session_id):
        return self.sessions.get(session_id)

    async def list_messages(self, user_id, session_id, limit=200):
        return list(self.messages), None

    async def upsert_session(self, user_id, agent_id, config, state=None, session_id=None, **_):
        session = self.sessions.get(session_id) or _Session(
            id=session_id,
            agent_id=agent_id,
            config=config,
            team_id=None,
            state=SimpleNamespace(middle_context={}),
        )
        if state is not None:
            session.state = state
        self.sessions[session_id] = session
        return session

    async def upsert_team(self, user_id, team):
        self.teams = {**getattr(self, "teams", {}), team.id: team}

    async def set_session_team_id(self, user_id, session_id, team_id):
        self.sessions[session_id].team_id = team_id

    async def get_mcp(self, user_id, mcp_id):
        return self.mcp if mcp_id == "mcp-1" else None


class _Workspace:
    default_mcps: list = []

    async def list_mcps(self, **_):
        return []


class _WorkspaceManager:
    async def get_workspace(self, *_args):
        return _Workspace()


class _Leader:
    """The model: each script calls the case tools the way a model would."""

    def __init__(self, runner):
        self.runner = runner
        self.scripts = []
        self.inputs = []
        self.messages = []

    async def run(self, user_id, session_id, agent_id, input_msg):
        self.messages.append(input_msg)
        self.inputs.append(getattr(input_msg, "get_text_content", lambda: str(input_msg))())
        middlewares = await self.runner.case_middlewares(user_id, agent_id, session_id)
        if not middlewares:
            # A member's resumed call: its report wakes the ticket's Leader.
            ticket = next(iter(self.runner._app.state.storage.sessions.values()))
            middlewares = await self.runner.case_middlewares(user_id, ticket.agent_id, ticket.id)
        middleware = middlewares[0]
        tools = {tool.name: tool for tool in await middleware.list_tools()}
        # The coordinator's calls in the room run under the same ticket.
        case = middleware._case
        for tool in await self.runner._case._tools(user_id, case, case.route):
            tools[tool.name] = tool
        self.tools = tools
        await self.scripts.pop(0)(tools)


async def call(tools, name, **kwargs) -> str:
    chunk = await tools[name].call(**kwargs)
    return "\n".join(block.text for block in chunk.content)


async def _provider_principal(api_key):
    if api_key != "provider-key":
        raise PermissionError("unknown provider key")
    return PartnerPrincipal(key_id="pkey-1", client_id="partner-1", tenant_id="tenant-1", domain_id="domain-1")


def signed(body: dict, secret: str = SIGNING_SECRET) -> tuple[bytes, dict]:
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    stamp = str(int(time.time()))
    signature = "v1=" + hmac.new(secret.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, {
        "Authorization": "ApiKey provider-key",
        "Content-Type": "application/json",
        "X-Partner-Timestamp": stamp,
        "X-Partner-Key-Id": "sk_1",
        "X-Partner-Signature": signature,
    }


class _CaseHarness(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"PARTNER_API_KEY_PEPPER": PEPPER})
        self.env.start()
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{(Path(self.temp.name) / 'case.sqlite3').as_posix()}",
        )
        async with self.engine.begin() as connection:
            from agentscope.app.workforce.assets._tables import metadata as asset_metadata

            for meta in (foundation_metadata, get_execution_metadata(), get_metadata(), unified_metadata(), asset_metadata):
                await connection.run_sync(meta.create_all)
            await connection.execute(
                text("CREATE TABLE partner_api_clients (id TEXT PRIMARY KEY, tenant_id TEXT, status TEXT)"),
            )
            await connection.execute(text("INSERT INTO partner_api_clients VALUES ('partner-1', 'tenant-1', 'active')"))
            await connection.execute(insert(partner_manager_routes).values(
                id="route-1", **SCOPE.model_dump(), partner_client_id="partner-1",
                external_management_ref="local-management", status="active", revision=1,
                membership_revision=1, allowed_operations=[op.value for op in PartnerOperation],
                granted_by="fixture", confirmed_by_client_id="partner-1", created_at=NOW, updated_at=NOW,
            ))
            await connection.execute(
                insert(provider_integrations).values(
                    id="pi-1", tenant_id="tenant-1", partner_client_id="partner-1",
                    name="Vinhomes events", status="active", created_at=NOW, updated_at=NOW,
                ),
            )
            await connection.execute(
                insert(provider_credentials).values(
                    id="pc-1", provider_integration_id="pi-1", api_credential_id="pkey-1",
                    signing_key_id="sk_1", secret_ref=seal(SIGNING_SECRET), purpose="provider_events",
                    allowed_operations=["publish_job_event", "read_event_receipt"], status="active",
                    expires_at=None, revoked_at=None, created_at=NOW, updated_at=NOW,
                ),
            )
            await connection.execute(
                insert(integrations).values(
                    integration_id="pi-1", tenant_id="tenant-1", partner_client_id="partner-1",
                    event_schema=SCHEMA, created_at=NOW, updated_at=NOW,
                ),
            )
            await connection.execute(
                insert(routes).values(
                    route_id="route-1", tenant_id="tenant-1", partner_client_id="partner-1",
                    manager_account_id="manager-1", leader_agent_id="leader-vh", integration_id="pi-1",
                    config={"rules": RULES, "policy": {"approval_ttl_seconds": 600},
                            "member_agents": {"leader-vh": COORDINATOR},
                            "ticket_title_fields": ["Mô tả của cư dân", "Căn"]}, tools=TOOLS,
                    created_at=NOW, updated_at=NOW,
                ),
            )
        uows = SqlAlchemyUnitOfWorkFactory(async_sessionmaker(self.engine, expire_on_commit=False))
        self.uows = uows
        bus = InMemoryMessageBus()
        # No delay between attempts: a retried turn runs on the next worker step.
        jobs = DurableJobService(SqlDurableJobRepository(uows), retry_base=timedelta(0))
        foundation = SimpleNamespace(
            uows=uows,
            jobs=jobs,
            public_event_signal=MessageBusPublicEventSignal(bus),
            request_completion_signal=MessageBusRequestCompletionSignal(bus),
            identity=_Identity(),
            partner_routing=_Routing(),
            management_verification=None,
            route_grants=None,
            provider_auth=HmacProviderAuth(
                SqlProviderCredentialRepository(uows),
                _provider_principal,
                resolve_signing_secret,
            ),
        )
        self.storage = _Storage()
        self.runner = ChatLeaderTurnRunner(uows, wait_seconds=1)
        self.assembly = build_unified_runtime(foundation, self.runner, bounded_wait_seconds=0)
        self.leader = _Leader(self.runner)
        self.runner.bind(
            SimpleNamespace(
                state=SimpleNamespace(
                    chat_service=self.leader,
                    storage=self.storage,
                    workspace_manager=_WorkspaceManager(),
                    message_bus=bus,
                    shared_context_storage=None,
                ),
            ),
        )
        self.worker = DurableJobWorker(jobs, self.assembly.job_handlers, worker_id="case-test", heartbeat_interval=10.0)
        self.mcp_calls = []

        async def fake_mcp_call(tool, **kwargs):
            self.mcp_calls.append((tool._tool.name, kwargs))
            if tool._tool.name == "vh_work_order_dispatch":
                async with self.uows() as uow:
                    intent = (await uow.execute(select(operations).where(
                        operations.c.client_reference == kwargs["client_reference"],
                    ))).mappings().one()
                    self.assertEqual("dispatching", intent["status"])
                    if getattr(self, "early_progress", False):
                        await uow.execute(update(operations).where(
                            operations.c.operation_id == intent["operation_id"],
                        ).values(status="arrived", rank=40, external_job_id="WO-1"))
                        await uow.commit()
                body = {"status": "pending", "external_job_id": "WO-1", "offered_to": "An"}
            else:
                body = {"ticket_status": "open", "appointment": "09:30 20/10/2026", "quote": {"total": 450000}}
            return ToolChunk(content=[TextBlock(text=json.dumps(body, ensure_ascii=False))], state=ToolResultState.RUNNING)

        async def no_pending(*_args):
            return []

        async def console_leader(*_args):
            # The manager's console Leader runs every partner ticket.
            primary = SimpleNamespace(config=SimpleNamespace(chat_model_config=None))
            return SimpleNamespace(id="leader-console"), primary

        self.patches = [
            # Readiness has its own real-storage regression suite; this harness isolates case/close behavior.
            patch("agentscope.app.workforce.integrations.unified._readiness.route_readiness", AsyncMock(return_value={"ready": True})),
            patch.object(MCPTool, "call", fake_mcp_call),
            patch.object(runner_module, "pending_chat_actions", no_pending),
            patch("agentscope.app._router._workforce_console._leader", console_leader),
        ]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        for item in self.patches:
            item.stop()
        self.env.stop()
        await self.engine.dispose()
        self.temp.cleanup()

    def _client(self):
        from agentscope.app._router._business import get_partner_principal

        app = FastAPI()
        for router in self.assembly.routers:
            app.include_router(router)
        app.dependency_overrides[get_partner_principal] = lambda: PartnerPrincipal(
            key_id="key-1", client_id="partner-1", tenant_id="tenant-1", domain_id="domain-1",
        )
        return AsyncClient(transport=ASGITransport(app=app), base_url="https://platform.test")

    @staticmethod
    def _start(request_id="vh-cmd-1", text_value=HANDOVER):
        return PartnerRequestEnvelope(
            schema_version="1",
            command_type="start_workflow",
            external_request_id=request_id,
            external_management_ref="local-management",
            external_user_id="resident-1",
            external_ticket_id="T-77",
            external_conversation_id="chat-9:T-77",
            message={"type": "text", "text": text_value},
        ).model_dump(mode="json")

    async def _run(self) -> str:
        """One worker step; a failed job shows its stored error."""
        outcome = await self.worker.run_once()
        if outcome.status not in ("succeeded", "idle"):
            async with self.engine.connect() as connection:
                errors = (await connection.execute(text("SELECT error FROM wf_durable_jobs"))).all()
            raise AssertionError(f"{outcome.status}: {errors}")
        return outcome.status

    async def _history(self, client, conversation_id):
        page = await client.get(
            f"/workforce/v1/partner/conversations/{conversation_id}/event-history",
            params={"external_user_id": "resident-1", "limit": 200},
        )
        return page.json()["items"]

    @staticmethod
    def _acceptance(ticket="T-77", job="WO-1"):
        return {"external_ticket_id": ticket, "external_user_id": "resident-1",
                "ticket_status": "closed", "ticket_version": 3, "approval_id": "domain-approval-1",
                "decided_event_id": "domain-event-1", "work_order_ids": [job]}

    async def _completed_work(self, workflow_id, *, job="WO-1", terminal=True, outcome="completed", status="result_published"):
        async with self.uows() as uow:
            await uow.execute(insert(operations).values(
                operation_id="op-" + workflow_id, workflow_id=workflow_id, integration_id="pi-1",
                tool_name="vh_work_order_dispatch", client_reference="cr_" + workflow_id,
                external_job_id=job, status=status, rank=90, terminal=terminal, outcome=outcome,
                created_at=NOW, updated_at=NOW,
            ))
            await uow.commit()


class UnifiedCaseCloseBarrierTest(_CaseHarness):
    async def _ready(self, client):
        async def confirmation(tools):
            await call(tools, "CaseSay", text="Please confirm completion.", expects="confirmation")

        self.leader.scripts = [confirmation]
        started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
        self.assertEqual("succeeded", await self._run())
        items = await self._history(client, started["conversation_id"])
        revision = [i["payload"]["revision"] for i in items if i["event_type"] == "workflow.status_changed"][-1]
        self.close_body = {
            "schema_version": "1", "external_request_id": "close-1", "external_user_id": "resident-1",
            "external_ticket_id": "T-77", "external_conversation_id": "chat-9:T-77",
            "expected_revision": revision, "reason": "resident_confirmed",
            "domain_acceptance": self._acceptance(),
        }
        return started

    async def _close(self, client, started, **changes):
        return await client.post(f"/workforce/v1/partner/workflows/{started['workflow_id']}/close",
                                 json={**self.close_body, **changes})

    async def test_confirmation_text_and_domain_assertion_cannot_replace_terminal_work(self):
        async with self._client() as client:
            started = await self._ready(client)
            response = await self._close(client, started)
            self.assertEqual((409, "WORKFLOW_NOT_READY_TO_CLOSE"),
                             (response.status_code, response.json()["error"]["code"]))
            await self._completed_work(started["workflow_id"], outcome="cancelled", status="cancelled")
            response = await self._close(client, started)
            self.assertEqual(409, response.status_code)

    async def test_actual_pending_and_unknown_work_block_even_when_checkpoint_has_no_refs(self):
        async with self._client() as client:
            started = await self._ready(client)
            await self._completed_work(started["workflow_id"], terminal=False)
            for status in ("pending", "dispatching", "unknown"):
                with self.subTest(status=status):
                    async with self.uows() as uow:
                        await uow.execute(update(operations).values(status=status, terminal=False))
                        await uow.commit()
                    response = await self._close(client, started)
                    self.assertEqual((409, "WORKFLOW_NOT_READY_TO_CLOSE"),
                                     (response.status_code, response.json()["error"]["code"]))

    async def test_actual_pending_approval_blocks_despite_empty_checkpoint(self):
        async with self._client() as client:
            started = await self._ready(client)
            await self._completed_work(started["workflow_id"])
            async with self.uows() as uow:
                await uow.execute(insert(approvals).values(
                    approval_id="pending-approval", workflow_id=started["workflow_id"],
                    session_id="member-session", agent_id="member", tool_call_id="call-1", tool_name="write",
                    arguments={}, arguments_hash="sha256:a", expected_revision=1, summary={}, status="pending",
                    expires_at=NOW, created_at=NOW, decided_at=None,
                ))
                await uow.commit()
            response = await self._close(client, started)
            self.assertEqual((409, "APPROVAL_PENDING"), (response.status_code, response.json()["error"]["code"]))

    async def test_domain_acceptance_is_required_and_bound_to_customer_ticket_and_work(self):
        async with self._client() as client:
            started = await self._ready(client)
            await self._completed_work(started["workflow_id"])
            for acceptance in (None, {**self._acceptance(), "external_ticket_id": "another-ticket"},
                               {**self._acceptance(), "external_user_id": "another-resident"},
                               {**self._acceptance(), "work_order_ids": ["another-job"]}):
                with self.subTest(acceptance=acceptance):
                    response = await self._close(client, started, domain_acceptance=acceptance)
                    self.assertEqual(409, response.status_code)
            response = await self._close(client, started, reason="model_says_done")
            self.assertEqual(409, response.status_code)

    async def test_successful_close_preserves_revision_audience_and_replay(self):
        async with self._client() as client:
            started = await self._ready(client)
            await self._completed_work(started["workflow_id"])
            stale = await self._close(client, started, expected_revision=1)
            self.assertEqual((409, "REVISION_CONFLICT"), (stale.status_code, stale.json()["error"]["code"]))
            wrong = await self._close(client, started, external_user_id="another-resident")
            self.assertIn(wrong.status_code, (403, 404))
            closed = await self._close(client, started)
            self.assertEqual(200, closed.status_code, closed.text)
            self.assertEqual("closed", closed.json()["workflow_state"])
            replay = await self._close(client, started)
            self.assertEqual(closed.json(), replay.json())
            items = await self._history(client, started["conversation_id"])
            endings = [i for i in items if i["event_type"] == "workflow.closed"]
            self.assertEqual(1, len(endings))
            self.assertFalse(endings[0]["payload"]["stop_tracking_only"])

    async def test_stop_tracking_is_distinct_and_closed_cases_cannot_start_more_work(self):
        async with self._client() as client:
            started = await self._ready(client)
            await self._completed_work(started["workflow_id"], terminal=False, status="unknown")
            spoof = await self._close(client, started, stop_tracking_only=True)
            self.assertEqual(409, spoof.status_code)
            closed = await self._close(client, started, reason="resident_requested_stop_tracking",
                                       stop_tracking_only=True, domain_acceptance=None)
            self.assertEqual(200, closed.status_code, closed.text)
            items = await self._history(client, started["conversation_id"])
            ending = next(i for i in items if i["event_type"] == "workflow.closed")
            self.assertTrue(ending["payload"]["stop_tracking_only"])
            with self.assertRaisesRegex(ValueError, "closed workflows"):
                await self.runner._case.store.record_operation({
                    "workflow_id": started["workflow_id"], "client_reference": "late-operation",
                })


class UnifiedPartnerCaseTest(_CaseHarness):
    async def test_claim_rejection_keeps_supported_lines_for_both_delivery_tools(self):
        valid = "Hotel Alpha costs 100 USD."
        invalid = "Hotel Beta costs 100 USD."
        corrected = valid + "\nHotel Beta costs 200 USD."

        async def first_turn(tools):
            case = tools["CaseSay"]._case
            labels = []
            for hotel, price in (("Hotel Alpha", 100), ("Hotel Beta", 200)):
                seq = await case.store.append(
                    case.workflow_id,
                    "evidence",
                    json.dumps({"hotel": hotel, "price": price, "currency": "USD"}),
                )
                labels.append(f"E{seq}")
            for name, key in (("CaseSay", "text"), ("CaseFinalize", "answer")):
                rejected = await tools[name].call(**{key: valid + "\n" + invalid, "cites": labels})
                self.assertEqual(ToolResultState.ERROR, rejected.state)
                validation = rejected.metadata["evidence_validation"]
                self.assertIn(valid, validation["supported_text"])
                self.assertNotIn(invalid, validation["supported_text"])
                self.assertIn(invalid, validation["rejected_texts"])
                self.assertIn(valid, rejected.content[0].text)
                self.assertEqual([], await case.store.entries(case.workflow_id, kind="say"))
            accepted = await tools["CaseSay"].call(text=corrected, cites=labels)
            self.assertEqual(ToolResultState.SUCCESS, accepted.state)
            [said] = await case.store.entries(case.workflow_id, kind="say")
            self.assertEqual(corrected, said["text"])

        self.leader.scripts = [first_turn]
        async with self._client() as client:
            self.assertEqual(202, (await client.post("/workforce/v1/partner/requests", json=self._start())).status_code)
            self.assertEqual("succeeded", await self._run())
        self.assertEqual([], self.mcp_calls)

    async def test_an_agent_a_partner_route_uses_cannot_be_removed(self):
        [guard] = self.runner._app.state.agent_delete_guards
        async with self.uows() as uow:
            await uow.execute(update(routes).where(routes.c.route_id == "route-1").values(
                config={"rules": RULES, "member_agents": {"member-kt": {"name": "KyThuat", "tools": []}}},
            ))
            await uow.commit()
        self.assertTrue(await guard("manager-1", "leader-vh"))
        self.assertTrue(await guard("manager-1", "member-kt"))
        self.assertIsNone(await guard("manager-1", "agent-other"))
        self.assertIsNone(await guard("manager-2", "leader-vh"))

    async def test_silent_chat_failure_is_not_a_successful_customer_turn(self):
        async def failed_before_reply(_tools):
            return None
        self.leader.scripts = [failed_before_reply]
        async with self._client() as client:
            started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
            await self._run()
            result = (await client.get(f"/workforce/v1/partner/requests/{started['request_id']}",
                params={"external_user_id": "resident-1"})).json()
        self.assertEqual("needs_attention", result["workflow_state"])
        self.assertEqual("fallback", result["result"]["data"]["outcome"])
        self.assertEqual(RULES["safe_reply"], result["result"]["messages"][0]["text"])
        [why] = await self.runner._case.store.entries(started["workflow_id"], kind="attention")
        self.assertEqual("Leader không gửi tin nào cho người dùng trong lượt này.", why["text"])

    async def test_a_ticket_stopped_by_an_empty_model_account_says_so(self):
        async def out_of_credit(tools):
            self.storage.messages.append(SimpleNamespace(id=self.leader.messages[-1].id, usage=None, error=None))
            self.storage.messages.append(SimpleNamespace(id="reply-q", usage=None, error=SimpleNamespace(type="quota")))

        self.leader.scripts = [out_of_credit]
        async with self._client() as client:
            started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
            self.assertEqual("succeeded", await self._run())  # not retried: more tries do not add credit
            result = (await client.get(f"/workforce/v1/partner/requests/{started['request_id']}",
                                       params={"external_user_id": "resident-1"})).json()
        self.assertEqual("needs_attention", result["workflow_state"])
        [why] = await self.runner._case.store.entries(started["workflow_id"], kind="attention")
        self.assertIn("hết tiền", why["text"])

    async def test_early_progress_is_not_orphaned_or_rolled_back_by_dispatch_response(self):
        self.early_progress = True
        async def dispatch(tools):
            await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Test early progress")
            await call(tools, "CaseSay", text="Yêu cầu đang được xử lý.", expects="none")
        self.leader.scripts = [dispatch]
        async with self._client() as client:
            self.assertEqual(202, (await client.post("/workforce/v1/partner/requests", json=self._start())).status_code)
            self.assertEqual("succeeded", await self._run())
        reference = next(args["client_reference"] for name, args in self.mcp_calls if name == "vh_work_order_dispatch")
        async with self.uows() as uow:
            operation = (await uow.execute(select(operations).where(operations.c.client_reference == reference))).mappings().one()
        self.assertEqual(("arrived", 40, "WO-1"), (operation["status"], operation["rank"], operation["external_job_id"]))

    async def test_a_turn_adds_its_tokens_to_the_workflow_budget(self):
        from agentscope.message import Usage

        async def first_turn(tools):
            self.storage.messages.append(SimpleNamespace(id="m-1", usage=Usage(input_tokens=1200, output_tokens=80)))
            await call(tools, "CaseSay", text="Yêu cầu đã được tiếp nhận.", expects="none")

        self.storage.messages.append(SimpleNamespace(id="m-old", usage=Usage(input_tokens=999, output_tokens=9)))
        self.leader.scripts = [first_turn]
        async with self._client() as client:
            started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
            self.assertEqual("succeeded", await self._run())
        async with self.uows() as uow:
            payload = (await uow.execute(
                select(workflow_checkpoints.c.payload)
                .where(workflow_checkpoints.c.workflow_id == started["workflow_id"])
                .order_by(workflow_checkpoints.c.state_revision.desc()),
            )).scalars().first()
        budget = payload["used_budget"]
        self.assertEqual((1200, 80), (budget["input_tokens"], budget["output_tokens"]))

    async def test_the_room_teaches_its_agents_only_when_the_user_confirms(self):
        scheduled = []

        async def summary(tools):
            for session in self.storage.sessions.values():
                session.team_id = "team-9"  # the leader opened a room earlier
            await call(tools, "CaseSay", text="Nhân viên đã báo xong, bạn xác nhận giúp tôi.", expects="confirmation")

        scored = []

        async def record_ticket_outcome(user_id, team_id, success):
            scored.append((team_id, success))
            return []

        self.leader.schedule_learning = lambda user_id, session, team_id: scheduled.append(team_id)
        self.leader.record_ticket_outcome = record_ticket_outcome
        self.leader.scripts = [summary, summary]
        async with self._client() as client:
            for request_id, ticket, reason in (("vh-cmd-1", "T-77", "resident_cancelled"), ("vh-cmd-2", "T-78", "resident_confirmed")):
                start = self._start(request_id=request_id)
                start.update(external_ticket_id=ticket, external_conversation_id=f"chat-9:{ticket}")
                started = (await client.post("/workforce/v1/partner/requests", json=start)).json()
                self.assertEqual("succeeded", await self._run())
                # Asking for confirmation teaches nothing yet.
                self.assertEqual([], scheduled)
                items = await self._history(client, started["conversation_id"])
                revision = [i["payload"]["revision"] for i in items if i["event_type"] == "workflow.status_changed"][-1]
                extra = {"stop_tracking_only": True}
                if reason == "resident_confirmed":
                    await self._completed_work(started["workflow_id"])
                    extra = {"domain_acceptance": self._acceptance(ticket)}
                else:
                    reason = "resident_requested_stop_tracking"
                closed = await client.post(f"/workforce/v1/partner/workflows/{started['workflow_id']}/close", json={
                    "schema_version": "1", "external_request_id": f"close-{ticket}", "external_user_id": "resident-1",
                    "external_ticket_id": ticket, "external_conversation_id": f"chat-9:{ticket}",
                    "expected_revision": revision, "reason": reason,
                    **extra,
                })
                self.assertEqual("closed", closed.json()["workflow_state"], closed.text)
        # Cancelled: nothing learned; confirmed: the room teaches its agents, and
        # the memories it recalled count as helpful (confirmed at the first ask).
        self.assertEqual(["team-9"], scheduled)
        self.assertEqual([("team-9", True)], scored)

    async def test_quality_counts_outcomes_refusals_and_cost(self):
        from agentscope.app.workforce.integrations.unified._quality import ticket_quality

        async def summary(tools):
            for session in self.storage.sessions.values():
                session.team_id = "team-1"
            await call(tools, "CaseSay", text="Việc này được miễn phí.", expects="none")  # refused
            await call(tools, "CaseSay", text="Đã xong, bạn xác nhận giúp tôi.", expects="confirmation")

        self.leader.scripts = [summary]
        async with self._client() as client:
            started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
            self.assertEqual("succeeded", await self._run())
            items = await self._history(client, started["conversation_id"])
            revision = [i["payload"]["revision"] for i in items if i["event_type"] == "workflow.status_changed"][-1]
            await self._completed_work(started["workflow_id"])
            closed = await client.post(f"/workforce/v1/partner/workflows/{started['workflow_id']}/close", json={
                "schema_version": "1", "external_request_id": "close-1", "external_user_id": "resident-1",
                "external_ticket_id": "T-77", "external_conversation_id": "chat-9:T-77",
                "expected_revision": revision, "reason": "resident_confirmed",
                "domain_acceptance": self._acceptance(),
            })
            self.assertEqual("closed", closed.json()["workflow_state"], closed.text)
        usage = {
            "leader": SimpleNamespace(model="gpt-5.5", input_tokens=10_000, cached_input_tokens=8_000, output_tokens=500),
            "member": SimpleNamespace(model="gpt-5.4-mini", input_tokens=4_000, cached_input_tokens=0, output_tokens=200),
        }

        async def room(*_args):
            return SimpleNamespace(state=SimpleNamespace(metrics=SimpleNamespace(provider_usage=usage)))

        self.storage.model_calls = [
            {"id": "call-1", "workflow_id": started["workflow_id"], "purpose": "runtime", "model": "gpt-5.5",
             "status": "completed", "input_tokens": 10000, "cached_input_tokens": 8000, "output_tokens": 500,
             "usage_complete": True, "cost_complete": False, "cost_usd": None},
            {"id": "call-2", "workflow_id": started["workflow_id"], "purpose": "learning", "model": "gpt-5.4-mini",
             "status": "completed", "input_tokens": 4000, "cached_input_tokens": 0, "output_tokens": 200,
             "usage_complete": True, "cost_complete": False, "cost_usd": None},
        ]
        quality = await ticket_quality(self.uows, self.storage, SimpleNamespace(get_team_shared_context=room), "manager-1")
        self.assertEqual(
            (1, 1, 1, 1, 1, 0.5),
            (quality["tickets"], quality["closed_confirmed"], quality["first_time_confirmed"],
             quality["messages_sent"], quality["messages_refused"], quality["refusal_rate"]),
        )
        self.assertIsNone(quality["est_cost_usd"])
        self.assertIsNone(quality["cost_per_confirmed_usd"])
        self.assertFalse(quality["cost_complete"])
        self.assertEqual(14000, quality["input_tokens"])
        self.assertEqual(round(8_000 / 14_000, 3), quality["cache_rate"])

    async def test_a_transient_model_error_retries_the_turn_without_resending_the_input(self):
        async def provider_down(tools):
            # The chat runtime stored the input, then the reply ended on a 429.
            self.storage.messages.append(SimpleNamespace(id=self.leader.messages[-1].id, usage=None, error=None))
            self.storage.messages.append(
                SimpleNamespace(id="reply-err", usage=None, error=SimpleNamespace(type="rate_limit")),
            )

        async def answers(tools):
            await call(tools, "CaseSay", text="Yêu cầu đã được tiếp nhận.", expects="none")

        self.leader.scripts = [provider_down, answers]
        async with self._client() as client:
            started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
            self.assertEqual("retry_scheduled", (await self.worker.run_once()).status)
            self.assertEqual("succeeded", await self._run())
            result = (await client.get(f"/workforce/v1/partner/requests/{started['request_id']}",
                                       params={"external_user_id": "resident-1"})).json()
        first, retry = self.leader.messages
        self.assertTrue(first.id.endswith(":input"))
        self.assertTrue(retry.id.endswith(":retry1"))
        self.assertIn("Lượt trước bị lỗi model", retry.get_text_content())
        self.assertEqual(["Yêu cầu đã được tiếp nhận."], [m["text"] for m in result["result"]["messages"]])

    async def test_the_end_users_photos_reach_the_leader_once(self):
        from contextlib import asynccontextmanager

        from agentscope.app.workforce.assets._tables import assets
        from agentscope.message import DataBlock

        class Blobs:
            @asynccontextmanager
            async def open(self, uri):
                yield SimpleNamespace(read=lambda: _bytes())

        async def _bytes():
            return b"\x89PNG fake"

        self.runner.attach_images(Blobs())

        async def say(tools):
            await call(tools, "CaseSay", text="Tôi đã xem ảnh của anh/chị.", expects="none")

        self.leader.scripts = [say, say]
        async with self._client() as client:
            started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
            async with self.uows() as uow:
                for asset_id, kind in (("as-photo", "image/png"), ("as-pdf", "application/pdf")):
                    await uow.execute(insert(assets).values(
                        id=asset_id, tenant_id="tenant-1", domain_id="domain-1", area_id="area-1",
                        manager_account_id="manager-1", origin="customer", status="active", partner_client_id="partner-1",
                        external_user_id="resident-1", external_ticket_id="T-77", external_conversation_id="chat-9:T-77",
                        workflow_id=started["workflow_id"], object_uri=f"s3://b/{asset_id}", filename=f"{asset_id}.bin",
                        content_type=kind, expected_size=10, actual_size=10, upload_expires_at=NOW, created_at=NOW,
                        updated_at=NOW,
                    ))
                await uow.commit()
            self.assertEqual("succeeded", await self._run())
            reply = self._start(request_id="vh-cmd-2", text_value="Anh xem ảnh giúp")
            reply.update(command_type="workflow_reply", workflow_id=started["workflow_id"])
            await client.post("/workforce/v1/partner/requests", json=reply)
            self.assertEqual("succeeded", await self._run())
        first, second = self.leader.messages
        images = [block for block in first.content if isinstance(block, DataBlock)]
        self.assertEqual(1, len(images))  # the PDF is not an image
        self.assertEqual("image/png", images[0].source.media_type)
        self.assertIn("gửi kèm 1 ảnh", first.get_text_content())
        self.assertFalse([block for block in second.content if isinstance(block, DataBlock)])

    async def test_staff_progress_reaches_the_room_of_the_ticket(self):
        async def first_turn(tools):
            await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Sửa rò nước")
            await call(tools, "CaseSay", text="Yêu cầu đã được gửi cho nhân viên.", expects="none")

        self.leader.scripts = [first_turn]
        shared = []

        class Shared:
            def __init__(self, *_args):
                pass

            async def append_event(self, **event):
                shared.append(event)

        async def in_room(*_args):
            return SimpleNamespace(team_id="team-1")

        async with self._client() as client:
            await client.post("/workforce/v1/partner/requests", json=self._start())
            self.assertEqual("succeeded", await self._run())
            reference = next(args for name, args in self.mcp_calls if name == "vh_work_order_dispatch")["client_reference"]
            raw, headers = signed({
                "schema_version": "1", "external_event_id": "ev-room", "external_job_id": "WO-1",
                "client_reference": reference, "event_type": "job.accepted", "provider_version": 2,
                "occurred_at": "2026-10-20T02:00:00.000000Z", "data": {"staff_name": "Bình", "eta": "09:30 20/10/2026"},
            })
            self.runner._app.state.shared_context_storage = object()
            with patch("agentscope.app._shared_context.SharedContextService", Shared), \
                    patch.object(self.storage, "get_session", in_room):
                accepted = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
        self.assertEqual("applied", accepted.json()["ingestion_status"])
        [event] = shared
        self.assertEqual(("team-1", "external_event"), (event["team_id"], event["kind"]))
        self.assertIn("job.accepted", event["content"])
        self.assertIn("Bình", event["content"])

    async def test_the_message_sent_is_the_rooms_reply(self):
        shared = []

        class Shared:
            def __init__(self, *_args):
                pass

            async def append_event(self, **event):
                shared.append(event)

        async def say(tools):
            for session in self.storage.sessions.values():
                session.team_id = "team-1"
            await call(tools, "CaseSay", text="Thợ đã nhận việc, bạn chờ thông báo tiếp nhé.", expects="none")

        async def no_context(*_args):
            return None

        self.leader.scripts = [say]
        self.runner._app.state.shared_context_storage = SimpleNamespace(get_team_shared_context=no_context)
        with patch("agentscope.app._shared_context.SharedContextService", Shared):
            async with self._client() as client:
                await client.post("/workforce/v1/partner/requests", json=self._start())
                self.assertEqual("succeeded", await self._run())
        [event] = shared
        self.assertEqual(
            ("customer_reply", "Thợ đã nhận việc, bạn chờ thông báo tiếp nhé."),
            (event["kind"], event["content"]),
        )
        self.assertIsNone(event["delta"])

    async def test_dispatch_progress_events_result_and_close_like_the_vinhomes_bridge(self):
        async def first_turn(tools):
            self.assertNotIn("client_reference", tools["vh_work_order_dispatch"].input_schema["properties"])
            self.assertEqual("Create the work and offer it to staff.", tools["vh_work_order_dispatch"].description)
            ticket = await call(tools, "vh_ticket_get", ticket_id="T-77")
            self.assertTrue(ticket.startswith("E1: "))
            dispatched = await call(tools, "vh_work_order_dispatch", ticket_id="T-77", description="Sửa rò nước bồn rửa")
            label = dispatched.split(":")[0]
            refused = await call(
                tools,
                "CaseSay",
                text="Thợ sẽ đến trong 30 phút.",
                expects="none",
                cites=[label],
            )
            self.assertIn("bị từ chối", refused)
            said = await call(
                tools,
                "CaseSay",
                text="Chào anh/chị An, tôi là trợ lý điều phối. Yêu cầu đã được gửi cho nhân viên và đang chờ người nhận.",
                expects="none",
                cites=[label],
            )
            self.assertIn("Đã gửi", said)
            again = await call(tools, "CaseSay", text="Nhắc lại lần nữa.", expects="none")
            self.assertIn("đã gửi một tin", again)

        async def woken(tools):
            self.assertIn("job.result_published", self.leader.inputs[-1])
            await call(
                tools,
                "CaseSay",
                text="Nhân viên đã gửi kết quả nghiệm thu phía trên. Anh/chị xem rồi xác nhận hoàn thành giúp tôi.",
                expects="confirmation",
            )

        self.leader.scripts = [first_turn, woken]
        async with self._client() as client:
            started = await client.post("/workforce/v1/partner/requests", json=self._start())
            self.assertEqual(202, started.status_code, started.text)
            first = started.json()
            self.assertEqual("succeeded", await self._run())
            result = (
                await client.get(
                    f"/workforce/v1/partner/requests/{first['request_id']}",
                    params={"external_user_id": "resident-1"},
                )
            ).json()
            self.assertEqual("awaiting_user", result["workflow_state"])
            # The ticket is a session of the console Leader: the Leader page lists it.
            [ticket] = self.storage.sessions.values()
            self.assertEqual(("leader-console", "Rò nước bồn rửa · S1-1205"), (ticket.agent_id, ticket.config.name))
            self.assertEqual(1, len(result["result"]["messages"]))
            self.assertIn("đang chờ người nhận", result["result"]["messages"][0]["text"])

            # The platform filled the hidden client_reference and tracks the job.
            dispatch_args = next(args for name, args in self.mcp_calls if name == "vh_work_order_dispatch")
            reference = dispatch_args["client_reference"]
            async with self.uows() as uow:
                operation = (
                    await uow.execute(select(operations).where(operations.c.client_reference == reference))
                ).mappings().one()
            self.assertEqual("WO-1", operation["external_job_id"])
            context = await self.runner._case.store.grant_context(first["workflow_id"])
            self.assertEqual({"ticket_id": "T-77", "external_request_id": "vh-cmd-1"}, context)

            def event(event_id, event_type, data, version):
                return {
                    "schema_version": "1",
                    "external_event_id": event_id,
                    "external_job_id": "WO-1",
                    "client_reference": reference,
                    "event_type": event_type,
                    "provider_version": version,
                    "occurred_at": "2026-10-20T02:00:00.000000Z",
                    "data": data,
                }

            accepted_body = event("ev-1", "job.accepted", {"staff_name": "Bình", "eta": "09:30 20/10/2026"}, 2)
            raw, headers = signed(accepted_body)
            accepted = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
            self.assertEqual(202, accepted.status_code, accepted.text)
            self.assertEqual("applied", accepted.json()["ingestion_status"])
            raw, headers = signed(accepted_body)
            again = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
            self.assertTrue(again.json()["duplicate"])
            raw, headers = signed({**accepted_body, "data": {"staff_name": "Khác", "eta": "10:00"}})
            conflict = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
            self.assertEqual("EVENT_ID_CONFLICT", conflict.json()["error"]["code"])
            raw, headers = signed(event("ev-0", "job.offered", {}, 1))
            stale = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
            receipt = await client.get(
                stale.json()["status_url"],
                headers={"Authorization": "ApiKey provider-key"},
            )
            self.assertEqual("rejected", receipt.json()["ingestion_status"])
            self.assertEqual("STALE_EVENT", receipt.json()["error"]["code"])
            raw, headers = signed(event("ev-2", "job.en_route", {}, 3))
            invalid = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
            self.assertEqual("EVENT_DATA_INVALID", invalid.json()["error"]["code"])
            raw, headers = signed(event("ev-3", "job.en_route", {"staff_name": "Bình"}, 3))
            bad = dict(headers, **{"X-Partner-Signature": "v1=" + "0" * 64})
            refused = await client.post("/workforce/v1/provider/job-events", content=raw, headers=bad)
            self.assertEqual(401, refused.status_code)

            items = await self._history(client, first["conversation_id"])
            texts = [item["payload"].get("text") for item in items if item["event_type"] == "assistant.message"]
            self.assertIn("Nhân viên Bình đã nhận yêu cầu của bạn, dự kiến đến lúc 09:30 20/10/2026.", texts)
            # A template event does not wake the leader.
            self.assertEqual("idle", await self._run())

            raw, headers = signed(
                event(
                    "ev-9",
                    "job.result_published",
                    {"summary": "Đã thay ống xả", "photo_count": 2, "reported_by": "Bình"},
                    9,
                ),
            )
            published = await client.post("/workforce/v1/provider/job-events", content=raw, headers=headers)
            self.assertEqual("applied", published.json()["ingestion_status"])
            self.assertEqual("succeeded", await self._run())
            items = await self._history(client, first["conversation_id"])
            states = [item["payload"]["state"] for item in items if item["event_type"] == "workflow.status_changed"]
            self.assertEqual("awaiting_confirmation", states[-1])
            revision = [item["payload"]["revision"] for item in items if item["event_type"] == "workflow.status_changed"][-1]

            closed = await client.post(
                f"/workforce/v1/partner/workflows/{first['workflow_id']}/close",
                json={
                    "schema_version": "1",
                    "external_request_id": "vh-close-1",
                    "external_user_id": "resident-1",
                    "external_ticket_id": "T-77",
                    "external_conversation_id": "chat-9:T-77",
                    "expected_revision": revision,
                    "reason": "resident_confirmed",
                    "domain_acceptance": self._acceptance(),
                },
            )
            self.assertEqual(200, closed.status_code, closed.text)
            self.assertEqual("closed", closed.json()["workflow_state"])

    async def test_a_turn_whose_every_say_is_refused_sends_the_safe_reply(self):
        async def stubborn(tools):
            await call(tools, "CaseSay", text="Việc này được miễn phí.", expects="none")

        self.leader.scripts = [stubborn]
        async with self._client() as client:
            started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
            await self._run()
            result = (
                await client.get(
                    f"/workforce/v1/partner/requests/{started['request_id']}",
                    params={"external_user_id": "resident-1"},
                )
            ).json()
        self.assertEqual([RULES["safe_reply"]], [m["text"] for m in result["result"]["messages"]])
        self.assertEqual("needs_attention", result["workflow_state"])


class UnifiedPartnerApprovalTest(_CaseHarness):
    """D1: a tool that needs consent is decided by the end user via the partner."""

    async def test_approval_required_decision_and_resume(self):
        from agentscope.app._chat_consent import PendingChatAction
        from agentscope.event import UserConfirmResultEvent
        from agentscope.message import ToolCallBlock

        parked = [
            PendingChatAction(
                agent_id="leader-vh",
                session_id="s-coordinator",
                reply_id="reply-1",
                tool_call=ToolCallBlock(id="call-1", name="vh_amenity_book", input='{"ticket_id": "T-77"}'),
            ),
        ]

        async def pending(storage, user_id, agent_id, session_id):
            return parked

        async def asks(tools):
            return None  # the model's tool call parked; nothing said yet

        async def resumed(tools):
            decision = self.leader.last_input
            self.assertIsInstance(decision, UserConfirmResultEvent)
            self.assertTrue(decision.confirm_results[0].confirmed)
            self.assertEqual("call-1", decision.confirm_results[0].tool_call.id)
            parked.clear()
            await call(tools, "CaseSay", text="Đã gửi thẻ đặt chỗ, anh/chị bấm xác nhận giúp tôi.", expects="none")

        original_run = self.leader.run

        async def run(user_id, session_id, agent_id, input_msg):
            self.leader.last_input = input_msg
            await original_run(user_id, session_id, agent_id, input_msg)

        self.leader.run = run
        self.leader.scripts = [asks, resumed]
        with patch.object(runner_module, "pending_chat_actions", pending):
            async with self._client() as client:
                started = (await client.post("/workforce/v1/partner/requests", json=self._start())).json()
                self.assertEqual("succeeded", await self._run())
                items = await self._history(client, started["conversation_id"])
                required = next(item for item in items if item["event_type"] == "approval.required")["payload"]
                state = [i["payload"]["state"] for i in items if i["event_type"] == "workflow.status_changed"][-1]
                self.assertEqual("awaiting_approval", state)
                # A partner that lost its cursor gets from the snapshot what its decision must carry.
                snapshot_url = f"/workforce/v1/partner/conversations/{started['conversation_id']}"
                snapshot = await client.get(snapshot_url, params={"external_user_id": "resident-1"})
                self.assertEqual(200, snapshot.status_code, snapshot.text)
                self.assertEqual(
                    [{**required, "workflow_id": started["workflow_id"], "status": "pending"}],
                    snapshot.json()["pending_approvals"],
                )
                body = {
                    "schema_version": "1",
                    "external_request_id": "vh-decision-1",
                    "external_user_id": "resident-1",
                    "external_ticket_id": "T-77",
                    "external_conversation_id": "chat-9:T-77",
                    "workflow_id": started["workflow_id"],
                    "decision": "approve",
                    "expected_revision": required["expected_revision"],
                    "arguments_hash": "sha256:wrong",
                }
                url = f"/workforce/v1/partner/approvals/{required['approval_id']}/decision"
                mismatch = await client.post(url, json=body)
                self.assertEqual("APPROVAL_MISMATCH", mismatch.json()["error"]["code"])
                body["arguments_hash"] = required["arguments_hash"]
                decided = await client.post(url, json=body)
                self.assertEqual(202, decided.status_code, decided.text)
                self.assertEqual("approved", decided.json()["status"])
                again = await client.post(url, json=body)
                self.assertEqual(202, again.status_code)
                self.assertEqual("succeeded", await self._run())
                items = await self._history(client, started["conversation_id"])
                snapshot = await client.get(snapshot_url, params={"external_user_id": "resident-1"})
                self.assertEqual([], snapshot.json()["pending_approvals"])
        kinds = [item["event_type"] for item in items]
        self.assertIn("approval.resolved", kinds)
        texts = [i["payload"].get("text") for i in items if i["event_type"] == "assistant.message"]
        self.assertIn("Đã gửi thẻ đặt chỗ, anh/chị bấm xác nhận giúp tôi.", texts)
        state = [i["payload"]["state"] for i in items if i["event_type"] == "workflow.status_changed"][-1]
        self.assertEqual("awaiting_user", state)


def _unsaid_case(said: bool = False, route: dict | None = None):
    async def answer():
        return said

    return SimpleNamespace(rules={}, said=answer, route=route or {}, trigger_id=AsyncMock(return_value="active-turn"))


class PartnerToolsOnlyTest(unittest.IsolatedAsyncioTestCase):
    async def test_after_the_turns_message_the_turn_ends_without_a_model_call(self):
        from agentscope.app.workforce.integrations.unified._case import PartnerCaseMiddleware
        from agentscope.model import ChatResponse

        middleware = PartnerCaseMiddleware(_unsaid_case(said=True), [SimpleNamespace(name="vh_ticket_get")])
        seen = {}

        async def next_handler(**kwargs):
            seen.update(kwargs)

        offered = [{"type": "function", "function": {"name": n}} for n in ("CaseSay", "CaseFinalize", "vh_ticket_get")]
        response = await middleware.on_model_call(None, {"tools": offered}, next_handler)
        self.assertEqual({}, seen)  # the model was not called
        self.assertIsInstance(response, ChatResponse)
        self.assertTrue(response.is_last)
        self.assertEqual(["text"], [block.type for block in response.content])

    async def test_the_case_middleware_offers_only_case_and_given_tools(self):
        from agentscope.app.workforce.integrations.unified._case import PartnerCaseMiddleware

        middleware = PartnerCaseMiddleware(
            _unsaid_case(),
            [SimpleNamespace(name="vh_ticket_get")],
        )
        seen = {}

        async def next_handler(**kwargs):
            seen.update(kwargs)
            return "response"

        offered = [
            {"type": "function", "function": {"name": name}}
            for name in ("TeamCreate", "TeamSay", "AgentInvite", "CaseSay", "CaseFinalize", "vh_ticket_get")
        ]
        answer = await middleware.on_model_call(None, {"tools": offered}, next_handler)
        self.assertEqual("response", answer)
        self.assertEqual(
            ["CaseSay", "CaseFinalize", "vh_ticket_get"],
            [tool["function"]["name"] for tool in seen["tools"]],
        )

    async def test_the_leader_opens_a_room_with_the_routes_agents_only(self):
        import copy

        from agentscope.app._tool._agent_invite import _AgentInviteParams, _display_name
        from agentscope.app.workforce.integrations.unified._case import PartnerCaseMiddleware, _members

        route = {"config": {
            "member_agents": {
                "a-dp": COORDINATOR,
                "a-kt": {"name": "KyThuatVinhomes", "tools": ["vh_ticket_get"]},
            },
            "leader_brief": "Gọi cư dân là bạn.",
        }}
        members = _members(route)
        names = [_display_name("DieuPhoiVinhomes", "a-dp"), _display_name("KyThuatVinhomes", "a-kt"),
                 _display_name("Travel", "a-x")]
        self.assertEqual(names[:2], list(members))
        # The toolkit's AgentInvite lists every invitable agent of the manager.
        parameters = copy.deepcopy(_AgentInviteParams.model_json_schema())
        parameters["properties"]["target"]["enum"] = list(names)
        extra = parameters["$defs"]["_AdditionalAssignment"]["properties"]
        extra["target"]["enum"] = list(names)
        invite = {
            "type": "function",
            "function": {
                "name": "AgentInvite",
                "description": "Invite.\n" + "\n".join(f"- ``{name!r}`` — x; tools=" for name in names),
                "parameters": parameters,
            },
        }
        # The Leader holds no partner tool.
        middleware = PartnerCaseMiddleware(_unsaid_case(route=route), [], members)
        seen = {}

        async def next_handler(**kwargs):
            seen.update(kwargs)

        offered = [
            {"type": "function", "function": {"name": name}}
            for name in ("TeamCreate", "TeamSay", "TeamDelete", "CaseSay", "vh_ticket_get", "Bash")
        ] + [invite]
        await middleware.on_model_call(None, {"tools": offered}, next_handler)
        kept = {tool["function"]["name"]: tool for tool in seen["tools"]}
        self.assertEqual({"TeamSay", "CaseSay", "AgentInvite"}, set(kept))
        limited = kept["AgentInvite"]["function"]
        self.assertEqual(names[:2], limited["parameters"]["properties"]["target"]["enum"])
        self.assertEqual(
            names[:2],
            limited["parameters"]["$defs"]["_AdditionalAssignment"]["properties"]["target"]["enum"],
        )
        self.assertNotIn("Travel", limited["description"])
        self.assertEqual(names, invite["function"]["parameters"]["properties"]["target"]["enum"])  # not mutated
        prompt = await middleware.on_system_prompt(None, "Bạn là Leader.")
        self.assertIn("PHÒNG XỬ LÝ", prompt)
        self.assertIn(f"{names[0]} (điều phối của đối tác) luôn có mặt", prompt)
        self.assertIn("Gọi cư dân là bạn.", prompt)

    @patch("agentscope.app.workforce.integrations.unified._contract.route_for_workflow", new_callable=AsyncMock)
    async def test_a_declared_member_in_the_ticket_room_gets_its_tools_under_the_case(self, pinned_route):
        from agentscope.app.workforce.integrations.unified._case import CaseRuntime, PartnerMemberMiddleware

        leader = {"session_id": "s-leader", "workflow_id": "wf-1", "route_id": "r-1", "agent_id": "a-leader"}
        route = {
            "route_id": "r-1",
            "config": {"member_agents": {"a-kt": {"name": "KyThuatVinhomes", "tools": ["vh_ticket_get"]}}},
        }
        pinned_route.return_value = route

        class Store:
            async def session(self, session_id):
                return leader if session_id == "s-leader" else None

            async def route(self, route_id):
                return route

        removed = []

        class Workspace:
            default_mcps = [SimpleNamespace(name="default")]

            async def list_mcps(self, agent_id, session_id):
                return [SimpleNamespace(name="vinhomes")]

            async def remove_mcp(self, name, agent_id, session_id):
                removed.append((name, agent_id, session_id))

        sessions = {
            "s-kt": SimpleNamespace(id="s-kt", team_id="team-1", state=SimpleNamespace(middle_context={}), config=SimpleNamespace(workspace_id="w")),
            "s-other": SimpleNamespace(id="s-other", team_id=None, state=SimpleNamespace(middle_context={}), config=SimpleNamespace(workspace_id="w")),
        }

        class Storage:
            async def get_session(self, user_id, agent_id, session_id):
                return sessions.get(session_id)

            async def get_team(self, user_id, team_id):
                return SimpleNamespace(session_id="s-leader")

        async def get_workspace(*_args):
            return Workspace()

        runtime = CaseRuntime(Store())
        runtime.bind(SimpleNamespace(state=SimpleNamespace(
            storage=Storage(), workspace_manager=SimpleNamespace(get_workspace=get_workspace),
        )))
        asked = {}

        async def tools(user_id, case, route_, only=None):
            asked.update(workflow=case.workflow_id, only=only)
            return [SimpleNamespace(name="vh_ticket_get")]

        runtime._tools = tools
        [member] = await runtime.middlewares("u", "a-kt", "s-kt")
        self.assertIsInstance(member, PartnerMemberMiddleware)
        self.assertEqual({"workflow": "wf-1", "only": {"vh_ticket_get"}}, asked)
        self.assertEqual({"vinhomes", "default"}, {name for name, *_ in removed})
        # Not a declared member, or not in a team: nothing.
        self.assertEqual([], await runtime.middlewares("u", "a-travel", "s-kt"))
        self.assertEqual([], await runtime.middlewares("u", "a-kt", "s-other"))
        seen = {}

        async def next_handler(**kwargs):
            seen.update(kwargs)

        offered = [{"type": "function", "function": {"name": n}} for n in ("TeamSay", "CaseSay", "vh_ticket_get", "Bash")]
        agent = SimpleNamespace(state=SimpleNamespace(reply_id="r-now"))
        await member.on_model_call(agent, {"tools": offered, "messages": []}, next_handler)
        self.assertEqual(["TeamSay", "vh_ticket_get"], [t["function"]["name"] for t in seen["tools"]])


class ClearOldResultsTest(unittest.TestCase):
    def test_earlier_long_results_shrink_to_their_label_in_one_batch(self):
        from agentscope.app.workforce.integrations.unified._case import clear_old_results
        from agentscope.message import AssistantMsg, ToolResultBlock

        def reply(reply_id, label, size):
            return AssistantMsg(id=reply_id, name="DieuPhoi", content=[ToolResultBlock(
                id=f"c-{reply_id}", name="vh_ticket_get", output=[TextBlock(text=f"{label}: " + "x" * size)],
            )])

        old, current = reply("r-old", "E1", 7000), reply("r-now", "E2", 7000)
        cleared = clear_old_results([old, current], "r-now")
        [stub] = cleared[0].content[0].output
        self.assertTrue(stub.text.startswith("E1: (kết quả của lượt trước"))
        self.assertIs(current, cleared[1])  # this reply keeps its results
        # Too little to free: nothing changes, so the cached prefix holds.
        small = reply("r-old", "E1", 1000)
        self.assertIs(small, clear_old_results([small, current], "r-now")[0])


class TicketTitleTest(unittest.TestCase):
    def test_the_declared_fields_name_the_ticket(self):
        from agentscope.app.workforce.integrations.unified._runner import ticket_title

        self.assertEqual("Rò nước bồn rửa · S1-1205", ticket_title(HANDOVER, ["Mô tả của cư dân", "căn"]))
        self.assertEqual("", ticket_title(HANDOVER, []))
        self.assertEqual("", ticket_title(None, ["Căn"]))
        long = ticket_title("Tiêu đề: " + "x" * 200, ["Tiêu đề"])
        self.assertEqual(80, len(long))
        self.assertTrue(long.endswith("…"))


class TicketBriefTest(unittest.TestCase):
    SPEC = {
        "fields": ["ticket_id", "Tiêu đề", "Mô tả của cư dân", "Căn", "response_due_at"],
        "request": ["Tiêu đề", "Mô tả của cư dân"],
        "facts": ["Căn"],
    }
    HANDOVER = (
        "ticket_id: T-77\nhandover_version: v1.1\nTiêu đề: Rò nước bồn rửa\n"
        "Mô tả của cư dân: Rò nước bồn rửa, nước chảy ra sàn\nCăn: S1-1205\n"
        "response_due_at: unknown\nKhông xác định lại cư dân/căn hộ."
    )

    def test_the_leader_reads_only_the_declared_fields(self):
        from agentscope.app.workforce.integrations.unified._runner import ticket_brief

        brief, card = ticket_brief(self.HANDOVER, self.SPEC)
        self.assertEqual(
            "ticket_id: T-77\nTiêu đề: Rò nước bồn rửa\n"
            "Mô tả của cư dân: Rò nước bồn rửa, nước chảy ra sàn\nCăn: S1-1205",
            brief,
        )
        # The description repeats the title, so the card shows it alone.
        self.assertEqual({"request": "Rò nước bồn rửa, nước chảy ra sàn", "facts": ["S1-1205"]}, card)

    def test_without_a_declaration_or_a_handover_the_text_passes_through(self):
        from agentscope.app.workforce.integrations.unified._runner import ticket_brief

        self.assertEqual((self.HANDOVER, None), ticket_brief(self.HANDOVER, None))
        self.assertEqual(("Nước vẫn chảy", None), ticket_brief("Nước vẫn chảy", self.SPEC))
        self.assertEqual((None, None), ticket_brief(None, self.SPEC))


class PartnerFactTest(unittest.TestCase):
    def test_partner_facts_keep_exact_evidence_for_packet_projection(self):
        from agentscope.app._service._chat import _partner_fact
        from agentscope.message import ToolCallBlock, ToolResultBlock

        call = ToolCallBlock(id="c1", name="vh_ticket_get", input='{"ticket_id": "T-77"}')
        short = ToolResultBlock(id="c1", name="vh_ticket_get", output=[TextBlock(text='E4: {"ticket_status": "open"}')])
        value = json.loads(_partner_fact(call, short))
        self.assertEqual(value["tool_result"]["output"][0]["text"], 'E4: {"ticket_status": "open"}')
        long = ToolResultBlock(id="c1", name="vh_ticket_get", output="E5: " + "x" * 5000)
        fact = _partner_fact(call, long)
        self.assertIn("E5: ", fact)
        self.assertEqual(json.loads(fact)["tool_result"]["output"], long.output)


class CheckSayTest(unittest.TestCase):
    def test_figures_must_be_cited_or_said_by_the_user(self):
        self.assertEqual([], check_say("Thợ đến lúc 09:30.", ["E2"], {}, {"E2": "eta 09:30"}, []))
        self.assertTrue(check_say("Phí 150.000 đồng.", [], {}, {}, []))
        self.assertEqual([], check_say("Căn S1-1205 của anh/chị.", [], {}, {}, ["Căn S1-1205"]))
        self.assertEqual([], check_say("Có 2 ảnh.", [], {}, {}, []))

    def test_phrase_rules_and_unless(self):
        rules = RULES
        self.assertTrue(check_say("Thợ sẽ có mặt ngay.", [], rules, {}, []))
        self.assertTrue(check_say("Việc này được miễn phí.", [], rules, {}, []))
        self.assertEqual(
            [],
            check_say("Việc này được miễn phí.", ["E1"], rules, {"E1": "Phí kiểm tra: miễn phí"}, []),
        )

    def test_unknown_labels_are_refused(self):
        self.assertTrue(check_say("Đã ghi nhận.", ["E9"], {}, {}, []))

    def test_cited_prices_stay_with_their_entity(self):
        sources = {
            "E1": '{"hotel": "Hotel Alpha", "price": 100, "currency": "USD"}',
            "E2": '{"hotel": "Hotel Beta", "price": 200, "currency": "USD"}',
        }
        self.assertEqual([], check_say("Hotel Alpha costs 100 USD.", ["E1"], {}, sources, []))
        self.assertTrue(check_say("Hotel Alpha costs 200 USD.", ["E1", "E2"], {}, sources, []))

    def test_cited_price_keeps_its_currency_and_unit(self):
        sources = {"E1": '{"hotel": "Hotel Alpha", "price": 100, "currency": "USD", "unit": "night"}'}
        self.assertEqual([], check_say("Hotel Alpha costs 100 USD per night.", ["E1"], {}, sources, []))
        self.assertTrue(check_say("Hotel Alpha costs 100 EUR per night.", ["E1"], {}, sources, []))
        self.assertTrue(check_say("Hotel Alpha costs 100 USD per guest.", ["E1"], {}, sources, []))

    def test_formatting_and_quoted_instructions_do_not_need_evidence(self):
        text_value = "## Proposed Action Plan\n> Please confirm your preference.\n12. Compare the available options."
        self.assertEqual([], check_say(text_value, [], {}, {}, []))


class PromptCacheOrderTest(unittest.TestCase):
    def test_the_session_notification_goes_after_the_fixed_instructions(self):
        from agentscope.app.workforce.integrations.unified._case import notification_last

        prompt = "Agent.\n\n<system-notification>session (id=1), roster: A</system-notification>\n<workspace>w</workspace>\n\nPOLICY"
        self.assertEqual(
            "Agent.\n\n<workspace>w</workspace>\n\nPOLICY\n\n<system-notification>session (id=1), roster: A</system-notification>",
            notification_last(prompt),
        )
        self.assertEqual("no note", notification_last("no note"))


class RoomStepEndTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_waiter_resumes_case_say_or_parks_without_an_attribute_error(self):
        from agentscope.agent import ReActConfig
        from agentscope.app.middleware import LeaderEvidenceMiddleware
        from agentscope.app.workforce.integrations.unified._case import CaseSay, PartnerCaseMiddleware
        from agentscope.event import ReplyEndEvent
        from agentscope.message import ToolCallBlock, ToolResultBlock
        from agentscope.state import AgentState

        scenarios = (
            ((1, 0, 1, False), "completed", False, True, True),
            ((1, 0, 1, False), "running", False, True, True),
            ((1, 1, 0, False), "running", False, True, True),
            ((0, 0, 0, False), "running", False, True, False),
            ((0, 0, 0, False), "review", False, True, True),
            ((1, 0, 1, False), "completed", True, True, False),
            ((1, 0, 1, False), "completed", False, False, False),
        )
        for evidence, status, consent, team_exists, should_say in scenarios:
            with self.subTest(evidence=evidence, status=status, consent=consent, team=team_exists):
                task = SimpleNamespace(latest_customer_revision=1, collaboration={
                    "worker": SimpleNamespace(customer_revision=1, status=status),
                })
                shared = SimpleNamespace(
                    team_evidence_status=AsyncMock(return_value=evidence),
                    collaboration_review=AsyncMock(return_value=[] if status == "completed" else ["worker"]),
                    storage=SimpleNamespace(get_team_shared_context=AsyncMock(return_value=SimpleNamespace(
                        state=SimpleNamespace(active_task_id="task", tasks={"task": task}),
                    ))),
                )
                storage = SimpleNamespace(get_session=AsyncMock(
                    return_value=SimpleNamespace(team_id="team-1") if team_exists else None,
                ))
                waiter = LeaderEvidenceMiddleware(storage, shared, "u", "leader", "session-1", wait_seconds=0)
                waiter._pending_consent = AsyncMock(return_value=consent)
                says = []
                case = _unsaid_case()
                case.workflow_id, case.on_say = "workflow", None
                case.said = AsyncMock(side_effect=lambda: bool(says))

                async def append(workflow_id, kind, text, **kwargs):
                    self.assertEqual(kind, "say")
                    says.append({"text": text, **kwargs})
                    return 1

                case.store = SimpleNamespace(
                    entries=AsyncMock(side_effect=lambda *args, **kwargs: list(says)),
                    labelled=AsyncMock(return_value={}), customer_texts=AsyncMock(return_value=[]),
                    append=append,
                )
                middleware = PartnerCaseMiddleware(case, [], {"Worker": {}}, waiter)
                state = AgentState(session_id="session-1")
                state.reply_id = "reply-1"
                state.append_context("Leader", [
                    ToolCallBlock(id="invite", name="AgentInvite", input='{"target":"Worker"}'),
                    ToolResultBlock(id="invite", name="AgentInvite", output="invited", state=ToolResultState.SUCCESS),
                ])
                agent = SimpleNamespace(name="Leader", state=state, react_config=ReActConfig(max_iters=5))

                async def next_handler(**kwargs):
                    yield ReplyEndEvent(session_id="session-1", reply_id="reply-1")
                    if any(message.get_content_blocks("hint") for message in state.context):
                        result = await CaseSay(case).call(text="Yêu cầu đã được tiếp nhận.")
                        self.assertEqual(result.state, ToolResultState.SUCCESS, result.content)
                        yield ReplyEndEvent(session_id="session-1", reply_id="reply-1")

                events = [event async for event in middleware.on_reply(agent, {}, next_handler)]
                self.assertEqual(len(says), int(should_say))
                self.assertEqual(len(events), 1)

    async def test_after_inviting_the_step_ends_once_and_the_reports_wake_the_leader(self):
        from agentscope.app.workforce.integrations.unified._case import ROOM_WORKING, PartnerCaseMiddleware
        from agentscope.message import AssistantMsg, ToolResultBlock, ToolResultState

        def reply(name, state=ToolResultState.SUCCESS):
            return AssistantMsg(id="r1", name="Leader", content=[ToolResultBlock(
                id=f"c-{name}", name=name, output=[TextBlock(text="ok")], state=state,
            )])

        members = {"DieuPhoi@a": {"name": "DieuPhoi"}}
        middleware = PartnerCaseMiddleware(_unsaid_case(), [], members, waiter=object())
        agent = SimpleNamespace(state=SimpleNamespace(reply_id="r1"))
        calls = []

        async def next_handler(**kwargs):
            calls.append(kwargs)
            return "model"

        first = await middleware.on_model_call(agent, {"tools": [], "messages": [reply("AgentInvite")]}, next_handler)
        self.assertEqual(ROOM_WORKING, first.content[0].text)
        self.assertEqual([], calls)
        # Woken by the reports (same reply, same invite): the model answers.
        again = await middleware.on_model_call(agent, {"tools": [], "messages": [reply("AgentInvite")]}, next_handler)
        self.assertEqual("model", again)
        # A failed invite, or any other last step, goes to the model.
        fresh = PartnerCaseMiddleware(_unsaid_case(), [], members, waiter=object())
        for messages in ([reply("AgentInvite", ToolResultState.ERROR)], [reply("TeamSay")]):
            self.assertEqual("model", await fresh.on_model_call(agent, {"tools": [], "messages": messages}, next_handler))
