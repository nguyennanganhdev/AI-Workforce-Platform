"""Private-bot access runs before attachment IO, dispatch and delivery."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from vin_fixtures import authority as authority  # noqa: F401

from agentscope.app.channel import DiscordChannel, ChannelEvent, ChannelTypeRegistry
from agentscope.app._service._channel import ChannelService
from agentscope.app.channel._errors import ChannelError


def channel(*, private_account=False, **config):
    value = DiscordChannel("private-bot", DiscordChannel.Credentials(bot_token="offline-fixture", application_id="1"),
        DiscordChannel.Config(**config), private_account=private_account)
    value._emit = AsyncMock()
    value._client = SimpleNamespace(user=SimpleNamespace(id=999))
    return value


def message(user=100, *, guild=None, attachments=()):
    return SimpleNamespace(id=7, author=SimpleNamespace(id=user), guild=guild,
        channel=SimpleNamespace(id=77), content="hello", attachments=list(attachments), mentions=[])


@pytest.mark.asyncio
@pytest.mark.parametrize("allowed", [None, [], ["200"]])
async def test_denied_user_never_downloads_or_emits(monkeypatch, allowed):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    value = channel(private_account=True, allowed_user_ids=allowed)
    attachment = SimpleNamespace(read=AsyncMock())
    await value._on_message(message(attachments=[attachment]))
    attachment.read.assert_not_awaited()
    value._emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_allowlisted_owner_dm_emits_but_guild_does_not(monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    value = channel(allowed_user_ids=["100"])
    await value._on_message(message())
    event = value._emit.await_args.args[0]
    assert event.channel_user_id == "100" and event.metadata["chat_type"] == "dm"
    value._emit.reset_mock()
    attachment = SimpleNamespace(read=AsyncMock())
    await value._on_message(message(guild=object(), attachments=[attachment]))
    attachment.read.assert_not_awaited()
    value._emit.assert_not_awaited()


def test_removed_users_cannot_approve_even_if_previously_requester_or_approver(monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    value = channel(allowed_user_ids=["100"], approver_user_ids=["200"])
    assert value.may_decide("100", "100")
    assert not value.may_decide("200", "100")
    value._config.allowed_user_ids = []
    assert not value.may_decide("100", "100")


@pytest.mark.parametrize("flag", ["false", "true"])
def test_bot_privacy_uses_owner_and_explicit_list_independently_of_global_flag(monkeypatch, flag):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", flag)
    assert channel().may_chat("100")
    assert not channel(private_account=True).may_chat("100")
    assert not channel(allowed_user_ids=[]).may_chat("100")


@pytest.mark.asyncio
async def test_vin_enabled_bql_bot_without_list_still_answers_guild_mention(monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    registry = ChannelTypeRegistry([DiscordChannel])
    storage = SimpleNamespace(vin_platform_service=SimpleNamespace(context=AsyncMock(return_value=SimpleNamespace(role="AREA_MANAGER"))))
    record = SimpleNamespace(channel_type="discord", id="bql-bot", user_id="manager", platform_config={},
        credentials={"bot_token": "offline-fixture", "application_id": "1"})
    value = await registry.create_for_record(storage, record)
    value._emit = AsyncMock()
    value._client = SimpleNamespace(user=SimpleNamespace(id=999))
    inbound = message(guild=object())
    inbound.mentions = [value._client.user]
    inbound.content = "<@999> hello"
    await value._on_message(inbound)
    value._emit.assert_awaited_once()
    assert value._emit.await_args.args[0].metadata["chat_type"] == "guild"
    storage.vin_platform_service.context.return_value = SimpleNamespace(role="VIN_USER")
    customer = await registry.create_for_record(storage, record)
    assert customer.private_access_required and not customer.may_chat("100")


@pytest.mark.asyncio
async def test_customer_channel_creation_requires_owner_and_defaults_access_to_owner(authority):
    from agentscope.app._service._discord_identity import _identity_id
    storage = authority.storage
    storage.vin_platform_service = authority
    context = await authority.context("alice")
    service = ChannelService(storage, None, ChannelTypeRegistry([DiscordChannel]))
    with pytest.raises(ChannelError) as missing:
        await service._discord_config("alice", "discord", {}, creating=True)
    assert missing.value.status_code == 403
    await authority.automation_put(context, _identity_id(context), "channel", {"state": "verified", "discord_user_id": "100", "verified_at": 1})
    config = await service._discord_config("alice", "discord", {}, creating=True)
    assert config["allowed_user_ids"] == config["approver_user_ids"] == ["100"]
    assert config["owner_user_id"] == "100"
    with pytest.raises(ChannelError, match="DISCORD_OWNER_MISMATCH"):
        await service._discord_config("alice", "discord", {"owner_user_id": "200"}, creating=True)
    with pytest.raises(ChannelError):
        await service._discord_config("alice", "discord", {"owner_user_id": "100", "allowed_user_ids": []}, creating=True)
    # An existing channel may deliberately block everyone.
    assert (await service._discord_config("alice", "discord", {"allowed_user_ids": []}))["allowed_user_ids"] == []


@pytest.mark.parametrize("ident", ["", "0", "abc", "1 2", "-1", "１", "1" * 21])
def test_invalid_user_id_is_rejected(ident):
    with pytest.raises(ValidationError):
        DiscordChannel.Config(allowed_user_ids=[ident])


@pytest.mark.asyncio
async def test_private_delivery_refuses_guild_and_unknown_recipient_before_network(monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    value = channel(allowed_user_ids=["100"])
    value._channel = AsyncMock(side_effect=AssertionError("No Discord request allowed"))
    for user, kind in [("200", "dm"), ("100", "guild"), ("100", "unknown")]:
        event = ChannelEvent(channel_id="private-bot", channel_user_id=user,
            chat_id="77", channel_message_id="7", content=[], metadata={"chat_type": kind})
        await value.send_response(event, None)
    value._channel.assert_not_awaited()
