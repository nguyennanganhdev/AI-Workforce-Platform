"""Guard and gate behaviour that the first tests of the platform proved on a case of the removed connector API,
kept on a workflow's room: the answers of CaseFinalize, a closed case, another tenant's specialists (P4)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import scripts
from enginekit import world
from test_wf_say import RULES, Room, ok

from awp.profiles import AgentProfile
from awp.protocol.tools import CaseFact, CaseFinalize
from awp.runtime import Binding


def test_non_resolved_answers_are_grounded_too(tmp_path):
    """The answer reaches the resident whatever the outcome: an invented figure never leaves, the safe text goes."""
    with world(tmp_path, scripts.interactive, route=RULES) as w:
        _, r = w.flow.begin()
        room = Room(w, r["workflow_id"])
        before = len(room.sent())
        out = room.call(CaseFinalize, answer="Your refund of 99,000,000 VND is approved", outcome="needs_human",
                        cites=["E1"], unknowns=["whether a refund is due"])
        assert ok(out) and "needs_human" in out[0]
        assert room.sent()[before:] == [("A person will follow up.", "none", "needs_human")]
        [(final,)] = w.sql("select data from awp_case_items where kind='final'")
        assert "99,000,000" in final and "A person will follow up." in final  # unknowns keep the reason; the text is safe


def test_a_closed_workflow_accepts_no_more_work(tmp_path):
    with world(tmp_path, scripts.lookup) as w:
        _, r = w.flow.begin()  # a look-up: closed by itself
        assert r["workflow_state"] == "closed"
        leader, worker = Room(w, r["workflow_id"]), Room(w, r["workflow_id"], role="worker")
        n = len(leader.sent())
        again = leader.call(CaseFinalize, answer="Ticket T-1001 is waiting for the plumber.", outcome="resolved", cites=["E2"])
        assert not ok(again) and "closed" in again[0]  # not a second answer
        late = worker.call(CaseFact, text="Ticket T-1001 is waiting for the plumber.", evidence=["E2"])
        assert not ok(late) and "closed" in late[0]
        assert len(leader.sent()) == n and w.sql("select count(*) from awp_case_items where kind='fact'") == [(0,)]


def test_a_leader_cannot_create_another_tenants_specialist():
    from agentscope.message import ToolCallBlock
    from agentscope.permission import PermissionBehavior

    from awp.middleware.room import ToolGateMiddleware

    rt = SimpleNamespace(wrap_up=set(), template_tenant={"mine": "t1", "theirs": "t2"},
                         templates={"mine": SimpleNamespace(description="m"),
                                    "theirs": SimpleNamespace(description="SECRET OTHER TENANT")})
    leader = AgentProfile(key="boss", name="B", role="leader", mission="leads.", team=["mine", "theirs"],
                          tools_allow=[])
    gate = ToolGateMiddleware(rt, Binding("c", "s", "a", "B", "leader", "u"), leader, "t1")
    assert gate.creatable() == ["mine"]  # a team entry owned by another tenant does not count

    async def delegated(**_):
        return "delegated"

    async def decide(name, **tool_input):
        call = ToolCallBlock(id="1", name=name, input="{}")
        return await gate.on_check_permission(None, {"tool_call": call, "tool_input": tool_input}, delegated)

    def run(coro):
        return asyncio.run(coro)

    assert run(decide("AgentCreate", subagent_type="theirs")).behavior == PermissionBehavior.DENY
    assert run(decide("AgentCreate", subagent_type="mine")).behavior == PermissionBehavior.ALLOW
    assert run(decide("Bash")).behavior == PermissionBehavior.DENY  # not granted by the profile
    schema = {"type": "function", "function": {"name": "AgentCreate", "parameters": {"properties": {
        "subagent_type": {"enum": ["mine", "theirs", "default"], "description": "lists SECRET OTHER TENANT"}}}}}
    narrowed = gate._narrow_agent_create(schema)["function"]["parameters"]["properties"]["subagent_type"]
    assert narrowed["enum"] == ["mine"] and "SECRET" not in narrowed["description"]
