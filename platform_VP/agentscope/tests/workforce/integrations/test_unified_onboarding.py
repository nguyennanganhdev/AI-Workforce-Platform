"""Three-party route onboarding on the real migrated schema.

Admin verifies the area manager, the manager grants a route to a partner, the
partner confirms it — after which the production SQL routing resolves the
partner's tickets to exactly that manager.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentscope.app._router._business import get_partner_principal
from agentscope.app.business import PartnerPrincipal
from agentscope.app.deps import get_business_service, get_current_principal
from agentscope.app.workforce.contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
)
from agentscope.app.workforce.foundation import SqlAlchemyUnitOfWorkFactory
from agentscope.app.workforce.foundation._identity import (
    ManagementVerificationService,
    SqlIdentityPort,
)
from agentscope.app.workforce.foundation._partner_routing import SqlPartnerRoutingPort
from agentscope.app.workforce.foundation._route_grants import PartnerRouteGrantService
from agentscope.app.workforce.integrations.unified import onboarding_router

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 14, 8, 0)


class _Business:
    def verify_provisioning_secret(self, secret):
        if secret != "provision-me":
            raise PermissionError("bad provisioning secret")


class UnifiedOnboardingTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        url = f"sqlite+aiosqlite:///{(Path(self.temp.name) / 'onboarding.sqlite3').as_posix()}"
        await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(ROOT / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"),
                "upgrade",
                "head",
            ],
            check=True,
            cwd=ROOT,
            env={**os.environ, "AGENTSCOPE_SQL_URL": url},
            capture_output=True,
        )
        self.engine = create_async_engine(url)
        async with self.engine.begin() as connection:
            for statement in (
                "INSERT INTO business_domains VALUES ('domain-1','tenant-1','Vinhomes','active')",
                "INSERT INTO areas VALUES ('area-1','domain-1','Tower A','active')",
                (
                    "INSERT INTO auth_users (id, tenant_id, email, username, password_hash, status,"
                    " created_at, updated_at, role, domain_id, area_id) VALUES ('manager-1','tenant-1',"
                    " 'm@example.com','manager','x','active', :now, :now, 'AREA_MANAGER','domain-1','area-1')"
                ),
                (
                    "INSERT INTO wf_manager_memberships (id, tenant_id, domain_id, area_id,"
                    " manager_account_id, status, revision, created_at, updated_at) VALUES"
                    " ('mem-1','tenant-1','domain-1','area-1','manager-1','pending_verification',1,:now,:now)"
                ),
                "INSERT INTO partner_api_clients VALUES ('partner-1','tenant-1','domain-1','Partner','active',:now)",
            ):
                await connection.execute(text(statement), {"now": NOW})
        uows = SqlAlchemyUnitOfWorkFactory(async_sessionmaker(self.engine, expire_on_commit=False))
        self.routing = SqlPartnerRoutingPort(uows)
        foundation = SimpleNamespace(
            uows=uows,
            identity=SqlIdentityPort(uows),
            management_verification=ManagementVerificationService(uows),
            route_grants=PartnerRouteGrantService(uows),
            partner_routing=self.routing,
        )
        app = FastAPI()
        app.include_router(onboarding_router(foundation))
        app.dependency_overrides[get_business_service] = _Business
        app.dependency_overrides[get_current_principal] = lambda: SimpleNamespace(
            role="AREA_MANAGER",
            user_id="manager-1",
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
        )
        app.dependency_overrides[get_partner_principal] = lambda: PartnerPrincipal(
            key_id="key-1",
            client_id="partner-1",
            tenant_id="tenant-1",
            domain_id="domain-1",
        )
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="https://platform.test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.engine.dispose()
        self.temp.cleanup()

    async def test_operator_verification_approves_a_waiting_account(self):
        async with self.engine.begin() as connection:
            await connection.execute(text("UPDATE auth_users SET status = 'pending' WHERE id = 'manager-1'"))
        verified = await self.client.post(
            "/workforce/v1/admin/memberships/verify",
            json={"manager_account_id": "manager-1"},
            headers={"X-Provisioning-Secret": "provision-me"},
        )
        self.assertEqual(200, verified.status_code, verified.text)
        async with self.engine.connect() as connection:
            account = (await connection.execute(text("SELECT status FROM auth_users WHERE id = 'manager-1'"))).scalar()
            membership = (await connection.execute(
                text("SELECT status FROM wf_manager_memberships WHERE manager_account_id = 'manager-1'"),
            )).scalar()
        self.assertEqual(("active", "verified"), (account, membership))

    async def test_admin_verify_manager_grant_partner_confirm_then_route_resolves(self):
        denied = await self.client.post(
            "/workforce/v1/admin/memberships/verify",
            json={"manager_account_id": "manager-1"},
            headers={"X-Provisioning-Secret": "wrong"},
        )
        self.assertEqual(403, denied.status_code)

        verified = await self.client.post(
            "/workforce/v1/admin/memberships/verify",
            json={"manager_account_id": "manager-1"},
            headers={"X-Provisioning-Secret": "provision-me"},
        )
        self.assertEqual(200, verified.status_code, verified.text)
        self.assertEqual("verified", verified.json()["status"])

        granted = await self.client.post(
            "/workforce/v1/manager/partner-routes",
            json={"partner_client_id": "partner-1", "external_management_ref": "tower-a"},
        )
        self.assertEqual(201, granted.status_code, granted.text)
        route = granted.json()
        listed = await self.client.get("/workforce/v1/manager/partner-routes")
        self.assertEqual([route["route_id"]], [item["route_id"] for item in listed.json()])
        self.assertEqual("pending_confirmation", listed.json()[0]["status"])

        confirmed = await self.client.post(
            f"/workforce/v1/partner/routes/{route['route_id']}/confirm",
            json={"expected_revision": route["revision"]},
        )
        self.assertEqual(200, confirmed.status_code, confirmed.text)
        self.assertEqual("active", confirmed.json()["status"])

        resolved = await self.routing.resolve(
            ActorContext(
                kind=ActorKind.PARTNER,
                actor_id="partner-1:resident-1",
                partner_client_id="partner-1",
                credential_id="key-1",
                credential_purpose=CredentialPurpose.CUSTOMER_API,
                external_user_id="resident-1",
                authentication_source="test",
            ),
            {"external_management_ref": "tower-a", "external_user_id": "resident-1"},
        )
        self.assertEqual("manager-1", resolved.scope.manager_account_id)


class _Workspace:
    default_mcps: list = []

    async def list_mcps(self, **_):
        return []

    async def remove_mcp(self, *_args, **_kwargs):
        return None

    async def add_mcp(self, client, **_):
        return client


class _WorkspaceManager:
    async def assign_workspace_id(self, **_kwargs):
        return "ws-1"

    async def get_workspace(self, *_args):
        return _Workspace()


class _StudioStorage:
    """Agents, sessions and the MCP library of the manager (in memory)."""

    def __init__(self):
        self.agents, self.sessions, self.mcps = {}, {}, {}

    async def list_mcps(self, _user):
        return list(self.mcps.values())

    async def upsert_mcp(self, _user, record):
        self.mcps[record.id] = record
        return record

    async def get_mcp(self, _user, mcp_id):
        return self.mcps.get(mcp_id)

    async def list_agents(self, _user):
        return [r.model_copy(deep=True) for r in self.agents.values()]

    async def get_agent(self, _user, agent_id):
        return self.agents.get(agent_id)

    async def upsert_agent(self, _user, record):
        self.agents[record.id] = record.model_copy(deep=True)
        return record

    async def upsert_session(self, user_id, agent_id, config, state=None, session_id=None, **_):
        from agentscope.app.storage import SessionRecord

        record = SessionRecord(id=session_id or f"s-{agent_id}", user_id=user_id, agent_id=agent_id, config=config)
        self.sessions[record.id] = record
        return record

    async def list_sessions(self, _user, agent_id):
        return [s for s in self.sessions.values() if s.agent_id == agent_id]


DECLARATION = {
    "declaration": "test-partner-v1",
    "client": {"name": "Vinhomes", "domain": "domain-1"},
    "customer_key": {
        "operations": [
            "submit_request", "reply", "read_result", "receive_events",
            "submit_consent", "close_workflow", "confirm_route",
        ],
    },
    "provider_key": {"operations": ["publish_job_event", "read_event_receipt"]},
    "profiles": [
        {
            "key": "vh_dieu_phoi",
            "name": "DieuPhoiVinhomes",
            "role": "leader",
            "mission": "trợ lý điều phối của Ban quản lý",
            "handles": ["giao việc sửa chữa"],
            "refuses": ["việc không liên quan"],
            "instructions": "Luôn kết thúc lượt bằng CaseSay.",
            "tools_allow": ["vh_*"],
            "model_tier": "standard",
            "escalate_when": ["cư dân khiếu nại"],
        },
    ],
    "route": {
        "leader_profile": "vh_dieu_phoi",
        "config": {"wait_seconds": 25.0, "rules": {"safe_reply": "Chưa xác minh được."}},
    },
    "mcp_server": {"name": "vinhomes", "transport": "streamable_http", "timeout": 8.0},
    "tools": [
        {
            "name": "vh_ticket_get", "server": "vinhomes", "mcp_tool": "vh_ticket_get",
            "kind": "lookup", "read_only": True, "requires_consent": False, "tracking": "none",
        },
        {
            "name": "vh_work_order_dispatch", "server": "vinhomes", "mcp_tool": "vh_work_order_dispatch",
            "kind": "action", "read_only": False, "requires_consent": False, "tracking": "events",
            "client_reference_arg": "client_reference",
        },
    ],
    "integration": {"event_schema": {"version": "1", "events": {"job.accepted": {"status": "accepted", "rank": 20}}}},
}
PROVISIONING = "provision-secret-" + "x" * 24


class PartnerOnboardingTest(UnifiedOnboardingTest):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from unittest.mock import patch

        from agentscope.app._router import _mcp, _workforce_studio
        from agentscope.app.business import BusinessService
        from agentscope.app.deps import get_storage, get_workspace_manager
        from agentscope.app.storage import ChatModelConfig

        self.pepper = "q" * 40
        self.env = patch.dict(os.environ, {"PARTNER_API_KEY_PEPPER": self.pepper})
        self.env.start()
        self.business = BusinessService(
            database_url=str(self.engine.url),
            api_key_pepper=self.pepper,
            provisioning_secret=PROVISIONING,
        )
        await self.business.__aenter__()
        self.storage = _StudioStorage()
        self.uows = SqlAlchemyUnitOfWorkFactory(async_sessionmaker(self.engine, expire_on_commit=False))
        foundation = SimpleNamespace(
            uows=self.uows,
            identity=SqlIdentityPort(self.uows),
            management_verification=ManagementVerificationService(self.uows),
            route_grants=PartnerRouteGrantService(self.uows),
            partner_routing=SqlPartnerRoutingPort(self.uows),
        )
        app = FastAPI()
        app.include_router(onboarding_router(foundation))
        app.dependency_overrides[get_business_service] = lambda: self.business
        app.dependency_overrides[get_current_principal] = lambda: SimpleNamespace(
            role="AREA_MANAGER", user_id="manager-1", tenant_id="tenant-1", domain_id="domain-1", area_id="area-1",
        )
        app.dependency_overrides[get_storage] = lambda: self.storage
        app.dependency_overrides[get_workspace_manager] = _WorkspaceManager
        self.partner_app = AsyncClient(transport=ASGITransport(app=app), base_url="https://platform.test")

        async def discover(client, timeout):
            return [
                {"name": "vh_ticket_get", "description": "Read", "input_schema": {"type": "object"}, "read_only": True},
                {"name": "vh_work_order_dispatch", "description": "Dispatch", "input_schema": {"type": "object"}, "read_only": False},
                {"name": "unrelated_tool", "description": "x", "input_schema": {"type": "object"}, "read_only": True},
            ]

        async def model_config(*_args):
            return ChatModelConfig(type="openai_credential", credential_id="c", model="m", parameters={})

        self.patches = [
            patch.object(_mcp, "_discover_tools", discover),
            patch.object(_workforce_studio, "_model_config", model_config),
        ]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        for item in self.patches:
            item.stop()
        await self.partner_app.aclose()
        await self.business.__aexit__(None, None, None)
        self.env.stop()
        await super().asyncTearDown()

    async def _onboard(self, **extra):
        secret = {"X-Provisioning-Secret": PROVISIONING}
        await self.partner_app.post(
            "/workforce/v1/admin/memberships/verify", json={"manager_account_id": "manager-1"}, headers=secret,
        )
        return await self.partner_app.post(
            "/workforce/v1/admin/partner-onboarding",
            headers=secret,
            json={
                "declaration": DECLARATION,
                "manager_account_id": "manager-1",
                "mcp_url": "https://partner.example/mcp",
                "mcp_token": "t" * 40,
                "management_refs": ["local-management"],
                "environment": "sandbox",
                "trusted_provisioning_reason": "Explicit operator-approved fixture provisioning",
                **extra,
            },
        )

    async def test_admin_verify_manager_grant_partner_confirm_then_route_resolves(self):
        """Covered by the parent class; not repeated here."""

    async def test_team_readiness_is_owner_scoped_and_never_treats_provisioning_as_model_eval(self):
        from agentscope.app.deps import get_current_principal
        response = await self._onboard()
        route = response.json()["routes"][0]
        path = f"/workforce/v1/manager/partner-routes/{route['route_id']}"
        readiness = await self.partner_app.get(path + "/readiness")
        self.assertEqual(200, readiness.status_code, readiness.text)
        self.assertFalse(readiness.json()["ready"])
        codes = [issue["code"] for issue in readiness.json()["issues"]]
        self.assertIn("ROUTE_NOT_ACTIVE", codes)
        self.assertIn("AGENT_EVALUATION_REQUIRED", codes)
        self.assertEqual(404, (await self.partner_app.get(
            "/workforce/v1/manager/partner-routes/not-owned/readiness")).status_code)

    async def test_default_onboarding_creates_drafts_without_restoring_published_presets(self):
        response = await self._onboard(trusted_provisioning_reason=None)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(0, response.json()["leader_version"])
        self.assertTrue(self.storage.agents)
        for record in self.storage.agents.values():
            self.assertEqual("draft", record.data.lifecycle_state)
            self.assertFalse(record.data.invite_config.invitable)

    async def test_declaration_onboards_once_and_reruns_without_new_keys(self):
        import hashlib
        import hmac
        import time

        from agentscope.app.workforce.foundation._provider_auth import (
            HmacProviderAuth,
            SqlProviderCredentialRepository,
        )
        from agentscope.app.workforce.integrations.unified import resolve_signing_secret

        first = await self._onboard()
        self.assertEqual(200, first.status_code, first.text)
        body = first.json()
        keys = body["keys"]
        self.assertTrue(keys["customer_key"].startswith("dp_"))
        self.assertTrue(keys["signing_key_id"].startswith("sk_"))
        self.assertEqual(["vh_ticket_get", "vh_work_order_dispatch"], body["tools"])
        self.assertEqual("pending_confirmation", body["routes"][0]["status"])
        self.assertEqual(1, body["leader_version"])
        # The declared leader profile is the coordinator the platform Leader invites.
        leader = self.storage.agents[body["leader_agent_id"]]
        self.assertTrue(leader.data.invite_config.invitable)
        self.assertIn("Luôn kết thúc lượt bằng CaseSay.", leader.data.system_prompt)
        mcp = next(iter(self.storage.mcps.values()))
        self.assertEqual("Bearer " + "t" * 40, mcp.client.mcp_config.headers["Authorization"])

        again = (await self._onboard()).json()
        self.assertEqual({}, again["keys"])
        self.assertEqual(body["routes"][0]["route_id"], again["routes"][0]["route_id"])
        self.assertEqual(1, again["leader_version"])

        customer = await self.business.authenticate_partner_api_key(keys["customer_key"])
        raw = b'{"x":1}'
        stamp = str(int(time.time()))
        signature = "v1=" + hmac.new(
            keys["signing_secret"].encode(), stamp.encode() + b"." + raw, hashlib.sha256,
        ).hexdigest()
        auth = HmacProviderAuth(
            SqlProviderCredentialRepository(self.uows),
            self.business.authenticate_partner_api_key,
            resolve_signing_secret,
        )
        verified = await auth.authenticate(
            raw,
            {
                "Authorization": "ApiKey " + keys["provider_key"],
                "X-Partner-Timestamp": stamp,
                "X-Partner-Key-Id": keys["signing_key_id"],
                "X-Partner-Signature": signature,
            },
        )
        self.assertEqual(body["integration_id"], verified.provider_integration_id)
        self.assertEqual(customer.client_id, verified.partner_client_id)

        # The partner confirms its route with the customer key, like the bridge does.
        route = body["routes"][0]
        confirmed = await self.partner_app.post(
            f"/workforce/v1/partner/routes/{route['route_id']}/confirm",
            headers={"Authorization": "ApiKey " + keys["customer_key"]},
            json={
                "schema_version": "1",
                "external_management_ref": "local-management",
                "expected_revision": route["revision"],
            },
        )
        self.assertEqual(200, confirmed.status_code, confirmed.text)
        self.assertEqual("active", confirmed.json()["status"])

        renewed = (await self._onboard(new_keys=True)).json()["keys"]
        self.assertNotEqual(keys["customer_key"], renewed["customer_key"])
        from agentscope.app.business._service import InvalidPartnerApiKeyError

        with self.assertRaises(InvalidPartnerApiKeyError):
            await self.business.authenticate_partner_api_key(keys["customer_key"])
        await self.business.authenticate_partner_api_key(renewed["customer_key"])
        await self.business.authenticate_partner_api_key(renewed["provider_key"])

    async def test_partner_profiles_become_agents_the_leader_may_invite(self):
        import copy
        import json

        declaration = copy.deepcopy(DECLARATION)
        declaration["profiles"].append({
            "key": "vh_ky_thuat", "name": "KyThuatVinhomes", "role": "member",
            "mission": "đánh giá kỹ thuật của sự cố", "tools_allow": ["vh_ticket_get"],
        })
        answer = await self._onboard(declaration=declaration)
        self.assertEqual(200, answer.status_code, answer.text)
        [member] = answer.json()["members"]
        self.assertEqual(("KyThuatVinhomes", ["vh_ticket_get"]), (member["name"], member["tools"]))
        agent = self.storage.agents[member["agent_id"]]
        self.assertTrue(agent.data.invite_config.invitable)
        self.assertEqual("đánh giá kỹ thuật của sự cố", agent.data.invite_config.invite_description)
        coordinator = answer.json()["leader_agent_id"]
        self.assertTrue(self.storage.agents[coordinator].data.invite_config.invitable)
        async with self.engine.connect() as connection:
            config = (await connection.execute(text("SELECT config FROM wf_unified_routes"))).scalar()
        config = json.loads(config) if isinstance(config, str) else config
        self.assertEqual(
            {
                coordinator: {
                    "name": DECLARATION["profiles"][0]["name"],
                    "tools": ["vh_ticket_get", "vh_work_order_dispatch"],
                    "version": 1,
                    "coordinator": True,
                },
                member["agent_id"]: {"name": "KyThuatVinhomes", "tools": ["vh_ticket_get"], "version": 1},
            },
            config["member_agents"],
        )
        # A member works under the ticket's grant, which covers the route's tools only.
        declaration["profiles"][0]["tools_allow"] = ["vh_ticket_get"]
        declaration["profiles"][1]["tools_allow"] = ["vh_work_order_dispatch"]
        refused = await self._onboard(declaration=declaration)
        self.assertEqual(422, refused.status_code, refused.text)

    async def test_an_unreachable_mcp_issues_no_keys(self):
        from unittest.mock import patch

        from agentscope.app._router import _mcp

        async def down(client, timeout):
            raise ConnectionError("partner MCP is down")

        with patch.object(_mcp, "_discover_tools", down):
            failed = await self._onboard()
        self.assertEqual(502, failed.status_code)
        self.assertEqual("MCP_UNREACHABLE", failed.json()["error"]["code"])
        async with self.engine.connect() as connection:
            clients = (await connection.execute(text("SELECT count(*) FROM partner_api_clients"))).scalar()
        self.assertEqual(1, clients)  # only the fixture's client
        first = (await self._onboard()).json()
        self.assertIn("customer_key", first["keys"])
