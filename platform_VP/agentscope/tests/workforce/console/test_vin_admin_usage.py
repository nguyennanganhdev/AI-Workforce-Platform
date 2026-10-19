"""Admin UI usage consumer delegates to authority and fences tenant/workspace."""

import pytest
from fastapi import HTTPException

from vin_fixtures import authority as authority, seed_policy_catalog  # noqa: F401
from agentscope.app._router._workforce_console import admin_vin_usage


@pytest.mark.asyncio
async def test_admin_reads_effective_customer_limits_without_secrets(authority, monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    await seed_policy_catalog(authority)
    authority.storage.vin_platform_service = authority
    view = await admin_vin_usage("alice", "admin", authority.storage)
    assert view["policy_revision"] == 1 and len(view["effective_limits"]) == 3
    assert all(item["subject"] == "user:alice" and item["remaining"] == item["limit"] for item in view["effective_limits"])


@pytest.mark.asyncio
@pytest.mark.parametrize("caller,target", [("alice", "bob"), ("admin", "other")])
async def test_customer_or_foreign_tenant_cannot_use_admin_usage(authority, monkeypatch, caller, target):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    authority.storage.vin_platform_service = authority
    with pytest.raises(HTTPException) as error:
        await admin_vin_usage(target, caller, authority.storage)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_disabled_vin_has_no_admin_usage_fallback(authority, monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "false")
    with pytest.raises(HTTPException) as error:
        await admin_vin_usage("alice", "admin", authority.storage)
    assert error.value.status_code == 503
