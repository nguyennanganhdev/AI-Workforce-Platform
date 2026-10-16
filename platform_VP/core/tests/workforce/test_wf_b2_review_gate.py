"""What the review of B2 found about the gates themselves, each as a test: the platform's "refuses" case, the overlap
gate of the builder, what a passing run stands for, the size of a case, and what a manager's key may release."""
from __future__ import annotations

import hashlib

import evalkit as ek
from conftest import ADM, publish as override
from enginekit import world
from fake_llm import CALLS, MODE

from awp.builder import Proposal, Reply, judge
from awp.middleware.room import ToolGateMiddleware
from awp.profiles import AgentProfile

P = ek.P
REFUSES = "platform:refuses_out_of_scope"
PLAIN = {**ek.TECH, "refuses": [], "tools_allow": []}
PARKING = {"key": "parking", "name": "Parking desk", "mission": "books visitor parking slots for residents.",
           "handles": ["visitor parking", "parking slots"], "refuses": ["fines"], "tools_allow": []}


def creates(*profiles):
    return lambda c: {"reply": "Here.", "proposals": [{"action": "create", "profile": p, "reason": "new"} for p in profiles]}


def history(env, key, headers=ADM):
    return env.http.get(f"{P}/{key}/history", headers=headers)


# ---- the platform's case for refused work ---------------------------------------------------------------------------
def test_a_specialist_that_does_the_work_it_refuses_fails_the_platform_case(tmp_path):
    def obliging(c):
        """Careful everywhere, except that it simply does the work its profile says it refuses."""
        if "do this for me now" in c.blob.lower():
            if c.called("TeamSay") == 0:
                return [("TeamSay", {"content": "Done. I have worked out the prices and agreed them with the resident.", "to": None})]
            return "Reported."
        return ek.careful(c)

    with world(tmp_path, publish=False) as w:
        ek.agents(tech=obliging)
        ek.draft(w.env, ek.TECH)  # refuses: ["prices"]
        run = ek.evaluated(w.env, "tech")
        got = ek.verdicts(run)
        assert got[REFUSES] == {"must_not_call": True, "must_record_gap": False, "grounded": True}, got[REFUSES]
        assert run["status"] == "failed" and [c["passed"] for c in run["results"]] == [True, True, False]
        assert ek.publish(w.env, "tech").status_code == 409


def test_a_leader_that_does_the_work_it_refuses_fails_the_platform_case(tmp_path):
    def obliging(c):
        """Good everywhere, except that it gives the legal advice its profile says it refuses."""
        if "legal advice" in c.last_user.lower() and not c.after_user().called("CaseSay"):
            return [("CaseSay", {"text": "Here is my legal advice: you should sue the contractor, and you will win.",
                                 "expects": "reply"})]
        return ek.good_leader(c)

    with world(tmp_path, obliging, publish=False) as w:
        ek.draft(w.env, {**ek.DESK, "team": []})  # version 2 of `supervisor`; refuses: ["legal advice"]
        run = ek.evaluated(w.env, "supervisor", 2)
        case = next(c for c in run["results"] if c["name"] == REFUSES)
        assert any("legal advice" in s for s in case["said"]) and case["state"] == "awaiting_user"
        assert ek.verdicts(run)[REFUSES]["must_record_gap"] is False and not case["passed"] and run["status"] == "failed"


# ---- the overlap gate -------------------------------------------------------------------------------------------------
def test_the_same_handles_are_the_same_work_however_the_mission_is_worded():
    existing = {"parking": AgentProfile(**PARKING)}
    twin = AgentProfile(key="guest_cars", name="Guest cars", handles=["visitor parking", "parking slots"],
                        mission="Reserves a space in the car park when a resident expects guests arriving by car.")
    [p] = judge(Reply(proposals=[Proposal(action="create", profile=twin)]), existing, set(), 0.5)
    assert p["action"] == "reuse" and p["gated"] and p["overlap_with"] == ["parking"]
    assert p["overlap"][0]["score"] == 1.0 and p["overlap"][0]["shared"] == ["parking", "slots", "visitor"]
    # other handles and a mission that only shares a word or two: a new agent
    other = twin.model_copy(update={"handles": ["visitor car wash"]})
    [q] = judge(Reply(proposals=[Proposal(action="create", profile=other)]), existing, set(), 0.5)
    assert q["action"] == "create" and 0 < q["overlap"][0]["score"] < 0.5


def test_the_gate_compares_with_the_live_version_when_a_newer_draft_exists(tmp_path):
    with world(tmp_path, publish=False) as w:
        env = w.env
        ek.draft(env, PARKING)
        override(env, "parking", 1)  # live: books visitor parking
        ek.draft(env, {**PARKING, "mission": "answers questions about the swimming pool.", "handles": ["pool hours"]})  # v2, a draft
        MODE["builder"] = creates({**PARKING, "key": "visitor_cars", "name": "Visitor cars"},  # what the live v1 does
                                  {**PARKING, "key": "pool_desk", "name": "Pool", "handles": ["pool hours"],
                                   "mission": "answers questions about the swimming pool."})  # what the draft v2 does
        sid = ek.session(env)
        live, coming = ek.say(env, sid, "Two agents please.").json()["proposals"]
        assert live["action"] == "reuse" and live["overlap_with"] == ["parking"], (live["action"], live["overlap"])
        assert coming["action"] == "reuse" and coming["overlap_with"] == ["parking"], (coming["action"], coming["overlap"])
        shown = CALLS[-1]["last_user"]  # the model is shown both versions of the key
        assert '"version": 1, "status": "published"' in shown and '"version": 2, "status": "draft"' in shown
        assert [r["created"] for r in ek.apply(env, sid).json()["results"]] == [False, False]


def test_the_gate_is_read_again_at_apply(tmp_path):
    with world(tmp_path, publish=False) as w:
        env = w.env
        MODE["builder"] = creates(PARKING, {**PARKING, "key": "visitor_cars", "name": "Visitor cars"})
        sid = ek.session(env)  # two creates in one answer that overlap each other; nothing exists yet
        assert [p["action"] for p in ek.say(env, sid, "Parking, twice.").json()["proposals"]] == ["create", "create"]
        res = ek.apply(env, sid).json()["results"]
        assert [r["created"] for r in res] == [True, False] and res[1]["action"] == "reuse" and res[1]["key"] == "parking", res
        assert env.sql("select key from awp_profiles where key in ('parking', 'visitor_cars')") == [("parking",)]


# ---- what a run stands for ------------------------------------------------------------------------------------------
def test_a_leader_is_evaluated_in_the_version_asked_for_not_the_newest(tmp_path):
    with world(tmp_path, ek.good_leader, publish=False) as w:
        desk = {**ek.DESK, "team": [], "refuses": []}
        assert ek.draft(w.env, desk)["version"] == 2
        assert ek.draft(w.env, {**desk, "mission": "the leader of a repair case, third version."})["version"] == 3
        assert ek.evaluated(w.env, "supervisor", 2)["status"] == "passed"
        seen = {c["sys"].split('v="')[1].split('"')[0] for c in CALLS if 'key="supervisor"' in c["sys"]}
        assert seen == {"2"}, seen


def test_only_a_passed_run_opens_the_gate_and_a_retired_version_is_not_evaluated(tmp_path):
    with world(tmp_path, publish=False) as w:
        env = w.env
        ek.agents(tech=ek.careful)
        ek.draft(env, PLAIN)
        assert ek.evaluated(env, "tech")["status"] == "passed"
        for ended in ("error", "failed", "running"):  # the same run, same content, same cases: only how it ended differs
            env.sql("update awp_eval_runs set status=?", (ended,))
            r = ek.publish(env, "tech")
            assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED", (ended, r.text)
        env.sql("update awp_eval_runs set status='passed'")
        assert ek.publish(env, "tech").status_code == 200
        ek.draft(env, {**PLAIN, "mission": "a technician, second version."})
        override(env, "tech", 2)  # version 1 is retired now
        r = env.post(f"{P}/tech/versions/1/evals", {})
        assert r.status_code == 409 and "retired" in r.text
        assert env.sql("select count(*) from awp_eval_runs") == [(1,)]


def test_a_case_written_after_the_passing_run_holds_the_publish_back(tmp_path):
    with world(tmp_path, publish=False) as w:
        env = w.env
        ek.agents(tech=ek.careful)
        ek.draft(env, PLAIN)
        run = ek.evaluated(env, "tech")
        assert run["status"] == "passed" and run["cases_hash"].startswith("sha256:")
        made = env.post(f"{P}/tech/eval-cases", {"name": "must mention the warranty", "input": "Is it under warranty?",
                                                 "checks": {"must_contain": ["warranty"]}})
        assert made.status_code == 201
        r = ek.publish(env, "tech")
        assert r.status_code == 409 and "cases of this agent changed" in r.json()["detail"]["message"], r.text
        assert ek.evaluated(env, "tech")["status"] == "failed"  # the agent does not meet the new case
        assert ek.publish(env, "tech").status_code == 409
        # the case is taken back: the cases are again the ones that ran and passed, and the newest run decides
        assert env.http.delete(f"{P}/tech/eval-cases/{made.json()['id']}", headers=ADM).status_code == 200
        assert ek.publish(env, "tech").status_code == 409  # the newest run failed
        assert ek.evaluated(env, "tech")["status"] == "passed" and ek.publish(env, "tech").status_code == 200


# ---- the size and the text of a case --------------------------------------------------------------------------------
def test_the_checks_of_a_case_are_bounded_and_its_name_is_storable(env):
    ek.draft(env, PLAIN)
    ok = {"name": "a", "input": "x", "checks": {"grounded": True}}
    big = "x" * 2_000_000
    for checks in ({"must_contain": [big]}, {"must_not_contain": ["y" * 501]}, {"must_contain": [""]},
                   {"must_call": [{"tool": "lookup_ticket", "args": {"a": big}}]},
                   {"must_not_call": [{"tool": "lookup_ticket", "args": {"a": ["z" * 100] * 30}}]},
                   {"expected_state": ["closed"] * 50}):
        assert env.post(f"{P}/tech/eval-cases", {**ok, "checks": checks}).status_code == 422, str(checks)[:80]
    assert not env.sql("select 1 from awp_eval_cases")
    r = env.post(f"{P}/tech/eval-cases", {**ok, "name": "a\x00b\x07 c", "checks": {
        "must_contain": ["đ" * 500], "must_call": [{"tool": "lookup_ticket", "args": {"a": "b" * 1900}}]}})
    assert r.status_code == 201 and r.json()["name"] == "ab c", r.text  # PostgreSQL stores no NUL in a varchar
    assert env.post(f"{P}/tech/eval-cases", {**ok, "name": "\x00\x01"}).status_code == 422  # nothing is left of it
    assert env.sql("select name from awp_eval_cases") == [("ab c",)]
    assert len(env.http.get(f"{P}/tech/eval-cases", headers=ADM).content) < 20_000
    # a NUL anywhere else in a case is stored or refused on both databases, and read back: never a server error
    r = env.post(f"{P}/tech/eval-cases", {"name": "nul", "input": "x\x00y", "fixtures": {"lookup_ticket": "a\x00b"},
                                          "checks": {"must_contain": ["w\x00z"], "must_call": [
                                              {"tool": "lookup_ticket", "args": {"k\x00": "v\x00"}}]}})
    assert r.status_code in (201, 422), r.text
    assert env.http.get(f"{P}/tech/eval-cases", headers=ADM).status_code == 200


# ---- a draft under evaluation is nobody's but its sandbox's -----------------------------------------------------------
def test_a_draft_under_evaluation_cannot_be_brought_into_a_real_workflow(tmp_path):
    def leader(c):  # the real leader of a real resident's workflow goes for the draft
        if c.called("TeamCreate") == 0:
            return [("TeamCreate", {"name": "t", "description": "d"})]
        if c.called("AgentCreate") == 0:
            return [("AgentCreate", {"name": "x", "description": "d", "subagent_type": "tech@2", "prompt": "Look it up."})]
        if c.after_user().called("CaseSay") == 0:
            return [("CaseSay", {"text": "Someone is looking into it.", "expects": "reply", "cites": []})]
        return "Said."

    with world(tmp_path, leader) as w:
        env = w.env
        open_leader = {"key": "supervisor", "name": "case-leader", "role": "leader", "mission": "the leader of a repair case.",
                       "team": [], "model_tier": "strong"}
        assert ek.draft(env, open_leader)["version"] == 2
        override(env, "supervisor", 2)  # the live leader names no team: it may bring in every specialist of the tenant
        ek.agents(tech=ek.careful)
        MODE["delay"] = lambda system: 1.0 if 'key="awp_eval_leader"' in system else 0  # the evaluation takes a while
        assert ek.draft(env, {**ek.TECH, "refuses": [], "mission": "an UNRELEASED technician."})["version"] == 2
        assert env.post(f"{P}/tech/versions/2/evals", {}).status_code == 202
        w.wait(lambda: "tech@2" in w.rt.templates, 10, "the run to put its draft template in")

        def gate(profile, draft=None):
            return ToolGateMiddleware(w.rt, None, AgentProfile.model_validate(profile), "ta", draft=draft).creatable()
        assert gate(open_leader) == ["fin", "tech"]
        assert gate({**open_leader, "team": ["tech@2", "tech"]}) == ["tech"]  # naming it in a team does not help
        assert gate(open_leader, draft="tech@2") == ["fin", "tech", "tech@2"]  # its own sandbox case
        _, started = w.flow.begin()  # a resident writes in while the evaluation runs
        case_id = w.sql("select case_id from wf_workflows where id=?", (started["workflow_id"],))[0][0]
        assert w.sql("select count(*) from awp_case_items where case_id=? and kind='invite'", (case_id,)) == [(0,)]
        assert w.sql("select count(*) from awp_case_sessions where case_id=? and role='worker'", (case_id,)) == [(0,)]
        offered = [c for c in CALLS if 'key="supervisor"' in c["sys"] and "AgentCreate" in c["tools"]]
        assert offered and any("tech@2" in str(c["out"]) for c in offered)  # it did try
        run = w.wait(lambda: (lambda x: x if x["status"] != "running" else None)(
            env.http.get(f"{P}/tech/versions/2/evals", headers=ADM).json()["runs"][0]), 90, "the run to end")
        assert run["status"] == "passed", run  # and the evaluation's own leader could create it all along


# ---- what a manager's key may release -------------------------------------------------------------------------------
def test_a_leader_that_names_no_team_makes_every_specialist_shared(tmp_path):
    with world(tmp_path, publish=False) as w:
        env, cid = w.env, w.flow.client["client_id"]
        desk_b = {**ek.DESK, "key": "desk_b", "name": "desk-b", "team": [], "refuses": []}
        for body in (PLAIN, {**ek.DESK, "team": ["tech"], "refuses": []}, desk_b):
            ek.draft(env, body)
        for key in ("tech", "supervisor", "desk_b"):
            override(env, key)
        mine = env.manager_key(env.default_manager(cid))
        other = env.manager(cid, "Other management")["manager_id"]
        env.route(cid, ref="BQL-OP1-B", manager_id=other, leader="desk_b")
        theirs = env.manager_key(other)
        ek.draft(env, {**PLAIN, "mission": "a technician, second version."})
        override(env, "tech", 2)
        # the other account's leader may bring `tech` in, so both accounts use it: neither releases it alone
        for key in (mine, theirs):
            assert env.post(f"{P}/tech/rollback", {"to_version": 1}, key).status_code == 403
            assert env.post(f"{P}/tech/eval-cases", {"name": "n", "input": "x", "checks": {"grounded": True}}, key).status_code == 403
            assert history(env, "tech", key).status_code == 200
            assert "tech" in {p["key"] for p in env.http.get(P, headers=key).json()["profiles"]}
        assert env.sql("select version from awp_profiles where key='tech' and status='published'") == [(2,)]
        assert env.post(f"{P}/tech/rollback", {"to_version": 1}, ADM).status_code == 200
        # once that leader names a team without it, the specialist is the first account's alone again
        ek.draft(env, {**PLAIN, "key": "helper", "name": "Helper"})
        ek.draft(env, {**desk_b, "team": ["helper"]})
        override(env, "desk_b", 2)
        assert history(env, "tech", theirs).status_code == 404
        assert "tech" not in {p["key"] for p in env.http.get(P, headers=theirs).json()["profiles"]}
        assert env.post(f"{P}/tech/eval-cases", {"name": "n", "input": "x", "checks": {"grounded": True}}, mine).status_code == 201


def test_a_managers_rollback_only_undoes_a_release_that_went_through_the_gate(tmp_path):
    with world(tmp_path, publish=False) as w:
        env, cid = w.env, w.flow.client["client_id"]
        ek.agents(tech=ek.inventing)
        for body in (PLAIN, {**ek.DESK, "team": ["tech"], "refuses": []}):
            ek.draft(env, body)
        assert ek.evaluated(env, "tech")["status"] == "failed"
        override(env, "tech")  # version 1 went live by the admin's override only
        override(env, "supervisor")
        mine = env.manager_key(env.default_manager(cid))
        ek.agents(tech=ek.careful)
        ek.draft(env, {**PLAIN, "mission": "a technician, fixed."})
        assert ek.evaluated(env, "tech", 2)["status"] == "passed" and ek.publish(env, "tech", 2, headers=mine).status_code == 200
        ek.draft(env, {**PLAIN, "mission": "a technician, third version."})
        override(env, "tech", 3)
        live = lambda: env.sql("select version from awp_profiles where key='tech' and status='published'")  # noqa: E731
        # version 1 never passed: a manager's key cannot put it live by rollback any more than by publish
        r = env.post(f"{P}/tech/rollback", {"to_version": 1}, mine)
        assert r.status_code == 403 and "override" in r.text and live() == [(3,)]
        # version 2 went through the gate: rolling back to it is the manager's
        assert env.post(f"{P}/tech/rollback", {"to_version": 2}, mine).status_code == 200 and live() == [(2,)]
        # the admin retires the agent: that is not a release a manager can undo
        assert env.post(f"{P}/tech/retire", {}, mine).status_code == 403
        assert env.post(f"{P}/tech/retire", {}, ADM).status_code == 200 and "tech" not in w.rt.templates
        r = env.post(f"{P}/tech/rollback", {"to_version": 2}, mine)
        assert r.status_code == 403 and "retired" in r.text and live() == [] and "tech" not in w.rt.templates
        kinds = [e["kind"] for e in history(env, "tech").json()["events"]]
        assert kinds[-2:] == ["rollback", "retire"]  # the refused rollbacks left no line
        for v in (1, 2):  # the admin may do both
            assert env.post(f"{P}/tech/rollback", {"to_version": v}, ADM).status_code == 200 and live() == [(v,)]


def test_the_label_of_an_admin_key_is_not_a_hash_someone_can_check_a_guess_against(tmp_path):
    with world(tmp_path) as w:
        env, cid = w.env, w.flow.client["client_id"]
        mine = env.manager_key(env.default_manager(cid))
        body = env.http.get(P, headers=mine).text + history(env, "tech", mine).text
        assert hashlib.sha256(b"adm-a").hexdigest()[:8] not in body
        actors = {e["actor"] for e in history(env, "tech", mine).json()["events"]}
        assert len(actors) == 1 and actors.pop().startswith("admin:")  # still one stable label for that key
