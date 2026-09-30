"""AgentScope 2.0.9 primitive adapter; NOT Agent Team Service.

A trusted upstream provider lends an existing, isolated Agent. No registry,
agent factory, service scheduler or production in-memory state is invented here.
"""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from importlib.metadata import version
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
        """Lend pinned existing Agent with exclusive, fenced scope binding.

        No cross-room Agent/state/toolkit/workspace/cache sharing; no scheduling
        middleware, incoming event bus, background jobs or hidden SDK retries.
        Persist AgentState.model_dump(mode='json') + cursor under DEV-4 lease;
        restore using AgentState.model_validate. Never expose private state.
        Hold a lease for full reply; preflight must not send model/tool requests.
        Provider is trusted integration code, not supplied by client commands.
        """
        ...

    async def cancel(self, invocation: Invocation) -> bool:
        """Confirm terminal AND suppress future dispatch of this operation ID.

        HTTP disconnect/task.cancel alone is not confirmation.
        """
        ...


class AgentScopeAdapter:
    def __init__(self, provider: AgentSessionProvider):
        if version("agentscope") != "2.0.9":
            raise RuntimeError("AgentScope adapter requires exactly 2.0.9")
        self.provider = provider

    async def _validate(self, session: AgentSession, invocation: Invocation) -> None:
        p, agent = invocation.participant, session.agent
        if (
            session.framework_agent_id != p.framework_agent_id
            or session.framework_reference != p.framework_reference
        ):
            raise RoomError("MAPPING_MISSING")
        # Narrow no-tools integration until backend tool-grant adapter is supplied.
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
            messages = [
                UserMsg(
                    name="room-context", content=[TextBlock(text=m.model_dump_json())]
                )
                for m in invocation.transcript
                if m.sequence > session.transcript_cursor
            ]
            messages.append(
                UserMsg(
                    name="room-context",
                    content=[TextBlock(text=invocation.instruction)],
                )
            )
            reply = await session.agent.reply(messages)
            # Only final text/validated structured content; no thinking/tool blocks.
            if reply.structured_output is not None:
                output = AgentOutput.model_validate(reply.structured_output)
            else:
                text = reply.get_text_content() or ""
                # Published agent may return JSON; no repair/retry on invalid output.
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
