"""The pure parts of B2, without an app: the overlap score (the builder's hard gate), what the platform makes of a
model's proposals, the checks of an evaluation case, and the platform's own cases."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from awp.builder import Proposal, Reply, judge, tidy
from awp.evals.checks import Checks, Observation, evaluate, ungrounded
from awp.evals.defaults import default_cases
from awp.evals.store import CaseIn, digest
from awp.overlap import normalise, overlaps, profile_tokens, score, tokens
from awp.profiles import AgentProfile


def prof(key="plumber", role="specialist", **over) -> AgentProfile:
    base = dict(key=key, name=key, role=role, mission="a plumber who repairs leaking pipes.",
                handles=["leaking pipes", "blocked drains"])
    return AgentProfile(**{**base, **over})


# ---- overlap -----------------------------------------------------------------------------------------------------------
def test_normalise_strips_case_and_vietnamese_marks():
    assert normalise("Sửa Ống Nước RÒ RỈ") == "sua ong nuoc ro ri"
    assert normalise("Đặt lịch Đường ống") == "dat lich duong ong"
    assert normalise("Crème brûlée") == "creme brulee"


def test_tokens_drop_stop_words_and_single_letters():
    assert tokens("The agent handles a leaking pipe and the drains") == frozenset({"leaking", "pipe", "drains"})
    assert tokens("chuyên viên xử lý các yêu cầu sửa ống nước", ["của cư dân"]) == frozenset({"sua", "ong", "nuoc", "cu", "dan"})
    assert tokens("") == frozenset() and tokens("a I x") == frozenset()
    assert tokens("pipes", ["Pipes", "PIPES!"]) == frozenset({"pipes"})  # a set: saying it three times adds nothing


def test_the_score_is_jaccard_over_handles_and_mission():
    a, b = frozenset({"sua", "ong", "nuoc"}), frozenset({"sua", "ong", "dien"})
    assert score(a, b) == pytest.approx(2 / 4) and score(a, a) == 1.0 and score(a, frozenset({"xe"})) == 0.0
    assert score(frozenset(), frozenset()) == 0.0 and score(a, frozenset()) == 0.0  # nothing said: nothing shared
    assert score(a, b) == score(b, a)
    assert profile_tokens(prof()) == frozenset({"plumber", "repairs", "leaking", "pipes", "blocked", "drains"})
    assert profile_tokens({"mission": "repairs pipes", "handles": None}) == frozenset({"repairs", "pipes"})


def test_the_same_work_written_with_and_without_marks_overlaps_fully():
    vi = prof("tho_nuoc", mission="thợ sửa ống nước bị rò rỉ.", handles=["ống nước rò rỉ", "tắc cống"])
    plain = prof("tho_ong", mission="Tho sua ong nuoc bi ro ri", handles=["ONG NUOC RO RI", "tac cong"])
    [found] = overlaps(plain, {"tho_nuoc": vi})
    assert found["key"] == "tho_nuoc" and found["score"] == 1.0 and "ong" in found["shared"]


def test_overlaps_are_ordered_explained_and_leave_strangers_out():
    existing = {"electric": prof("electric", mission="an electrician who repairs wiring.", handles=["power cuts"]),
                "pipes": prof("pipes", mission="repairs leaking pipes.", handles=["leaking pipes"]),
                "parking": prof("parking", mission="books visitor parking.", handles=["parking slots"])}
    found = overlaps(prof(), existing)
    assert [o["key"] for o in found] == ["pipes", "electric"]  # highest first; the parking agent shares no word
    assert found[0]["score"] == 0.5 and found[0]["shared"] == ["leaking", "pipes", "repairs"]
    assert found[1]["score"] < 0.2 and found[1]["shared"] == ["repairs"]
    assert overlaps(prof(), existing) == found  # nothing but the text decides


# ---- what the platform makes of a proposal ------------------------------------------------------------------------------
def test_a_create_that_overlaps_an_existing_agent_becomes_a_reuse_whatever_the_model_says():
    existing = {"pipes": prof("pipes", mission="repairs leaking pipes.", handles=["leaking pipes", "blocked drains"])}
    reply = Reply(proposals=[Proposal(action="create", profile=prof("water_fixer"), reason="a new one is needed")])
    [item] = judge(reply, existing, set(), 0.5)
    assert item["action"] == "reuse" and item["proposed_action"] == "create" and item["gated"] is True
    assert item["overlap_with"] == ["pipes"] and item["overlap"][0]["score"] >= 0.5
    assert "pipes" in item["notes"][-1] and "leaking" in item["notes"][-1] and "override_reason" in item["notes"][-1]
    assert item["profile"]["key"] == "water_fixer"  # kept, for an admin who applies it with a reason
    partly = Reply(proposals=[Proposal(action="create", profile=prof("water_fixer", handles=["leaking pipes"]))])
    [below] = judge(partly, existing, set(), 0.95)  # the threshold is configuration (the same handles are 1.0 at any threshold)
    assert below["action"] == "create" and below["gated"] is False and below["overlap"][0]["key"] == "pipes"
    # another role is another job: a leader that talks about pipes does not duplicate the plumber
    [leader] = judge(Reply(proposals=[Proposal(action="create", profile=prof("pipe_desk", role="leader"))]), existing, set(), 0.5)
    assert leader["action"] == "create" and leader["overlap"] == []


def test_the_models_opinion_about_overlap_is_shown_but_does_not_decide():
    existing = {"parking": prof("parking", mission="books visitor parking.", handles=["parking slots"])}
    said = Proposal(action="create", profile=prof(), overlap_with=["parking", "ghost"], reason="similar to parking")
    [item] = judge(Reply(proposals=[said]), existing, set(), 0.5)
    assert item["action"] == "create" and item["advised_overlap"] == ["parking"] and item["overlap_with"] == []
    [reuse] = judge(Reply(proposals=[Proposal(action="reuse", overlap_with=["parking", "ghost"], reason="it does this")]),
                    existing, set(), 0.5)
    assert reuse["action"] == "reuse" and reuse["overlap_with"] == ["parking"] and reuse["profile"] is None
    [nobody] = judge(Reply(proposals=[Proposal(action="reuse", overlap_with=["ghost"])]), existing, set(), 0.5)
    assert nobody["action"] == "clarify"  # there is no such agent to reuse


def test_a_taken_key_a_revise_of_nobody_and_an_empty_proposal():
    existing = {"plumber": prof(mission="books parking.", handles=["parking"])}
    [taken] = judge(Reply(proposals=[Proposal(action="create", profile=prof())]), existing, set(), 0.5)
    assert taken["action"] == "reuse" and taken["gated"] and taken["overlap_with"] == ["plumber"] and "exists already" in taken["notes"][-1]
    [revise] = judge(Reply(proposals=[Proposal(action="revise", profile=prof())]), existing, set(), 0.5)
    assert revise["action"] == "revise" and not revise["gated"]
    [new] = judge(Reply(proposals=[Proposal(action="revise", profile=prof("nobody"))]), {}, set(), 0.5)
    assert new["action"] == "create" and "no agent 'nobody' to revise" in new["notes"][-1]
    [empty] = judge(Reply(proposals=[Proposal(action="create")]), {}, set(), 0.5)
    assert empty["action"] == "clarify" and empty["question"]
    many = judge(Reply(proposals=[Proposal(action="clarify", question=f"q{i}?") for i in range(20)]), {}, set(), 0.5)
    assert len(many) == 8 and [m["index"] for m in many] == list(range(8))


def test_tidy_keeps_only_what_a_chat_may_set():
    wild = prof(tools_allow=["lookup_ticket", "Bash", "mcp__*", "book_repair"], mission="m" * 5000, instructions="i" * 20000,
                handles=[f"h{i}" for i in range(50)] + ["  "], knowledge={"knowledge_base_ids": ["kb1"], "mcp_servers": ["x"]},
                memory={"enabled": True, "scope": "team"})
    clean, notes = tidy(wild, {"lookup_ticket", "book_repair"}, set())
    assert clean.tools_allow == ["lookup_ticket", "book_repair"] and "Bash" in notes[0] and "mcp__*" in notes[0]
    assert len(clean.mission) == 600 and len(clean.instructions) == 8000 and len(clean.handles) == 20
    assert clean.knowledge.knowledge_base_ids == [] and clean.knowledge.mcp_servers == [] and clean.memory.enabled is False
    leader = prof("desk", role="leader", team=["plumber", "ghost", "desk_two"])
    clean, notes = tidy(leader, set(), {"plumber"})
    assert clean.team == ["plumber"] and "ghost" in notes[0]


# ---- the checks of a case -------------------------------------------------------------------------------------------------
def call(tool, ok=True, **args):
    return {"tool": tool, "input": json.dumps(args), "ok": ok}


def names(verdicts):
    return {v["check"]: v["ok"] for v in verdicts}


def test_must_call_and_must_not_call_match_a_tool_and_the_arguments_named():
    obs = Observation(calls=[call("lookup", ticket_id="T-1"), call("AgentCreate", subagent_type="tech", name="t")], outputs=["ok"])
    checks = Checks(must_call=["lookup", {"tool": "AgentCreate", "args": {"subagent_type": "tech"}}],
                    must_not_call=["book", {"tool": "AgentCreate", "args": {"subagent_type": "fin"}}])
    assert [v["ok"] for v in evaluate(checks, obs)] == [True, True, True, True]
    wrong = Checks(must_call=[{"tool": "AgentCreate", "args": {"subagent_type": "fin"}}], must_not_call=["lookup"])
    assert [(v["check"], v["ok"]) for v in evaluate(wrong, obs)] == [("must_call", False), ("must_not_call", False)]
    assert 'AgentCreate({"subagent_type": "fin"})' in evaluate(wrong, obs)[0]["detail"]
    broken = Observation(calls=[{"tool": "lookup", "input": "not json", "ok": False}], outputs=["x"])
    assert names(evaluate(Checks(must_call=["lookup", {"tool": "lookup", "args": {"a": 1}}]), broken)) == {"must_call": False}


def test_grounded_means_every_figure_is_in_a_tool_result_or_the_input():
    sources = ["Ticket T-1001 opened 03/10, fee 150.000 VND", "what does 0901 234 567 owe?"]
    fine = Observation(outputs=["T-1001 was opened on 03/10; the fee is 150000 VND (see F1, E2). Call 0901234567."], sources=sources)
    assert ungrounded(fine) == [] and names(evaluate(Checks(grounded=True), fine)) == {"grounded": True}
    invented = Observation(outputs=["The fee is 2000000 VND, due 15/11."], sources=sources)
    bad = evaluate(Checks(grounded=True), invented)[0]
    assert not bad["ok"] and "2000000" in bad["detail"] and "15/11" in bad["detail"]
    words = Observation(outputs=["It costs two million dong."], sources=sources)
    assert "million" in ungrounded(words)[0]
    # what it tried to say counts, also when the call was refused; a tool that states nothing does not
    tried = Observation(outputs=["I cannot say yet."], sources=sources, calls=[
        call("CaseSay", ok=False, text="The fee is 999 VND."), call("lookup", ticket_id="77777")])
    assert ungrounded(tried) == ["999"]
    assert names(evaluate(Checks(), invented)) == {}  # a check that was not asked for is not made


def test_gap_text_state_cost_and_the_two_ways_a_run_fails_as_a_whole():
    obs = Observation(outputs=["The ticket is WAITING for parts."], gaps=1, state="awaiting_user", cost_usd=0.02)
    good = Checks(must_contain=["waiting for parts"], must_not_contain=["finished"], must_record_gap=True,
                  expected_state=["awaiting_user", "needs_attention"], max_cost_usd=0.05)
    assert all(v["ok"] for v in evaluate(good, obs)) and len(evaluate(good, obs)) == 5
    bad = Checks(must_contain=["finished"], must_not_contain=["waiting"], expected_state="closed", max_cost_usd=0.01)
    assert names(evaluate(bad, obs)) == {"must_contain": False, "must_not_contain": False, "expected_state": False,
                                         "max_cost_usd": False}
    assert names(evaluate(Checks(must_record_gap=True), Observation(outputs=["x"]))) == {"must_record_gap": False}
    late = evaluate(Checks(grounded=True), Observation(timed_out=True, responded=False))
    assert late[0] == {"check": "finished", "ok": False, "detail": "the run did not come to rest in time"}
    quiet = evaluate(Checks(grounded=True, must_not_call=["x"]), Observation(responded=False))
    assert quiet[0]["check"] == "responded" and not quiet[0]["ok"]  # doing nothing wrong is not passing


def test_checks_and_cases_refuse_what_they_do_not_know():
    for bad in ({"expected_state": ["sleeping"]}, {"must_call": ["two words"]}, {"max_cost_usd": -1}, {"judge": "be nice"},
                {"must_call": [{"tool": "x", "arguments": {}}]}):
        with pytest.raises(ValidationError):
            Checks(**bad)
    assert Checks(expected_state="closed").expected_state == ["closed"] and Checks().empty()
    with pytest.raises(ValidationError):
        CaseIn(name="platform:x", input="i", checks={"grounded": True})
    with pytest.raises(ValidationError):
        CaseIn(name="x", input="i", checks={})
    assert CaseIn(name=" x ", input="a\x00b", checks={"grounded": True}).model_dump()["input"] == "ab"
    assert digest(prof()) == digest(prof()) != digest(prof(mission="another mission."))


# ---- the platform's own cases -----------------------------------------------------------------------------------------------
def test_every_agent_gets_the_three_platform_cases_and_a_leader_two_more():
    tech = prof("tech", handles=["tickets"], refuses=["prices"], tools_allow=["lookup_ticket", "mcp__x__*"])
    cases = {c["name"]: c for c in default_cases(tech)}
    assert list(cases) == ["platform:no_invented_figures", "platform:says_unknown_when_data_is_missing",
                           "platform:refuses_out_of_scope"]
    assert cases["platform:no_invented_figures"]["checks"] == {"grounded": True}
    assert cases["platform:says_unknown_when_data_is_missing"]["checks"] == {"must_record_gap": True, "grounded": True}
    assert "prices" in cases["platform:refuses_out_of_scope"]["input"] and "tickets" in cases["platform:no_invented_figures"]["input"]
    for c in cases.values():  # a recorded answer for every tool named outright; a pattern gets none
        assert list(c["fixtures"]) == ["lookup_ticket"] and c["platform"] is True and Checks.model_validate(c["checks"])
    assert "NOT FOUND" in cases["platform:says_unknown_when_data_is_missing"]["fixtures"]["lookup_ticket"]
    assert [c["name"] for c in default_cases(prof("bare", refuses=[], handles=[]))] == [
        "platform:no_invented_figures", "platform:says_unknown_when_data_is_missing"]
    fin = prof("fin", handles=["invoices"], tools_allow=["price_list"])
    desk = prof("desk", role="leader", team=["tech", "fin", "ghost"], refuses=["legal advice"])
    lead = {c["name"]: c for c in default_cases(desk, {"tech": tech, "fin": fin})}
    assert list(lead)[-2:] == ["platform:simple_work_needs_no_team", "platform:picks_the_right_specialist"]
    assert lead["platform:simple_work_needs_no_team"]["checks"]["must_not_call"] == ["TeamCreate", "AgentCreate"]
    picks = lead["platform:picks_the_right_specialist"]
    assert "tickets" in picks["input"] and picks["checks"]["must_call"] == [{"tool": "AgentCreate", "args": {"subagent_type": "tech"}}]
    assert [c["args"]["subagent_type"] for c in picks["checks"]["must_not_call"]] == ["fin", "ghost"]
    assert "lookup_ticket" in picks["fixtures"]
    assert lead["platform:refuses_out_of_scope"]["checks"]["expected_state"] == ["needs_attention", "awaiting_user"]
    assert "platform:picks_the_right_specialist" not in {c["name"] for c in default_cases(desk, {})}  # no team profile to ask for
