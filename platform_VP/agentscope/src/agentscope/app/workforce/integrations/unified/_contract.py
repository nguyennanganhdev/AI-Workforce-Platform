"""Immutable partner contracts captured with the ticket's initial SQL write."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from ...foundation._tables import partner_manager_routes
from ...orchestration._tables import workflows
from ._tables import integrations, routes


def _json(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported contract value: {type(value).__name__}")


def transport_identity(client: Any) -> dict:
    """Freeze transport settings without copying credentials into workflow JSON."""
    config = copy.deepcopy(client.model_dump(mode="json"))
    mcp_config = config.get("mcp_config") or {}
    # Credential rotation is allowed. Changed endpoints fail closed because a
    # current credential must not be sent to an older or different endpoint.
    mcp_config.pop("headers", None)
    mcp_config.pop("env", None)
    return config


def tool_descriptor(spec: dict, current_mcp: Any) -> dict | None:
    """Use a frozen schema while still honoring current connector revocation."""
    if current_mcp is None or not current_mcp.enabled:
        return None
    snapshot = spec.get("catalog_snapshot")
    if snapshot:
        if snapshot["transport"] != transport_identity(current_mcp.client):
            raise ValueError("MCP_TRANSPORT_REVISION_CHANGED")
        if not any(item.get("name") == spec.get("mcp_tool") for item in current_mcp.discovered_tools):
            raise ValueError("MCP_TOOL_REVOKED")
        return copy.deepcopy(snapshot["descriptor"])
    return next((item for item in current_mcp.discovered_tools
                 if item.get("name") == spec.get("mcp_tool")), None)


class ContractPinnedBootstrap:
    """Wrap bootstrap so reserve() persists the same contract read at start."""

    def __init__(self, bootstrap: Any, storage_provider: Any = None) -> None:
        self._bootstrap = bootstrap
        self._storage_provider = storage_provider

    async def prepare(self, scope, actor, audience, message, uow):
        aggregate = await self._bootstrap.prepare(scope, actor, audience, message, uow)
        workflow = aggregate.workflow
        row = (await uow.execute(select(routes).where(
            routes.c.route_id == workflow.route_id,
            routes.c.tenant_id == scope.tenant_id,
            routes.c.manager_account_id == scope.manager_account_id,
            routes.c.partner_client_id == audience.partner_client_id,
        ).with_for_update())).mappings().first()
        if row is None:
            return aggregate  # Non-case workflows retain their existing runtime.
        grant = (await uow.execute(select(partner_manager_routes).where(
            partner_manager_routes.c.id == workflow.route_id,
            partner_manager_routes.c.tenant_id == scope.tenant_id,
            partner_manager_routes.c.manager_account_id == scope.manager_account_id,
            partner_manager_routes.c.partner_client_id == audience.partner_client_id,
        ).with_for_update())).mappings().first()
        if grant is None or grant["status"] != "active" or grant["revision"] != workflow.route_revision:
            raise PermissionError("Route grant changed before contract capture")
        route = json.loads(json.dumps(dict(row), default=_json))
        integration = (await uow.execute(select(integrations).where(
            integrations.c.integration_id == route.get("integration_id"),
            integrations.c.tenant_id == scope.tenant_id,
        ))).mappings().first()
        route["event_schema"] = copy.deepcopy(integration["event_schema"] if integration else {"events": {}})
        route["grant_snapshot"] = json.loads(json.dumps(dict(grant), default=_json))
        storage = self._storage_provider() if self._storage_provider is not None else None
        if storage is not None:
            from ...._service._agent_studio import pinned_view
            members = (route.get("config") or {}).get("member_agents") or {}
            for agent_id, member in members.items():
                record = await storage.get_agent(scope.manager_account_id, agent_id)
                if record is None:
                    raise ValueError("PINNED_AGENT_UNAVAILABLE")
                version = member.get("version") or record.data.published_version
                pinned_view(record, int(version))
                member["version"] = int(version)
            for spec in route.get("tools") or []:
                record = await storage.get_mcp(scope.manager_account_id, spec.get("mcp_id"))
                descriptor = tool_descriptor(spec, record)
                if descriptor is None:
                    raise ValueError("PINNED_TOOL_UNAVAILABLE")
                spec["catalog_snapshot"] = {
                    "revision": getattr(record, "catalog_revision", None),
                    "descriptor": copy.deepcopy(descriptor),
                    "transport": transport_identity(record.client),
                }
        route["contract_frozen"] = True
        snapshot = {"format": 1, "route": route}
        snapshot["sha256"] = hashlib.sha256(json.dumps(
            snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
        return aggregate.model_copy(update={"workflow": workflow.model_copy(
            update={"contract_snapshot": snapshot},
        )})


def read_contract(payload: dict) -> dict | None:
    snapshot = ((payload or {}).get("workflow") or {}).get("contract_snapshot") or {}
    if not snapshot:
        return None
    check = {key: value for key, value in snapshot.items() if key != "sha256"}
    digest = hashlib.sha256(json.dumps(check, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    if snapshot.get("format") != 1 or snapshot.get("sha256") != digest or not snapshot.get("route"):
        raise ValueError("WORKFLOW_CONTRACT_CORRUPT")
    return copy.deepcopy(snapshot["route"])


async def route_for_workflow(store: Any, workflow_id: str, route_id: str | None = None) -> dict | None:
    """Resolve the persisted contract; legacy tickets cannot silently drift."""
    async with store._uows() as uow:
        row = (await uow.execute(select(workflows.c.payload).where(
            workflows.c.id == workflow_id,
        ))).first()
    if row:
        workflow = (row[0] or {}).get("workflow") or {}
        pinned = read_contract(row[0])
        if pinned is not None:
            return pinned
        route_id = workflow.get("route_id") or route_id
    route = await store.route(route_id) if route_id else None
    if row and route is not None:
        raise ValueError("WORKFLOW_CONTRACT_NOT_PINNED")
    return route
