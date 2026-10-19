# -*- coding: utf-8 -*-
"""Telegram text messages over the Bot API, using long polling."""
import asyncio
import re
from typing import Any, AsyncIterator, Awaitable, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...._logging import logger
from ....event import ReplyEndEvent, RequireUserConfirmEvent
from ....message import Msg, TextBlock
from .._base import (
    ChannelBase,
    ChannelCapability,
    ChannelConfirmationResultEvent,
    ChannelEvent,
    ChannelStatus,
    _EVENT_ADAPTER,
)
from .._errors import ChannelError


# A revoked token or another poller/webhook (409) is rechecked this often.
_BLOCKED_RETRY_SECONDS = 60.0


class TelegramChannel(ChannelBase):
    """Connect a Telegram bot to the agent's text conversation."""

    channel_type = "telegram"
    display_name = "Telegram"
    description = "Telegram text chat. Create a bot with @BotFather."
    icon_url = "https://www.google.com/s2/favicons?domain=telegram.org&sz=128"
    platform_bot_id_field = "bot_id"
    capabilities = ChannelCapability(max_message_length=4096)

    class Credentials(BaseModel):
        """Keep the public bot id separate from its secret token."""

        model_config = ConfigDict(hide_input_in_errors=True)

        bot_token: str = Field(
            title="Bot Token",
            description="Token issued by @BotFather.",
            pattern=r"^[0-9]+:[A-Za-z0-9_-]+$",
            json_schema_extra={"format": "password"},
        )
        bot_id: str = Field(
            title="Bot ID",
            description="The numeric part before ':' in the Bot Token.",
            pattern=r"^[0-9]+$",
        )

        @model_validator(mode="after")
        def check_bot_id(self) -> "TelegramChannel.Credentials":
            """Prevent a second registration under an unrelated bot id."""
            if self.bot_id != self.bot_token.split(":", 1)[0]:
                raise ValueError("Bot ID must match the Bot Token prefix.")
            return self

    class Config(BaseModel):
        """Reuse the channel UI's group-mention switch."""

        only_at_reply: bool = Field(
            default=True,
            title="Reply only when mentioned",
        )

    def __init__(
        self,
        channel_id: str,
        credentials: "TelegramChannel.Credentials",
        config: "TelegramChannel.Config",
    ) -> None:
        """Read the validated bot credentials and reply policy."""
        self._channel_id = channel_id
        self._token = credentials.bot_token
        self._bot_id = credentials.bot_id
        self._username = ""
        self._config = config
        self._http: httpx.AsyncClient | None = None
        self.status = ChannelStatus()

    @property
    def channel_id(self) -> str:
        """The stored channel's identifier."""
        return self._channel_id

    async def _request(self, method: str, **payload: object) -> Any:
        """Call the Bot API without exposing the secret URL in errors."""
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=40.0)
        try:
            response = await self._http.post(
                f"https://api.telegram.org/bot{self._token}/{method}",
                json=payload,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ChannelError(
                f"Telegram {method} failed ({type(exc).__name__}).",
                502,
            ) from None
        if response.is_error or not body.get("ok"):
            code = body.get("error_code", response.status_code)
            hint = (
                " Stop other pollers and remove any existing webhook."
                if code == 409
                else ""
            )
            raise ChannelError(
                f"Telegram {method} failed ({code}).{hint}",
                code,
            )
        return body["result"]

    async def aclose(self) -> None:
        """Release REST clients, including instances that never listen."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def start_listening(
        self,
        emit: Callable[
            [ChannelEvent | ChannelConfirmationResultEvent],
            Awaitable[None],
        ],
    ) -> None:
        """Poll updates and retry transient failures until cancelled."""
        # shortcut: one poller per bot, elect a leader before scaling workers.
        self._emit = emit
        self.status.state = "connecting"
        offset = 0
        backoff = 1.0
        try:
            while True:
                try:
                    if not self._username:
                        me = await self._request("getMe")
                        if str(me["id"]) != self._bot_id:
                            raise ChannelError(
                                "Telegram Bot ID does not match the token.",
                                401,
                            )
                        self._username = me["username"]
                    updates = await self._request(
                        "getUpdates",
                        offset=offset,
                        timeout=30,
                        allowed_updates=["message"],
                    )
                    self.status.state = "connected"
                    self.status.last_error = ""
                    backoff = 1.0
                    for update in updates:
                        # Advance first: a message that fails to handle is
                        # logged and skipped instead of replayed forever.
                        offset = update["update_id"] + 1
                        await self._on_message(update.get("message", {}))
                except ChannelError as exc:
                    self.status.last_error = str(exc)
                    if exc.status_code in (401, 403, 409):
                        # Token revoked or another poller/webhook owns the bot:
                        # keep checking slowly so the channel recovers by itself.
                        self.status.state = "failed"
                        await asyncio.sleep(_BLOCKED_RETRY_SECONDS)
                        continue
                    self.status.state = "retrying"
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                except Exception:  # pylint: disable=broad-except
                    self.status.state = "retrying"
                    self.status.last_error = (
                        "Telegram message handling failed."
                    )
                    logger.warning(
                        "Telegram '%s' message handling failed",
                        self._channel_id,
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
        finally:
            self.status.state = "stopped"
            await self._confirm_offset(offset)
            await self.aclose()

    async def _confirm_offset(self, offset: int) -> None:
        """Tell Telegram the handled updates are done, so a restart does not replay them.

        Updates are confirmed only by the next getUpdates call with a higher
        offset; without this, a stop right after handling re-delivers them.
        """
        if not offset:
            return
        try:
            await asyncio.wait_for(
                self._request("getUpdates", offset=offset, timeout=0, limit=1),
                timeout=5.0,
            )
        except Exception:  # pylint: disable=broad-except
            logger.info("Telegram '%s' could not confirm its last offset", self._channel_id)

    async def _on_message(self, message: dict) -> None:
        """Normalise text messages and ignore bots and unaddressed groups."""
        sender = message.get("from", {})
        chat = message.get("chat", {})
        text = message.get("text", "")
        if not text or not sender.get("id") or sender.get("is_bot"):
            return
        if chat.get("type") != "private" and self._config.only_at_reply:
            mention = rf"(?<!\w)@{re.escape(self._username)}(?!\w)"
            replying_to_bot = str(
                message.get("reply_to_message", {})
                .get("from", {})
                .get("id", ""),
            ) == self._bot_id
            if not replying_to_bot and not re.search(
                mention, text, re.IGNORECASE,
            ):
                return
            text = re.sub(mention, "", text, flags=re.IGNORECASE).strip()
        if text and self._emit:
            await self._emit(
                ChannelEvent(
                    channel_id=self._channel_id,
                    channel_user_id=str(sender["id"]),
                    channel_user_name=" ".join(
                        sender[k]
                        for k in ("first_name", "last_name")
                        if sender.get(k)
                    ),
                    chat_id=str(chat["id"]),
                    chat_name=chat.get("title", ""),
                    channel_message_id=str(message["message_id"]),
                    content=[TextBlock(text=text)],
                    metadata={
                        "chat_type": chat.get("type", ""),
                        "message_thread_id": message.get("message_thread_id"),
                    },
                ),
            )

    async def send_response(
        self,
        event: ChannelEvent,
        events: AsyncIterator[dict],
    ) -> None:
        """Fold the existing agent event stream into Telegram text replies."""
        reply: Msg | None = None
        confirmation = False
        async for raw in events:
            evt = _EVENT_ADAPTER.validate_python(raw)
            if isinstance(evt, RequireUserConfirmEvent):
                confirmation = True
                break
            reply_id = getattr(evt, "reply_id", None)
            if reply_id is not None:
                if reply is None:
                    reply = Msg(name="assistant", role="assistant", content=[])
                    reply.id = reply_id
                reply.append_event(evt)
            if isinstance(evt, ReplyEndEvent):
                break
        texts = [
            block.text
            for block in self._render(reply)
            if isinstance(block, TextBlock)
        ]
        if confirmation:
            texts.append(
                "Tool execution needs approval. Open this channel's "
                "conversation in the web app to review and approve it.",
            )
        for text in texts:
            for start in range(0, len(text), 4096):
                payload: dict[str, object] = {
                    "chat_id": event.chat_id,
                    "text": text[start : start + 4096],
                }
                if event.metadata.get("message_thread_id") is not None:
                    payload["message_thread_id"] = event.metadata[
                        "message_thread_id"
                    ]
                await self._request("sendMessage", **payload)
