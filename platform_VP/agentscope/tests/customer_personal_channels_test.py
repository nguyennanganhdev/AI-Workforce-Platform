"""Personal bots can be configured without the operator's Discord OAuth app."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from agentscope.app._service._channel import ChannelService
from agentscope.app.channel import ChannelTypeRegistry, DiscordChannel, ZaloOAChannel, ChannelError
from agentscope.app.channel._secrets import open_credentials
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import ChannelBinding, RoutingConfig, SessionSettings
from vin_fixtures import authority  # noqa: F401


@pytest.mark.asyncio
async def test_personal_discord_bot_uses_verified_application_owner_without_platform_oauth(authority, monkeypatch):
    monkeypatch.delenv("DISCORD_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("DISCORD_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("CHANNEL_CREDENTIALS_KEY", "offline-encryption-fixture-" * 3)
    storage = SimpleNamespace(vin_platform_service=authority,
        get_channel_id_by_platform_bot_id=AsyncMock(return_value=None), upsert_channel=AsyncMock())
    calls = []

    def discord(request):
        calls.append(request.url.path)
        assert request.headers["Authorization"] == "Bot offline-bot-token"
        assert request.url.path == "/api/v10/applications/@me"
        return httpx.Response(200, json={"id": "1", "owner": {"id": "100"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(discord)) as client:
        authority.http_client = client
        service = ChannelService(storage, InMemoryMessageBus(), ChannelTypeRegistry([DiscordChannel]))
        record = await service.create(user_id="alice", channel_type="discord",
            credentials={"application_id": "1", "bot_token": "offline-bot-token"}, platform_config={"owner_user_id": "100"},
            routing=RoutingConfig(bindings=[ChannelBinding(agent_id="agent")]),
            session=SessionSettings(chat_model_config={}))
    assert record.user_id == "alice"
    assert record.platform_config["owner_user_id"] == "100"
    assert record.platform_config["allowed_user_ids"] == ["100"]
    assert record.platform_config["approver_user_ids"] == ["100"]
    storage.upsert_channel.assert_awaited_once()
    assert record.credentials["bot_token"].startswith("enc:v1:")
    assert open_credentials(record.credentials)["bot_token"] == "offline-bot-token"
    assert calls == ["/api/v10/applications/@me"]


@pytest.mark.asyncio
@pytest.mark.parametrize("response,code", [
    ({"id": "2", "owner": {"id": "100"}}, "DISCORD_APPLICATION_MISMATCH"),
    ({"id": "1", "owner": {}}, "DISCORD_BOT_OWNER_UNAVAILABLE"),
    (None, "DISCORD_BOT_VERIFICATION_FAILED"),
])
async def test_invalid_personal_bot_is_not_persisted(authority, response, code):
    storage = SimpleNamespace(vin_platform_service=authority,
        get_channel_id_by_platform_bot_id=AsyncMock(return_value=None), upsert_channel=AsyncMock())
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _request: httpx.Response(401) if response is None else httpx.Response(200, json=response))) as client:
        authority.http_client = client
        service = ChannelService(storage, InMemoryMessageBus(), ChannelTypeRegistry([DiscordChannel]))
        with pytest.raises(ChannelError, match=code):
            await service.create(user_id="alice", channel_type="discord",
                credentials={"application_id": "1", "bot_token": "offline-token"}, platform_config={"owner_user_id": "100"},
                routing=RoutingConfig(bindings=[ChannelBinding(agent_id="agent")]),
                session=SessionSettings(chat_model_config={}))
    storage.upsert_channel.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform_config,code", [
    ({}, "DISCORD_OWNER_REQUIRED"),
    # A bot built by someone else (agency, team owner) never becomes the customer's owner.
    ({"owner_user_id": "200"}, "DISCORD_OWNER_MISMATCH"),
])
async def test_personal_bot_owner_is_never_adopted_silently(authority, monkeypatch, platform_config, code):
    monkeypatch.delenv("DISCORD_OAUTH_CLIENT_ID", raising=False)
    storage = SimpleNamespace(vin_platform_service=authority,
        get_channel_id_by_platform_bot_id=AsyncMock(return_value=None), upsert_channel=AsyncMock())
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"id": "1", "owner": {"id": "100"}}))) as client:
        authority.http_client = client
        service = ChannelService(storage, InMemoryMessageBus(), ChannelTypeRegistry([DiscordChannel]))
        with pytest.raises(ChannelError, match=code):
            await service.create(user_id="alice", channel_type="discord",
                credentials={"application_id": "1", "bot_token": "offline-token"}, platform_config=platform_config,
                routing=RoutingConfig(bindings=[ChannelBinding(agent_id="agent")]),
                session=SessionSettings(chat_model_config={}))
    storage.upsert_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_customer_creates_own_zalo_oa_with_encrypted_credentials(authority, monkeypatch):
    monkeypatch.setenv("CHANNEL_CREDENTIALS_KEY", "offline-encryption-fixture-" * 3)
    storage = SimpleNamespace(vin_platform_service=authority,
        get_channel_id_by_platform_bot_id=AsyncMock(return_value=None), upsert_channel=AsyncMock())
    service = ChannelService(storage, InMemoryMessageBus(), ChannelTypeRegistry([ZaloOAChannel]))
    record = await service.create(user_id="alice", channel_type="zalo_oa",
        credentials={"oa_id": "1", "app_id": "2", "access_token": "offline-token", "oa_secret_key": "offline-secret"},
        platform_config={}, routing=RoutingConfig(bindings=[ChannelBinding(agent_id="agent")]),
        session=SessionSettings(chat_model_config={}))
    assert record.user_id == "alice"
    assert record.credentials["access_token"].startswith("enc:v1:")
    assert record.credentials["oa_secret_key"].startswith("enc:v1:")
