"""Test fixtures of the engine tests: two read-only look-up tools and three demo profiles (a leader and two specialists)."""
from __future__ import annotations

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk
from pydantic import Field

from awp.profiles import AgentProfile


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


def demo_profiles() -> list[AgentProfile]:
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
