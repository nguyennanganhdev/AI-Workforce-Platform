"""Final SDK-boundary tests with fake credentials and no network provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from vin_platform_authority_test import authority as authority  # noqa: F401
from agentscope.app.vin_platform import PlatformError, QuotaPolicy
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
from agentscope.app.vin_platform._model_guard import ModelQuotaGuard
from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel, OpenAIResponseModel
from agentscope.model._call_observer import observed_call


async def model_for(service, cls=OpenAIChatModel):
    admin = await service.context("admin")
    await service.set_policy(admin, "role:VIN_USER", QuotaPolicy(daily_tokens=20000, monthly_tokens=30000,
        max_output_tokens=100, models=["test-model"], enabled=True))
    catalog = await service.publish_catalog(admin, CatalogEntry(kind="credential", resource_id="provider",
        owner_id="admin", name="Test", model_names=["test-model"]))
    grant = await service.grant(admin, ResourceGrant(catalog_id=catalog, subject_kind="user", subject_id="alice",
        permissions=["view", "execute"]))
    model = cls(credential=OpenAICredential(api_key="fake-offline-key"), model="test-model", stream=False)
    model._quota_guard = ModelQuotaGuard(service, "alice", "provider")
    endpoint = AsyncMock(return_value=SimpleNamespace())
    if cls is OpenAIChatModel:
        model.client.chat.completions.create = endpoint
    else:
        model.client.responses.create = endpoint
    from agentscope.model import ChatResponse, ChatUsage
    model._parse_completion_response = lambda *a: ChatResponse(content=[], is_last=True, usage=ChatUsage(input_tokens=10, output_tokens=5, time=0))
    return model, endpoint, grant


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", [OpenAIChatModel, OpenAIResponseModel])
async def test_exact_payload_cap_settlement_and_revoke(authority, cls):
    model, endpoint, grant = await model_for(authority, cls)
    await observed_call(model, model._call_api, "test-model", messages=[UserMsg(name="user", content="hello")], max_tokens=9000)
    kwargs = endpoint.call_args.kwargs
    assert kwargs.get("max_completion_tokens", kwargs.get("max_output_tokens")) == 100
    assert model.client.max_retries == 0
    assert all(b["used"] == 15 and b["reserved"] == 0 for b in (await authority.quota.usage(await authority.context("alice")))["buckets"])
    await authority.revoke_grant(await authority.context("admin"), grant)
    with pytest.raises(PlatformError, match="MODEL_NOT_ENTITLED"):
        await observed_call(model, model._call_api, "test-model", messages=[])
    assert endpoint.await_count == 1
    await model.client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [{"extra_body": {"max_completion_tokens": 999999}},
    {"extra_body": {"model": "other"}}, {"n": 4}, {"audio": {"voice": "alloy"}},
    {"previous_response_id": "hidden-context"}, {"max_tokens": -1}])
async def test_unbounded_payload_never_reaches_provider(authority, override):
    model, endpoint, _ = await model_for(authority)
    with pytest.raises(PlatformError):
        await observed_call(model, model._call_api, "test-model", messages=[], **override)
    endpoint.assert_not_awaited()
    assert (await authority.quota.usage(await authority.context("alice")))["buckets"] == []
    await model.client.close()


@pytest.mark.asyncio
async def test_final_tools_and_retrieval_are_reserved_before_call(authority):
    model, endpoint, _ = await model_for(authority)
    with pytest.raises(PlatformError, match="QUOTA_EXCEEDED"):
        await observed_call(model, model._call_api, "test-model", messages=[UserMsg(name="user", content="r" * 25000)])
    endpoint.assert_not_awaited()
    with pytest.raises(PlatformError, match="PROVIDER_ATTEMPT_REQUIRED"):
        await model._call_api("test-model", messages=[])
    endpoint.assert_not_awaited()
    await model.client.close()


@pytest.mark.asyncio
async def test_embedding_override_denied_without_io(authority):
    from agentscope.app.vin_platform._embedding_guard import embedding_attempt
    model = SimpleNamespace(_vin_authority=authority, _vin_user_id="alice", _call_api=AsyncMock())
    # Unsupported adapter/input is rejected even before the override check.
    with pytest.raises(PlatformError):
        await embedding_attempt(model, ["hello"], {"input": ["another-payload"]})
    model._call_api.assert_not_awaited()
