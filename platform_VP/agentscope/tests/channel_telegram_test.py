# -*- coding: utf-8 -*-
"""Telegram registration, message delivery and polling checks."""
import asyncio
from typing import AsyncIterator
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError

from agentscope.app.channel import (
    ChannelEvent,
    ChannelTypeRegistry,
    TelegramChannel,
)
from agentscope.app.channel._errors import ChannelError
from agentscope.event import (
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
)


def _message(text: str = "Hello", chat_type: str = "private") -> dict:
    return {
        "message_id": 8,
        "from": {"id": 9, "first_name": "Test"},
        "chat": {"id": -10, "type": chat_type, "title": "Team"},
        "text": text,
        "message_thread_id": 7,
    }


async def _events(
    text: str = "",
    *,
    confirm: bool = False,
) -> AsyncIterator[dict]:
    events = [ReplyStartEvent(session_id="s", reply_id="r", name="bot")]
    if text:
        events.extend(
            [
                TextBlockStartEvent(reply_id="r", block_id="text"),
                TextBlockDeltaEvent(reply_id="r", block_id="text", delta=text),
                TextBlockEndEvent(reply_id="r", block_id="text"),
            ],
        )
    events.append(
        RequireUserConfirmEvent(reply_id="r", tool_calls=[])
        if confirm
        else ReplyEndEvent(session_id="s", reply_id="r"),
    )
    for event in events:
        yield event.model_dump(mode="json")


class TelegramChannelTest(IsolatedAsyncioTestCase):
    """Use real channel code with isolated HTTP and gateway I/O."""

    def setUp(self) -> None:
        self.channel = TelegramChannel(
            "tele-1",
            TelegramChannel.Credentials(bot_id="123", bot_token="123:secret"),
            TelegramChannel.Config(),
        )
        self.channel._username = "demo_bot"
        self.channel._emit = AsyncMock()

    async def asyncTearDown(self) -> None:
        await self.channel.aclose()

    def test_registration_and_secret_schema(self) -> None:
        registry = ChannelTypeRegistry([TelegramChannel])
        schema = registry.list_types()[0]
        self.assertEqual(schema.channel_type, "telegram")
        self.assertEqual(
            schema.credentials_schema["properties"]["bot_token"]["format"],
            "password",
        )
        self.assertEqual(
            registry.extract_platform_bot_id("telegram", {"bot_id": "123"}),
            "123",
        )
        for token, bot_id in [("bad/token", "123"), ("123:secret", "999")]:
            with self.assertRaises(ValidationError) as error:
                TelegramChannel.Credentials(bot_id=bot_id, bot_token=token)
            self.assertNotIn(token, str(error.exception))

    async def test_private_text_and_forum_topic_are_normalised(self) -> None:
        await self.channel._on_message(_message())
        event = self.channel._emit.call_args.args[0]
        self.assertEqual(event.message, "Hello")
        self.assertEqual(event.channel_user_id, "9")
        self.assertEqual(event.chat_id, "-10")
        self.assertEqual(event.metadata["message_thread_id"], 7)

    async def test_group_mentions_and_replies(self) -> None:
        for text in ["Hello", "@demo_bot_other hello"]:
            await self.channel._on_message(_message(text, "supergroup"))
        self.channel._emit.assert_not_awaited()
        await self.channel._on_message(_message("@DEMO_BOT hello", "group"))
        self.assertEqual(self.channel._emit.call_args.args[0].message, "hello")
        message = _message("Reply", "group")
        message["reply_to_message"] = {"from": {"id": 123}}
        await self.channel._on_message(message)
        self.assertEqual(self.channel._emit.await_count, 2)
        self.channel._config.only_at_reply = False
        await self.channel._on_message(_message("Group text", "group"))
        self.assertEqual(self.channel._emit.await_count, 3)

    async def test_bots_and_media_do_not_trigger_the_agent(self) -> None:
        message = _message()
        message["from"]["is_bot"] = True
        await self.channel._on_message(message)
        await self.channel._on_message(_message(""))
        await self.channel._on_message({})
        self.channel._emit.assert_not_awaited()

    async def test_replies_split_and_keep_the_forum_topic(self) -> None:
        self.channel._request = AsyncMock()
        event = ChannelEvent(
            channel_id="tele-1",
            channel_user_id="9",
            chat_id="-10",
            metadata={"message_thread_id": 7},
        )
        text = "Xin chào 👋 " * 500
        await self.channel.send_response(event, _events(text))
        calls = self.channel._request.call_args_list
        parts = [call.kwargs["text"] for call in calls]
        self.assertEqual("".join(parts), text.strip())
        self.assertTrue(all(0 < len(part) <= 4096 for part in parts))
        self.assertTrue(
            all(call.kwargs["message_thread_id"] == 7 for call in calls),
        )
        self.assertTrue(all(call.args == ("sendMessage",) for call in calls))

    async def test_tool_approval_points_to_the_web_app(self) -> None:
        self.channel._request = AsyncMock()
        event = ChannelEvent(
            channel_id="tele-1", channel_user_id="9", chat_id="-10",
        )
        await self.channel.send_response(event, _events(confirm=True))
        text = self.channel._request.call_args.kwargs["text"]
        self.assertIn("web app", text)
        self.channel._emit.assert_not_awaited()

    async def test_http_errors_never_expose_the_bot_token(self) -> None:
        async def fail(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(str(request.url), request=request)

        self.channel._http = httpx.AsyncClient(
            transport=httpx.MockTransport(fail),
        )
        with self.assertRaises(ChannelError) as error:
            await self.channel._request("getMe")
        self.assertNotIn("secret", str(error.exception))
        await self.channel.aclose()
        self.channel._http = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    409, json={"ok": False, "error_code": 409},
                ),
            ),
        )
        with self.assertRaises(ChannelError) as error:
            await self.channel._request("getUpdates")
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("webhook", str(error.exception))

    async def test_polling_offsets_and_cancellation(self) -> None:
        polled = asyncio.Event()
        calls = []
        self.channel._username = ""

        async def request(method: str, **payload: object) -> object:
            calls.append((method, payload))
            if method == "getMe":
                return {"id": 123, "username": "demo_bot"}
            if payload.get("timeout") == 0:
                return []
            if len(calls) == 2:
                return [{"update_id": 42, "message": _message()}]
            polled.set()
            await asyncio.Future()

        self.channel._request = request
        self.channel.aclose = AsyncMock()
        task = asyncio.create_task(
            self.channel.start_listening(self.channel._emit),
        )
        try:
            await asyncio.wait_for(polled.wait(), timeout=1)
            self.assertEqual(calls[0][0], "getMe")
            self.assertEqual(calls[1][1]["offset"], 0)
            self.assertEqual(calls[2][1]["offset"], 43)
            self.assertEqual(self.channel.status.state, "connected")
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(self.channel.status.state, "stopped")
        # Stopping confirms the handled update so a restart does not replay it.
        self.assertEqual(calls[-1], ("getUpdates", {"offset": 43, "timeout": 0, "limit": 1}))
        self.channel.aclose.assert_awaited_once()

    async def test_failing_message_is_skipped_not_replayed(self) -> None:
        offsets = []
        done = asyncio.Event()

        async def request(method: str, **payload: object) -> object:
            if payload.get("timeout") == 0:
                return []
            offsets.append(payload["offset"])
            if len(offsets) == 1:
                return [{"update_id": 5, "message": _message()}]
            done.set()
            await asyncio.Future()

        self.channel._request = request
        self.channel._emit = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("agentscope.app.channel._telegram._channel.asyncio.sleep", AsyncMock()):
            task = asyncio.create_task(self.channel.start_listening(self.channel._emit))
            try:
                await asyncio.wait_for(done.wait(), timeout=1)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        self.assertEqual(offsets, [0, 6])

    async def test_conflict_is_retried_and_recovers(self) -> None:
        attempts = []
        recovered = asyncio.Event()

        async def request(method: str, **payload: object) -> object:
            if payload.get("timeout") == 0:
                return []
            attempts.append(method)
            if len(attempts) == 1:
                raise ChannelError("Telegram getUpdates failed (409).", 409)
            recovered.set()
            await asyncio.Future()

        self.channel._request = request
        with patch("agentscope.app.channel._telegram._channel._BLOCKED_RETRY_SECONDS", 0):
            task = asyncio.create_task(self.channel.start_listening(self.channel._emit))
            try:
                await asyncio.wait_for(recovered.wait(), timeout=1)
                self.assertEqual(len(attempts), 2)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

    async def test_invalid_token_stays_failed_until_cancelled(self) -> None:
        attempted = asyncio.Event()
        self.channel._username = ""

        async def request(method: str) -> None:
            self.assertEqual(method, "getMe")
            attempted.set()
            raise ChannelError("Telegram getMe failed (401).", 401)

        self.channel._request = request
        task = asyncio.create_task(
            self.channel.start_listening(self.channel._emit),
        )
        try:
            await asyncio.wait_for(attempted.wait(), timeout=1)
            self.assertEqual(self.channel.status.state, "failed")
            self.assertIn("401", self.channel.status.last_error)
            self.assertFalse(task.done())
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
