"""Customer-selected Domain tools use short-lived, owner-bound ticket grants."""

from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException

from ...mcp import MCPClient
from ...message import TextBlock, ToolResultState
from ...tool import ToolBase, ToolChunk
from ..vin_platform._contracts import PlatformError
from ..vin_platform._domain import DomainAdapter
from ._catalog_resources import resolve_catalog_resource

DOMAIN_TAG = "vin-customer-domain:"
CUSTOMER_TOOLS = frozenset({"vh_ticket_get", "vh_knowledge_search", "vh_staff_available",
    "vh_work_order_dispatch", "vh_operation_get", "vh_ticket_add_note", "vh_service_context", "vh_amenity_availability"})


def domain_id(record):
    values = [tag.removeprefix(DOMAIN_TAG) for tag in record.tags if tag.startswith(DOMAIN_TAG)]
    return values[0] if len(values) == 1 else None


async def granted_client(storage, user_id, mcp_id, name, arguments):
    """Refresh catalog/link/ownership before every call; never use discovery auth."""
    authority = storage.vin_platform_service
    context = await authority.context(user_id)
    if context.role != "VIN_USER" or context.environment != "production":
        raise PlatformError("CUSTOMER_MCP_CONTEXT_REQUIRED", 403)
    record = await resolve_catalog_resource(storage, user_id, "mcp", mcp_id, permission="execute")
    provider_id = domain_id(record)
    if not provider_id or name not in CUSTOMER_TOOLS or name not in {t["name"] for t in record.discovered_tools}:
        raise PlatformError("CUSTOMER_TOOL_NOT_DELEGATED", 403)
    if (record.client.enable_tools is not None and name not in record.client.enable_tools) or name in (record.client.disable_tools or []):
        raise PlatformError("CUSTOMER_TOOL_NOT_DELEGATED", 403)
    try:
        ticket_id = str(UUID(str(arguments.get("ticket_id", ""))))
    except ValueError:
        raise PlatformError("CUSTOMER_TICKET_REQUIRED", 422) from None
    adapter = DomainAdapter(authority)
    provider = await adapter.provider(context, provider_id)
    target, source = urlsplit(record.client.mcp_config.url), urlsplit(provider.api_base_url)
    if (target.scheme, target.netloc) != (source.scheme, source.netloc) or target.path.rstrip("/") != "/mcp" or target.query or target.fragment:
        raise PlatformError("CUSTOMER_CONNECTOR_ORIGIN_MISMATCH", 409)
    # Only cases created/bound by this customer's Platform conversations.
    # Domain rechecks ticket->case->link/subject and active revision as well.
    for row in await authority.automation_list(context, "derived"):
        data = row["data"]
        if data.get("type") != "customer-case" or not data.get("case_id"):
            continue
        case = await adapter.get_case(context, data["case_id"])
        if any(str(item.get("id")) == ticket_id for item in case["data"].get("domain", {}).get("tickets", [])):
            grant = await adapter.ticket_grant(context, case["id"], ticket_id, [name])
            client = MCPClient.model_validate(record.client.model_dump(mode="json"))
            client.is_stateful = False
            client.enable_tools = [name]
            client.mcp_config.headers = {"Authorization": "Bearer " + grant["bearer_token"]}
            return client
    raise PlatformError("CUSTOMER_TICKET_NOT_FOUND", 404)


class CustomerMCPTool(ToolBase):
    is_concurrency_safe = False
    is_mcp = True

    def __init__(self, storage, user_id, record, descriptor):
        super().__init__()
        self.storage, self.user_id, self.mcp_id = storage, user_id, record.id
        self.name, self.description = descriptor["name"], descriptor.get("description", "")
        self.input_schema = descriptor.get("input_schema") or {}
        self.is_read_only = descriptor.get("read_only") is True
        self.mcp_name = record.name
        self.force_confirmation = self.name in (record.client.confirm_tools or []) or not self.is_read_only

    async def check_permissions(self, *_args, **_kwargs):
        from mcp.types import ToolAnnotations
        from ...permission._mcp import mcp_tool_permission
        return mcp_tool_permission(self.name, ToolAnnotations(readOnlyHint=self.is_read_only),
            self.input_schema, force_confirmation=self.force_confirmation)

    async def call(self, **arguments):
        try:
            client = await granted_client(self.storage, self.user_id, self.mcp_id, self.name, arguments)
            tool = await client.get_tool(self.name)
            return await tool(**arguments)
        except PlatformError as exc:
            return ToolChunk(content=[TextBlock(text=exc.code)], state=ToolResultState.ERROR)
        except HTTPException:
            return ToolChunk(content=[TextBlock(text="CUSTOMER_MCP_UNAVAILABLE")], state=ToolResultState.ERROR)
        except Exception:
            # Transport exceptions can contain request headers/grant material.
            return ToolChunk(content=[TextBlock(text="DOMAIN_TOOL_TEMPORARILY_UNAVAILABLE")], state=ToolResultState.ERROR)


async def customer_tools(storage, user_id, clients, records):
    """Replace selected Domain clients only; preserve unrelated connectors."""
    remaining, tools = [], []
    for client in clients:
        record = records.get(client.name)
        if record is None or domain_id(record) is None:
            remaining.append(client)
            continue
        for descriptor in record.discovered_tools:
            name = descriptor.get("name")
            if name in CUSTOMER_TOOLS and (client.enable_tools is None or name in client.enable_tools) and name not in (client.disable_tools or []):
                tools.append(CustomerMCPTool(storage, user_id, record, descriptor))
    return remaining, tools
