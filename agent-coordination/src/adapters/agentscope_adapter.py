"""AgentScope primitive adapter.

Trusted upstream provider cấp một Agent có sẵn và được isolate. Module không tự tạo
registry, agent factory, service scheduler hoặc production in-memory state.
"""

import json
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from agentscope.agent import Agent
from agentscope.message import TextBlock, UserMsg
from groupchat.models import AgentOutput, RoomError
from groupchat.ports import Invocation


@dataclass
class AgentSession:
    agent: Agent
    framework_agent_id: str
    framework_reference: str
    transcript_cursor: int = 0


class AgentSessionProvider(Protocol):
    def session(
        self, invocation: Invocation
    ) -> AbstractAsyncContextManager[AgentSession]:
        """Cấp pinned Agent với exclusive, fenced scope binding.

        Không share Agent/state/toolkit/workspace/cache giữa các room; không có
        scheduling middleware, incoming event bus, background job hoặc SDK retry ngầm.
        Persist AgentState.model_dump(mode='json') và cursor dưới storage lease;
        restore bằng AgentState.model_validate. Không expose private state.
        Giữ lease trong toàn bộ reply; preflight không được gửi model/tool request.
        Provider là trusted integration code, không do client command cung cấp.
        """
        ...

    async def cancel(self, invocation: Invocation) -> bool:
        """Xác nhận terminal state và chặn future dispatch của operation ID này.

        HTTP disconnect hoặc task.cancel riêng lẻ chưa phải là confirmation.
        """
        ...


class AgentScopeAdapter:
    def __init__(self, provider: AgentSessionProvider):
        self.provider = provider

    async def _validate(self, session: AgentSession, invocation: Invocation) -> None:
        p, agent = invocation.participant, session.agent
        if (
            session.framework_agent_id != p.framework_agent_id
            or session.framework_reference != p.framework_reference
        ):
            raise RoomError("MAPPING_MISSING")
        # Chỉ hỗ trợ no-tools profile cho đến khi có backend tool-grant adapter.
        if any(
            g.tools or g.mcps or g.skills_or_loaders for g in agent.toolkit.tool_groups
        ):
            raise RoomError(
                "FORBIDDEN",
                "This adapter profile accepts no registered tools or skills",
            )
        if (
            agent.model_config.max_retries != 0
            or agent.model.max_retries != 0
            or agent.model_config.fallback_model is not None
        ):
            raise RoomError("VALIDATION_ERROR", "Disable model retries and fallback")
        if not agent.react_config.interruption_raise_cancelled_error:
            raise RoomError("VALIDATION_ERROR", "Cancellation must propagate")

    async def prepare(self, invocation: Invocation) -> None:
        async with self.provider.session(invocation) as session:
            await self._validate(session, invocation)

    async def invoke(self, invocation: Invocation) -> AgentOutput:
        async with self.provider.session(invocation) as session:
            await self._validate(session, invocation)
            # Thay model-visible history ở mỗi lượt: cursor sẽ giữ stale task ACL
            # và bỏ sót pending mail cũ do Context Builder chọn.
            session.agent.state.context = []
            messages = [
                UserMsg(
                    name="room-context", content=[TextBlock(text=m.model_dump_json())]
                )
                for m in invocation.transcript
            ]
            messages.append(
                UserMsg(
                    name="room-data",
                    content=[
                        TextBlock(
                            text=json.dumps(
                                {
                                    "ticket_id": invocation.context.ticket_id,
                                    "ticket_generation": invocation.context.ticket_generation,
                                    "ticket_context": [
                                        item.model_dump(mode="json")
                                        for item in invocation.ticket_context
                                    ],
                                    "task_board": [
                                        task.model_dump(mode="json")
                                        for task in invocation.tasks
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        )
                    ],
                )
            )
            messages.append(
                UserMsg(
                    name="room-context",
                    content=[TextBlock(text=invocation.instruction)],
                )
            )
            reply = await session.agent.reply(messages)
            # Chỉ lấy final text hoặc validated structured content; bỏ thinking/tool blocks.
            if reply.structured_output is not None:
                output = AgentOutput.model_validate(reply.structured_output)
            else:
                text = reply.get_text_content() or ""
                # Published agent có thể trả JSON; không repair/retry invalid output.
                output = (
                    AgentOutput.model_validate_json(text)
                    if text.lstrip().startswith("{")
                    else AgentOutput(content=text)
                )
            session.transcript_cursor = max(
                (m.sequence for m in invocation.transcript), default=0
            )
            return output

    async def cancel(self, invocation: Invocation) -> bool:
        return await self.provider.cancel(invocation)
