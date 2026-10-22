# -*- coding: utf-8 -*-
"""The agent owner's per-tool policy for MCP tools.

The platform asks before a sensitive MCP tool runs (booking, paying,
cancelling, sending, deleting…) and runs the others on its own. The owner
can override that per tool, per agent (``AgentData.tool_policies``):

- ``auto`` — run without asking, also in scheduled runs where nobody is
  there to ask ("Luôn cho phép"). Explicit deny rules still win.
- ``ask`` — always ask first, even for a tool the platform deems safe.
  With nobody to ask (scheduled runs) the call is refused.
- ``deny`` — never run it.

Policies are read when a tool is checked, so "Luôn cho phép" on an
approval card holds for the rest of the run that raised it.
"""
from typing import Any, Awaitable, Callable

from ...middleware import MiddlewareBase
from ...message import ToolCallState
from ...permission import PermissionBehavior, PermissionDecision, PermissionMode

TOOL_POLICIES = ("auto", "ask", "deny")


def is_policy_tool(tool_name: str) -> bool:
    """Policies cover MCP tools, the only ones with real-world effects."""
    return tool_name.startswith("mcp__")


class ToolPolicyMiddleware(MiddlewareBase):
    """Apply the owner's per-tool policy on top of the platform's check."""

    def __init__(self, load_policies: Callable[[], Awaitable[dict[str, str]]]) -> None:
        """
        Args:
            load_policies: Returns the agent's current ``tool_policies``.
        """
        self._load_policies = load_policies

    async def on_check_permission(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., Awaitable[PermissionDecision]],
    ) -> PermissionDecision:
        tool = input_kwargs["tool"]
        if not is_policy_tool(tool.name):
            return await next_handler(**input_kwargs)
        policy = (await self._load_policies()).get(tool.name)
        if policy == "deny":
            return PermissionDecision(
                behavior=PermissionBehavior.DENY,
                message=f"Chủ agent đã cấm tool {tool.name}.",
                decision_reason="Owner tool policy: deny",
            )
        if policy == "auto":
            # pylint: disable-next=protected-access
            denied = await agent._engine._check_deny_rules(tool, input_kwargs["tool_input"])
            return denied or PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message=f"Chủ agent cho phép {tool.name} chạy không cần hỏi.",
                decision_reason="Owner tool policy: auto",
            )
        decision = await next_handler(**input_kwargs)
        if (
            policy == "ask"
            and decision.behavior is PermissionBehavior.ALLOW
            and input_kwargs["tool_call"].state != ToolCallState.ALLOWED
        ):
            # pylint: disable-next=protected-access
            if agent._engine.context.mode is PermissionMode.DONT_ASK:
                return PermissionDecision(
                    behavior=PermissionBehavior.DENY,
                    message=(
                        f"{tool.name} cần chủ agent duyệt, nhưng lượt chạy này "
                        "không có ai để hỏi."
                    ),
                    decision_reason="Owner tool policy: ask, nobody to ask",
                )
            return PermissionDecision(
                behavior=PermissionBehavior.ASK,
                message=f"Chủ agent muốn duyệt trước mỗi lần {tool.name} chạy.",
                decision_reason="Owner tool policy: ask",
            )
        return decision
