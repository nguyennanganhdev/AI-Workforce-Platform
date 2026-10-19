"""HTTP capability boundary and owner isolation with real persisted authority."""
from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from vin_fixtures import authority  # noqa: F401


@pytest.mark.asyncio
async def test_customer_skill_http_create_review_delete_and_hub_browse(authority, monkeypatch):
    from agentscope.app import create_app
    from agentscope.app import deps
    from agentscope.app.auth import AuthPrincipal

    records = {}
    async def save(user, record): records[(user, record.id)] = record
    async def load(user, ident): return records.get((user, ident))
    async def listing(user): return [record for (owner, _), record in records.items() if owner == user]
    async def remove(user, ident): return records.pop((user, ident), None) is not None
    storage = SimpleNamespace(get_skill_by_name=AsyncMock(return_value=None), upsert_skill=save,
        get_skill=load, list_skills=listing, delete_skill=remove)
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("VIN_PLATFORM_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    app = create_app(storage, MagicMock(), MagicMock(), auth_service=authority.auth,
        vin_platform_enabled=True, enable_scheduler=False, enable_channel_worker=False)
    principal = AuthPrincipal(user_id="alice", tenant_id="vin", session_id="fixture", token_id="fixture", role="VIN_USER")
    async def who(*args, **kwargs): return principal
    async def dependency(): return principal
    app.dependency_overrides[deps.get_current_principal] = dependency
    monkeypatch.setattr(deps, "get_current_principal", who)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        response = await client.post("/skill", json={"name":"private-procedure", "description":"Personal skill",
            "markdown":"# Procedure\nRead the request and verify the supplied information before answering."})
        assert response.status_code == 201, response.text
        ident = response.json()["id"]
        approved = await client.post(f"/skill/{ident}/review", json={"status":"approved"})
        assert approved.status_code == 200 and approved.json()["enabled"]
        assert (await client.get("/skill")).json()[0]["editable"]
        assert (await client.get("/hub/skill")).status_code == 200
        principal = replace(principal, user_id="bob")
        assert (await client.get("/skill")).json() == []
        assert (await client.delete(f"/skill/{ident}")).status_code == 404
        assert (await client.post(f"/skill/{ident}/review", json={"status":"revoked"})).status_code == 404
        principal = replace(principal, user_id="alice")
        assert (await client.delete(f"/skill/{ident}")).status_code == 204
