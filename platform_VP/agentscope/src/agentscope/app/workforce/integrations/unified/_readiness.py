"""Readiness of the actual published agents bound to a partner route."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ...._agent_spec import AgentSpec
from ...._service._agent_studio import pinned_view, tool_catalog
from ...._service._publish_gate import publication_blocker


def team_hash(route: dict) -> str:
    members = (route.get("config") or {}).get("member_agents") or {}
    return hashlib.sha256(json.dumps(members, sort_keys=True).encode()).hexdigest()


def route_tools(route: dict) -> dict[str, dict]:
    tools = route.get("tools") or []
    return ({name: tool for name, tool in tools.items() if not tool.get("internal")}
            if isinstance(tools, dict) else {tool["name"]: tool for tool in tools if not tool.get("internal")})


async def checked_agent(storage: Any, user_id: str, agent_id: str, version: int | None = None) -> tuple[Any, AgentSpec]:
    record = await storage.get_agent(user_id, agent_id)
    if record is None or record.user_id != user_id or record.source != "user":
        raise ValueError("AGENT_NOT_OWNED")
    data = record.data
    if data.system_role != "business" or data.lifecycle_state != "published" or not data.published_version:
        raise ValueError("AGENT_NOT_PUBLISHED")
    if not data.invite_config.invitable or not (data.invite_config.invite_description or "").strip():
        raise ValueError("AGENT_NOT_INVITABLE")
    if version is not None:
        record = pinned_view(record, version)
        data = record.data
    try:
        spec = AgentSpec.model_validate(data.spec)
    except ValueError as exc:
        raise ValueError("AGENT_SPEC_INVALID") from exc
    if publication_blocker(spec, data.evaluation):
        raise ValueError("AGENT_EVALUATION_REQUIRED")
    declared = {(tool.mcp_id, tool.tool_name) for tool in spec.tools}
    bound = {(tool.get("mcp_id"), tool.get("tool_name")) for tool in data.tool_bindings}
    if bound != declared:
        raise ValueError("AGENT_TOOL_BINDING_MISSING")
    sessions = await storage.list_sessions(user_id, agent_id)
    if not any(session.origin.type == "user" and not session.team_id for session in sessions):
        raise ValueError("AGENT_PRIMARY_SESSION_MISSING")
    return record, spec


async def route_readiness(storage: Any, route: dict, *, status: str = "active") -> dict:
    """Fail closed on missing roster, ownership, evaluation or tool bindings."""
    user_id = route["manager_account_id"]
    members = (route.get("config") or {}).get("member_agents") or {}
    tools = route_tools(route)
    issues: list[dict] = []
    views: list[dict] = []
    covered: set[str] = set()
    writers: dict[str, list[str]] = {}
    if status != "active":
        issues.append({"code": "ROUTE_NOT_ACTIVE"})
    if not members:
        issues.append({"code": "TEAM_NOT_BOUND"})
    catalog = await tool_catalog(storage, user_id)
    for agent_id, binding in members.items():
        try:
            record, spec = await checked_agent(storage, user_id, agent_id, binding.get("version") if route.get("contract_frozen") else None)
        except ValueError as exc:
            issues.append({"code": str(exc), "agent_id": agent_id})
            continue
        permitted = set(binding.get("tools") or [])
        actual: set[str] = set()
        for tool in spec.tools:
            meta = catalog.get(tool.tool_id)
            names = [name for name, config in tools.items()
                     if (config.get("mcp_tool") or name) == tool.tool_name
                     and config.get("mcp_id") == tool.mcp_id]
            if meta is None or meta.get("mcp_id") != tool.mcp_id or meta.get("tool_name") != tool.tool_name:
                issues.append({"code": "TOOL_NOT_REGISTERED", "agent_id": agent_id, "tool": tool.tool_name})
            elif not names:
                issues.append({"code": "TOOL_OUTSIDE_ROUTE", "agent_id": agent_id, "tool": tool.tool_name})
            else:
                actual.update(names)
        if not permitted <= actual or not permitted <= set(tools):
            issues.append({"code": "TOOL_BINDING_INVALID", "agent_id": agent_id})
        if not permitted and not binding.get("coordinator"):
            issues.append({"code": "AGENT_CAPABILITY_MISSING", "agent_id": agent_id})
        covered.update(permitted & actual)
        for name in permitted & actual:
            if tools[name].get("read_only") is not True:
                writers.setdefault(name, []).append(agent_id)
                if not binding.get("coordinator"):
                    issues.append({"code": "WRITE_TOOL_REQUIRES_COORDINATOR", "agent_id": agent_id, "tool": name})
        views.append({"agent_id": agent_id, "name": record.data.name,
                      "published_version": record.data.published_version,
                      "coordinator": bool(binding.get("coordinator")), "tools": sorted(permitted)})
    for name in sorted(set(tools) - covered):
        issues.append({"code": "ROUTE_TOOL_UNASSIGNED", "tool": name})
    for name, owners in writers.items():
        if len(owners) > 1:
            issues.append({"code": "WRITE_TOOL_MULTIPLE_OWNERS", "tool": name})
    return {"route_id": route["route_id"], "ready": not issues,
            "team_hash": team_hash(route), "agents": views, "issues": issues}


async def bindable_members(storage: Any, route: dict, agent_ids: list[str], coordinator_id: str) -> dict:
    if len(set(agent_ids)) != len(agent_ids) or coordinator_id not in agent_ids:
        raise ValueError("TEAM_MEMBERS_INVALID")
    tools = route_tools(route)
    members = {}
    for agent_id in agent_ids:
        record, spec = await checked_agent(storage, route["manager_account_id"], agent_id)
        assigned = [name for name, config in tools.items() for tool in spec.tools
                    if (config.get("mcp_tool") or name) == tool.tool_name
                    and config.get("mcp_id") == tool.mcp_id]
        members[agent_id] = {"name": record.data.name, "tools": sorted(set(assigned)),
                             "version": record.data.published_version,
                             **({"coordinator": True} if agent_id == coordinator_id else {})}
    return members
