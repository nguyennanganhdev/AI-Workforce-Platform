# -*- coding: utf-8 -*-
"""ToolBase wrappers route all invocation forms through ExecutionGateway."""

from typing import Any

import json

from ._utils import ExecutionError


def guarded_tool(
    gateway: Any, scope: Any, descriptor: Any, request_factory: Any
) -> Any:
    """
    Lazy import avoids loading SDK/optional tool dependencies at module import.
    """
    from agentscope.tool import ToolBase, ToolChunk
    from agentscope.message import TextBlock, ToolResultState
    from agentscope.permission import PermissionDecision, PermissionBehavior

    class GuardedTool(ToolBase):
        """No raw MCPTool is exposed to legacy tool assembly."""

        def __init__(self) -> None:
            super().__init__()
            self.name = descriptor["llm_alias"]
            self.description = descriptor["description"]
            self.input_schema = (
                gateway.mcp.model_input_schema(descriptor)
                if descriptor["source_kind"] == "mcp"
                else descriptor["input_schema"]
            )
            self.is_read_only = descriptor["effect"] == "read"
            self.is_concurrency_safe = self.is_read_only

        async def check_permissions(self, *_args: Any, **_kwargs: Any) -> Any:
            # The wrapper has no raw execution path. Returning ALLOW delegates
            # consent to the persisted Workforce approval inside call(), rather
            # than treating a generic workspace permission as booking consent.
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="Guarded by Workforce policy and consent.",
            )

        async def call(self, **kwargs: Any) -> Any:
            try:
                request = await request_factory(
                    descriptor["tool_version_id"], kwargs
                )
                result = await gateway.execute(scope, request)
                # Only the model-safe projection leaves the gateway wrapper.
                public = {
                    k: result.get(k)
                    for k in (
                        "call_id",
                        "status",
                        "output",
                        "error",
                        "approval_id",
                    )
                }
                return ToolChunk(
                    content=[
                        TextBlock(text=json.dumps(public, ensure_ascii=False))
                    ],
                    state=ToolResultState.SUCCESS,
                )
            except ExecutionError as error:
                return ToolChunk(
                    content=[TextBlock(text=json.dumps(error.public()))],
                    state=ToolResultState.DENIED,
                )

    return GuardedTool()


async def assemble_toolkit(
    gateway: Any, scope: Any, context: Any, spec: Any, request_factory: Any
) -> Any:
    """
    Return only available pinned bindings with unique stable model aliases.
    """
    from agentscope.tool import Toolkit

    tools, aliases = [], set()
    for binding in spec.get("tool_bindings", []):
        request = {
            "run_id": context["run_id"],
            "agent_id": spec["agent_id"],
            "version_id": spec["version_id"],
            "tool_version_id": binding["tool_version_id"],
        }
        try:
            _, descriptor = await gateway.policy.check(
                scope, request, operation="prepare_toolkit"
            )
        except ExecutionError:
            continue
        alias = descriptor["llm_alias"]
        if alias in aliases:
            raise ExecutionError("TOOL_ALIAS_CONFLICT", 422)
        aliases.add(alias)
        tools.append(guarded_tool(gateway, scope, descriptor, request_factory))
    return Toolkit(tools=tools)
