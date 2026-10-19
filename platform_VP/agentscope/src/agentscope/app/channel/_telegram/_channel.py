# -*- coding: utf-8 -*-
"""Telegram private text chats via Bot API long polling.

Run one channel worker per bot. A polling conflict parks this listener
instead of repeatedly terminating the other worker's getUpdates request.
"""
import asyncio
import hashlib
import hmac
from typing import Any, AsyncIterator, Awaitable, Callable, Self

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_validator,
)

from ...._logging import logger
from ....event import ReplyEndEvent, RequireUserConfirmEvent
from ....message import Msg, TextBlock
from .._base import (
    ChannelBase,
    ChannelCapability,
    ChannelConfirmationResultEvent,
    ChannelEvent,
    ChannelStatus,
    ChatKind,
    _EVENT_ADAPTER,
)
from ._openapi import _TelegramAPIError, _TelegramOpenAPI

_MAX_LEN = 4096
_POLL_TIMEOUT = 25


class TelegramChannel(ChannelBase):
    """Connect a Telegram bot to private text conversations."""

    channel_type = "telegram"
    display_name = "Telegram"
    description = "Bot for Telegram private text chats."
    icon_url = "https://www.google.com/s2/favicons?domain=telegram.org&sz=128"
    platform_bot_id_field = "bot_id"

    class Credentials(BaseModel):
        """BotFather token and its non-secret numeric bot identity."""

        model_config = ConfigDict(
            hide_input_in_errors=True,
            str_strip_whitespace=True,
        )

        bot_id: str = Field(
            title="Bot ID",
            description="Numeric prefix before ':' in the BotFather token",
            pattern=r"^[1-9][0-9]*$",
        )
        bot_token: str = Field(
            title="Bot Token",
            description="Token issued by @BotFather",
            pattern=r"^[1-9][0-9]*:[A-Za-z0-9_-]+$",
            json_schema_extra={"format": "password"},
        )

        @field_validator("bot_token", mode="wrap")
        @classmethod
        def _validate_token(
            cls, value: Any, handler: ValidatorFunctionWrapHandler
        ) -> str:
            """Explain token mistakes without revealing the secret."""
            try:
                return handler(value)
            except ValidationError:
                raise ValueError(
                    "Bot Token must be the full BotFather token in the "
                    "format <bot_id>:<secret>, not a Bot ID, @username or URL."
                ) from None

        @model_validator(mode="after")
        def _matching_bot_id(self) -> Self:
            """Keep the uniqueness index tied to the authenticated bot."""
            if self.bot_token.split(":", 1)[0] != self.bot_id:
                raise ValueError("Bot ID must match the prefix of Bot Token.")
            return self

    class Config(BaseModel):
        """Reply visibility, matching the other channel adapters."""

        show_tool_process: bool = Field(
            default=False,
            title="Show tool process",
            description="Show tool calls and results inline in the reply",
        )
        show_thinking: bool = Field(
            default=False,
            title="Show thinking",
            description="Show the model's reasoning inline in the reply",
        )

    capabilities = ChannelCapability(
        text=True,
        interactive=True,
        max_message_length=_MAX_LEN,
    )

    def __init__(
        self,
        channel_id: str,
        credentials: "TelegramChannel.Credentials",
        config: "TelegramChannel.Config",
    ) -> None:
        self._channel_id = channel_id
        self._bot_id = credentials.bot_id
        self._bot_token = credentials.bot_token
        self._config = config
        self.status = ChannelStatus()
        self._http: httpx.AsyncClient | None = None
        self._openapi: _TelegramOpenAPI | None = None
        self._emit: Callable[
            [ChannelEvent | ChannelConfirmationResultEvent], Awaitable[None]
        ] | None = None

    @property
    def channel_id(self) -> str:
        """The unique channel instance identifier."""
        return self._channel_id

    def _api(self) -> _TelegramOpenAPI:
        """Build REST resources lazily, including on client-only instances."""
        if self._openapi is None:
            self._http = httpx.AsyncClient(timeout=_POLL_TIMEOUT + 10)
            self._openapi = _TelegramOpenAPI(self._bot_token, self._http)
        return self._openapi

    async def aclose(self) -> None:
        """Release REST resources opened by either lifecycle path."""
        if self._http is not None:
            await self._http.aclose()
        self._http = None
        self._openapi = None

    async def start_listening(
        self,
        emit: Callable[
            [ChannelEvent | ChannelConfirmationResultEvent], Awaitable[None]
        ],
    ) -> None:
        """Validate the bot, poll updates, and retry transient errors."""
        self._emit = emit
        self.status.state = "connecting"
        checked = False
        offset = 0
        backoff = 1.0
        try:
            while True:
                try:
                    if not checked:
                        me = await self._api().call("getMe")
                        if (
                            not isinstance(me, dict)
                            or str(me.get("id")) != self._bot_id
                        ):
                            raise _TelegramAPIError(
                                "Bot ID does not match getMe.", 400
                            )
                        webhook = await self._api().call("getWebhookInfo")
                        if not isinstance(webhook, dict):
                            raise _TelegramAPIError(
                                "Telegram returned invalid webhook info."
                            )
                        if webhook.get("url"):
                            raise _TelegramAPIError(
                                "This bot has a webhook. Remove it before "
                                "enabling Telegram long polling.",
                                409,
                            )
                        checked = True
                    updates = await self._api().call(
                        "getUpdates",
                        offset=offset,
                        timeout=_POLL_TIMEOUT,
                        allowed_updates=["message", "callback_query"],
                    )
                    if not isinstance(updates, list) or any(
                        not isinstance(update, dict)
                        or not isinstance(update.get("update_id"), int)
                        for update in updates
                    ):
                        raise _TelegramAPIError(
                            "Telegram returned invalid updates."
                        )
                    self.status.state = "connected"
                    self.status.last_error = ""
                    backoff = 1.0
                    for update in updates:
                        if update["update_id"] < offset:
                            continue
                        try:
                            await self._on_update(update)
                        except _TelegramAPIError as exc:
                            if exc.code not in (400, 403, 404):
                                raise
                            # Expired buttons or a blocked chat must not stop
                            # the bot from receiving other users' messages.
                            logger.warning(
                                "Telegram '%s': %s", self.channel_id, exc
                            )
                        # shortcut: crashes may replay a batch; persist offsets
                        # when durable ingestion is required.
                        offset = update["update_id"] + 1
                except _TelegramAPIError as exc:
                    self.status.last_error = str(exc)
                    if exc.code in (400, 401, 403, 404, 409):
                        self.status.state = "failed"
                        if exc.code == 409 and checked:
                            self.status.last_error = (
                                "Another poller or webhook is using this bot. "
                                "Run only one Telegram channel worker."
                            )
                        logger.error(
                            "Telegram '%s': %s",
                            self.channel_id,
                            self.status.last_error,
                        )
                        await asyncio.Future()
                    self.status.state = "retrying"
                    await asyncio.sleep(max(backoff, exc.retry_after))
                    backoff = min(backoff * 2, 30.0)
        finally:
            self._emit = None
            await self.aclose()
            self.status.state = "stopped"

    async def _on_update(self, update: dict[str, Any]) -> None:
        """Accept private user text or an authenticated approval button."""
        if "callback_query" in update:
            await self._on_callback(update["callback_query"])
            return
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if (
            chat.get("type") != "private"
            or sender.get("is_bot", False)
            or not sender.get("id")
            or sender.get("id") != chat.get("id")
        ):
            return
        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            await self._api().call(
                "sendMessage",
                chat_id=str(chat["id"]),
                text="This bot currently supports text messages only.",
            )
            return
        if self._emit is not None:
            name = " ".join(
                part
                for part in (sender.get("first_name"), sender.get("last_name"))
                if part
            )
            await self._emit(
                ChannelEvent(
                    channel_id=self.channel_id,
                    channel_user_id=str(sender["id"]),
                    channel_user_name=name or sender.get("username", ""),
                    chat_id=str(chat["id"]),
                    channel_message_id=str(message["message_id"]),
                    content=[TextBlock(text=text)],
                    metadata={"chat_type": "private"},
                ),
            )

    def _callback_data(
        self, chat_id: str, tool_id: str, approved: bool
    ) -> str:
        """Bind a decision to its channel, private chat and pending tool."""
        payload = f"{'a' if approved else 'd'}:{tool_id}"
        signature = hmac.new(
            self._bot_token.encode(),
            f"{self.channel_id}:{chat_id}:{payload}".encode(),
            hashlib.sha256,
        ).hexdigest()[:24]
        return f"{payload}:{signature}"

    async def _on_callback(self, callback: dict[str, Any]) -> None:
        """Validate the actor and signature before emitting a tool decision."""
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        sender = callback.get("from") or {}
        data = callback.get("data", "")
        parts: list[str] = []
        if isinstance(data, str):
            action, _, rest = data.partition(":")
            tool_id, _, signature = rest.rpartition(":")
            parts = [action, tool_id, signature]
        valid = (
            chat.get("type") == "private"
            and sender.get("id") == chat.get("id")
            and str((message.get("from") or {}).get("id")) == self._bot_id
            and len(parts) == 3
            and parts[0] in ("a", "d")
            and bool(parts[1])
            and hmac.compare_digest(
                data.encode(),
                self._callback_data(
                    str(chat.get("id")), parts[1], parts[0] == "a"
                ).encode(),
            )
        )
        await self._api().call(
            "answerCallbackQuery",
            callback_query_id=callback["id"],
            text="Decision received" if valid else "Invalid approval button",
        )
        if not valid or self._emit is None:
            return
        await self._emit(
            ChannelConfirmationResultEvent(
                channel_id=self.channel_id,
                chat_id=str(chat["id"]),
                channel_user_id=str(sender["id"]),
                actor=str(sender["id"]),
                tool_call_id=parts[1],
                approved=parts[0] == "a",
            ),
        )
        await self._api().call(
            "editMessageReplyMarkup",
            chat_id=str(chat["id"]),
            message_id=message["message_id"],
            reply_markup={"inline_keyboard": []},
        )

    async def send_response(
        self,
        event: ChannelEvent,
        events: AsyncIterator[dict],
    ) -> None:
        """Render final text and native approval buttons in the target DM."""
        if not event.chat_id.isdecimal() or int(event.chat_id) <= 0:
            raise ValueError("Telegram currently supports private chats only.")
        reply: Msg | None = None
        confirm: RequireUserConfirmEvent | None = None
        async for raw in events:
            agent_event = _EVENT_ADAPTER.validate_python(raw)
            if isinstance(agent_event, RequireUserConfirmEvent):
                confirm = agent_event
                break
            reply_id = getattr(agent_event, "reply_id", None)
            if reply_id is not None:
                if reply is None:
                    reply = Msg(name="assistant", role="assistant", content=[])
                    reply.id = reply_id
                reply.append_event(agent_event)
            if isinstance(agent_event, ReplyEndEvent):
                break
        for block in self._render(
            reply,
            show_thinking=self._config.show_thinking,
            show_tool_process=self._config.show_tool_process,
        ):
            text = (
                block.text
                if isinstance(block, TextBlock)
                else (
                    "The agent returned an attachment. "
                    "Open the session in Web UI to view it."
                )
            )
            for part in self._split_long_message(text):
                if part:
                    await self._api().call(
                        "sendMessage", chat_id=event.chat_id, text=part
                    )
        if confirm is not None:
            await self._present_confirm(event, confirm)

    async def _present_confirm(
        self,
        event: ChannelEvent,
        request: RequireUserConfirmEvent,
    ) -> None:
        """Send a signed approve/deny button for each pending tool call."""
        for tool in request.tool_calls:
            buttons = [
                {
                    "text": label,
                    "callback_data": self._callback_data(
                        event.chat_id, tool.id, approved
                    ),
                }
                for label, approved in (("Approve", True), ("Deny", False))
            ]
            text = (
                f"Tool execution needs approval\nTool: {tool.name}\n"
                f"Arguments: {str(tool.input)[:800]}"
            )
            markup = {"inline_keyboard": [buttons]}
            if any(
                len(button["callback_data"].encode()) > 64
                for button in buttons
            ):
                # shortcut: long ids use Web UI; add shared bindings to
                # support their approval directly in Telegram.
                markup = {"inline_keyboard": []}
                text += "\nOpen this session in Web UI to approve or deny."
            await self._api().call(
                "sendMessage",
                chat_id=event.chat_id,
                text=text,
                reply_markup=markup,
            )

    def _split_long_message(self, text: str) -> list[str]:
        """Keep chunks within Telegram's limit, including astral emoji."""
        parts: list[str] = []
        start = size = 0
        for index, char in enumerate(text):
            width = 2 if ord(char) > 0xFFFF else 1
            if size + width > _MAX_LEN:
                parts.append(text[start:index])
                start, size = index, 0
            size += width
        parts.append(text[start:])
        return parts

    async def chat_kind(self, chat_id: str) -> ChatKind | None:
        """Positive numeric ids are the private chats this adapter accepts."""
        return (
            ChatKind.PRIVATE
            if chat_id.isdecimal() and int(chat_id) > 0
            else None
        )
