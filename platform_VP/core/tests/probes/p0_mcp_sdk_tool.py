"""PartnerTool: one partner-MCP tool as an AgentScope ToolBase, plus a test pack/stack that runs it
inside a real agent run on a scripted model (extra_agent_tools -> tool_factory -> pack.tools).
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
from typing import Any, Callable

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ToolBase, ToolChunk
from fastapi.testclient import TestClient

from awp.app import build_app
from awp.config import ServiceKey, Settings
from awp.guard import Rules
from awp.profiles import AgentProfile
from awp.providers import ModelCatalog, ModelSpec

from p0_mcp_sdk_client import FAILED, OK, PENDING, UNKNOWN, PartnerMCP, PartnerResult, ToolSpec
from p0_mcp_sdk_llm import CALLS, MODE, FakeServer

SVC = {"Authorization": "Bearer svc-key"}
ADM = {"Authorization": "Bearer adm-key"}


def client_reference(tool: str, args: dict) -> str:
    """Deterministic idempotency key: the same call (tool + visible args) always gets the same reference.
    In the real platform it is derived from (workflow, tool, args_hash, tool_call_id)."""
    digest = hashlib.sha256(json.dumps([tool, args], sort_keys=True).encode()).hexdigest()[:12]
    return f"wf-{digest}"


def render(res: PartnerResult) -> str:
    """The words the agent sees. They never claim more than was verified."""
    if res.outcome == OK:
        return res.text
    if res.outcome == PENDING:
        return (f"PENDING: the partner accepted the request but has not finished it. "
                f"Reference: {res.external_job_id or 'none given'}. You will be told when it changes. "
                f"Say only that it is pending; do not say it is done. Partner said: {res.text}")
    if res.outcome == FAILED:
        return f"FAILED: {res.text}"
    return ("UNKNOWN: the request may or may not have been carried out. Do not retry and do not tell the "
            f"resident it was done or that it failed. ({res.text})")


class PartnerTool(ToolBase):
    """Built from a ToolSpec out of the cached list, so constructing it never touches the network."""

    is_concurrency_safe = False     # same as AgentScope's own MCPTool: calls run one after another

    def __init__(self, client: PartnerMCP, spec: ToolSpec, *, prefix: str = "partner_",
                 inject: dict[str, Callable[[str, dict], Any]] | None = None, allow_actions: bool = False,
                 tracking: str = "poll", timeout: float | None = None,
                 on_result: Callable[["PartnerTool", dict, PartnerResult], Any] | None = None) -> None:
        super().__init__()
        self.client, self.spec = client, spec
        self.name = f"{prefix}{spec.name}"
        self.description = spec.description or spec.name
        self.is_read_only = spec.read_only          # only the partner's own readOnlyHint=true counts
        self.kind = "lookup" if spec.read_only else "action"
        self.inject = inject or {}
        schema = copy.deepcopy(spec.input_schema)
        for key in self.inject:                      # the model never sees or fills the injected parameters
            (schema.get("properties") or {}).pop(key, None)
            schema["required"] = [r for r in schema.get("required", []) if r != key]
        self.input_schema = schema
        self.allow_actions, self.tracking, self.timeout, self.on_result = allow_actions, tracking, timeout, on_result

    async def check_permissions(self, tool_input, context):
        if self.is_read_only or self.allow_actions:
            return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="partner tool allowed")
        return PermissionDecision(behavior=PermissionBehavior.ASK, message=f"{self.name} changes things at the partner")

    async def call(self, **kwargs: Any) -> ToolChunk:
        args = {**kwargs, **{k: fn(self.spec.name, kwargs) for k, fn in self.inject.items()}}
        res = await self.client.call(self.spec.name, args, kind=self.kind, timeout=self.timeout,
                                     tracking=self.tracking)
        if self.on_result is not None:
            r = self.on_result(self, args, res)
            if hasattr(r, "__await__"):
                await r
        state = ToolResultState.SUCCESS if res.outcome in (OK, PENDING) else ToolResultState.ERROR
        return ToolChunk(content=[TextBlock(text=render(res))], state=state,
                         metadata={"partner_outcome": res.outcome, "external_job_id": res.external_job_id,
                                   "error": res.error})


class McpPack:
    """Test domain pack whose tools come from a PartnerMCP (cached list)."""
    domain = "p0mcp"
    default_leader = "supervisor"

    def __init__(self, partner: PartnerMCP, **tool_kw: Any) -> None:
        self.partner, self.tool_kw = partner, tool_kw
        self.built: list[list[str]] = []     # tool names handed to each agent build
        self.results: list[tuple[dict, Any]] = []

    def profiles(self):
        return [
            AgentProfile(key="supervisor", name="case-leader", role="leader", mission="the leader of a repair case.",
                         team=["tech"], model_tier="strong", instructions="Answer in English."),
            AgentProfile(key="tech", name="Technician", mission="a technician who works with the partner's system.",
                         handles=["tickets", "bookings"], tools_allow=["partner_*"], model_tier="cheap",
                         invite_description="Looks up tickets and books plumbers at the partner."),
        ]

    def rules(self):
        return Rules(safe_reply="A person will follow up.")

    async def tools(self, rt, binding):
        specs = await self.partner.list_tools()          # cached after the first agent build
        tools = [PartnerTool(self.partner, s, **self.tool_kw) for s in specs]
        self.built.append([t.name for t in tools])
        return tools

    def request_kinds(self):
        return []

    async def deliver_request(self, case, request):
        pass

    async def deliver_result(self, case, result):
        self.results.append((case, result))

    async def start(self, rt, intake, tenant):
        pass

    async def stop(self):
        pass


@contextlib.contextmanager
def make_mcp_stack(tmp_path, partner: PartnerMCP, **tool_kw):
    """A running platform on the scripted model whose agents get PartnerTools: (client, pack, rt)."""
    with FakeServer() as fake:
        settings = Settings(
            db_url=f"sqlite+aiosqlite:///{(tmp_path / 'awp.db').as_posix()}",
            agentscope_db_url=f"sqlite+aiosqlite:///{(tmp_path / 'as.db').as_posix()}",
            workspace_dir=str(tmp_path / "ws"),
            service_keys={"svc-key": ServiceKey("t1", "p0mcp")}, admin_keys={"adm-key": "t1"})
        catalog = ModelCatalog([
            ModelSpec(id="strong", provider="openai_compatible", model="fake-strong", tier="strong",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=2.0, price_out=8.0),
            ModelSpec(id="cheap", provider="openai_compatible", model="fake-cheap", tier="cheap",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=0.5, price_out=2.0),
        ], env={"FAKE_KEY": "x"})
        pack = McpPack(partner, **tool_kw)
        app = build_app(settings, packs=[pack], catalog=catalog)
        with TestClient(app) as client:
            yield client, pack, app.state.awp.rt
    CALLS.clear()
    MODE.update({"worker_calls": [], "answer": "", "fact_texts": []})
