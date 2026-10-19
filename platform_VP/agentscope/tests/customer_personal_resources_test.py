"""Customer-owned providers stay separate from the managed platform catalog."""

import pytest
from fastapi import HTTPException
from types import SimpleNamespace
from unittest.mock import AsyncMock

from agentscope.app._service import ResourceAccessService
from agentscope.app.access import ResourceKind
from agentscope.app.storage import CredentialRecord
from agentscope.app.vin_platform._resources import PersistedResourcePolicy
from agentscope.app.vin_platform._resources import resolve_platform_credential
from resource_access_policy_test import _FakeStorage
from vin_fixtures import authority  # noqa: F401


@pytest.mark.asyncio
async def test_customer_can_manage_private_provider_without_managing_catalog(authority):
    context = await authority.context("alice")
    view = await authority.capabilities(context)
    assert view["capabilities"]["providers.private.manage"] is True
    assert view["capabilities"]["providers.manage"] is False


@pytest.mark.asyncio
async def test_personal_provider_uses_owner_access_instead_of_a_shared_catalog_grant(authority):
    # None means normal owner-isolated credential resolution continues. It must
    # not demand a grant for a key the customer added to their own account.
    assert await resolve_platform_credential(authority, "alice", "personal-provider") is None


@pytest.mark.asyncio
async def test_personal_key_is_visible_editable_and_usable_only_by_its_owner(authority):
    storage = _FakeStorage()
    storage.vin_platform_service = authority
    authority.storage = storage
    storage.credentials[("alice", "personal")] = CredentialRecord(
        id="personal", user_id="alice",
        data={"type": "openai_credential", "name": "My provider", "api_key": "offline-private-key"},
    )
    access = ResourceAccessService(storage, PersistedResourcePolicy(authority))
    listed = await access.list_resource("alice", ResourceKind.CREDENTIAL)
    assert len(listed) == 1 and listed[0].editable
    assert "api_key" not in listed[0].data
    owner, _ = await access.resolve_for_edit("alice", ResourceKind.CREDENTIAL, "personal")
    assert owner == "alice"
    assert (await access.resolve_credential("alice", "personal")).data["api_key"] == "offline-private-key"
    assert await access.list_resource("bob", ResourceKind.CREDENTIAL) == []
    with pytest.raises(HTTPException) as denied:
        await access.resolve_credential("bob", "personal")
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException):
        await access.resolve_for_edit("bob", ResourceKind.CREDENTIAL, "personal")


@pytest.mark.asyncio
async def test_legacy_managed_key_never_becomes_an_editable_private_provider(authority):
    storage = _FakeStorage()
    storage.vin_platform_service = authority
    authority.storage = storage
    storage.credentials[("alice", "legacy")] = CredentialRecord(
        id="legacy", user_id="alice",
        data={"type": "openai_credential", "name": "Managed", "secret_ref": "vin:platform-openai"},
    )
    access = ResourceAccessService(storage, PersistedResourcePolicy(authority))
    assert not (await access.get_resource("alice", ResourceKind.CREDENTIAL, "legacy")).editable
    with pytest.raises(HTTPException):
        await access.resolve_for_edit("alice", ResourceKind.CREDENTIAL, "legacy")
    with pytest.raises(HTTPException):
        await access.resolve_credential("alice", "legacy")


@pytest.mark.asyncio
async def test_editing_provider_name_preserves_the_write_only_key():
    from agentscope.app._router._credential import update_credential
    from agentscope.app._router._schema._credential import UpdateCredentialRequest

    original = CredentialRecord(id="personal", user_id="alice", data={
        "type": "openai_credential", "name": "Old", "api_key": "offline-private-key",
        "base_url": "https://fixture.invalid/v1",
    })
    storage = SimpleNamespace(upsert_credential=AsyncMock(), get_credential=AsyncMock(return_value=original))
    access = SimpleNamespace(resolve_for_edit=AsyncMock(return_value=("alice", original)))
    await update_credential("personal", UpdateCredentialRequest(data={"type": "openai_credential", "name": "New"}),
                            "alice", storage, access)
    credential = storage.upsert_credential.call_args.args[1]
    assert credential.api_key.get_secret_value() == "offline-private-key"
    assert credential.base_url == "https://fixture.invalid/v1"


@pytest.mark.asyncio
async def test_private_model_runs_with_its_owner_key_and_keeps_quota_and_revocation(authority):
    from vin_provider_boundary_test import model_for
    from agentscope.app.vin_platform import PlatformError
    from agentscope.app.vin_platform._model_guard import ModelQuotaGuard
    from agentscope.model._call_observer import observed_call

    model, endpoint, _ = await model_for(authority)
    storage = _FakeStorage()
    storage.credentials[("alice", "personal")] = CredentialRecord(
        id="personal", user_id="alice", data={"type": "openai_credential", "api_key": "offline-private-key"},
    )
    authority.storage = storage
    model._quota_guard = ModelQuotaGuard(authority, "alice", "personal")
    try:
        await observed_call(model, model._call_api, "private-model", messages=[])
        assert endpoint.call_args.kwargs["model"] == "private-model"
        assert endpoint.call_args.kwargs["max_completion_tokens"] == 100
        usage = await authority.quota.usage(await authority.context("alice"))
        assert all(bucket["used"] == 15 and bucket["reserved"] == 0 for bucket in usage["buckets"])
        with pytest.raises(PlatformError, match="MODEL_NOT_ENTITLED"):
            await authority.quota.reserve(await authority.context("bob"), budget=1, purpose="chat", model="private-model", private_credential_id="personal")
        storage.credentials.pop(("alice", "personal"))
        with pytest.raises(PlatformError, match="MODEL_NOT_ENTITLED"):
            await observed_call(model, model._call_api, "private-model", messages=[])
        assert endpoint.await_count == 1
    finally:
        await model.client.close()


@pytest.mark.parametrize("data", [{"id": "vin-platform-openai"}, {"secret_ref": "vin:platform-openai"}])
def test_personal_credential_payload_cannot_replace_managed_provider(data):
    from agentscope.app._router._credential import _private_payload
    with pytest.raises(HTTPException) as denied:
        _private_payload(data)
    assert denied.value.status_code == 403
