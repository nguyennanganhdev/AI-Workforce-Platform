"""Unified mode: a partner workflow is answered by the console Leader runtime.

Real Workforce SQL repositories, durable jobs, ingress, router and
``build_unified_runtime``; the console ChatService is a scripted double that
writes the Leader's reply the way the real service persists it.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
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
from agentscope.app.workforce.foundation._tables import metadata as foundation_metadata
from agentscope.app.workforce.integrations.unified import (
    ChatLeaderTurnRunner,
    build_unified_runtime,
)
from agentscope.app.workforce.integrations.unified import get_metadata as unified_metadata
from agentscope.app.workforce.integrations.unified import _runner as runner_module
from agentscope.app.workforce.orchestration import get_metadata
from agentscope.message import AssistantMsg, TextBlock

SCOPE = Scope(
    tenant_id="tenant-1",
    domain_id="domain-1",
    area_id="area-1",
    manager_account_id="manager-1",
)
NOW = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)


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


class _ConsoleStorage:
    """Just enough of StorageBase for the runner."""

    def __init__(self):
        self.sessions = {}
        self.messages = {}

    async def get_session(self, user_id, agent_id, session_id):
        return self.sessions.get(session_id)

    async def upsert_session(self, user_id, agent_id, config, state=None, session_id=None, **_):
        session = SimpleNamespace(id=session_id, agent_id=agent_id, config=config, team_id=None)
        self.sessions[session_id] = session
        return session

    async def list_messages(self, user_id, session_id, limit=200, before=None):
        return list(self.messages.get(session_id, [])), False

    async def upsert_message(self, user_id, session_id, message):
        self.messages.setdefault(session_id, []).append(message)


class _ChatService:
    """Persists the customer message and a scripted Leader reply."""

    def __init__(self, storage, replies):
        self.storage = storage
        self.replies = list(replies)
        self.inputs = []

    async def run(self, user_id, session_id, agent_id, input_msg):
        self.inputs.append(input_msg.get_text_content())
        await self.storage.upsert_message(user_id, session_id, input_msg)
        await self.storage.upsert_message(
            user_id,
            session_id,
            AssistantMsg(name="Leader", content=[TextBlock(text=self.replies.pop(0))]),
        )


class _Workspace:
    default_mcps: ClassVar[list] = []


class _WorkspaceManager:
    async def get_workspace(self, *_args):
        return _Workspace()


class UnifiedPartnerModeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{(Path(self.temp.name) / 'unified.sqlite3').as_posix()}",
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(foundation_metadata.create_all)
            await connection.run_sync(get_execution_metadata().create_all)
            await connection.run_sync(get_metadata().create_all)
            await connection.run_sync(unified_metadata().create_all)
            await connection.execute(
                text("CREATE TABLE partner_api_clients (id TEXT PRIMARY KEY, tenant_id TEXT, status TEXT)"),
            )
            await connection.execute(
                text("INSERT INTO partner_api_clients VALUES ('partner-1', 'tenant-1', 'active')"),
            )
        uows = SqlAlchemyUnitOfWorkFactory(async_sessionmaker(self.engine, expire_on_commit=False))
        bus = InMemoryMessageBus()
        jobs = DurableJobService(SqlDurableJobRepository(uows))
        foundation = SimpleNamespace(
            uows=uows,
            jobs=jobs,
            public_event_signal=MessageBusPublicEventSignal(bus),
            request_completion_signal=MessageBusRequestCompletionSignal(bus),
            identity=_Identity(),
            partner_routing=_Routing(),
            management_verification=None,
            route_grants=None,
        )
        self.console = _ConsoleStorage()
        self.chat = _ChatService(
            self.console,
            ["Ống nước khẩn cấp: anh/chị khoá van tổng giúp em. Căn hộ số mấy ạ?", "Đã ghi nhận, thợ đến lúc 09:00."],
        )
        self.runner = ChatLeaderTurnRunner(uows, wait_seconds=1)
        self.runner.bind(
            SimpleNamespace(
                state=SimpleNamespace(
                    chat_service=self.chat,
                    storage=self.console,
                    workspace_manager=_WorkspaceManager(),
                    message_bus=bus,
                    shared_context_storage=self.console,
                ),
            ),
        )
        self.assembly = build_unified_runtime(foundation, self.runner, bounded_wait_seconds=0)
        self.worker = DurableJobWorker(
            jobs,
            self.assembly.job_handlers,
            worker_id="unified-test",
            heartbeat_interval=10.0,
        )
        leader = SimpleNamespace(id="leader-agent")
        primary = SimpleNamespace(config=SimpleNamespace(chat_model_config=None))

        async def fake_leader(user_id, storage, workspace_manager):
            assert user_id == "manager-1"
            return leader, primary

        async def no_pending(*_args):
            return []

        self.patches = [
            patch("agentscope.app._router._workforce_console._leader", fake_leader),
            patch.object(runner_module, "pending_chat_actions", no_pending),
        ]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        for item in self.patches:
            item.stop()
        await self.engine.dispose()
        self.temp.cleanup()

    def _client(self):
        from agentscope.app._router._business import get_partner_principal

        app = FastAPI()
        for router in self.assembly.routers:
            app.include_router(router)
        app.dependency_overrides[get_partner_principal] = lambda: PartnerPrincipal(
            key_id="key-1",
            client_id="partner-1",
            tenant_id="tenant-1",
            domain_id="domain-1",
        )
        return AsyncClient(transport=ASGITransport(app=app), base_url="https://platform.test")

    @staticmethod
    def _envelope(request_id, text_value, **extra):
        body = PartnerRequestEnvelope(
            schema_version="1",
            command_type="start_workflow",
            external_request_id=request_id,
            external_management_ref="tower-a",
            external_user_id="resident-1",
            external_ticket_id="ticket-1",
            external_conversation_id="chat-1",
            message={"type": "text", "text": text_value},
        ).model_dump(mode="json")
        body.update(extra)
        return body

    async def test_partner_ticket_runs_console_leader_and_follows_question_then_answer(self):
        headers = {}
        async with self._client() as client:
            accepted = await client.post(
                "/workforce/v1/partner/requests",
                json=self._envelope("req-1", "Vỡ ống nước dưới bồn rửa!"),
                headers=headers,
            )
            self.assertEqual(202, accepted.status_code, accepted.text)
            first = accepted.json()
            self.assertEqual("succeeded", (await self.worker.run_once()).status)

            result = await client.get(
                f"/workforce/v1/partner/requests/{first['request_id']}",
                params={"external_user_id": "resident-1"},
                headers=headers,
            )
            body = result.json()
            self.assertEqual("awaiting_user", body["workflow_state"])
            self.assertIn("khoá van tổng", body["result"]["messages"][0]["text"])

            reply = await client.post(
                "/workforce/v1/partner/requests",
                json=self._envelope(
                    "req-2",
                    "Căn S1-1205",
                    command_type="workflow_reply",
                    workflow_id=first["workflow_id"],
                ),
                headers=headers,
            )
            self.assertIn(reply.status_code, (200, 202), reply.text)
            self.assertEqual("succeeded", (await self.worker.run_once()).status)
            second = await client.get(
                f"/workforce/v1/partner/requests/{reply.json()['request_id']}",
                params={"external_user_id": "resident-1"},
                headers=headers,
            )
            self.assertEqual("awaiting_confirmation", second.json()["workflow_state"])

            closed = await client.post(
                f"/workforce/v1/partner/workflows/{first['workflow_id']}/close",
                json={
                    "schema_version": "1",
                    "external_request_id": "close-1",
                    "external_user_id": "resident-1",
                    "external_ticket_id": "ticket-1",
                    "external_conversation_id": "chat-1",
                    "expected_revision": second.json()["workflow_revision"],
                    "reason": "resolved",
                },
                headers=headers,
            )
            self.assertEqual(200, closed.status_code, closed.text)
            self.assertEqual("closed", closed.json()["workflow_state"])

        # Same Leader session for both turns; the customer text reached it.
        self.assertEqual(["Vỡ ống nước dưới bồn rửa!", "Căn S1-1205"], self.chat.inputs)
        self.assertEqual(1, len(self.console.sessions))

    async def test_close_errors_use_the_contract_codes(self):
        async with self._client() as client:
            first = (
                await client.post(
                    "/workforce/v1/partner/requests",
                    json=self._envelope("req-1", "Vỡ ống nước dưới bồn rửa!"),
                )
            ).json()
            await self.worker.run_once()
            state = (
                await client.get(
                    f"/workforce/v1/partner/requests/{first['request_id']}",
                    params={"external_user_id": "resident-1"},
                )
            ).json()

            def close(request_id, revision):
                return client.post(
                    f"/workforce/v1/partner/workflows/{first['workflow_id']}/close",
                    json={
                        "schema_version": "1",
                        "external_request_id": request_id,
                        "external_user_id": "resident-1",
                        "external_ticket_id": "ticket-1",
                        "external_conversation_id": "chat-1",
                        "expected_revision": revision,
                        "reason": "resolved",
                    },
                )

            not_ready = await close("close-1", state["workflow_revision"])
            stale = await close("close-2", state["workflow_revision"] + 5)

        self.assertEqual("awaiting_user", state["workflow_state"])
        self.assertEqual(409, not_ready.status_code)
        self.assertEqual("WORKFLOW_NOT_READY_TO_CLOSE", not_ready.json()["error"]["code"])
        self.assertEqual("REVISION_CONFLICT", stale.json()["error"]["code"])
        self.assertEqual(
            state["workflow_revision"],
            stale.json()["error"]["details"]["current_revision"],
        )

    async def test_end_user_comes_from_query_or_body_as_in_the_contract(self):
        async with self._client() as client:
            missing = await client.get("/workforce/v1/partner/requests/unknown")
            accepted = await client.post(
                "/workforce/v1/partner/requests",
                json=self._envelope("req-x", "xin chào"),
            )
            other_user = await client.get(
                f"/workforce/v1/partner/requests/{accepted.json()['request_id']}",
                params={"external_user_id": "someone-else"},
            )
        self.assertEqual(422, missing.status_code)
        self.assertEqual(202, accepted.status_code, accepted.text)
        self.assertIn(other_user.status_code, (403, 404))

    async def test_sandbox_script_drives_the_whole_contract(self):
        import argparse
        import asyncio
        import importlib.util

        from agentscope.app._router._business import get_partner_principal

        root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "partner_sandbox_check",
            root / "scripts/workforce/partner_sandbox_check.py",
        )
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)

        app = FastAPI()
        for router in self.assembly.routers:
            app.include_router(router)
        app.dependency_overrides[get_partner_principal] = lambda: PartnerPrincipal(
            key_id="key-1", client_id="partner-1", tenant_id="tenant-1", domain_id="domain-1"
        )
        stop = asyncio.Event()

        async def worker():
            while not stop.is_set():
                if (await self.worker.run_once()).status == "idle":
                    await asyncio.sleep(0.05)

        task = asyncio.create_task(worker())
        with tempfile.TemporaryDirectory() as out:
            args = argparse.Namespace(
                base_url="https://platform.test",
                api_key="unused",
                management_ref="tower-a",
                external_user_id="resident-1",
                message="Vỡ ống nước",
                reply="Căn S1-1205",
                timeout=20,
                output=out,
            )
            code = await script.run(args, transport=ASGITransport(app=app))
            evidence = next(Path(out).glob("*/evidence.json")).read_text(encoding="utf-8")
        stop.set()
        await task

        steps = {step["step"]: step["ok"] for step in json.loads(evidence)["steps"]}
        for name in ("start_workflow", "read_result", "idempotent_retry", "event_history", "workflow_reply", "close_workflow"):
            self.assertTrue(steps.get(name), (name, steps))
        self.assertIn("sse_replay", steps)
        self.assertIn(code, (0, 1))
