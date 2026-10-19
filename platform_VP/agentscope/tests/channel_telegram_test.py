# -*- coding: utf-8 -*-
"""Telegram adapter tests; all Bot API traffic uses a mock transport."""
import asyncio
import json
from contextlib import suppress
from copy import deepcopy
from typing import Any, AsyncIterator
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError

from agentscope.app._router._channel import _to_response
from agentscope.app._service import ChannelService
from agentscope.app.channel import (
    ChannelConfirmationResultEvent,
    ChannelEvent,
    ChannelTypeRegistry,
    ChatKind,
    TelegramChannel,
)
from agentscope.app.channel._telegram._openapi import (
    _TelegramAPIError,
    _TelegramOpenAPI,
)
from agentscope.app.storage import (
    ChannelBinding,
    RoutingConfig,
    SessionSettings,
)
from agentscope.event import (
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
    TextBlockStartEvent,
)
from agentscope.message import ToolCallBlock

_TOKEN = "123456:test-token"


def _channel() -> TelegramChannel:
    return TelegramChannel(
        "telegram-1",
        TelegramChannel.Credentials(bot_id="123456", bot_token=_TOKEN),
        TelegramChannel.Config(),
    )


def _message(update_id: int = 40) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 7,
            "from": {"id": 99, "first_name": "Test", "is_bot": False},
            "chat": {"id": 99, "type": "private"},
            "text": "hello",
        },
    }


def _callback(data: str) -> dict:
    return {
        "id": "callback-1",
        "from": {"id": 99},
        "message": {
            "message_id": 10,
            "from": {"id": 123456},
            "chat": {"id": 99, "type": "private"},
        },
        "data": data,
    }


async def _events(
    text: str = "hello from agent",
    tool_id: str | None = None,
) -> AsyncIterator[dict]:
    for event in (
        ReplyStartEvent(session_id="s-1", reply_id="r-1", name="assistant"),
        TextBlockStartEvent(reply_id="r-1", block_id="text-1"),
        TextBlockDeltaEvent(reply_id="r-1", block_id="text-1", delta=text),
    ):
        yield event.model_dump(mode="json")
    if tool_id is not None:
        yield RequireUserConfirmEvent(
            reply_id="r-1",
            tool_calls=[
                ToolCallBlock(id=tool_id, name="execute", input='{"x": 1}')
            ],
        ).model_dump(mode="json")
    else:
        yield ReplyEndEvent(session_id="s-1", reply_id="r-1").model_dump(
            mode="json"
        )


class TelegramChannelTest(IsolatedAsyncioTestCase):
    """Exercise lifecycle, private-chat isolation, replies and approvals."""

    def _http(
        self, channel: TelegramChannel, handler: Any
    ) -> httpx.AsyncClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        channel._http = http
        channel._openapi = _TelegramOpenAPI(_TOKEN, http)
        self.addAsyncCleanup(channel.aclose)
        return http

    async def test_schema_and_create_hide_the_token(self) -> None:
        registry = ChannelTypeRegistry([TelegramChannel])
        schema = registry.list_types()[0]
        self.assertEqual(schema.channel_type, "telegram")
        self.assertEqual(
            schema.credentials_schema["properties"]["bot_token"]["format"],
            "password",
        )
        self.assertEqual(schema.platform_bot_id_field, "bot_id")
        storage = AsyncMock()
        storage.get_channel_id_by_platform_bot_id.return_value = None
        service = ChannelService(storage, AsyncMock(), registry)
        record = await service.create(
            user_id="owner-1",
            channel_type="telegram",
            credentials={
                "bot_id": " 123456 ",
                "bot_token": f" \n{_TOKEN}\r\n",
            },
            platform_config={},
            routing=RoutingConfig(
                bindings=[ChannelBinding(match_value="*", agent_id="agent-1")]
            ),
            session=SessionSettings(chat_model_config={"type": "test"}),
        )
        self.assertNotIn(
            _TOKEN, _to_response(record, registry).model_dump_json()
        )
        self.assertEqual(
            _to_response(record, registry).platform_bot_id, "123456"
        )
        self.assertEqual(
            record.credentials,
            {"bot_id": "123456", "bot_token": _TOKEN},
        )
        storage.get_channel_id_by_platform_bot_id.assert_awaited_once_with(
            "123456",
        )
        self.assertEqual(storage.upsert_channel.call_args.args[1], "123456")

    async def test_invalid_token_format_has_a_safe_actionable_error(
        self,
    ) -> None:
        for token in (
            "123456",
            "@example_bot",
            "https://t.me/example_bot",
            f"https://api.telegram.org/bot{_TOKEN}/getMe",
            f'"{_TOKEN}"',
            _TOKEN + "...",
            "123456:test\n-token",
        ):
            with self.subTest(token=token):
                with self.assertRaisesRegex(
                    ValidationError,
                    "full BotFather token",
                ) as caught:
                    TelegramChannel.Credentials(
                        bot_id="123456",
                        bot_token=token,
                    )
                self.assertNotIn(_TOKEN, str(caught.exception))

    async def test_invalid_credentials_are_rejected_before_storage(
        self,
    ) -> None:
        storage = AsyncMock()
        service = ChannelService(
            storage, AsyncMock(), ChannelTypeRegistry([TelegramChannel])
        )
        for credentials in (
            {"bot_id": "1", "bot_token": _TOKEN},
            {"bot_id": "123456", "bot_token": _TOKEN + "/../getUpdates"},
        ):
            with self.subTest(credentials=credentials):
                with self.assertRaises(ValidationError) as caught:
                    await service.create(
                        user_id="owner-1",
                        channel_type="telegram",
                        credentials=credentials,
                        platform_config={},
                        routing=RoutingConfig(
                            bindings=[
                                ChannelBinding(
                                    match_value="*", agent_id="agent-1"
                                )
                            ]
                        ),
                        session=SessionSettings(
                            chat_model_config={"type": "test"}
                        ),
                    )
                self.assertNotIn(_TOKEN, str(caught.exception))
        storage.upsert_channel.assert_not_awaited()

    async def test_normalizes_private_text(self) -> None:
        channel = _channel()
        received = AsyncMock()
        channel._emit = received
        await channel._on_update(_message())
        event = received.call_args.args[0]
        self.assertIsInstance(event, ChannelEvent)
        self.assertEqual(
            (event.channel_user_id, event.chat_id, event.channel_message_id),
            ("99", "99", "7"),
        )
        self.assertEqual(event.channel_user_name, "Test")
        self.assertEqual(event.message, "hello")
        self.assertEqual(await channel.chat_kind("99"), ChatKind.PRIVATE)
        self.assertIsNone(await channel.chat_kind("-10099"))

    async def test_ignores_groups_bots_and_mismatched_senders(self) -> None:
        channel = _channel()
        channel._emit = AsyncMock()
        for change in ("group", "bot", "sender"):
            update = _message()
            if change == "group":
                update["message"]["chat"]["type"] = "supergroup"
            elif change == "bot":
                update["message"]["from"]["is_bot"] = True
            else:
                update["message"]["from"]["id"] = 100
            await channel._on_update(update)
        channel._emit.assert_not_awaited()

    async def test_unsupported_media_gets_an_explicit_reply(self) -> None:
        channel = _channel()
        channel._openapi = AsyncMock()
        channel._emit = AsyncMock()
        update = _message()
        del update["message"]["text"]
        update["message"]["photo"] = [{"file_id": "photo-1"}]
        await channel._on_update(update)
        channel._emit.assert_not_awaited()
        self.assertIn(
            "text messages only",
            channel._openapi.call.call_args.kwargs["text"],
        )

    async def test_replies_work_without_starting_a_listener(self) -> None:
        channel = _channel()
        sent: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.content))
            return httpx.Response(
                200, json={"ok": True, "result": {"message_id": 8}}
            )

        http = self._http(channel, handler)
        event = ChannelEvent(
            channel_id=channel.channel_id, channel_user_id="", chat_id="99"
        )
        text = "😀" * 3000 + "literal *markdown*"
        await channel.send_response(event, _events(text))
        self.assertEqual("".join(item["text"] for item in sent), text)
        self.assertTrue(
            all(
                len(item["text"].encode("utf-16-le")) // 2 <= 4096
                for item in sent
            )
        )
        self.assertTrue(
            all(
                item["chat_id"] == "99" and "parse_mode" not in item
                for item in sent
            )
        )
        await channel.aclose()
        self.assertTrue(http.is_closed)

    async def test_group_delivery_is_rejected(self) -> None:
        event = ChannelEvent(
            channel_id="telegram-1", channel_user_id="99", chat_id="-10099"
        )
        with self.assertRaisesRegex(ValueError, "private chats only"):
            await _channel().send_response(event, _events())

    async def test_approval_buttons_survive_a_new_listener_instance(
        self,
    ) -> None:
        outbound = _channel()
        outbound._openapi = AsyncMock()
        event = ChannelEvent(
            channel_id=outbound.channel_id, channel_user_id="", chat_id="99"
        )
        await outbound.send_response(event, _events(tool_id="call:tool-1"))
        card = outbound._openapi.call.call_args.kwargs
        buttons = card["reply_markup"]["inline_keyboard"][0]
        self.assertTrue(
            all(
                len(button["callback_data"].encode()) <= 64
                for button in buttons
            )
        )
        for button, approved in zip(buttons, (True, False)):
            inbound = _channel()
            inbound._openapi = AsyncMock()
            inbound._emit = AsyncMock()
            await inbound._on_callback(_callback(button["callback_data"]))
            decision = inbound._emit.call_args.args[0]
            self.assertIsInstance(decision, ChannelConfirmationResultEvent)
            self.assertEqual(decision.tool_call_id, "call:tool-1")
            self.assertEqual(decision.channel_user_id, "99")
            self.assertEqual(decision.approved, approved)
            self.assertEqual(
                inbound._openapi.call.call_args.args[0],
                "editMessageReplyMarkup",
            )

    async def test_forged_forwarded_or_wrong_actor_buttons_are_rejected(
        self,
    ) -> None:
        channel = _channel()
        channel._openapi = AsyncMock()
        channel._emit = AsyncMock()
        original = _callback(channel._callback_data("99", "tool-1", True))
        for change in (
            "signature",
            "actor",
            "chat",
            "bot",
            "unicode",
            "empty",
        ):
            callback = deepcopy(original)
            if change == "signature":
                callback["data"] = callback["data"].replace("tool-1", "tool-2")
            elif change == "actor":
                callback["from"]["id"] = 100
            elif change == "chat":
                callback["from"]["id"] = callback["message"]["chat"][
                    "id"
                ] = 100
            elif change == "bot":
                callback["message"]["from"]["id"] = 123
            elif change == "unicode":
                callback["data"] = "a:😀:forged"
            else:
                callback["data"] = ""
            await channel._on_callback(callback)
        channel._emit.assert_not_awaited()

    async def test_long_tool_ids_fall_back_to_web_ui(self) -> None:
        channel = _channel()
        channel._openapi = AsyncMock()
        event = ChannelEvent(
            channel_id=channel.channel_id, channel_user_id="99", chat_id="99"
        )
        await channel.send_response(event, _events(tool_id="x" * 100))
        card = channel._openapi.call.call_args.kwargs
        self.assertEqual(card["reply_markup"], {"inline_keyboard": []})
        self.assertIn("Web UI", card["text"])

    async def test_polling_advances_offset_and_closes_on_cancel(self) -> None:
        channel = _channel()
        received = AsyncMock()
        second_poll = asyncio.Event()
        polls: list[dict] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            method = request.url.path.rsplit("/", 1)[1]
            if method == "getMe":
                result = {"id": 123456}
            elif method == "getWebhookInfo":
                result = {"url": ""}
            else:
                polls.append(json.loads(request.content))
                if len(polls) == 1:
                    result = [_message(), _message()]
                else:
                    second_poll.set()
                    await asyncio.Future()
            return httpx.Response(200, json={"ok": True, "result": result})

        http = self._http(channel, handler)
        task = asyncio.create_task(channel.start_listening(received))
        try:
            await asyncio.wait_for(second_poll.wait(), 1)
            self.assertEqual(polls[1]["offset"], 41)
            self.assertEqual(
                polls[0]["allowed_updates"], ["message", "callback_query"]
            )
            received.assert_awaited_once()
            self.assertEqual(channel.status.state, "connected")
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.assertTrue(http.is_closed)
        self.assertEqual(channel.status.state, "stopped")

    async def test_polling_recovers_from_network_and_expired_button_errors(
        self,
    ) -> None:
        channel = _channel()
        received = AsyncMock()
        finished = asyncio.Event()
        offsets: list[int] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            method = request.url.path.rsplit("/", 1)[1]
            if method == "getMe":
                result = {"id": 123456}
            elif method == "getWebhookInfo":
                result = {"url": ""}
            elif method == "answerCallbackQuery":
                return httpx.Response(
                    400,
                    json={"ok": False, "error_code": 400},
                )
            else:
                offsets.append(json.loads(request.content)["offset"])
                if len(offsets) == 1:
                    raise httpx.ReadTimeout("Temporary network failure")
                if len(offsets) == 2:
                    result = [
                        {
                            "update_id": 41,
                            "callback_query": _callback(
                                channel._callback_data("99", "tool-1", True),
                            ),
                        },
                        _message(42),
                    ]
                else:
                    finished.set()
                    await asyncio.Future()
            return httpx.Response(200, json={"ok": True, "result": result})

        self._http(channel, handler)
        with patch(
            "agentscope.app.channel._telegram._channel.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep:
            task = asyncio.create_task(channel.start_listening(received))
            try:
                await asyncio.wait_for(finished.wait(), 1)
                self.assertEqual(offsets, [0, 0, 43])
                sleep.assert_awaited_once_with(1)
                received.assert_awaited_once()
                self.assertIsInstance(received.call_args.args[0], ChannelEvent)
                self.assertEqual(channel.status.state, "connected")
                self.assertEqual(channel.status.last_error, "")
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def test_token_webhook_and_poller_conflicts_park_without_retries(
        self,
    ) -> None:
        for failure in ("token", "webhook", "poller"):
            with self.subTest(failure=failure):
                channel = _channel()
                failed = asyncio.Event()
                calls: list[str] = []

                def handler(request: httpx.Request) -> httpx.Response:
                    method = request.url.path.rsplit("/", 1)[1]
                    calls.append(method)
                    if failure == "token":
                        return httpx.Response(
                            401,
                            json={
                                "ok": False,
                                "error_code": 401,
                                "description": "Unauthorized",
                            },
                        )
                    if method == "getMe":
                        result = {"id": 123456}
                    elif method == "getWebhookInfo":
                        result = {
                            "url": "https://example.test/webhook"
                            if failure == "webhook"
                            else ""
                        }
                    else:
                        return httpx.Response(
                            409,
                            json={
                                "ok": False,
                                "error_code": 409,
                                "description": "Conflict",
                            },
                        )
                    return httpx.Response(
                        200, json={"ok": True, "result": result}
                    )

                self._http(channel, handler)
                with patch(
                    "agentscope.app.channel._telegram._channel.logger.error",
                    side_effect=lambda *args: failed.set(),
                ):
                    task = asyncio.create_task(
                        channel.start_listening(AsyncMock())
                    )
                    try:
                        await asyncio.wait_for(failed.wait(), 1)
                        self.assertEqual(channel.status.state, "failed")
                        self.assertEqual(
                            len(calls),
                            {"token": 1, "webhook": 2, "poller": 3}[failure],
                        )
                        self.assertNotIn("deleteWebhook", calls)
                    finally:
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task


class TelegramOpenAPITest(IsolatedAsyncioTestCase):
    """Check safe errors, logging, and Telegram's explicit rate limits."""

    async def test_rate_limit_waits_then_retries(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(
                    429,
                    json={
                        "ok": False,
                        "error_code": 429,
                        "parameters": {"retry_after": 70},
                    },
                )
            return httpx.Response(
                200, json={"ok": True, "result": {"message_id": 1}}
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http:
            with patch(
                "agentscope.app.channel._telegram._openapi.asyncio.sleep",
                new_callable=AsyncMock,
            ) as sleep:
                await _TelegramOpenAPI(_TOKEN, http).call(
                    "sendMessage", chat_id="99", text="hello"
                )
                sleep.assert_awaited_once_with(70)
        self.assertEqual(attempts, 2)

    async def test_httpx_logs_redact_token_paths(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"ok": True, "result": {"id": 123456}}
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http:
            with self.assertLogs("httpx", level="INFO") as logs:
                await _TelegramOpenAPI(_TOKEN, http).call("getMe")
        self.assertNotIn(_TOKEN, "\n".join(logs.output))
        self.assertIn("<redacted>", "\n".join(logs.output))

    async def test_exhausted_rate_limits_keep_the_retry_after(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "description": f"Rate limit for {_TOKEN}",
                    "parameters": {"retry_after": 70},
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http:
            with patch(
                "agentscope.app.channel._telegram._openapi.asyncio.sleep",
                new_callable=AsyncMock,
            ) as sleep:
                with self.assertRaises(_TelegramAPIError) as caught:
                    await _TelegramOpenAPI(_TOKEN, http).call("getUpdates")
                self.assertEqual(sleep.await_count, 2)
                self.assertEqual(caught.exception.retry_after, 70)
                self.assertNotIn(_TOKEN, str(caught.exception))

    async def test_transport_error_does_not_leak_token_or_retry_send(
        self,
    ) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError(str(request.url), request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http:
            with self.assertRaises(_TelegramAPIError) as caught:
                await _TelegramOpenAPI(_TOKEN, http).call(
                    "sendMessage", chat_id="99", text="hello"
                )
        self.assertNotIn(_TOKEN, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(calls, 1)

    async def test_invalid_json_has_a_safe_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="bad gateway")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http:
            with self.assertRaisesRegex(_TelegramAPIError, "invalid response"):
                await _TelegramOpenAPI(_TOKEN, http).call("getMe")
