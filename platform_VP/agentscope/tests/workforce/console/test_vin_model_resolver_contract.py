"""Consumer/producer integration; runs when the C01-C03 owner package is present."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine

pytest.importorskip("agentscope.app.vin_platform", reason="Integrate the N1 authority package to run C01-C03 producer checks")

from agentscope.app._router._workforce_console import _model_config
from agentscope.app.vin_platform import QuotaPolicy, VinPlatformService
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
from agentscope.app.vin_platform._resources import PLATFORM_PROVIDER_ID


@pytest_asyncio.fixture
async def real_authority(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "consumer-contract.db"))
    async with engine.begin() as db:
        await db.run_sync(t.metadata.create_all)
        await db.execute(text("CREATE TABLE auth_users (id TEXT PRIMARY KEY, tenant_id TEXT, role TEXT, status TEXT)"))
        for user, role in [("service", "PLATFORM_ADMIN"), ("resident-a", "VIN_USER"), ("resident-b", "VIN_USER")]:
            await db.execute(text("INSERT INTO auth_users VALUES (:u,'tenant-a',:r,'active')"), {"u": user, "r": role})
            await db.execute(insert(t.accounts).values(user_id=user, tenant_id="tenant-a", eligible=True, revision=1))
    storage = SimpleNamespace(
        upsert_credential=AsyncMock(side_effect=AssertionError("user-owned credential write")),
        list_credentials=AsyncMock(side_effect=AssertionError("legacy credential fallback")),
    )
    service = VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), storage)
    storage.vin_platform_service = service
    admin = await service.context("service")
    catalog_id = await service.publish_catalog(admin, CatalogEntry(kind="credential", resource_id=PLATFORM_PROVIDER_ID,
        owner_id="service", name="Service provider", model_names=["offline-entitled-alias"]))
    grant = await service.grant(admin, ResourceGrant(catalog_id=catalog_id, subject_kind="role", subject_id="VIN_USER", permissions=["execute"]))
    await service.set_policy(admin, "role:VIN_USER", QuotaPolicy(daily_tokens=10000, monthly_tokens=100000,
        models=["offline-entitled-alias"], enabled=True, max_output_tokens=512))
    yield storage, service, admin, grant
    storage.upsert_credential.assert_not_awaited()
    storage.list_credentials.assert_not_awaited()
    await engine.dispose()


@pytest.mark.asyncio
async def test_two_users_resolve_one_service_provider_without_user_key_records(real_authority, monkeypatch):
    storage, service, _, _ = real_authority
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("WORKFORCE_MODEL_NAME", "unentitled-legacy-model")
    configs = [await _model_config(storage, user) for user in ("resident-a", "resident-b")]
    assert all(config.credential_id == PLATFORM_PROVIDER_ID and config.model == "offline-entitled-alias" for config in configs)
    assert all(config.parameters == {"max_tokens": 512} for config in configs)
    assert "api_key" not in json.dumps([config.model_dump(mode="json") for config in configs])
    folder = Path(".artifacts/vin-contract-fixtures")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "capabilities.json").write_text(json.dumps(await service.capabilities(await service.context("resident-a"))), encoding="utf-8")
    (folder / "usage.json").write_text(json.dumps(await service.quota.usage(await service.context("resident-a"))), encoding="utf-8")


@pytest.mark.asyncio
async def test_revoked_resource_cannot_resolve_a_new_console_or_studio_configuration(real_authority):
    storage, service, admin, grant = real_authority
    await _model_config(storage, "resident-a")
    await service.revoke_grant(admin, grant)
    with pytest.raises(HTTPException) as denied:
        await _model_config(storage, "resident-a")
    assert denied.value.status_code == 403
    assert denied.value.detail == "MODEL_NOT_ENTITLED"


@pytest.mark.asyncio
async def test_missing_policy_never_resolves_configuration_or_falls_back(real_authority):
    storage, service, _, _ = real_authority
    from sqlalchemy import delete

    async with service.engine.begin() as db:
        await db.execute(delete(t.policies))
    with pytest.raises(HTTPException) as denied:
        await _model_config(storage, "resident-a")
    assert denied.value.status_code == 403
