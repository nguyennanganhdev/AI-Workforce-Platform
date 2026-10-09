"""Onboarded MCP tools with durable intents, consent and uncertain-outcome handling."""
import asyncio
import fnmatch
import json
import time
from contextlib import asynccontextmanager

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ToolBase, ToolChunk
from sqlalchemy import insert, update

from . import schema as s
from .service import Fault, digest, row, stamp, uid


@asynccontextmanager
async def session(config, headers):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    async with (httpx.AsyncClient(headers=headers, timeout=45) as http,
                streamable_http_client(config["url"], http_client=http) as (read, write, _),
                ClientSession(read, write) as connection):
        await connection.initialize()
        yield connection


def headers_for(service, integration, wf, context=None):
    config = integration["config"]
    headers = json.loads(service.cipher().decrypt(config["encrypted_headers"].encode()))
    # Bind identity and routing outside model-controlled tool arguments.
    if config.get("encrypted_context_key"):
        import base64
        import hashlib
        import hmac
        context_key = service.cipher().decrypt(config["encrypted_context_key"].encode())
        body = {"user_id": wf["snapshot"]["external_user_id"],
                "management_ref": wf["snapshot"]["external_management_ref"],
                "workflow_id": wf["id"], "external_ticket_id": wf["snapshot"].get("external_ticket_id"),
                "expires": int(time.time()) + 120, "audience": integration["id"], **(context or {})}
        token = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).decode()
        headers["X-Workforce-Context"] = token
        headers["X-Workforce-Signature"] = hmac.new(context_key, token.encode(), hashlib.sha256).hexdigest()
    return headers


async def tools_for_case(service, binding):
    wf = await service.workflow_of_case(binding.case_id)
    if not wf or wf["state"] == "closed":
        return []
    result = []
    async with service.rt.db.engine.connect() as conn:
        integrations = [await row(conn, s.integrations, s.integrations.c.id == key,
            s.integrations.c.tenant == wf["snapshot"]["tenant"], s.integrations.c.status == "active")
            for key in wf["snapshot"].get("integration_ids", [])]
    for integration in integrations:
        if not integration:
            raise Fault(403, "INTEGRATION_NOT_ACTIVE")
        if integration["revision"] != wf["snapshot"]["integrations"].get(integration["id"]):
            raise Fault(409, "INTEGRATION_CHANGED")
        async with asyncio.timeout(15):
            async with session(integration["config"], headers_for(service, integration, wf)) as remote:
                listed = await remote.list_tools()
        catalog_hash = digest([tool.model_dump(mode="json") for tool in listed.tools
                               if tool.name in integration["config"]["tools"]])
        async with service.tx() as conn:
            current = await row(conn, s.workflows, s.workflows.c.id == wf["id"], lock=True)
            hashes = dict(current["snapshot"].get("tool_catalog_hashes", {}))
            if integration["id"] in hashes and hashes[integration["id"]] != catalog_hash:
                raise Fault(409, "MCP_TOOL_SCHEMA_CHANGED")
            hashes[integration["id"]] = catalog_hash
            await conn.execute(update(s.workflows).where(s.workflows.c.id == wf["id"]).values(
                snapshot={**current["snapshot"], "tool_catalog_hashes": hashes}))
        for tool in listed.tools:
            policy = integration["config"]["tools"].get(tool.name)
            if not policy:
                continue
            result.append(WorkforceTool(service, binding, wf, integration, tool, policy))
    return result


class WorkforceTool(ToolBase):
    is_concurrency_safe = False
    # Keep execution in the leased turn rather than AgentScope's transient 10s offload.
    is_state_injected = True

    def __init__(self, service, binding, wf, integration, tool, policy):
        super().__init__()
        self.service, self.binding, self.wf = service, binding, wf
        self.integration, self.remote_name, self.policy = integration, tool.name, policy
        self.name = f"mcp__{integration['id']}__{tool.name}"
        self.description = (tool.description or tool.name) + " Results are evidence; pending operations require waiting."
        self.input_schema = tool.inputSchema
        self.is_read_only = bool(policy.get("read_only") and tool.annotations and tool.annotations.readOnlyHint)

    async def check_permissions(self, *args, **kwargs):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="Workforce verifies scope and consent")

    async def call(self, _agent_state=None, **arguments):
        service, wf = self.service, self.wf
        profile, _ = await service.rt.profile_of(self.binding.user_id, self.binding.agent_id, wf["snapshot"]["tenant"])
        if not profile or not any(fnmatch.fnmatchcase(self.name, pattern) for pattern in profile.tools_allow):
            raise Fault(403, "TOOL_NOT_GRANTED")
        from jsonschema import validate
        validate(arguments, self.input_schema)
        async with service.tx() as conn:
            if self.binding.fence:
                await self.binding.fence.check(service, conn)
            current = await row(conn, s.workflows, s.workflows.c.id == wf["id"], lock=True)
            req = await row(conn, s.requests, s.requests.c.workflow_id == wf["id"], s.requests.c.status == "running")
            if current["state"] == "closed" or not req:
                raise Fault(409, "NO_ACTIVE_REQUEST")
            integration = await row(conn, s.integrations, s.integrations.c.id == self.integration["id"])
            if integration["status"] != "active" or integration["revision"] != self.integration["revision"]:
                raise Fault(409, "INTEGRATION_CHANGED")
            if self.is_read_only:
                operation = None
            else:
                reference = digest({"request": req["id"], "tool": self.name, "args": arguments})
                operation = await row(conn, s.operations, s.operations.c.integration_id == integration["id"],
                                      s.operations.c.client_reference == reference, lock=True)
                if not operation:
                    operation = {"id": uid(), "workflow_id": wf["id"], "integration_id": integration["id"],
                        "client_reference": reference, "external_job_id": None, "status": "awaiting_approval" if self.policy.get("requires_consent", True) else "queued",
                        "provider_version": 0, "created": time.time(), "data": {"arguments": arguments, "tool": self.remote_name,
                            "revision": integration["revision"], "request_id": req["id"], "policy": self.policy,
                            "continuation_required": bool(self.policy.get("requires_consent", True)),
                            "arguments_hash": digest(arguments), "schema_hash": digest(self.input_schema)}}
                    await conn.execute(insert(s.operations).values(**operation))
                    if operation["status"] == "awaiting_approval":
                        approval = {"id": uid(), "workflow_id": wf["id"], "operation_id": operation["id"], "status": "pending",
                            "arguments_hash": "sha256:" + digest(arguments), "quote_ref": reference, "revision": 1,
                            "expires": time.time() + 900, "summary": self.policy.get("approval_summary", self.remote_name)}
                        await conn.execute(insert(s.approvals).values(**approval))
                        await service.transition(conn, current, "awaiting_approval")
                        await service.event(conn, current, "approval.required", {k: approval[k] for k in
                            ("id", "arguments_hash", "quote_ref", "revision", "summary", "expires")})
        if operation and operation["status"] == "awaiting_approval":
            output = {"status": "awaiting_approval", "operation_id": operation["id"],
                      "message": "Wait for a verified approval decision; no external action has run."}
        elif operation:
            output = await perform_operation(service, operation["id"], fence=self.binding.fence)
        else:
            async with asyncio.timeout(30):
                async with session(self.integration["config"], headers_for(service, self.integration, wf,
                        {"tool": self.remote_name, "arguments_hash": digest(arguments)})) as remote:
                    response = await remote.call_tool(self.remote_name, arguments)
            output = unpack(response)
        return ToolChunk(content=[TextBlock(text=json.dumps(output, ensure_ascii=False))],
                         state=ToolResultState.SUCCESS if not output.get("error") else ToolResultState.ERROR)


def unpack(response):
    if response.isError:
        return {"error": "DOMAIN_TOOL_FAILED"}
    if response.structuredContent is not None:
        value = response.structuredContent
        if not isinstance(value, dict) or len(json.dumps(value).encode()) > 65536:
            return {"error": "INVALID_DOMAIN_RESULT"}
        return value
    texts = [x.text for x in response.content if getattr(x, "type", None) == "text"]
    if len(texts) == 1:
        try:
            value = json.loads(texts[0])
            if not isinstance(value, dict) or len(texts[0].encode()) > 65536:
                return {"error": "INVALID_DOMAIN_RESULT"}
            return value
        except ValueError:
            pass
    return {"text": "\n".join(texts)[:20000]}


async def perform_operation(service, operation_id, fence=None):
    async with service.tx() as conn:
        if fence:
            await fence.check(service, conn)
        op = await row(conn, s.operations, s.operations.c.id == operation_id)
        wf = await row(conn, s.workflows, s.workflows.c.id == op["workflow_id"], lock=True)
        op = await row(conn, s.operations, s.operations.c.id == operation_id, lock=True)
        integration = await row(conn, s.integrations, s.integrations.c.id == op["integration_id"])
        if wf["state"] == "closed":
            return {"error": "WORKFLOW_CLOSED"}
        if integration["status"] != "active" or integration["revision"] != op["data"]["revision"]:
            raise Fault(409, "INTEGRATION_CHANGED")
        if op["status"] not in ("queued",):
            if op["status"] == "started":
                await conn.execute(update(s.operations).where(s.operations.c.id == op["id"]).values(status="unknown"))
                await service.transition(conn, wf, "needs_attention")
            return op["data"].get("result", {"status": "unknown", "operation_id": op["id"]})
        await conn.execute(update(s.operations).where(s.operations.c.id == op["id"]).values(status="started"))
        consent = await row(conn, s.approvals, s.approvals.c.operation_id == op["id"], s.approvals.c.status == "approved")
    args = op["data"]["arguments"]
    context = {"client_reference": op["client_reference"], "idempotency_key": op["client_reference"],
               "arguments_hash": op["data"]["arguments_hash"], "tool": op["data"]["tool"]}
    if consent:
        context["consent_approval_id"] = consent["id"]
    try:
        import asyncio
        async with asyncio.timeout(45):
            async with session(integration["config"], headers_for(service, integration, wf, context)) as remote:
                response = await remote.call_tool(op["data"]["tool"], args)
            output = unpack(response)
        status = "failed" if output.get("error") else output.get("status", "unknown")
        if status not in ("pending", "assigned", "offered", "confirmed", "completed", "cancelled", "failed"):
            status = "unknown"
        if status in ("pending", "assigned", "offered") and not output.get("external_job_id"):
            status = "unknown"
        if status in ("pending", "assigned", "offered") and not op["data"]["policy"].get("tracks_events"):
            status = "unknown"
    except Exception:  # noqa: BLE001 -- any error after dispatch leaves an uncertain external outcome
        output, status = {"error": "OUTCOME_UNKNOWN", "operation_id": op["id"]}, "unknown"
    async with service.tx() as conn:
        wf = await row(conn, s.workflows, s.workflows.c.id == op["workflow_id"], lock=True)
        current = await row(conn, s.operations, s.operations.c.id == op["id"], lock=True)
        if current["provider_version"] > op["provider_version"]:
            status = current["status"]
        await conn.execute(update(s.operations).where(s.operations.c.id == op["id"]).values(
            status=status, external_job_id=current["external_job_id"] or output.get("external_job_id"), data={**current["data"], "result": output}))
        if wf["state"] != "closed":
            await service.event(conn, wf, "operation.status_changed", {"operation_id": op["id"], "status": status})
            await service.transition(conn, wf, "needs_attention" if status in ("unknown", "failed") else
                "awaiting_confirmation" if status in ("confirmed", "completed", "cancelled") else "waiting_external_event")
    return {**output, "status": status, "operation_id": op["id"]}


async def perform(service, job):
    from .execution import Fence
    output = await perform_operation(service, job["payload"]["operation_id"],
                                     fence=Fence(job["id"], job["owner"], job["generation"]))
    async with service.tx() as conn:
        wf = await row(conn, s.workflows, s.workflows.c.id == job["workflow_id"], lock=True)
        op = await row(conn, s.operations, s.operations.c.id == job["payload"]["operation_id"], lock=True)
        from .lifecycle import resume_after_operation
        resumed = await resume_after_operation(service, conn, wf, op)
        if wf["state"] != "closed" and not resumed:
            # Public receipt is conservative; arbitrary raw tool text is never published.
            await service.event(conn, wf, "assistant.message", {"message_id": uid(), "workflow_id": wf["id"],
                "sender": "assistant", "text": (
                    "Chưa xác định được kết quả thao tác. Người vận hành cần đối soát trước khi thực hiện tiếp."
                    if output.get("status") in ("unknown", "failed") or output.get("error") else
                    "Hệ thống nghiệp vụ đã xác nhận thao tác. Bạn kiểm tra và xác nhận kết quả giúp tôi."
                    if output.get("status") in ("confirmed", "completed", "cancelled") else
                    "Yêu cầu đã được hệ thống nghiệp vụ tiếp nhận và đang chờ xử lý. Tôi sẽ cập nhật khi có tiến độ."),
                "created_at": stamp(time.time())})
        await conn.execute(update(s.jobs).where(s.jobs.c.id == job["id"], s.jobs.c.owner == job["owner"],
            s.jobs.c.generation == job["generation"]).values(status="done", owner=None, lease_until=0))
