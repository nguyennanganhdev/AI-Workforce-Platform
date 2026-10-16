"""M3, the evaluation: the exact draft version runs in a sandbox on the real engine with the scripted model, the
deterministic checks decide, and nothing of a run is visible to a partner or to another tenant."""
from __future__ import annotations

import json
import time

import evalkit as ek
import pytest
import scripts
from conftest import ADM, ADM_B, publish as override
from enginekit import world
from fake_llm import CALLS, MODE

from awp.evals.sandbox import ids

P = ek.P
PLATFORM = ["platform:no_invented_figures", "platform:says_unknown_when_data_is_missing", "platform:refuses_out_of_scope"]


def shown(run: dict) -> str:
    return json.dumps(run, indent=1, ensure_ascii=False)[:4000]


# ---- a specialist ---------------------------------------------------------------------------------------------------
def test_a_careful_specialist_passes_the_platform_cases_and_the_run_is_stored(tmp_path):
    with world(tmp_path, publish=False) as w:
        ek.agents(tech=ek.careful)
        ek.draft(w.env, ek.TECH)
        run = ek.evaluated(w.env, "tech")
        assert run["status"] == "passed" and run["score"] == 1.0, shown(run)
        assert [c["name"] for c in run["results"]] == PLATFORM
        assert run["version"] == 1 and run["started_by"].startswith("admin:") and run["duration_s"] > 0
        for case in run["results"]:  # per-case detail, cost and time are kept
            assert case["passed"] and case["checks"] and case["duration_s"] > 0 and case["cost_usd"] > 0
            assert "lookup_ticket" in case["calls"] and case["case_id"].startswith("case_")
        assert run["cost_usd"] == sum(c["cost_usd"] for c in run["results"]) > 0
        # the specialist that ran is the draft: its prompt carries version 1 of a profile that was never published,
        # under the platform's own leader
        assert w.sql("select status from awp_profiles where key='tech'") == [("draft",)]
        assert any('key="tech" v="1"' in c["sys"] for c in CALLS)
        assert any('key="awp_eval_leader"' in c["sys"] for c in CALLS)
        listed = w.env.http.get(f"{P}/tech/versions/1/evals", headers=ADM).json()["runs"]
        assert [x["run_id"] for x in listed] == [run["run_id"]] and listed[0]["results"] == run["results"]
        # its tool was the case's fixture, not the real look-up of the same name the test app also has
        texts = [json.loads(d)["text"] if isinstance(d, str) else d["text"] for (d,) in w.sql(
            "select data from awp_case_items where kind='evidence' and case_id=?", (run["results"][1]["case_id"],))]
        assert any(t.startswith("NOT FOUND: there is no record of this.") for t in texts) and not any("T-1001:" in t for t in texts)
        w.quiet()
        assert not w.sql("select 1 from wf_workflows where state <> 'closed'")  # every sandbox workflow is closed behind the run


def test_a_specialist_that_invents_a_figure_is_caught_by_the_platform_case(tmp_path):
    with world(tmp_path, publish=False) as w:
        ek.agents(tech=ek.inventing)
        ek.draft(w.env, ek.TECH)
        run = ek.evaluated(w.env, "tech")
        assert run["status"] == "failed" and run["score"] < 1, shown(run)
        case = next(c for c in run["results"] if c["name"] == "platform:no_invented_figures")
        [grounded] = [v for v in case["checks"] if v["check"] == "grounded"]
        assert not grounded["ok"] and "2000000" in grounded["detail"] and "15/11" in grounded["detail"]
        assert not case["passed"] and any("2000000" in s for s in case["said"])
        r = ek.publish(w.env, "tech")  # and so it is not released
        assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED", r.text
        assert "failed" in r.json()["detail"]["message"] and r.json()["detail"]["latest_run"]["run_id"] == run["run_id"]


def test_a_specialist_that_never_answers_does_not_pass_by_having_done_nothing_wrong(tmp_path):
    with world(tmp_path, publish=False) as w:
        ek.agents(tech=ek.silent)
        ek.draft(w.env, ek.TECH)
        run = ek.evaluated(w.env, "tech")
        assert run["status"] == "failed", shown(run)
        assert all(ek.verdicts(run)[name].get("responded") is False for name in PLATFORM)


@pytest.mark.slow
def test_a_tenants_own_case_runs_with_its_fixtures_and_checks(tmp_path):
    def reader(c):
        """Reads the ticket and records what the tool said, citing it."""
        if c.called("lookup_ticket") == 0:
            return [("lookup_ticket", {"ticket_id": "T-7"})]
        ev = scripts.evidence_of(" ".join(c.results("lookup_ticket")))
        if "waiting for parts" in c.blob and c.called("CaseFact") == 0:
            return [("CaseFact", {"text": "Ticket T-7 is waiting for parts since 03/10.", "evidence": ev[:1]})]
        if c.called("CaseFact") == 0 and c.called("CaseGap") == 0:
            return [("CaseGap", {"topic": "the ticket", "tried": "lookup_ticket"})]
        if c.called("TeamSay") == 0:
            return [("TeamSay", {"content": "See my facts and gaps.", "to": None})]
        return "Reported."

    with world(tmp_path, publish=False) as w:
        ek.agents(tech=reader)
        ek.draft(w.env, ek.TECH)
        body = {"name": "reads the ticket", "input": "What is the state of ticket T-7?",
                "fixtures": {"lookup_ticket": {"ticket": "T-7", "status": "waiting for parts", "since": "03/10"}},
                "checks": {"must_call": ["lookup_ticket", {"tool": "lookup_ticket", "args": {"ticket_id": "T-7"}}],
                           "must_not_call": ["price_list"], "must_contain": ["waiting for parts"],
                           "must_not_contain": ["finished"], "grounded": True, "max_cost_usd": 1.0}}
        made = w.env.post(f"{P}/tech/eval-cases", body)
        assert made.status_code == 201 and made.json()["platform"] is False, made.text
        cases = w.env.http.get(f"{P}/tech/eval-cases", headers=ADM).json()["cases"]
        assert [c["name"] for c in cases] == [*PLATFORM, "reads the ticket"] and [c["platform"] for c in cases] == [True] * 3 + [False]
        run = ek.evaluated(w.env, "tech")
        assert run["status"] == "passed", shown(run)
        mine = run["results"][-1]
        assert mine["name"] == "reads the ticket" and mine["platform"] is False
        assert [v["check"] for v in mine["checks"]] == ["must_call", "must_call", "must_not_call", "must_contain",
                                                         "must_not_contain", "grounded", "max_cost_usd"]
        # the same agent against a case it cannot meet: the run fails on exactly that check
        edited = {**body, "checks": {"must_contain": ["has been replaced"], "max_cost_usd": 0.0}}
        assert w.env.http.put(f"{P}/tech/eval-cases/{made.json()['id']}", json=edited, headers=ADM).status_code == 200
        run = ek.evaluated(w.env, "tech")
        assert run["status"] == "failed" and ek.verdicts(run)["reads the ticket"] == {"must_contain": False, "max_cost_usd": False}
        assert w.env.http.delete(f"{P}/tech/eval-cases/{made.json()['id']}", headers=ADM).status_code == 200
        assert [c["name"] for c in w.env.http.get(f"{P}/tech/eval-cases", headers=ADM).json()["cases"]] == PLATFORM


def test_case_bodies_are_checked_and_cases_belong_to_one_tenant(env):
    ek.draft(env, ek.TECH)
    ok = {"name": "a", "input": "x", "checks": {"grounded": True}}
    for bad in ({**ok, "name": "platform:mine"}, {**ok, "checks": {}}, {**ok, "checks": {"expected_state": "sleeping"}},
                {**ok, "fixtures": {"not a tool!": "x"}}, {**ok, "checks": {"must_call": ["no spaces"]}},
                {**ok, "checks": {"unknown_check": True}}, {**ok, "input": ""}, {**ok, "fixtures": {"t": "x" * 20001}}):
        assert env.post(f"{P}/tech/eval-cases", bad).status_code == 422, bad
    made = env.post(f"{P}/tech/eval-cases", ok)
    assert made.status_code == 201 and env.post(f"{P}/tech/eval-cases", ok).status_code == 409  # the name is taken
    assert env.post(f"{P}/ghost/eval-cases", ok).status_code == 404
    cid = made.json()["id"]
    # tenant tb has no such profile and no such case
    assert env.http.get(f"{P}/tech/eval-cases", headers=ADM_B).status_code == 404
    assert env.post(f"{P}/tech/eval-cases", ok, ADM_B).status_code == 404
    ek.draft(env, {**ek.TECH, "key": "tech_b"}, ADM_B)
    assert env.http.put(f"{P}/tech_b/eval-cases/{cid}", json=ok, headers=ADM_B).status_code == 404
    assert env.http.delete(f"{P}/tech_b/eval-cases/{cid}", headers=ADM_B).status_code == 404
    assert env.sql("select tenant, key, name from awp_eval_cases") == [("ta", "tech", "a")]


# ---- a leader --------------------------------------------------------------------------------------------------------
def test_a_leader_runs_as_a_sandbox_workflow_in_the_exact_draft_version(tmp_path):
    with world(tmp_path, ek.good_leader, publish=False) as w:  # the route's `supervisor` is version 1, a bare draft
        ek.agents(tech=ek.careful)
        ek.draft(w.env, ek.TECH)
        ek.publish(w.env, "tech", override_reason="the leader under test needs its specialist")
        assert ek.draft(w.env, ek.DESK)["version"] == 2
        run = ek.evaluated(w.env, "supervisor", 2)
        assert run["status"] == "passed", shown(run)
        got = ek.verdicts(run)
        assert list(got) == ["platform:no_invented_figures", "platform:says_unknown_when_data_is_missing",
                             "platform:refuses_out_of_scope", "platform:simple_work_needs_no_team",
                             "platform:picks_the_right_specialist"]
        assert got["platform:refuses_out_of_scope"]["expected_state"] and got["platform:picks_the_right_specialist"] == {
            "must_call": True}
        states = {c["name"]: c["state"] for c in run["results"]}
        assert states["platform:simple_work_needs_no_team"] == "awaiting_user"
        assert states["platform:refuses_out_of_scope"] == "needs_attention"
        picks = next(c for c in run["results"] if c["name"] == "platform:picks_the_right_specialist")
        assert picks["calls"][:2] == ["TeamCreate", "AgentCreate"]
        # version 2 ran (a draft; nothing of `supervisor` is published), with no agent kept for it
        assert any('key="supervisor" v="2"' in c["sys"] for c in CALLS) and not any('key="supervisor" v="1"' in c["sys"] for c in CALLS)
        assert w.sql("select version, status from awp_profiles where key='supervisor' order by version") == [(1, "draft"), (2, "draft")]
        assert not w.sql("select 1 from awp_agent_map where key='supervisor'")


def test_a_leader_that_invents_a_figure_is_caught_although_the_guard_kept_it_from_the_resident(tmp_path):
    with world(tmp_path, ek.inventing_leader, publish=False) as w:
        ek.draft(w.env, {**ek.DESK, "team": [], "refuses": []})
        run = ek.evaluated(w.env, "supervisor", 2)
        assert run["status"] == "failed", shown(run)
        case = run["results"][0]
        assert case["name"] == "platform:no_invented_figures" and ek.verdicts(run)[case["name"]]["grounded"] is False
        assert case["said"] == ["I cannot give a fee yet; a person will confirm it."]  # what it tried is judged, not only what got out
        assert "2000000" in next(v["detail"] for v in case["checks"] if v["check"] == "grounded")


# ---- the sandbox is nobody's but the run's ---------------------------------------------------------------------------
def test_nothing_of_an_evaluation_is_visible_to_a_partner_or_to_another_tenant(tmp_path):
    with world(tmp_path, scripts.interactive) as w:  # a real partner with a real workflow, and published profiles
        ek.agents(tech=ek.careful)
        start, started = w.flow.begin()
        real_conv, real_wf = started["conversation_id"], started["workflow_id"]
        events_before = w.sql("select count(*) from wf_events where conversation_id=?", (real_conv,))
        messages_before = w.sql("select count(*) from wf_messages")
        assert ek.draft(w.env, {**ek.TECH, "mission": "a technician, second version."})["version"] == 2
        run = ek.evaluated(w.env, "tech", 2)
        assert run["status"] == "passed", shown(run)
        client_id, route_id = ids("ta")
        boxes = w.sql("select id, conversation_id from wf_workflows where client_id=?", (client_id,))
        assert len(boxes) == 3 and {c["workflow_id"] for c in run["results"]} == {wid for wid, _ in boxes}
        # the real conversation got no event and no message of it
        assert w.sql("select count(*) from wf_events where conversation_id=?", (real_conv,)) == events_before
        assert w.sql("select count(*) from wf_messages where workflow_id=?", (real_wf,)) == [(1,)] or messages_before
        assert not w.sql("select 1 from wf_events where conversation_id=? and workflow_id<>?", (real_conv, real_wf))
        # /workforce/v1 with the tenant's own partner key: a sandbox conversation, workflow and request are not there
        for wid, conv in boxes:
            [(rid,)] = w.sql("select id from wf_requests where workflow_id=?", (wid,))
            for user in ("evaluation", "resident-123"):
                assert w.flow.snapshot(conv, user=user).status_code == 404
                assert w.flow.history(conv, user=user).status_code == 404
                assert w.flow.request(rid, user=user).status_code == 404
            body = w.flow.reply_body({"workflow_id": wid}, {**start, "external_user_id": "evaluation",
                                                            "external_conversation_id": f"{run['run_id']}:0",
                                                            "external_ticket_id": f"{run['run_id']}:0"})
            assert w.flow.post(body).status_code in (404, 409, 403) and "evaluation" not in w.flow.post(body).text.lower()
        assert w.sql("select count(*) from wf_messages where workflow_id in (select id from wf_workflows where client_id=?) "
                     "and sender='user'", (client_id,)) == [(3,)]  # the refused replies wrote nothing
        # no key can be made for the sandbox client, and it has none; its route has no tool and called no partner
        assert w.env.post(f"/platform/v1/wf/clients/{client_id}/keys", {"operations": ["read_result"]}).status_code == 404
        assert w.env.post(f"/platform/v1/wf/clients/{client_id}/managers", {"name": "x"}).status_code == 404
        assert not w.sql("select 1 from wf_keys where client_id=?", (client_id,))
        assert not w.sql("select 1 from wf_tools where route_id=?", (route_id,)) and not w.sql(
            "select 1 from wf_mcp_servers where route_id=?", (route_id,))
        assert not w.sql("select 1 from wf_operations where route_id=?", (route_id,))
        # the admin's own views of partner work do not show it either
        admin = lambda path: w.env.http.get("/platform/v1" + path, headers=ADM).json()  # noqa: E731
        assert [c["client_id"] for c in admin("/wf/clients")["clients"]] == [w.flow.client["client_id"]]
        assert {r["route_id"] for r in admin("/wf/routes")["routes"]} == {w.flow.route["route_id"]}
        assert {x["workflow_id"] for x in admin("/wf/workflows")["workflows"]} == {real_wf}
        assert w.env.http.get(f"/platform/v1/wf/workflows/{boxes[0][0]}", headers=ADM).status_code == 404
        assert all(c["domain"] != "awp:eval" for c in admin("/cases")["cases"]) and len(admin("/cases")["cases"]) == 1
        # another tenant: no run, no case file, no sandbox of the first
        assert w.env.http.get(f"{P}/tech/versions/2/evals", headers=ADM_B).status_code == 404
        assert w.env.post(f"{P}/tech/versions/2/evals", {}, ADM_B).status_code == 404
        case_id = run["results"][0]["case_id"]
        assert w.env.http.get(f"/platform/v1/cases/{case_id}/items", headers=ADM_B).status_code == 404
        assert w.env.http.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).status_code == 200  # its own admin may read it
        assert w.env.http.get("/platform/v1/wf/workflows", headers=ADM_B).json()["workflows"] == []
        assert w.sql("select distinct tenant from awp_eval_runs") == [("ta",)]
        assert w.sql("select distinct tenant from awp_ledger") == [("ta",)]  # the cost is the tenant's own
        # the published technician (version 1) is still what a real workflow would get
        assert sorted(k for k in w.rt.templates if k != "default") == ["fin", "tech"]


# ---- bounded ---------------------------------------------------------------------------------------------------------
@pytest.mark.slow
def test_a_case_that_does_not_end_is_cut_off_and_the_engine_goes_on(tmp_path):
    slept = []

    def stuck_once(system: str) -> float:
        """The first model call of the technician hangs for longer than a case may take."""
        if 'key="tech"' in system and not slept:
            slept.append(1)
            return 10.0
        return 0

    with world(tmp_path, scripts.interactive, eval_case_timeout_seconds=4.0) as w:
        ek.agents(tech=ek.careful)
        MODE["delay"] = stuck_once
        ek.draft(w.env, {**ek.TECH, "mission": "a technician, second version."})
        began = time.monotonic()
        run = ek.evaluated(w.env, "tech", 2)
        assert run["status"] == "failed", shown(run)
        first = run["results"][0]
        assert not first["passed"] and first["checks"][0] == {
            "check": "finished", "ok": False, "detail": "the run did not come to rest in time"}
        assert 4.0 <= first["duration_s"] < 10 and time.monotonic() - began < 60
        assert [c["passed"] for c in run["results"][1:]] == [True, True]  # the cases after it ran as usual
        assert w.sql("select state from wf_workflows where id=?", (first["workflow_id"],)) == [("closed",)]
        _, started = w.flow.begin()  # and a resident's request is served as before
        assert started["request_status"] == "completed" and started["workflow_state"] == "awaiting_user"
        w.quiet()


def test_a_sandbox_case_carries_the_budget_of_an_evaluation_and_a_second_run_waits_for_the_first(tmp_path):
    with world(tmp_path, publish=False, eval_case_budget_usd=0.25, eval_case_budget_tokens=5000, case_budget_usd=9.0) as w:
        ek.agents(tech=ek.careful)
        MODE["delay"] = lambda system: 0.25  # slow enough for a second request to arrive while the first run goes
        ek.draft(w.env, {**ek.TECH, "refuses": [], "tools_allow": []})
        first = w.env.post(f"{P}/tech/versions/1/evals", {})
        assert first.status_code == 202 and first.json()["status"] == "running" and first.json()["results"] == []
        again = w.env.post(f"{P}/tech/versions/1/evals", {})
        assert again.status_code == 409 and "running" in again.text
        r = ek.publish(w.env, "tech")
        assert r.status_code == 409 and "still running" in r.json()["detail"]["message"]
        ek.draft(w.env, {**ek.TECH, "key": "other", "name": "Other"})
        override(w.env, "other")  # a release meanwhile rebuilds the live templates: the draft under evaluation stays
        assert sorted(k for k in w.rt.templates if k != "default") == ["other", "tech@1"]
        run = w.wait(lambda: (lambda x: x if x["status"] != "running" else None)(
            w.env.http.get(f"{P}/tech/versions/1/evals", headers=ADM).json()["runs"][0]), 60, "the run to end")
        assert run["status"] == "passed" and run["run_id"] == first.json()["run_id"], shown(run)
        assert w.sql("select distinct budget_usd, budget_tokens from awp_cases") == [(0.25, 5000)]
        assert sorted(k for k in w.rt.templates if k != "default") == ["other"]  # and is gone when its run is over


def test_a_draft_edited_while_it_is_evaluated_has_no_result(tmp_path):
    with world(tmp_path, publish=False) as w:
        edited = {**ek.TECH, "refuses": [], "mission": "something else entirely."}

        def edits(c):
            if c.called("CaseGap") == 0 and c.called("lookup_ticket") == 1:  # in the middle of the first case
                w.sql("update awp_profiles set data=? where key='tech' and version=1", (json.dumps(edited),))
            return ek.careful(c)

        ek.agents(tech=edits)
        ek.draft(w.env, {**ek.TECH, "refuses": []})
        run = ek.evaluated(w.env, "tech")
        assert run["status"] == "error" and "edited" in run["error"], shown(run)
        assert ek.publish(w.env, "tech").status_code == 409


def test_a_run_left_running_by_a_process_that_died_ends_as_an_error(env):
    ek.draft(env, ek.TECH)
    row = ("run_dead", "ta", "tech", 1, "sha256:x", "running", "[]", 0.0, "admin", time.time() - 5, time.time() - 500)
    env.sql("insert into awp_eval_runs (id, tenant, key, version, profile_hash, status, results, cost_usd, started_by, "
            "deadline, created_at) values (?,?,?,?,?,?,?,?,?,?,?)", row)
    [run] = env.http.get(f"{P}/tech/versions/1/evals", headers=ADM).json()["runs"]
    assert run["status"] == "error" and "interrupted" in run["error"]
    r = ek.publish(env, "tech")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED"
    # with no model configured a run cannot pass either: it ends, as an error or a failure, and does not hang
    run = ek.evaluated(env, "tech")
    assert run["status"] in ("failed", "error") and all(not c["passed"] for c in run["results"])
