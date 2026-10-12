"""Keep partner tools out of AgentScope's background offload (spec A8, P0 item 22).

AgentScope moves a tool that has run for 10 seconds to the background and tells the model "you will be
notified". That promise dies with the process, and for a tool that changes things at a partner it hides the
real answer. The tools carry their own deadline (workforce/partner_tools.py); this is the second line: a tool
that says `allow_offload = False` goes straight through, every other tool is handled by the framework's own
middleware, which is installed first and unchanged. `build_app` passes `agent_cls` as `custom_agent_cls`.
"""
from __future__ import annotations

from agentscope.agent import Agent
from agentscope.app.middleware import ToolOffloadMiddleware
from agentscope.middleware import MiddlewareBase


class OffloadPolicy(MiddlewareBase):  # pylint: disable=abstract-method
    def __init__(self, inner: ToolOffloadMiddleware) -> None:
        self.inner = inner

    async def on_acting(self, agent, input_kwargs, next_handler):  # type: ignore[override]
        tool = await agent.toolkit.get_tool(input_kwargs["tool_call"].name)
        if tool is not None and getattr(tool, "allow_offload", True) is False:
            async for item in next_handler(**input_kwargs):
                yield item
            return
        async for item in self.inner.on_acting(agent, input_kwargs, next_handler):
            yield item


class PolicyAgent(Agent):
    """The agent class for `create_app(custom_agent_cls=...)`: the service's offload middleware, wrapped."""

    def __init__(self, *args, middlewares=None, **kwargs):
        wrapped = [OffloadPolicy(m) if type(m) is ToolOffloadMiddleware else m for m in (middlewares or [])]
        super().__init__(*args, middlewares=wrapped, **kwargs)
