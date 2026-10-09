"""A tiny domain pack for tests: two read-only tools and three profiles."""
from __future__ import annotations

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk
from pydantic import Field

from awp.guard import Rules
from awp.intake.models import CaseResult
from awp.profiles import AgentProfile
from awp.requests import RequestKind


class _TicketP(ParamsBase):
    ticket_id: str = Field(description="Ticket id")


class _PriceP(ParamsBase):
    item: str = Field(description="Item to price")


class _ReadOnly(ToolBase):
    is_read_only = True
    is_concurrency_safe = True

    async def check_permissions(self, *a, **k):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="test")


class LookupTicket(_ReadOnly):
    name = "lookup_ticket"
    description = "Look up a ticket by id."
    input_schema = _TicketP.model_json_schema()

    async def call(self, ticket_id: str):
        text = {"T-1001": "T-1001: leaking pipe, status waiting for plumber"}.get(ticket_id, "NOT FOUND")
        return ToolChunk(content=[TextBlock(text=text)], state=ToolResultState.SUCCESS)


class PriceList(_ReadOnly):
    name = "price_list"
    description = "Price of a repair item."
    input_schema = _PriceP.model_json_schema()

    async def call(self, item: str):
        return ToolChunk(content=[TextBlock(text="pipe repair: 1500000 VND")], state=ToolResultState.SUCCESS)


class DemoPack:
    domain = "test"
    default_leader = "supervisor"

    def __init__(self) -> None:
        self.results: list[tuple[dict, CaseResult]] = []
        self.requests: list[dict] = []

    def profiles(self):
        return [
            AgentProfile(key="supervisor", name="case-leader", role="leader",
                         mission="the leader of a repair case.", team=["tech", "fin"],
                         model_tier="strong", instructions="Answer in English."),
            AgentProfile(key="tech", name="Technician", mission="a technician who checks tickets.",
                         handles=["tickets"], refuses=["prices"], tools_allow=["lookup_ticket"],
                         model_tier="cheap", invite_description="Checks ticket status."),
            AgentProfile(key="fin", name="Finance", mission="a cost estimator.",
                         handles=["prices"], tools_allow=["price_list"], model_tier="cheap",
                         invite_description="Finds repair costs."),
        ]

    def rules(self):
        return Rules(safe_reply="A person will follow up.")

    def tools(self, rt, binding):
        return [LookupTicket(), PriceList()]

    def request_kinds(self):
        obj = {"type": "object"}
        return [
            RequestKind(key="work_request", description="Ask field staff to do the work and report costs.",
                        fields={**obj, "properties": {"unit": {"type": "string"}, "issue": {"type": "string"}},
                                "required": ["unit", "issue"]},
                        reply={**obj, "required": ["cost_items"], "properties": {"cost_items": {
                            "type": "array", "minItems": 1, "items": {
                                **obj, "required": ["label", "amount"],
                                "properties": {"label": {"type": "string"}, "amount": {"type": "number"}}}}}}),
            RequestKind(key="cost_confirmation", description="Ask the requester to confirm the cost.",
                        fields={**obj, "properties": {"total": {"type": "string"}, "items": {"type": "array"}},
                                "required": ["total"]},
                        reply={**obj, "required": ["confirmed"], "properties": {"confirmed": {"type": "boolean"}}}),
            RequestKind(key="progress_update", description="Tell the requester how far things are.",
                        fields={**obj, "properties": {"status": {"type": "string"}}, "required": ["status"]}),
        ]

    async def deliver_request(self, case, request):
        self.requests.append(request)

    async def deliver_result(self, case, result):
        self.results.append((case, result))

    async def start(self, rt, intake, tenant):
        pass

    async def stop(self):
        pass


import contextlib

from fastapi.testclient import TestClient

from awp.app import build_app
from awp.config import ServiceKey, Settings
from awp.providers import ModelCatalog, ModelSpec

from fake_llm import CALLS, FakeServer, MODE

SVC = {"Authorization": "Bearer svc-key"}
ADM = {"Authorization": "Bearer adm-key"}


@contextlib.contextmanager
def make_stack(tmp_path, judge=None, **settings_over):
    """A running platform on a scripted model: (client, pack, rt)."""
    MODE["leader"] = "normal"
    MODE["scenario"] = "default"
    with FakeServer() as fake:
        settings = Settings(
            db_url=f"sqlite+aiosqlite:///{(tmp_path / 'awp.db').as_posix()}",
            agentscope_db_url=f"sqlite+aiosqlite:///{(tmp_path / 'as.db').as_posix()}",
            workspace_dir=str(tmp_path / "ws"),
            service_keys={"svc-key": ServiceKey("t1", "test")},
            admin_keys={"adm-key": "t1"}, **settings_over)
        catalog = ModelCatalog([
            ModelSpec(id="strong", provider="openai_compatible", model="fake-strong", tier="strong",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=2.0, price_out=8.0),
            ModelSpec(id="cheap", provider="openai_compatible", model="fake-cheap", tier="cheap",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=0.5, price_out=2.0),
        ], env={"FAKE_KEY": "x"})
        pack = DemoPack()
        app = build_app(settings, packs=[pack], catalog=catalog, judge=judge)
        with TestClient(app) as client:
            yield client, pack, app.state.awp.rt
    CALLS.clear()
    MODE["leader"] = "normal"
    MODE["scenario"] = "default"
