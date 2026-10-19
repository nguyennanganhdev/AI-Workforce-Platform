# -*- coding: utf-8 -*-
"""Customers register without choosing a business domain or area."""

from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agentscope.app._router._auth import auth_router
from agentscope.app.auth import AuthService
from agentscope.app.auth._models import AuthUser
from agentscope.app.deps import get_auth_service


class _Service:
    default_tenant_id = "default"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def register(self, **kwargs):
        self.calls.append(kwargs)
        now = datetime.now(timezone.utc)
        return AuthUser(
            id="u1", tenant_id="default", email=kwargs["email"], username=kwargs["username"],
            status="active", role="AREA_MANAGER", domain_id=AuthService.DEFAULT_DOMAIN_ID,
            area_id=AuthService.DEFAULT_AREA_ID, created_at=now, updated_at=now,
        )


class AuthRegisterRouteTest(IsolatedAsyncioTestCase):
    async def test_register_needs_only_email_username_password(self) -> None:
        service = _Service()
        app = FastAPI()
        app.include_router(auth_router)
        app.dependency_overrides[get_auth_service] = lambda: service
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/auth/register", json={
                "email": "khach@example.com", "username": "khach",
                "password": "Mat-khau-dai-2026",
                # Old clients may still send a scope; the server must not use it.
                "domain_id": "vinhomes", "area_id": "ocean-park-1",
            })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(service.calls, [{
            "tenant_id": "default", "email": "khach@example.com",
            "username": "khach", "password": "Mat-khau-dai-2026",
        }])

    def test_default_scope_matches_the_seed_migration(self) -> None:
        from importlib import import_module

        migration = import_module(
            "agentscope.app.storage._sql._alembic.versions.0016_default_workspace",
        )
        self.assertEqual(migration._DOMAIN_ID, AuthService.DEFAULT_DOMAIN_ID)
        self.assertEqual(migration._AREA_ID, AuthService.DEFAULT_AREA_ID)
