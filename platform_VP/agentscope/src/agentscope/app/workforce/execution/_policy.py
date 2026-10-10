# -*- coding: utf-8 -*-
"""Fail-closed checks over persisted runtime, pins, catalog and audience."""

from typing import Any

import re

from ._effects import classify
from ._utils import ExecutionError, owner, value


class ExecutionPolicy:
    """
    Policy consumes authenticated runtime and Registry ports via injection.
    """

    def __init__(self, runtime: Any, registry: Any) -> None:
        self.runtime, self.registry = runtime, registry

    async def check(
        self,
        scope: Any,
        request: Any,
        operation: Any = "execute",
        uow: Any = None,
    ) -> Any:
        """
        Reload authority; broker/model claims cannot change the run owner.
        """
        scope, request = owner(scope), value(request)
        context = value(
            await self.runtime.load(scope, request["run_id"], uow=uow)
        )
        if not context or owner(context["scope"]) != scope:
            raise ExecutionError("RESOURCE_NOT_FOUND", 404)
        if context.get("status") in {"cancelled", "failed", "closed"}:
            raise ExecutionError("RUN_NOT_EXECUTABLE", 403)
        if context.get("mode") not in {"production", "evaluation"}:
            raise ExecutionError("EXECUTION_MODE_INVALID", 403)
        # The adapter revalidates membership, route revision, grant, audience,
        # workflow binding and cancellation using persisted records.
        await self.runtime.revalidate(scope, context, operation, uow=uow)
        pins = context.get("version_pins", [])
        if not any(
            p["agent_id"] == request["agent_id"]
            and p["version_id"] == request["version_id"]
            for p in pins
        ):
            raise ExecutionError("AGENT_VERSION_NOT_PINNED", 403)
        spec = value(
            await self.runtime.get_agent_spec(
                scope,
                request["agent_id"],
                request["version_id"],
                uow=uow,
            )
        )
        descriptor = value(
            await self.registry.get_tool_snapshot(
                scope,
                request["tool_version_id"],
            )
        )
        if (
            not descriptor
            or not descriptor.get("available")
            or ("scope" in descriptor and owner(descriptor["scope"]) != scope)
        ):
            raise ExecutionError("TOOL_UNAVAILABLE", 403)
        binding = next(
            (
                b
                for b in spec.get("tool_bindings", [])
                if b["tool_version_id"] == request["tool_version_id"]
            ),
            None,
        )
        if (
            not binding
            or binding["tool_id"] != descriptor["tool_id"]
            or binding["schema_hash"] != descriptor["schema_hash"]
        ):
            raise ExecutionError("TOOL_BINDING_MISMATCH", 403)
        if binding["required_capability"] not in descriptor["capabilities"]:
            raise ExecutionError("TOOL_CAPABILITY_MISMATCH", 403)
        effect = classify(descriptor)
        if effect not in spec.get("execution_policy", {}).get(
            "allowed_effects", []
        ):
            raise ExecutionError("EFFECT_NOT_ALLOWED", 403)
        if not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_-]{0,63}", descriptor["llm_alias"]
        ):
            raise ExecutionError("INVALID_TOOL_ALIAS", 422)
        await self.runtime.authorize_tool(scope, context, descriptor, uow=uow)
        return context, descriptor
