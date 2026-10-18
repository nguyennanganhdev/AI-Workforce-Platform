"""Telegram Bot API: long polling, text replies and bound approval buttons."""
import asyncio
import logging
import re

import httpx
from pydantic import Field, model_validator

from ...._logging import logger
from ....message import TextBlock
from .._base import ChannelCapability, ChannelEvent, ChannelStatus, ChatKind
from .._errors import ChannelError
from .._text import TextChannel, TextChannelConfig

# Tries of one update before it is skipped, so it never blocks the ones after it.
_MAX_UPDATE_ATTEMPTS = 3


class _HideBotToken(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r"(/bot)[^/\s]+", r"\1[redacted]", record.getMessage())
        record.args = ()
        return True


# httpx's INFO request log otherwise includes the token embedded in Telegram URLs.
logging.getLogger("httpx").addFilter(_HideBotToken())


class TelegramChannel(TextChannel):
    channel_type = "telegram"
    display_name = "Telegram"
    description = "Nhận tin nhắn từ bot Telegram và trả lời ngay trong cuộc trò chuyện."
    platform_bot_id_field = "bot_id"
    capabilities = ChannelCapability(interactive=True, max_message_length=4000)

    class Credentials(TextChannel.Credentials):
        bot_id: str = Field(min_length=1, pattern=r"^[0-9]+$", title="Bot ID",
            description="Phần số đứng trước dấu : trong token của BotFather.")
        bot_token: str = Field(min_length=1, title="Bot token", json_schema_extra={"format": "password"})

        @model_validator(mode="after")
        def token_matches_bot(self):
            if self.bot_token.split(":", 1)[0] != self.bot_id or ":" not in self.bot_token:
                raise ValueError("Bot ID phải khớp phần số đứng trước dấu : trong token.")
            return self

    class Config(TextChannelConfig):
        allowed_chat_ids: list[str] = Field(default_factory=list, title="Cuộc trò chuyện được phép",
            description="Để trống để nhận từ mọi cuộc trò chuyện mà bot tham gia.")
        only_at_reply: bool = Field(default=True, title="Chỉ trả lời khi được gọi trong nhóm")

    def __init__(self, channel_id, credentials, config):
        self._channel_id = channel_id
        self._credentials = credentials
        self._config = config
        self.status = ChannelStatus()
        self._client = None

    @property
    def channel_id(self):
        return self._channel_id

    async def aclose(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _api(self, method, **payload):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=40)
        # Never expose provider URLs/exceptions: Telegram places the token in the URL.
        try:
            response = await self._client.post(
                f"https://api.telegram.org/bot{self._credentials.bot_token}/{method}", json=payload)
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise ChannelError("Không kết nối được Telegram.", 502) from None
        if not isinstance(data, dict):
            raise ChannelError("Telegram trả về dữ liệu không hợp lệ.", 502)
        if response.status_code != 200 or data.get("ok") is not True:
            code = data.get("error_code", response.status_code)
            code = code if isinstance(code, int) else response.status_code
            if code in {401, 403}:
                raise ChannelError("Bot token không hợp lệ hoặc không có quyền truy cập Telegram.", code)
            if code == 409:
                raise ChannelError("Bot đang có webhook hoặc một bộ nhận tin khác. Tắt webhook và chỉ giữ một kết nối long polling.", 502)
            if code == 429:
                await asyncio.sleep(min(max(int(data.get("parameters", {}).get("retry_after", 1)), 1), 30))
            raise ChannelError(f"Telegram từ chối yêu cầu (mã {code}).", 502)
        return data.get("result")

    async def start_listening(self, emit):
        from ...message_bus import MessageBusKeys
        self.status.state = "connecting"
        key = MessageBusKeys.channel_poll_cursor(self.channel_id)
        try:
            # Only one poller per bot, also when API replicas all host dispatchers.
            async with self._bus.acquire_lock(key + ":lock", ttl_secs=60):
                backoff = 1
                while True:
                    try:
                        me = await self._api("getMe")
                        break
                    except ChannelError as exc:
                        if exc.status_code in {400, 401, 403}:
                            raise
                        self.status = ChannelStatus(state="retrying", last_error=str(exc))
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 30)
                if str(me.get("id")) != self._credentials.bot_id:
                    raise ChannelError("Token không thuộc Bot ID đã cấu hình.", 400)
                username = me.get("username", "")
                offset = int(await self._bus.registry_get(key, "offset") or 0)
                backoff = 1
                attempts: dict[int, int] = {}
                while True:
                    try:
                        updates = await self._api("getUpdates", offset=offset, timeout=25,
                                                 allowed_updates=["message", "callback_query"])
                        self.status = ChannelStatus(state="connected")
                        backoff = 1
                        for update in updates:
                            if not await self._process(update, emit, username, attempts):
                                raise ChannelError("Chưa xử lý được tin nhắn; sẽ thử lại.", 503)
                            offset = int(update["update_id"]) + 1
                            await self._bus.registry_set(key, "offset", str(offset))
                    except ChannelError as exc:
                        self.status = ChannelStatus(state="retrying", last_error=str(exc))
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 30)
        except asyncio.CancelledError:
            raise
        except ChannelError as exc:
            self.status = ChannelStatus(state="failed", last_error=str(exc))
            await asyncio.Future()
        finally:
            self.status.state = "stopped"
            await self.aclose()

    async def _process(self, update, emit, username, attempts: dict[int, int]) -> bool:
        """Handle one update. False: try it again later. An update that keeps
        failing is skipped after three tries, so it never blocks the ones after it."""
        update_id = int(update["update_id"])
        try:
            await self._update(update, emit, username)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one message must not stop the bot
            attempts[update_id] = attempts.get(update_id, 0) + 1
            if attempts[update_id] < _MAX_UPDATE_ATTEMPTS:
                return False
            logger.exception("Telegram channel %s skipped update %s after %s tries",
                             self.channel_id, update_id, _MAX_UPDATE_ATTEMPTS)
            chat_id = (update.get("message") or (update.get("callback_query") or {}).get("message") or {}).get("chat", {}).get("id")
            if chat_id is not None:
                try:
                    await self._send_text(str(chat_id), "Mình chưa xử lý được tin nhắn này. Bạn gửi lại sau ít phút nhé.")
                except ChannelError:
                    pass
        attempts.pop(update_id, None)
        return True

    async def _update(self, update, emit, username=""):
        query = update.get("callback_query")
        message = query.get("message", {}) if query else update.get("message", {})
        sender = query.get("from", {}) if query else message.get("from", {})
        chat = message.get("chat", {})
        user_id, chat_id = str(sender.get("id", "")), str(chat.get("id", ""))
        if not user_id or not chat_id or sender.get("is_bot"):
            return
        if not self.allows(user_id) or (self._config.allowed_chat_ids and chat_id not in self._config.allowed_chat_ids):
            if query:
                await self._api("answerCallbackQuery", callback_query_id=query["id"], text="Bạn không có quyền sử dụng kênh này.")
            return
        event = ChannelEvent(channel_id=self.channel_id, channel_user_id=user_id, chat_id=chat_id,
            channel_user_name=sender.get("first_name", ""), chat_name=chat.get("title", ""),
            channel_message_id=str(message.get("message_id", "")), metadata={"chat_type": chat.get("type", "private")})
        if query:
            data = query.get("data", "").split(":")
            answer = "Nút xác nhận không hợp lệ."
            if len(data) == 3 and data[0] == "wf" and data[1] in {"a", "d"}:
                answer = await self.decision(data[2], data[1] == "a", event, emit)
            await self._api("answerCallbackQuery", callback_query_id=query["id"], text=answer)
            return
        text = message.get("text", "").strip()
        if not text:
            return
        if chat.get("type") != "private" and self._config.only_at_reply:
            mentioned = bool(username and f"@{username}".casefold() in text.casefold())
            reply_to_bot = str(message.get("reply_to_message", {}).get("from", {}).get("id", "")) == self._credentials.bot_id
            if not mentioned and not reply_to_bot:
                return
            if username:
                text = re.sub(re.escape(f"@{username}") + r"\b", "", text, flags=re.IGNORECASE).strip()
        if text:
            event.content = [TextBlock(text=text)]
            await self.receive_text(event, emit)

    async def _send_text(self, chat_id, text):
        return await self._api("sendMessage", chat_id=chat_id, text=text)

    async def _send_approval(self, chat_id, name, token):
        await self._api("sendMessage", chat_id=chat_id, text=f"Cần bạn duyệt công cụ {name}. Hiệu lực 24 giờ.",
            reply_markup={"inline_keyboard": [[{"text": "Đồng ý", "callback_data": f"wf:a:{token}"},
                                               {"text": "Từ chối", "callback_data": f"wf:d:{token}"}]]})

    async def chat_kind(self, chat_id):
        return ChatKind.GROUP if str(chat_id).startswith("-") else ChatKind.PRIVATE
