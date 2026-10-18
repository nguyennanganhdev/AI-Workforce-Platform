"""Text channel delivery and short, durable approval references."""
import json
import re
import secrets

from pydantic import Field

from ...event import ReplyEndEvent, RequireUserConfirmEvent
from ...message import Msg, TextBlock
from ._base import ChannelBase, ChannelEvent, ChannelConfirmationResultEvent, _EVENT_ADAPTER


class TextChannelConfig(ChannelBase.Config):
    allowed_user_ids: list[str] = Field(default_factory=list, title="Người dùng được phép",
        description="ID người dùng. Để trống để nhận từ mọi người dùng của kênh.")
    approver_user_ids: list[str] = Field(default_factory=list, title="Người được duyệt thay",
        description="Ngoài người gửi yêu cầu, chỉ các ID này được duyệt thao tác.")
    show_thinking: bool = Field(default=False, title="Hiện suy luận")
    show_tool_process: bool = Field(default=False, title="Hiện tiến trình công cụ")


class TextChannel(ChannelBase):
    """Shared text-only presentation; adapters supply transport and ingress."""

    def bind_message_bus(self, bus):
        self._bus = bus

    def allows(self, user_id: str) -> bool:
        return not self._config.allowed_user_ids or user_id in self._config.allowed_user_ids

    def _approval_key(self, token: str) -> str:
        from ..message_bus import MessageBusKeys
        return MessageBusKeys.channel_approval(self.channel_id, token)

    async def _approval(self, event, tool):
        if getattr(self, "_bus", None) is None:
            raise RuntimeError("Channel approval requires a message bus")
        token = secrets.token_hex(8)
        target = {"chat_id": event.chat_id, "requester_id": event.channel_user_id,
            "agent_id": event.metadata.get("agent_id", ""),
            "session_id": event.metadata.get("session_id", ""), "tool_call_id": tool.id}
        await self._bus.registry_set(self._approval_key(token), "pending", json.dumps(target), ttl_secs=86400)
        return token

    async def decision(self, token: str, approved: bool, event: ChannelEvent, emit) -> str:
        """Only the original sender or an explicit approver in the same chat."""
        if not re.fullmatch(r"[0-9a-f]{16}", token) or not self.allows(event.channel_user_id):
            return "Bạn không có quyền duyệt yêu cầu này."
        key = self._approval_key(token)
        async with self._bus.acquire_lock(key + ":lock", ttl_secs=30):
            raw = await self._bus.registry_get(key, "pending")
            if not raw:
                return "Yêu cầu đã được xử lý hoặc hết hạn."
            target = json.loads(raw)
            if target["chat_id"] != event.chat_id or event.channel_user_id not in {
                target["requester_id"], *self._config.approver_user_ids,
            }:
                return "Bạn không có quyền duyệt yêu cầu này."
            await emit(ChannelConfirmationResultEvent(channel_id=self.channel_id,
                chat_id=event.chat_id, channel_user_id=target["requester_id"],
                actor=event.channel_user_id, agent_id=target["agent_id"],
                session_id=target["session_id"], tool_call_id=target["tool_call_id"], approved=approved))
            await self._bus.registry_del(key, "pending")
        return "Đã gửi quyết định đồng ý." if approved else "Đã gửi quyết định từ chối."

    async def receive_text(self, event: ChannelEvent, emit) -> None:
        if not self.allows(event.channel_user_id):
            return
        command = re.fullmatch(r"(DUYET|TUCHOI)\s+([0-9a-f]{16})", event.message.strip(), re.IGNORECASE)
        if command:
            answer = await self.decision(command[2].lower(), command[1].upper() == "DUYET", event, emit)
            await self._send_text(event.chat_id, answer)
            return
        await emit(event)

    async def send_response(self, event, events):
        reply = None
        confirm = None
        async for raw in events:
            item = _EVENT_ADAPTER.validate_python(raw)
            if isinstance(item, RequireUserConfirmEvent):
                confirm = item
                break
            reply_id = getattr(item, "reply_id", None)
            if reply_id is not None:
                if reply is None:
                    reply = Msg(name="assistant", role="assistant", content=[])
                    reply.id = reply_id
                reply.append_event(item)
            if isinstance(item, ReplyEndEvent):
                break
        for block in self._render(reply, show_thinking=self._config.show_thinking,
                                  show_tool_process=self._config.show_tool_process):
            if isinstance(block, TextBlock):
                for part in self._split_long_message(block.text):
                    if part:
                        await self._send_text(event.chat_id, part)
            else:
                await self._send_text(event.chat_id, "Có tệp đính kèm. Mở Platform để xem tệp.")
        if confirm:
            for tool in confirm.tool_calls:
                token = await self._approval(event, tool)
                await self._send_approval(event.chat_id, tool.name, token)

    async def _send_approval(self, chat_id: str, name: str, token: str):
        await self._send_text(chat_id, f"Cần bạn duyệt công cụ {name}.\n"
            f"Đồng ý: DUYET {token}\nTừ chối: TUCHOI {token}\nYêu cầu có hiệu lực trong 24 giờ.")
