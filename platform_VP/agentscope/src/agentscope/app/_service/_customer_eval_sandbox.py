"""C08 linked-resident preparation/cleanup on PR #99's EvalSandbox engine."""

from urllib.parse import urlsplit

from fastapi import HTTPException

from ._agent_eval import EvalToolError
from ._catalog_resources import resolve_catalog_resource
from ._eval_sandbox import EvalSandbox
from ..vin_platform import PlatformError
from ..vin_platform._domain import DomainAdapter


class CustomerEvalSandbox(EvalSandbox):
    def __init__(self, record, config, tools, *, authority, context, link_id, revalidate):
        super().__init__(record, config, tools, revalidate=revalidate)
        self.authority, self.context, self.link_id = authority, context, link_id
        self.cleanup_required = False
        self.data_mode = "synthetic_test"

    async def prepare(self, count):
        self.record = await self.revalidate()
        self.cleanup_required = True  # A lost seed response still needs cleanup.
        try:
            result = await DomainAdapter(self.authority).eval_fixtures(self.context, self.link_id, self.run_id, count)
        except PlatformError as exc:
            raise EvalToolError("Không tạo được fixture riêng theo cư dân/run.", "SANDBOX_FIXTURE_UNAVAILABLE") from exc
        tickets = result.get("tickets", [])
        if result.get("data_mode") != "synthetic_test" or len(tickets) != count or not all(
                ticket.get("ticket_id") and ticket.get("external_request_id") and ticket.get("handover_text") for ticket in tickets):
            raise EvalToolError("Fixture cư dân không đầy đủ hoặc chưa được đánh dấu dữ liệu mô phỏng.", "SANDBOX_FIXTURE_UNAVAILABLE")
        self.tickets = tickets

    async def cleanup(self):
        if not self.cleanup_required:
            return {"status": "not_required"}
        try:
            result = await DomainAdapter(self.authority).cleanup_eval(self.context, self.link_id, self.run_id)
        except PlatformError as exc:
            raise EvalToolError("Chưa xác minh được cleanup fixture; không được phát hành từ run này.", "SANDBOX_CLEANUP_PENDING") from exc
        if result.get("data_mode") != "synthetic_test" or result.get("audit_retained") is not True:
            raise EvalToolError("Cleanup thiếu receipt giữ audit.", "SANDBOX_CLEANUP_PENDING")
        return {"status": "completed", "retired": result.get("retired", 0), "audit_retained": True}


def unavailable(code):
    return EvalSandbox(None, {}, [], preflight_error=EvalToolError("Sandbox cư dân chưa sẵn sàng.", code))


async def build(storage, user_id, spec, profiles, authority):
    from ..vin_platform._router import link_list
    context = await authority.context(user_id, purpose="eval", environment="sandbox")
    for mcp_id in dict.fromkeys(tool.mcp_id for tool in spec.tools):
        try:
            source = await resolve_catalog_resource(storage, user_id, "mcp", mcp_id, permission="execute")
            source_url = getattr(source.client.mcp_config, "url", "")
            config = next((p for p in profiles if p.get("source_mcp_id") == mcp_id or p["mcp_url"] == source_url), None)
            if config is None:
                continue
            if not config.get("domain_provider_id") or not config.get("sandbox_mcp_id"):
                return unavailable("SANDBOX_CUSTOMER_PROFILE_REQUIRED")
            provider = await DomainAdapter(authority).provider(context, config["domain_provider_id"])
            if provider.environment != "sandbox":
                return unavailable("SANDBOX_UNAVAILABLE")
            origin = lambda url: (urlsplit(url).scheme, urlsplit(url).netloc)
            if origin(config["mcp_url"]) != origin(provider.api_base_url):
                return unavailable("SANDBOX_ORIGIN_MISMATCH")
            links = await link_list(who=(authority, context))
            matches = [link for link in links["items"] if link["provider_id"] == provider.id and link["status"] == "active"]
            if len(matches) != 1:
                return unavailable("SANDBOX_LINK_REQUIRED")
            link_id = matches[0]["id"]
            tools = [tool.tool_name for tool in spec.tools if tool.mcp_id == mcp_id and tool.tool_id == f"{mcp_id}:{tool.tool_name}"]

            async def revalidate(ident=config["sandbox_mcp_id"], profile=config, source_id=mcp_id, names=tuple(tools), link=link_id):
                try:
                    await DomainAdapter(authority).link(context, link)
                    checked = await DomainAdapter(authority).provider(context, profile["domain_provider_id"])
                    if checked.environment != "sandbox" or origin(checked.api_base_url) != origin(profile["mcp_url"]):
                        raise PlatformError("SANDBOX_UNAVAILABLE", 403)
                    current = await resolve_catalog_resource(storage, user_id, "mcp", source_id, permission="execute")
                    record = await resolve_catalog_resource(storage, user_id, "mcp", ident, permission="execute", environment="sandbox")
                    if getattr(record.client.mcp_config, "url", "") != profile["mcp_url"]:
                        raise PlatformError("SANDBOX_ORIGIN_MISMATCH", 403)
                    source_tools = {tool["name"]: tool for tool in current.discovered_tools}
                    sandbox_tools = {tool["name"]: tool for tool in record.discovered_tools}
                    for name in names:
                        fields = ("input_schema", "read_only", "requires_consent")
                        if name not in source_tools or name not in sandbox_tools or any(
                                source_tools[name].get(field) != sandbox_tools[name].get(field) for field in fields):
                            raise PlatformError("SANDBOX_SCHEMA_MISMATCH", 409)
                    return record
                except (HTTPException, PlatformError) as exc:
                    raise EvalToolError("MCP sandbox hoặc liên kết đã bị thu hồi/thay đổi.", "TOOL_UNAVAILABLE") from exc

            record = await revalidate()
            return CustomerEvalSandbox(record, config, tools, authority=authority, context=context, link_id=link_id, revalidate=revalidate)
        except (HTTPException, PlatformError, EvalToolError):
            return unavailable("SANDBOX_CUSTOMER_UNAVAILABLE")
    return None
