"""Onboard a partner from its declaration (unified mode).

The partner hands over one declaration (e.g. Vinhomes'
``deploy/platform/vinhomes-declaration.json``). The platform operator posts it
with the partner's MCP address and token; the platform then creates or
updates, idempotently:

* the partner client with its customer key, a provider integration with its
  provider key and HMAC signing key (keys are returned once, only when new or
  when ``new_keys`` asks for fresh ones; old keys are then revoked);
* the partner's MCP in the area manager's library (tools discovered);
* the route leader as an Agent Studio agent (a new version only when the
  declaration changed; open tickets keep the version they started with);
* the provider event schema of the integration;
* one route per management ref, pending until the partner confirms it.
"""

from __future__ import annotations

import fnmatch
import secrets
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr
from sqlalchemy import insert, select, text, update

from ...contracts import PartnerOperation, Scope
from ...foundation._tables import (
    manager_memberships,
    partner_manager_routes,
    provider_credentials,
    provider_integrations,
)
from ._secrets import seal
from ._tables import integrations, routes

CUSTOMER_OPERATIONS = {op.value for op in PartnerOperation} - {
    PartnerOperation.PUBLISH_JOB_EVENT.value,
    PartnerOperation.READ_EVENT_RECEIPT.value,
}


class OnboardingRequest(BaseModel):
    declaration: dict
    manager_account_id: str = Field(min_length=1, max_length=255)
    mcp_url: AnyHttpUrl
    mcp_token: SecretStr | None = None
    management_refs: list[str] = Field(min_length=1, max_length=50)
    environment: Literal["sandbox", "production"] = "sandbox"
    new_keys: bool = False


class OnboardingError(Exception):
    def __init__(self, status: int, code: str, details: Any = None) -> None:
        super().__init__(code)
        self.status, self.code, self.details = status, code, details


def _now() -> datetime:
    return datetime.now(UTC)


def leader_prompt(profile: dict) -> str:
    """The leader's authored prompt, built from the declared profile."""

    def bullets(items: list) -> str:
        return "\n".join(f"- {item}" for item in items if str(item).strip())

    parts = [f"Bạn là {profile['name']}: {profile.get('mission', '').strip()}"]
    if profile.get("handles"):
        parts.append("Việc bạn làm:\n" + bullets(profile["handles"]))
    if profile.get("refuses"):
        parts.append("Bạn từ chối:\n" + bullets(profile["refuses"]))
    if profile.get("escalate_when"):
        parts.append("Báo cho người phụ trách (nói rõ với người dùng) khi:\n" + bullets(profile["escalate_when"]))
    if profile.get("instructions"):
        parts.append(str(profile["instructions"]).strip())
    return "\n\n".join(parts)[:30000]


def allowed(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns or ["*"])


class PartnerOnboarding:
    def __init__(self, foundation: Any, discover: Any) -> None:
        self._foundation = foundation
        # ``discover(client) -> list[dict]``: the MCP catalog (network call).
        self._discover = discover

    async def _scope(self, manager_account_id: str) -> Scope:
        async with self._foundation.uows() as uow:
            row = (
                await uow.execute(
                    select(manager_memberships).where(
                        manager_memberships.c.manager_account_id == manager_account_id,
                        manager_memberships.c.status == "verified",
                    ),
                )
            ).mappings().first()
        if row is None:
            raise OnboardingError(409, "MANAGER_NOT_VERIFIED")
        return Scope(
            tenant_id=row["tenant_id"],
            domain_id=row["domain_id"],
            area_id=row["area_id"],
            manager_account_id=manager_account_id,
        )

    async def run(self, body: OnboardingRequest, business: Any, storage: Any, workspace_manager: Any) -> dict:
        declaration = body.declaration
        client_decl = declaration.get("client") or {}
        profiles = declaration.get("profiles") or []
        route_decl = declaration.get("route") or {}
        leader = next(
            (p for p in profiles if p.get("key") == route_decl.get("leader_profile")),
            None,
        )
        if not client_decl.get("name") or not client_decl.get("domain") or leader is None:
            raise OnboardingError(422, "DECLARATION_INVALID", "client and route.leader_profile are required")
        scope = await self._scope(body.manager_account_id)
        domain = str(client_decl["domain"]).strip().lower()
        if domain != scope.domain_id:
            raise OnboardingError(409, "DOMAIN_MISMATCH", {"manager_domain": scope.domain_id})
        keys: dict[str, str] = {}
        # Everything that can fail on the partner's side comes first: keys are
        # shown once, so none may be issued by a run that then fails.
        mcp_record = await self._mcp(body, declaration, storage)
        tools = self._tools(declaration, mcp_record, leader.get("tools_allow") or ["*"])

        client_id = await self._client(scope, f"{client_decl['name']} ({body.environment})")
        new_client = client_id is None
        if new_client:
            issued = await business.issue_partner_api_key(
                tenant_id=scope.tenant_id,
                domain_id=domain,
                name=f"{client_decl['name']} ({body.environment})",
            )
            client_id = issued.client_id
            keys["customer_key"] = issued.api_key
        elif body.new_keys:
            issued = await business.issue_client_key(client_id=client_id)
            keys["customer_key"] = issued.api_key
        integration_id = await self._integration(scope, client_id, f"{client_decl['name']} events")
        if new_client or body.new_keys or not await self._has_credential(integration_id):
            provider = await business.issue_client_key(client_id=client_id)
            signing_key_id = "sk_" + secrets.token_hex(8)
            signing_secret = secrets.token_urlsafe(32)
            await self._credential(
                integration_id,
                provider.key_id,
                signing_key_id,
                signing_secret,
                (declaration.get("provider_key") or {}).get("operations")
                or ["publish_job_event", "read_event_receipt"],
            )
            keys.update(
                provider_key=provider.api_key,
                signing_key_id=signing_key_id,
                signing_secret=signing_secret,
            )
            if body.new_keys and not new_client:
                kept = tuple(k.split(".")[0].removeprefix("dp_") for k in (keys["customer_key"], provider.api_key))
                await business.revoke_client_keys(client_id=client_id, keep=kept)

        agent_id, version = await self._leader(body, leader, tools, mcp_record, storage, workspace_manager)
        await self._schema(scope, client_id, integration_id, declaration)

        operations = [
            PartnerOperation(op)
            for op in (declaration.get("customer_key") or {}).get("operations") or sorted(CUSTOMER_OPERATIONS)
            if op in CUSTOMER_OPERATIONS
        ]
        out_routes = []
        for ref in dict.fromkeys(item.strip() for item in body.management_refs if item.strip()):
            route = await self._route(scope, client_id, ref, operations)
            await self._route_settings(route, scope, client_id, agent_id, integration_id, route_decl, tools)
            out_routes.append(
                {
                    "management_ref": ref,
                    "route_id": route["id"],
                    "revision": route["revision"],
                    "status": route["status"],
                },
            )
        return {
            "client_id": client_id,
            "integration_id": integration_id,
            "leader_agent_id": agent_id,
            "leader_version": version,
            "mcp": {"name": mcp_record.client.name, "tools": len(mcp_record.discovered_tools)},
            "tools": [tool["name"] for tool in tools],
            "routes": out_routes,
            "keys": keys,
        }

    # ---------------------------------------------------------- pieces

    async def _client(self, scope: Scope, name: str) -> str | None:
        async with self._foundation.uows() as uow:
            row = (
                await uow.execute(
                    text(
                        "SELECT id FROM partner_api_clients WHERE tenant_id = :tenant "
                        "AND domain_id = :domain AND name = :name AND status = 'active'",
                    ),
                    {"tenant": scope.tenant_id, "domain": scope.domain_id, "name": name},
                )
            ).first()
        return row[0] if row else None

    async def _integration(self, scope: Scope, client_id: str, name: str) -> str:
        async with self._foundation.uows() as uow:
            row = (
                await uow.execute(
                    select(provider_integrations.c.id).where(
                        provider_integrations.c.tenant_id == scope.tenant_id,
                        provider_integrations.c.partner_client_id == client_id,
                        provider_integrations.c.name == name,
                    ),
                )
            ).first()
            if row is not None:
                return row[0]
            integration_id = "pi_" + uuid4().hex
            now = _now()
            await uow.execute(
                insert(provider_integrations).values(
                    id=integration_id,
                    tenant_id=scope.tenant_id,
                    partner_client_id=client_id,
                    name=name,
                    status="active",
                    created_at=now,
                    updated_at=now,
                ),
            )
            await uow.commit()
        return integration_id

    async def _has_credential(self, integration_id: str) -> bool:
        async with self._foundation.uows() as uow:
            row = (
                await uow.execute(
                    select(provider_credentials.c.id).where(
                        provider_credentials.c.provider_integration_id == integration_id,
                        provider_credentials.c.status == "active",
                    ),
                )
            ).first()
        return row is not None

    async def _credential(self, integration_id, api_key_id, signing_key_id, secret, allowed_ops) -> None:
        now = _now()
        async with self._foundation.uows() as uow:
            await uow.execute(
                update(provider_credentials)
                .where(
                    provider_credentials.c.provider_integration_id == integration_id,
                    provider_credentials.c.status == "active",
                )
                .values(status="revoked", revoked_at=now, updated_at=now),
            )
            await uow.execute(
                insert(provider_credentials).values(
                    id="pc_" + uuid4().hex,
                    provider_integration_id=integration_id,
                    api_credential_id=api_key_id,
                    signing_key_id=signing_key_id,
                    secret_ref=seal(secret),
                    purpose="provider_events",
                    allowed_operations=list(allowed_ops),
                    status="active",
                    expires_at=None,
                    revoked_at=None,
                    created_at=now,
                    updated_at=now,
                ),
            )
            await uow.commit()

    async def _mcp(self, body: OnboardingRequest, declaration: dict, storage: Any) -> Any:
        from .....mcp import HttpMCPConfig, MCPClient
        from ....storage import MCPRecord

        server = declaration.get("mcp_server") or {}
        name = str(server.get("name") or "partner").strip()
        timeout = float(server.get("timeout") or 30.0)
        existing = next(
            (r for r in await storage.list_mcps(body.manager_account_id) if r.client.name == name),
            None,
        )
        headers = dict(existing.client.mcp_config.headers or {}) if existing is not None else {}
        if body.mcp_token is not None:
            headers["Authorization"] = "Bearer " + body.mcp_token.get_secret_value()
        client = MCPClient(
            name=name,
            is_stateful=False,
            mcp_config=HttpMCPConfig(url=str(body.mcp_url), headers=headers or None, timeout=timeout),
        )
        try:
            discovered = await self._discover(client)
        except Exception as exc:
            raise OnboardingError(502, "MCP_UNREACHABLE", str(exc)[:300]) from exc
        now = _now()
        if existing is not None:
            existing.client = client
            existing.url = str(body.mcp_url)
            existing.discovered_tools = discovered
            existing.catalog_revision = (existing.catalog_revision or 0) + 1
            existing.last_synced_at = now
            existing.enabled = True
            record = existing
        else:
            record = MCPRecord(
                user_id=body.manager_account_id,
                client=client,
                values={"auth_header": "Authorization"},
                display_name=name,
                description=f"MCP của đối tác {(declaration.get('client') or {}).get('name', '')}".strip(),
                url=str(body.mcp_url),
                tags=["partner", "declaration"],
                discovered_tools=discovered,
                catalog_revision=1,
                last_synced_at=now,
            )
        await storage.upsert_mcp(body.manager_account_id, record)
        return record

    @staticmethod
    def _tools(declaration: dict, mcp_record: Any, patterns: list[str]) -> list[dict]:
        catalog = {tool["name"]: tool for tool in mcp_record.discovered_tools}
        tools, missing = [], []
        for tool in declaration.get("tools") or []:
            if not allowed(tool["name"], patterns):
                continue
            mcp_tool = tool.get("mcp_tool") or tool["name"]
            if mcp_tool not in catalog:
                missing.append(mcp_tool)
                continue
            tools.append({**tool, "mcp_tool": mcp_tool, "mcp_id": mcp_record.id})
        if missing:
            raise OnboardingError(422, "TOOL_NOT_FOUND", missing)
        return tools

    async def _leader(self, body, profile, tools, mcp_record, storage, workspace_manager) -> tuple[str, int]:
        from ...._agent_spec import AgentSpec, SpecEscalation, SpecTool
        from ...._router._workforce_studio import _create_record
        from ...._service._agent_studio import materialize, set_draft

        tier = profile.get("model_tier") if profile.get("model_tier") in ("standard", "strong") else "standard"
        spec = AgentSpec(
            name=str(profile["name"])[:100],
            description=str(profile.get("mission") or "")[:1000],
            goal=str(profile.get("mission") or "")[:4000],
            language="vi",
            scope_in=[str(item)[:300] for item in (profile.get("handles") or [])][:30],
            scope_out=[str(item)[:300] for item in (profile.get("refuses") or [])][:30],
            escalation=[
                # Fixed ids: a rerun with the same declaration is no change.
                SpecEscalation(id=f"esc-{index}", when=str(item)[:1000], to="người phụ trách của đối tác")
                for index, item in enumerate(profile.get("escalate_when") or [])
            ][:30],
            tools=[
                SpecTool(
                    tool_id=f"{mcp_record.id}:{tool['mcp_tool']}",
                    mcp_id=mcp_record.id,
                    mcp_name=mcp_record.client.name,
                    tool_name=tool["mcp_tool"],
                    use_when=str(tool.get("description_override") or "")[:1000],
                    requires_consent=bool(tool.get("requires_consent")),
                    read_only=bool(tool.get("read_only")),
                )
                for tool in tools
            ][:60],
            prompt_override=leader_prompt(profile),
            model_tier=tier,
            memory_enabled=False,
            self_improve=False,
        )
        agents = await storage.list_agents(body.manager_account_id)
        record = next(
            (
                a for a in agents
                if a.data.system_role == "business" and a.data.name == spec.name
            ),
            None,
        )
        if record is None:
            record = await _create_record(storage, workspace_manager, body.manager_account_id, spec)
        current = record.data.spec if record.data.published_version else None
        if current != spec.model_dump(mode="json"):
            set_draft(record, spec, author="manager", note="Onboarding đối tác")
            materialize(record, spec, author="manager", note="Onboarding đối tác", evaluation=None)
        # A route leader answers its own partner tickets; the console Leader
        # must not borrow it (its tools need the partner case runtime).
        record.data.invite_config.invitable = False
        await storage.upsert_agent(body.manager_account_id, record)
        return record.id, int(record.data.published_version)

    async def _schema(self, scope: Scope, client_id: str, integration_id: str, declaration: dict) -> None:
        schema = (declaration.get("integration") or {}).get("event_schema") or {"events": {}}
        now = _now()
        async with self._foundation.uows() as uow:
            exists = (
                await uow.execute(
                    select(integrations.c.integration_id).where(integrations.c.integration_id == integration_id),
                )
            ).first()
            if exists is None:
                await uow.execute(
                    insert(integrations).values(
                        integration_id=integration_id,
                        tenant_id=scope.tenant_id,
                        partner_client_id=client_id,
                        event_schema=schema,
                        created_at=now,
                        updated_at=now,
                    ),
                )
            else:
                await uow.execute(
                    update(integrations)
                    .where(integrations.c.integration_id == integration_id)
                    .values(event_schema=schema, updated_at=now),
                )
            await uow.commit()

    async def _route(self, scope: Scope, client_id: str, ref: str, operations) -> dict:
        async with self._foundation.uows() as uow:
            row = (
                await uow.execute(
                    select(partner_manager_routes).where(
                        partner_manager_routes.c.partner_client_id == client_id,
                        partner_manager_routes.c.external_management_ref == ref,
                        partner_manager_routes.c.manager_account_id == scope.manager_account_id,
                        partner_manager_routes.c.status.in_(("pending_confirmation", "active")),
                    ),
                )
            ).mappings().first()
        if row is not None:
            return {"id": row["id"], "revision": row["revision"], "status": row["status"]}
        try:
            route = await self._foundation.route_grants.create_pending(
                scope, client_id, ref, operations, scope.manager_account_id,
            )
        except (PermissionError, ValueError) as exc:
            raise OnboardingError(409, "ROUTE_REFUSED", str(exc)) from exc
        return {"id": route.route_id, "revision": route.revision, "status": getattr(route.status, "value", route.status)}

    async def _route_settings(self, route, scope, client_id, agent_id, integration_id, route_decl, tools) -> None:
        now = _now()
        values = {
            "tenant_id": scope.tenant_id,
            "partner_client_id": client_id,
            "manager_account_id": scope.manager_account_id,
            "leader_agent_id": agent_id,
            "integration_id": integration_id,
            "config": route_decl.get("config") or {},
            "tools": tools,
            "updated_at": now,
        }
        async with self._foundation.uows() as uow:
            exists = (
                await uow.execute(select(routes.c.route_id).where(routes.c.route_id == route["id"]))
            ).first()
            if exists is None:
                await uow.execute(insert(routes).values(route_id=route["id"], created_at=now, **values))
            else:
                await uow.execute(update(routes).where(routes.c.route_id == route["id"]).values(**values))
            await uow.commit()


__all__ = ["OnboardingError", "OnboardingRequest", "PartnerOnboarding", "leader_prompt"]
