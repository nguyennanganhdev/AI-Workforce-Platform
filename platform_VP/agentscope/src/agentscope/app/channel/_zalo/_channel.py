"""Zalo OA customer-service text messages and signed webhook ingress."""
import asyncio
import hashlib
import hmac
import json
import re
import time

import httpx
from pydantic import Field

from ....message import TextBlock
from .._base import ChannelCapability, ChannelEvent, ChannelStatus, ChatKind
from .._errors import ChannelError
from .._text import TextChannel, TextChannelConfig


class ZaloOAChannel(TextChannel):
    channel_type = "zalo_oa"
    display_name = "Zalo OA"
    description = "Kết nối Zalo Official Account bằng webhook đã xác thực."
    platform_bot_id_field = "oa_id"
    capabilities = ChannelCapability(interactive=True, max_message_length=2000)

    class Credentials(TextChannel.Credentials):
        oa_id: str = Field(min_length=1, pattern=r"^[0-9]+$", title="Official Account ID")
        app_id: str = Field(min_length=1, pattern=r"^[0-9]+$", title="Zalo App ID")
        access_token: str = Field(min_length=1, title="OA access token", json_schema_extra={"format": "password"})
        oa_secret_key: str = Field(min_length=1, title="OA Secret Key", json_schema_extra={"format": "password"},
            description="Khóa xác thực webhook trong Zalo Developers.")

    Config = TextChannelConfig

    def __init__(self, channel_id, credentials, config):
        self._channel_id = channel_id
        self._credentials = credentials
        self._config = config
        self.status = ChannelStatus()
        self._client = None

    @property
    def channel_id(self):
        return self._channel_id

    async def start_listening(self, emit):
        # The API receives webhooks even when the channel worker is a separate process.
        self.status = ChannelStatus(state="connected")
        try:
            await asyncio.Future()
        finally:
            self.status.state = "stopped"
            await self.aclose()

    async def aclose(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def verify_webhook(self, raw: bytes, signature: str) -> dict:
        try:
            data = json.loads(raw)
            timestamp = str(data["timestamp"])
            valid_time = abs(time.time() - int(timestamp) / 1000) <= 300
        except (ValueError, TypeError, KeyError, UnicodeDecodeError):
            raise ChannelError("Webhook Zalo không hợp lệ.", 400) from None
        expected = hashlib.sha256(self._credentials.app_id.encode() + raw + timestamp.encode()
                                  + self._credentials.oa_secret_key.encode()).hexdigest()
        supplied = signature.strip().removeprefix("mac=")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", supplied) or not hmac.compare_digest(expected, supplied.lower()) or not valid_time:
            raise ChannelError("Chữ ký webhook Zalo không hợp lệ hoặc đã hết hạn.", 401)
        if not isinstance(data.get("recipient"), dict) or not isinstance(data.get("sender"), dict) or not isinstance(data.get("message"), dict):
            raise ChannelError("Webhook Zalo không hợp lệ.", 400)
        oa = data["sender"] if data.get("event_name", "").startswith("oa_") else data["recipient"]
        if str(data.get("app_id")) != self._credentials.app_id or str(oa.get("id")) != self._credentials.oa_id:
            raise ChannelError("Webhook không thuộc ứng dụng và OA này.", 403)
        return data

    def webhook_event(self, data):
        if data.get("event_name") != "user_send_text":
            return None
        sender = str(data.get("sender", {}).get("id", ""))
        message = data.get("message", {})
        text, message_id = message.get("text"), str(message.get("msg_id", ""))
        if not sender or not message_id or not isinstance(text, str) or not text.strip() or not self.allows(sender):
            return None
        return ChannelEvent(channel_id=self.channel_id, channel_user_id=sender, chat_id=sender,
            channel_message_id=message_id, content=[TextBlock(text=text)], metadata={"chat_type": "private"})

    async def _send_text(self, chat_id, text):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20)
        try:
            response = await self._client.post("https://openapi.zalo.me/v3.0/oa/message/cs",
                headers={"access_token": self._credentials.access_token},
                json={"recipient": {"user_id": chat_id}, "message": {"text": text}})
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise ChannelError("Không kết nối được Zalo OA.", 502) from None
        if not isinstance(data, dict):
            raise ChannelError("Zalo OA trả về dữ liệu không hợp lệ.", 502)
        if response.status_code != 200 or data.get("error") != 0:
            code = data.get("error", response.status_code)
            code = code if isinstance(code, int) else response.status_code
            raise ChannelError(f"Zalo OA từ chối gửi tin (mã {code}). Kiểm tra token và quyền nhắn tin.", 502)
        return data.get("data", {})

    async def chat_kind(self, chat_id):
        return ChatKind.PRIVATE
