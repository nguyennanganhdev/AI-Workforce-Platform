"""The leader of a workflow: how it is made, and how a room is assembled for it (slice S3)."""
from __future__ import annotations

import scripts
from enginekit import world
from fake_llm import CALLS

from awp.middleware import middleware_factory, tool_factory
from awp.workforce.turns import TurnRecorder


def names(items) -> list[str]:
    return [type(x).__name__ for x in items]


def test_one_leader_session_is_made_for_the_workflow_and_bound_to_its_case(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        start, first = w.flow.begin()
        case = w.sql("select id, leader_agent_id, leader_session_id from awp_cases where id=(select case_id from wf_workflows)")[0]
        assert case[1] and case[2]
        assert w.sql("select role, agent_name, agent_id from awp_case_sessions where session_id=?", (case[2],)) \
            == [("leader", "case-leader", case[1])]
        # one agent per profile version, whose prompt speaks through CaseSay
        assert w.sql("select key from awp_agent_map") == [("supervisor",)]
        # the session is named (a model call less) and every later message goes to it
        w.flow.reply(start, first, message={"type": "text", "text": "Tôi rảnh từ 14 giờ."})
        assert w.sql("select leader_session_id from awp_cases where id=?", (case[0],)) == [(case[2],)]
        assert w.sql("select count(*) from awp_case_sessions") == [(1,)]
        sys_prompt = w.run(lambda: w.rt.storage.get_agent("awp:ta", case[1])).data.system_prompt
        assert "CaseSay" in sys_prompt and 'key="supervisor"' in sys_prompt


def test_a_second_workflow_reuses_the_agent_but_gets_its_own_session(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        w.flow.begin()
        w.flow.begin()
        agents = w.sql("select distinct leader_agent_id from awp_cases")
        sessions = w.sql("select distinct leader_session_id from awp_cases")
        assert len(agents) == 1 and len(sessions) == 2


def test_a_route_whose_leader_cannot_start_fails_the_request_and_asks_for_attention(tmp_path):
    for broken in ("ghost", "tech"):  # not published at all / published, but a specialist
        (tmp_path / broken).mkdir()
        with world(tmp_path / broken, scripts.interactive) as w:
            w.sql("update wf_routes set leader_profile=?", (broken,))
            _, r = w.flow.begin()
            assert (r["request_status"], r["workflow_state"], r["next_action"]) == ("failed", "needs_attention", "resolve_attention")
            assert r["error"]["code"] == "engine_error" and r["result"]["messages"] == []
            wid = r["workflow_id"]
            assert w.sql("select attention_reason from wf_workflows where id=?", (wid,)) == [("engine_error",)]
            assert w.sql("select status, attempts from wf_jobs where workflow_id=?", (wid,)) == [("failed", 1)]  # no retry: it cannot work
            assert not CALLS  # no model was asked
            assert w.sql("select leader_session_id from awp_cases") == [(None,)]


def test_a_leader_is_recorded_and_a_session_outside_a_workflow_gets_no_room(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        _, r = w.flow.begin()
        case_id = w.sql("select case_id from wf_workflows where id=?", (r["workflow_id"],))[0][0]
        lead = w.run(lambda: w.rt.cases.sessions_of_case(case_id))[0]
        mws = w.run(lambda: middleware_factory(w.rt)("awp:ta", lead["agent_id"], lead["session_id"]))
        assert isinstance(mws[0], TurnRecorder) and "LeaderWatchdog" not in names(mws)  # the recorder is outermost; no watchdog exists any more
        tools = w.run(lambda: tool_factory(w.rt)("awp:ta", lead["agent_id"], lead["session_id"]))
        assert "CaseSay" in names(tools) and "CaseFinalize" in names(tools)

        # a case without a workflow (none is made by the platform) is not given a room: no middleware, no tools
        stray = w.run(lambda: w.rt.cases.create_case(tenant="ta", domain="test", external_ref="STRAY-1",
                                                     user_id="awp:ta", meta={}))
        w.run(lambda: w.rt.cases.bind_session(stray, "sess_stray", lead["agent_id"], "case-leader", "leader"))
        assert w.run(lambda: middleware_factory(w.rt)("awp:ta", lead["agent_id"], "sess_stray")) == []
        assert w.run(lambda: tool_factory(w.rt)("awp:ta", lead["agent_id"], "sess_stray")) == []


def test_a_worker_gets_no_recorder_and_no_say(tmp_path):
    with world(tmp_path, scripts.consult) as w:
        _, r = w.flow.begin()
        case_id = w.sql("select case_id from wf_workflows where id=?", (r["workflow_id"],))[0][0]
        worker = next(s for s in w.run(lambda: w.rt.cases.sessions_of_case(case_id)) if s["role"] == "worker")
        mws = w.run(lambda: middleware_factory(w.rt)("awp:ta", worker["agent_id"], worker["session_id"]))
        assert "TurnRecorder" not in names(mws)
        tools = w.run(lambda: tool_factory(w.rt)("awp:ta", worker["agent_id"], worker["session_id"]))
        assert "CaseSay" not in names(tools)


def test_say_is_in_the_leaders_tool_set_and_not_the_workers():
    import fnmatch

    from awp.profiles.compile import LEADER_TOOLS, WORKER_TOOLS, WRAP_UP_TOOLS
    assert any(fnmatch.fnmatchcase("CaseSay", p) for p in LEADER_TOOLS)
    assert not any(fnmatch.fnmatchcase("CaseSay", p) for p in WORKER_TOOLS)
    assert "CaseSay" in WRAP_UP_TOOLS  # a leader out of budget can still tell the resident


def test_the_team_roster_names_a_worker_before_the_room_has_bound_it(tmp_path):
    """The room binds a worker when its first run starts; the leader's chain must not look finished in
    the gap, so the roster AgentScope keeps is read too (a nudge in that gap was a real, flaky bug)."""
    from awp.workforce.settling import team_names
    with world(tmp_path, scripts.consult) as w:
        _, r = w.flow.begin()
        case_id = w.sql("select case_id from wf_workflows where id=?", (r["workflow_id"],))[0][0]
        leader = w.sql("select leader_session_id from awp_cases where id=?", (case_id,))[0][0]
        assert w.run(lambda: team_names(w.rt, "ta", leader)) == ["tech"]
        assert w.run(lambda: team_names(w.rt, "ta", "sess_other")) == []
