"""Telegram/Zalo contracts with scripted HTTP; no provider/model credentials."""
import asyncio
import hashlib
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from agentscope.app import deps
from agentscope.app._router._channel import channel_router
from agentscope.app._service._channel import ChannelService
from agentscope.app.channel import (ChannelClients, ChannelEvent, ChannelTypeRegistry, DingTalkChannel,
    DiscordChannel, FeishuChannel, TelegramChannel, ZaloOAChannel, ChannelGateway, ChannelConfirmationResultEvent)
from agentscope.app.channel._errors import ChannelError
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.storage import RoutingConfig, ChannelBinding, SessionSettings
from agentscope.message import TextBlock, ToolCallBlock
from agentscope.event import RequireUserConfirmEvent


def telegram(**config):
    value = TelegramChannel("tg", TelegramChannel.Credentials(bot_id="123", bot_token="123:offline"),
                            TelegramChannel.Config(**config))
    value.bind_message_bus(InMemoryMessageBus())
    return value


def zalo(**config):
    value = ZaloOAChannel("za", ZaloOAChannel.Credentials(oa_id="456", app_id="789",
        access_token="offline-token", oa_secret_key="offline-secret"), ZaloOAChannel.Config(**config))
    value.bind_message_bus(InMemoryMessageBus())
    return value


def inbound(chat="7", user="10"):
    return ChannelEvent(channel_id="tg", chat_id=chat, channel_user_id=user,
                        metadata={"agent_id": "agent", "session_id": "session"})


def tg_update(text="Xin chào", chat_type="private", **extra):
    return {"update_id": 4, "message": {"message_id": 2, "chat": {"id": 7, "type": chat_type},
        "from": {"id": 10, "first_name": "Người gửi"}, "text": text, **extra}}


def webhook(**changes):
    data = {"app_id": "789", "recipient": {"id": "456"}, "sender": {"id": "10"},
        "timestamp": str(int(time.time() * 1000)), "event_name": "user_send_text",
        "message": {"msg_id": "msg-1", "text": "Xin chào"}, **changes}
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    signature = hashlib.sha256(b"789" + raw + str(data["timestamp"]).encode() + b"offline-secret").hexdigest()
    return raw, "mac=" + signature


def test_new_catalog_hides_legacy_without_removing_runtime_types():
    registry = ChannelTypeRegistry([DingTalkChannel, DiscordChannel, FeishuChannel, TelegramChannel, ZaloOAChannel])
    assert [item.channel_type for item in registry.list_types()] == ["discord", "telegram", "zalo_oa"]
    assert registry.has_type("feishu") and registry.has_type("dingtalk")


@pytest.mark.parametrize("channel_type,credentials,fields", [
    ("telegram", {"bot_id": "123", "bot_token": "123:offline"}, ["bot_token"]),
    ("zalo_oa", {"oa_id": "456", "app_id": "789", "access_token": "offline-token", "oa_secret_key": "offline-secret"},
     ["access_token", "oa_secret_key"]),
])
def test_new_channel_secrets_round_trip_encrypted(channel_type, credentials, fields):
    registry = ChannelTypeRegistry([TelegramChannel, ZaloOAChannel])
    with patch.dict(os.environ, {"CHANNEL_CREDENTIALS_KEY": "k" * 40}):
        sealed = registry.seal_credentials(channel_type, credentials)
        for field in fields:
            assert sealed[field] != credentials[field]
        adapter = registry.create_channel(channel_type, "c", sealed, {})
        assert adapter._credentials.model_dump() == credentials


@pytest.mark.asyncio
async def test_invalid_token_is_rejected_before_persistence_without_leaking_the_token():
    storage = SimpleNamespace(upsert_channel=AsyncMock())
    service = ChannelService(storage, InMemoryMessageBus(), ChannelTypeRegistry([TelegramChannel]))
    with pytest.raises(ChannelError) as caught:
        await service.create(user_id="u", channel_type="telegram", credentials={"bot_id": "123", "bot_token": "456:secret"},
            platform_config={}, routing=RoutingConfig(bindings=[ChannelBinding(agent_id="a")]),
            session=SessionSettings(chat_model_config={}))
    assert "secret" not in str(caught.value)
    storage.upsert_channel.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_receives_text_and_filters_bots_groups_and_allowlists():
    adapter, emit = telegram(), AsyncMock()
    await adapter._update(tg_update(), emit)
    assert emit.await_args.args[0].message == "Xin chào"
    emit.reset_mock()
    await adapter._update(tg_update(chat_type="supergroup"), emit, "my_bot")
    emit.assert_not_called()
    await adapter._update(tg_update("@my_bot Xin chào", "supergroup"), emit, "my_bot")
    assert emit.await_args.args[0].message == "Xin chào"
    emit.reset_mock()
    restricted = telegram(allowed_user_ids=["20"])
    await restricted._update(tg_update(), emit)
    emit.assert_not_called()
    restricted = telegram(allowed_chat_ids=["20"])
    await restricted._update(tg_update(), emit)
    emit.assert_not_called()
    await adapter._update(tg_update(**{"from": {"id": 10, "is_bot": True}}), emit)
    emit.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_persists_cursor_only_after_a_processed_update_and_resumes_it():
    adapter, emit = telegram(), AsyncMock()
    calls = []

    async def api(method, **payload):
        calls.append((method, payload))
        if method == "getMe":
            return {"id": 123, "username": "my_bot"}
        if len(calls) == 2:
            return [tg_update()]
        raise asyncio.CancelledError

    adapter._api = api
    with pytest.raises(asyncio.CancelledError):
        await adapter.start_listening(emit)
    assert await adapter._bus.registry_get(MessageBusKeys.channel_poll_cursor("tg"), "offset") == "5"
    assert calls[-1][1]["offset"] == 5
    emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_retries_a_transient_startup_failure_without_losing_cursor():
    adapter = telegram()
    adapter._api = AsyncMock(side_effect=[ChannelError("offline temporary failure", 502), {"id": 123}, asyncio.CancelledError])
    with patch("agentscope.app.channel._telegram._channel.asyncio.sleep", new_callable=AsyncMock) as sleep:
        with pytest.raises(asyncio.CancelledError):
            await adapter.start_listening(AsyncMock())
    sleep.assert_awaited_once_with(1)
    assert adapter._api.await_args.args[0] == "getUpdates"


@pytest.mark.asyncio
async def test_telegram_http_payload_and_errors_never_include_token():
    adapter, seen = telegram(), []

    def provider(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 3}})

    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
    await adapter._send_text("7", "Kết quả")
    assert seen == [{"chat_id": "7", "text": "Kết quả"}]
    await adapter.aclose()


@pytest.mark.asyncio
async def test_telegram_request_log_redacts_the_token(caplog):
    adapter = telegram()
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True, "result": {}})))
    with caplog.at_level("INFO", logger="httpx"):
        await adapter._send_text("7", "x")
    assert "123:offline" not in caplog.text and "[redacted]" in caplog.text
    await adapter.aclose()

    def failure(request):
        raise httpx.ConnectError("123:offline", request=request)

    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(failure))
    with pytest.raises(ChannelError) as caught:
        await adapter._send_text("7", "x")
    assert "offline" not in str(caught.value)
    await adapter.aclose()


@pytest.mark.asyncio
async def test_approval_survives_another_adapter_and_rejects_other_chat_user_and_replay():
    first = telegram(approver_user_ids=["30"])
    token = await first._approval(inbound(), ToolCallBlock(id="call", name="write", input="{}"))
    second, emit = telegram(approver_user_ids=["30"]), AsyncMock()
    second.bind_message_bus(first._bus)
    assert "không có quyền" in await second.decision(token, True, inbound(user="20"), emit)
    assert "không có quyền" in await second.decision(token, True, inbound(chat="8"), emit)
    emit.assert_not_called()
    await second.decision(token, False, inbound(user="30"), emit)
    event = emit.await_args.args[0]
    assert (event.agent_id, event.session_id, event.tool_call_id, event.approved, event.actor, event.channel_user_id) == (
        "agent", "session", "call", False, "30", "10")
    assert "hết hạn" in await second.decision(token, True, inbound(), emit)
    emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_buttons_acknowledge_and_do_not_turn_decisions_into_user_messages():
    adapter, emit = telegram(), AsyncMock()
    token = await adapter._approval(inbound(), ToolCallBlock(id="call", name="write", input="{}"))
    adapter._api = AsyncMock()
    await adapter._send_approval("7", "write", token)
    markup = adapter._api.await_args.kwargs["reply_markup"]
    assert len(markup["inline_keyboard"][0][0]["callback_data"].encode()) <= 64
    await adapter._update({"callback_query": {"id": "q", "from": {"id": 10},
        "message": {"chat": {"id": 7}}, "data": f"wf:a:{token}"}}, emit)
    assert emit.await_args.args[0].approved is True
    assert adapter._api.await_args.args[0] == "answerCallbackQuery"


@pytest.mark.asyncio
async def test_zalo_uses_exact_raw_body_signature_and_oa_binding():
    adapter = zalo()
    raw, signature = webhook()
    data = adapter.verify_webhook(raw, signature)
    assert adapter.webhook_event(data).message == "Xin chào"
    for body, sign in [(raw + b" ", signature), webhook(timestamp="1000"), webhook(recipient={"id": "999"})]:
        with pytest.raises(ChannelError):
            adapter.verify_webhook(body, sign)
    with pytest.raises(ChannelError):
        adapter.verify_webhook(b"not-json", signature)
    assert adapter.webhook_event({"event_name": "oa_send_text"}) is None
    raw, signature = webhook(event_name="oa_send_text", sender={"id": "456"}, recipient={"id": "10"})
    assert adapter.webhook_event(adapter.verify_webhook(raw, signature)) is None


@pytest.mark.asyncio
async def test_zalo_text_reply_and_explicit_approval_command():
    adapter, seen, emit = zalo(), [], AsyncMock()

    def provider(request):
        assert request.headers["access_token"] == "offline-token"
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"error": 0, "data": {"message_id": "r1"}})

    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
    await adapter._send_text("10", "Kết quả")
    assert seen[0] == {"recipient": {"user_id": "10"}, "message": {"text": "Kết quả"}}
    event = inbound(chat="10")
    token = await adapter._approval(event, ToolCallBlock(id="call", name="write", input="{}"))
    event.content = [TextBlock(text="TUCHOI " + token)]
    await adapter.receive_text(event, emit)
    assert emit.await_args.args[0].approved is False
    await adapter.aclose()


@pytest.mark.asyncio
async def test_streamed_approval_is_delivered_without_executing_a_tool():
    adapter = zalo()
    adapter._send_text = AsyncMock()

    async def events():
        yield RequireUserConfirmEvent(reply_id="reply", tool_calls=[ToolCallBlock(id="call", name="write", input="{}")]).model_dump(mode="json")

    await adapter.send_response(inbound(), events())
    assert "DUYET" in adapter._send_text.await_args.args[1]


@pytest.mark.asyncio
async def test_webhook_route_authenticates_deduplicates_and_retries_failed_delivery():
    adapter, bus = zalo(), InMemoryMessageBus()
    adapter.bind_message_bus(bus)
    app = FastAPI()
    app.include_router(channel_router)
    app.dependency_overrides.update({deps.get_channel_clients: lambda: SimpleNamespace(get=AsyncMock(return_value=adapter)),
        deps.get_message_bus: lambda: bus, deps.get_storage: lambda: object(), deps.get_workspace_manager: lambda: object()})
    raw, signature = webhook()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        with patch("agentscope.app.channel.ChannelGateway.process", new_callable=AsyncMock) as process:
            response = await client.post("/channels/za/webhook", content=raw)
            assert response.status_code == 401
            process.assert_not_called()
            process.side_effect = RuntimeError("storage unavailable")
            response = await client.post("/channels/za/webhook", content=raw, headers={"X-ZEvent-Signature": signature})
            assert response.status_code == 503
            process.side_effect = None
            response = await client.post("/channels/za/webhook", content=raw, headers={"X-ZEvent-Signature": signature})
            assert response.json()["status"] == "accepted"
            response = await client.post("/channels/za/webhook", content=raw, headers={"X-ZEvent-Signature": signature})
            assert response.json()["status"] == "duplicate"
            assert process.await_count == 2
            assert process.await_args.kwargs == {"raise_errors": True}


@pytest.mark.asyncio
async def test_webhook_disabled_channel_and_oversized_body_are_rejected():
    app = FastAPI()
    app.include_router(channel_router)
    clients = SimpleNamespace(get=AsyncMock(return_value=None))
    app.dependency_overrides.update({deps.get_channel_clients: lambda: clients,
        deps.get_message_bus: lambda: InMemoryMessageBus(), deps.get_storage: lambda: object(),
        deps.get_workspace_manager: lambda: object()})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/channels/za/webhook", content=b"{}")).status_code == 404
        clients.get.return_value = zalo()
        assert (await client.post("/channels/za/webhook", content=b"x" * 262145)).status_code == 413


@pytest.mark.asyncio
async def test_token_rotation_keeps_channel_and_routing_and_refreshes_the_cached_client():
    registry, bus = ChannelTypeRegistry([TelegramChannel]), InMemoryMessageBus()
    storage = SimpleNamespace(get_channel_id_by_platform_bot_id=AsyncMock(return_value=None),
        upsert_channel=AsyncMock(), get_channel=AsyncMock())
    service = ChannelService(storage, bus, registry)
    with patch.dict(os.environ, {"CHANNEL_CREDENTIALS_KEY": "k" * 40}):
        record = await service.create(user_id="u", channel_type="telegram",
            credentials={"bot_id": "123", "bot_token": "123:offline"}, platform_config={},
            routing=RoutingConfig(bindings=[ChannelBinding(agent_id="agent")]),
            session=SessionSettings(chat_model_config={}))
        storage.get_channel.return_value = record
        clients = ChannelClients(storage, bus, registry)
        old = await clients.get(record.id)
        updated = await service.rotate_secrets(record.id, {"bot_token": "123:rotated"})
        assert updated.id == record.id and updated.routing == record.routing and updated.session == record.session
        assert "rotated" not in updated.credentials["bot_token"]
        storage.get_channel.return_value = updated
        fresh = await clients.get(record.id)
        assert fresh is not old and fresh._credentials.bot_token == "123:rotated"
        for changes in ({"bot_token": "456:wrong-bot"}, {"bot_id": "456"}, {"bot_token": ""}):
            with pytest.raises(ChannelError):
                await service.rotate_secrets(record.id, changes)


@pytest.mark.asyncio
async def test_token_rotation_is_owner_scoped_and_response_never_returns_secrets():
    registry, bus = ChannelTypeRegistry([ZaloOAChannel]), InMemoryMessageBus()
    storage = SimpleNamespace(get_channel_id_by_platform_bot_id=AsyncMock(return_value=None),
        upsert_channel=AsyncMock(), get_channel=AsyncMock())
    service = ChannelService(storage, bus, registry)
    record = await service.create(user_id="owner", channel_type="zalo_oa", credentials=zalo()._credentials.model_dump(),
        platform_config={}, routing=RoutingConfig(bindings=[ChannelBinding(agent_id="agent")]),
        session=SessionSettings(chat_model_config={}))
    storage.get_channel.return_value = record
    app = FastAPI()
    app.include_router(channel_router)
    app.dependency_overrides.update({deps.get_current_user_id: lambda: "other", deps.get_storage: lambda: storage,
        deps.get_channel_service: lambda: service, deps.get_channel_type_registry: lambda: registry})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.patch(f"/channels/{record.id}/credentials", json={"access_token": "new-token"})).status_code == 403
        app.dependency_overrides[deps.get_current_user_id] = lambda: "owner"
        response = await client.patch(f"/channels/{record.id}/credentials", json={"access_token": "new-token"})
        assert response.status_code == 200
        assert "new-token" not in response.text and "offline-secret" not in response.text


@pytest.mark.asyncio
async def test_a_stale_pinned_approval_never_resumes_a_different_session():
    storage = SimpleNamespace(get_channel=AsyncMock(return_value=SimpleNamespace(enabled=True, user_id="owner")),
        list_sessions_by_channel=AsyncMock())
    gateway = ChannelGateway(storage, InMemoryMessageBus(), object())
    gateway._resume = AsyncMock(return_value=False)
    await gateway.process(ChannelConfirmationResultEvent(channel_id="tg", chat_id="7", channel_user_id="10",
        agent_id="original-agent", session_id="original-session", tool_call_id="stale-call", approved=True))
    storage.list_sessions_by_channel.assert_not_called()
    assert gateway._resume.await_args.args[1] == ("original-agent", "original-session")


@pytest.mark.asyncio
async def test_a_failing_update_is_retried_then_skipped_and_never_blocks_the_next(monkeypatch):
    """A message the platform cannot process (a store outage, a bug) must not stop the bot."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    adapter = telegram()
    bad, good = tg_update("hỏng"), {**tg_update("tiếp theo"), "update_id": 5}
    handled, sent, polls = [], [], []

    async def emit(event):
        handled.append(event.message)
        if event.message == "hỏng":
            raise RuntimeError("routing store down")

    async def api(method, **payload):
        if method == "getMe":
            return {"id": 123, "username": "my_bot"}
        if method == "sendMessage":
            sent.append(payload["text"])
            return {}
        polls.append(payload["offset"])
        if payload["offset"] <= 4 and len(polls) <= 3:
            return [bad, good]
        if payload["offset"] <= 5 and len(polls) <= 4:
            return [good]
        raise asyncio.CancelledError

    adapter._api = api
    with pytest.raises(asyncio.CancelledError):
        await adapter.start_listening(emit)
    assert handled == ["hỏng", "hỏng", "hỏng", "tiếp theo"]
    assert polls[:4] == [0, 0, 0, 6] and "Bạn gửi lại sau ít phút" in sent[0]
    assert await adapter._bus.registry_get(MessageBusKeys.channel_poll_cursor("tg"), "offset") == "6"
