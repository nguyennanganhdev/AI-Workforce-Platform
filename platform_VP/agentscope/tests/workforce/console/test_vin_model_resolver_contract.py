"""Consumer/producer integration; runs when the C01-C03 owner package is present."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select

pytest.importorskip("vin_fixtures", reason="C01-C03 requires the committed N1 shared production-schema fixture")
from vin_fixtures import authority as authority, seed_policy_catalog

from agentscope.app._router._workforce_console import _model_config
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._contracts import ResourceGrant
from agentscope.app.vin_platform._resources import PLATFORM_PROVIDER_ID


@pytest_asyncio.fixture
async def real_authority(authority, monkeypatch):
    """Use N1's production auth migrations and opt-in catalog/policy fixture."""
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    storage = authority.storage
    storage.upsert_credential = AsyncMock(side_effect=AssertionError("user-owned credential write"))
    storage.list_credentials = AsyncMock(side_effect=AssertionError("legacy credential fallback"))
    storage.vin_platform_service = authority
    await seed_policy_catalog(authority, model="offline-entitled-alias")
    admin = await authority.context("admin")
    catalog = (await authority.catalog(await authority.context("alice"), "credential", "execute"))[0]
    await authority.grant(admin, ResourceGrant(catalog_id=catalog["catalog_id"], subject_kind="user",
        subject_id="bob", permissions=["execute"]))
    async with authority.engine.connect() as db:
        grant = (await db.execute(select(t.grants.c.id).where(t.grants.c.subject_id == "alice"))).scalar_one()
    yield storage, authority, admin, grant
    storage.upsert_credential.assert_not_awaited()
    storage.list_credentials.assert_not_awaited()


@pytest.mark.asyncio
async def test_two_users_resolve_one_service_provider_without_user_key_records(real_authority, monkeypatch):
    storage, service, _, _ = real_authority
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("WORKFORCE_MODEL_NAME", "unentitled-legacy-model")
    configs = [await _model_config(storage, user) for user in ("alice", "bob")]
    assert all(config.credential_id == PLATFORM_PROVIDER_ID and config.model == "offline-entitled-alias" for config in configs)
    assert all(config.parameters == {"max_tokens": 256} for config in configs)
    assert "api_key" not in json.dumps([config.model_dump(mode="json") for config in configs])
    folder = Path(".artifacts/vin-contract-fixtures")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "capabilities.json").write_text(json.dumps(await service.capabilities(await service.context("alice"))), encoding="utf-8")
    (folder / "usage.json").write_text(json.dumps(await service.quota.usage(await service.context("alice"))), encoding="utf-8")


@pytest.mark.asyncio
async def test_revoked_resource_cannot_resolve_a_new_console_or_studio_configuration(real_authority):
    storage, service, admin, grant = real_authority
    await _model_config(storage, "alice")
    await service.revoke_grant(admin, grant)
    with pytest.raises(HTTPException) as denied:
        await _model_config(storage, "alice")
    assert denied.value.status_code == 403
    assert denied.value.detail == "MODEL_NOT_ENTITLED"


@pytest.mark.asyncio
async def test_missing_policy_never_resolves_configuration_or_falls_back(real_authority):
    storage, service, _, _ = real_authority
    from sqlalchemy import delete

    async with service.engine.begin() as db:
        await db.execute(delete(t.policies))
    with pytest.raises(HTTPException) as denied:
        await _model_config(storage, "alice")
    assert denied.value.status_code == 403
