"""The team room inside a workflow: what the old end-to-end tests proved about the case file, the peer debate, the
guard, the tool filter and the cost ledger, now through the partner API on the real engine (P4).

The model is a script (tests/fake_llm.py `policy`, no workflow script): the leader brings in two specialists,
who look things up, record facts, ask each other a question and report. It proves the plumbing, not a real model.
"""
from __future__ import annotations

import threading

import pytest
from conftest import ADM, publish
from enginekit import profiles, world
from fake_llm import CALLS, MODE

from awp.profiles import MemoryConfig

TEAM = {"wf_wait_seconds": 60.0}


def admin_get(w, path: str):
    r = w.env.http.get(f"/platform/v1{path}", headers=ADM)
    assert r.status_code == 200, r.text
    return r.json()


def case_items(w, wid: str) -> list[dict]:
    case_id = w.sql("select case_id from wf_workflows where id=?", (wid,))[0][0]
    return admin_get(w, f"/cases/{case_id}/items")["items"]


@pytest.fixture(scope="module")
def team(tmp_path_factory):
    """One run of the whole team, read once: the answer, the case file, the cost and what the model was offered."""
    with world(tmp_path_factory.mktemp("team"), None, **TEAM) as w:
        _, r = w.flow.begin()
        wid = r["workflow_id"]
        case_id = w.sql("select case_id from wf_workflows where id=?", (wid,))[0][0]
        yield {"response": r, "items": case_items(w, wid), "messages": w.messages(wid),
               "cost": admin_get(w, f"/cases/{case_id}/cost"), "metrics": admin_get(w, "/metrics"),
               "calls": list(CALLS)}


def test_the_team_debate_ends_in_a_grounded_answer_to_the_resident(team):
    r, items = team["response"], team["items"]
    assert r["request_status"] == "completed" and r["workflow_state"] == "closed"  # a look-up closes itself
    said = " ".join(m[1] for m in team["messages"] if m[0] == "assistant")
    assert "1500000" in said and "2000000" not in said  # the figure the specialists found, not the invented one
    facts = {i["author"]: i for i in items if i["kind"] == "fact"}
    assert set(facts) == {"tech", "fin"}
    assert all(f["data"]["evidence"] for f in facts.values())  # tool output became the evidence the facts cite
    # the peer question and its answer are in the case file, between the two members
    q = [i for i in items if i["kind"] == "question"]
    a = [i for i in items if i["kind"] == "answer"]
    assert len(q) == 1 and q[0]["author"] == "fin" and q[0]["addressee"] == "tech"
    assert len(a) == 1 and a[0]["author"] == "tech" and a[0]["data"]["to_ref"] == q[0]["ref"]
    # the first final answer invented a figure and was refused before the accepted one
    notes = [i for i in items if i["kind"] == "note" and i["data"].get("type") == "final_attempt"]
    assert len(notes) == 1 and "2000000" in str(notes[0]["data"]["problems"])
    # a broadcast report by a specialist was turned into a report to the leader
    assert {i["author"] for i in items if i["kind"] == "report"} == {"tech", "fin"}


def test_cost_is_recorded_per_agent_and_model_with_prices_and_the_workers_ran_cheap(team):
    cost = team["cost"]
    assert cost["totals"]["calls"] >= 6 and cost["totals"]["cost_usd"] > 0
    assert {m["model"] for m in cost["by_model"]} == {"fake-strong", "fake-cheap"}
    assert {x["agent_name"] for x in cost["by_agent"]} >= {"case-leader", "tech", "fin"}


def test_tools_are_pruned_by_role(team):
    calls = team["calls"]
    leader = [c for c in calls if 'key="supervisor"' in c["sys"]]
    workers = [c for c in calls if 'key="tech"' in c["sys"] or 'key="fin"' in c["sys"]]
    assert leader and workers
    for c in leader:
        assert "CaseFinalize" in c["tools"] and "CaseSay" in c["tools"] and "Bash" not in c["tools"]
    for c in workers:
        assert not {"CaseFinalize", "CaseDecide", "CaseSay", "CaseAskConsent"} & set(c["tools"]), c["tools"]
        assert not {"TeamCreate", "AgentCreate", "TeamDelete", "Bash"} & set(c["tools"]), c["tools"]
    assert max(len(c["tools"]) for c in workers) <= 11  # a specialist sees few tools: that keeps the base cost low
    assert team["metrics"]["tool_schema_saving"] > 0.4  # the filter removes a good share of the tool schemas


def test_a_leader_cannot_answer_while_a_peer_question_is_open(tmp_path):
    """The leader once finalized a resolved answer while a teammate's question to another teammate had no answer
    yet, so the answer never reached the case file. Here the answer is held back until the leader has been refused."""
    gate = threading.Event()
    with world(tmp_path, None, wf_wait_seconds=0.5) as w:
        MODE["answer_gate"] = gate
        try:
            r, _ = w.flow.start()
            wid = r.json()["workflow_id"]
            refused = w.wait(lambda: any(m[0] == "tool" and "unanswered questions" in m[1]
                                         for c in w.model_calls() for m in c["shape"]),
                             timeout=60, what="the leader to be refused while the question is open")
            assert refused and w.sql("select count(*) from awp_case_items where kind='final'") == [(0,)]
        finally:
            gate.set()
        w.wait_state(wid, "closed", timeout=60)
        items = case_items(w, wid)
        q = [i for i in items if i["kind"] == "question"]
        a = [i for i in items if i["kind"] == "answer"]
        assert len(q) == 1 and len(a) == 1 and a[0]["data"]["to_ref"] == q[0]["ref"]
        final = next(i for i in items if i["kind"] == "final")
        assert a[0]["id"] < final["id"]  # the answer came before the end


def test_a_new_profile_version_is_the_one_the_next_specialist_runs_and_keeps_its_memory_per_workflow(tmp_path):
    with world(tmp_path, None, **TEAM) as w:
        tech = next(p for p in profiles() if p.key == "tech")
        v2 = tech.model_copy(update={"memory": MemoryConfig(enabled=True)})
        created = w.env.post("/platform/v1/profiles", v2.model_dump(mode="json"), ADM).json()
        assert created["version"] == 2
        publish(w.env, "tech", 2)
        _, r = w.flow.begin()
        assert any('key="tech" v="2"' in c["sys"] for c in CALLS)  # built from version 2: its prompt names the version
        assert (tmp_path / "ws" / "memory" / "ta" / "tech" / r["workflow_id"]).is_dir()


class _Judge:
    """Says the first answer is weakly supported, then accepts."""

    def __init__(self):
        self.asked = []

    async def support(self, claim, evidence):
        self.asked.append((claim, evidence))
        return 0.2 if len(self.asked) == 1 else 0.95


def test_a_second_opinion_can_block_a_grounded_looking_answer(tmp_path):
    judge = _Judge()
    with world(tmp_path, None, judge=judge, **TEAM) as w:
        _, r = w.flow.begin()
        notes = [i for i in case_items(w, r["workflow_id"]) if i["kind"] == "note" and i["data"].get("type") == "final_attempt"]
        assert len(notes) == 2  # one refused by the figure check, one by the second opinion
        assert "weakly supported" in str(notes[1]["data"]["problems"])
        assert len(judge.asked) == 2 and "1500000" in judge.asked[0][0]
        assert "1500000" in " ".join(judge.asked[0][1])  # it saw the cited evidence, nothing else


def test_a_report_is_in_the_case_file_before_the_message_that_wakes_the_leader_goes_out():
    """The leader reads the case file the moment the message wakes it (at its next step, when it is already running).
    A report recorded after the send was missed by that turn and never read: the workflow stayed `active` after its
    answer (one full run in some dozens; here the order itself is checked)."""
    import asyncio
    from types import SimpleNamespace

    from agentscope.message import TextBlock, ToolResultState
    from agentscope.tool import ToolResponse

    from awp.middleware.room import EvidenceMiddleware
    from awp.runtime import Binding

    order = []

    class Cases:
        async def get_case(self, case_id):
            return {"status": "open"}

        async def add(self, case_id, kind, author, data):
            order.append((kind, author, data["summary"]))

    async def leader_name(case_id):
        return "case-leader"

    async def send(**kw):
        order.append(("sent", kw["tool_call"].input))
        yield ToolResponse(content=[TextBlock(text="sent")], state=ToolResultState.SUCCESS)

    async def go():
        rt = SimpleNamespace(cases=Cases(), leader_name=leader_name)
        mw = EvidenceMiddleware(rt, Binding("case_1", "s", "a", "tech", "worker", "u"), None)
        call = SimpleNamespace(name="TeamSay", input='{"content": "Checked.", "to": null}',
                               model_copy=lambda update: SimpleNamespace(name="TeamSay", input=update["input"]))
        return [item async for item in mw.on_acting(None, {"tool_call": call}, send)]

    out = asyncio.run(go())
    assert len(out) == 1 and out[0].state == ToolResultState.SUCCESS
    assert order == [("report", "tech", "Checked."), ("sent", '{"content": "Checked.", "to": "case-leader"}')]
