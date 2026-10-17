"""Private-bot access runs before attachment IO, dispatch and delivery."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from agentscope.app.channel import DiscordChannel, ChannelEvent


def channel(**config):
    value = DiscordChannel("private-bot", DiscordChannel.Credentials(bot_token="offline-fixture", application_id="1"),
        DiscordChannel.Config(**config))
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
    value = channel(allowed_user_ids=allowed)
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


def test_legacy_bot_compatibility_requires_flag_off_and_no_explicit_list(monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "false")
    assert channel().may_chat("100")
    assert not channel(allowed_user_ids=[]).may_chat("100")


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
