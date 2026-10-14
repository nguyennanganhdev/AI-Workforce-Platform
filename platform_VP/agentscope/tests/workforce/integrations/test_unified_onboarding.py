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
