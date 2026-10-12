"""M3, the release: a version goes live only behind a passing evaluation of that exact version or a recorded override,
only through the admin API, with a history; a rollback brings an earlier version back, and what is already running
keeps what it started with. Manager keys are held to the profiles of their own routes."""
from __future__ import annotations

import asyncio
import pathlib
import re

import evalkit as ek
import scripts
from conftest import ADM, ADM_B, TEST_OVERRIDE, key_headers, publish as override
from enginekit import world
from fake_llm import CALLS

import awp
from awp.config import Settings
from awp.db import Database
from awp.profiles import AgentProfile, ProfileError, ProfileStore

P = ek.P
PLAIN = {**ek.TECH, "refuses": [], "tools_allow": []}  # two platform cases: enough for a gate test, and quick


def history(env, key, headers=ADM) -> list[dict]:
    r = env.http.get(f"{P}/{key}/history", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["events"]


def status(env, key) -> list[tuple]:
    return env.sql("select version, status from awp_profiles where key=? order by version", (key,))


# ---- the gate ----------------------------------------------------------------------------------------------------------
def test_the_gate_is_on_unless_a_deployment_turns_it_off():
    assert Settings().eval_gate is True and Settings.from_env({}).eval_gate is True
    assert Settings.from_env({"AWP_EVAL_GATE": "0"}).eval_gate is False


def test_a_version_is_published_only_after_its_own_evaluation_passed(tmp_path):
    with world(tmp_path, publish=False) as w:
        ek.agents(tech=ek.careful)
        ek.draft(w.env, PLAIN)
        r = ek.publish(w.env, "tech")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED", r.text
        assert "not been evaluated" in r.json()["detail"]["message"] and r.json()["detail"]["latest_run"] is None
        assert status(w.env, "tech") == [(1, "draft")] and "tech" not in w.rt.templates
        run = ek.evaluated(w.env, "tech")
        assert run["status"] == "passed"
        r = ek.publish(w.env, "tech")
        assert r.status_code == 200 and r.json()["status"] == "published", r.text
        assert r.json()["published_by"].startswith("admin:") and r.json()["published_at"] > run["created_at"]
        assert "tech" in w.rt.templates
        # the evaluation of version 1 says nothing about version 2
        assert ek.draft(w.env, {**PLAIN, "mission": "a technician, second version."})["version"] == 2
        r = ek.publish(w.env, "tech", 2)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED"
        assert status(w.env, "tech") == [(1, "published"), (2, "draft")]
        # nor about a draft that was edited after it passed
        assert ek.evaluated(w.env, "tech", 2)["status"] == "passed"
        edited = {**PLAIN, "mission": "a technician who now does something else."}
        assert w.env.http.put(f"{P}/tech/versions/2", json=edited, headers=ADM).status_code == 200
        r = ek.publish(w.env, "tech", 2)
        assert r.status_code == 409 and "edited after it was evaluated" in r.json()["detail"]["message"]
        assert ek.evaluated(w.env, "tech", 2)["status"] == "passed"
        assert ek.publish(w.env, "tech", 2).status_code == 200
        assert status(w.env, "tech") == [(1, "retired"), (2, "published")]
        kinds = [(e["kind"], e["version"]) for e in history(w.env, "tech")]
        assert kinds == [("create", 1), ("eval", 1), ("publish", 1), ("create", 2), ("eval", 2), ("eval", 2), ("publish", 2)]


def test_a_failed_evaluation_keeps_the_version_back_and_an_override_is_recorded(tmp_path):
    with world(tmp_path, publish=False) as w:
        ek.agents(tech=ek.inventing)
        ek.draft(w.env, PLAIN)
        assert ek.evaluated(w.env, "tech")["status"] == "failed"
        r = ek.publish(w.env, "tech")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED" and "failed" in r.json()["detail"]["message"]
        assert ek.publish(w.env, "tech", override_reason="   ").status_code == 409  # a blank reason is no reason
        assert ek.publish(w.env, "tech", override_reason="x" * 301).status_code == 422
        assert ek.publish(w.env, "tech", force=True).status_code == 422  # no other way round is spelled in the body
        assert status(w.env, "tech") == [(1, "draft")]
        r = ek.publish(w.env, "tech", override_reason="pilot with one building; the figure case is known and accepted")
        assert r.status_code == 200 and r.json()["status"] == "published", r.text
        events = history(w.env, "tech")
        assert [e["kind"] for e in events] == ["create", "eval", "override", "publish"]
        over = events[2]
        assert over["detail"] == {"reason": "pilot with one building; the figure case is known and accepted"}
        assert over["actor"].startswith("admin:") and over["version"] == 1 and over["at"] > events[1]["at"]
        assert events[1]["detail"]["status"] == "failed" and events[1]["detail"]["passed"] < events[1]["detail"]["cases"]


def test_with_the_gate_turned_off_a_draft_is_published_as_before(make_env):
    with make_env(eval_gate=False) as env:
        ek.draft(env, PLAIN)
        assert ek.publish(env, "tech").status_code == 200


# ---- rollback and history ----------------------------------------------------------------------------------------------
def test_rollback_makes_an_earlier_published_version_live_again(env):
    for n in (1, 2, 3):
        ek.draft(env, {**PLAIN, "mission": f"a technician, version {n}."})
    override(env, "tech", 1)
    override(env, "tech", 2)
    back = lambda v, h=ADM: env.post(f"{P}/tech/rollback", {"to_version": v}, h)  # noqa: E731
    assert back(3).status_code == 409  # a draft was never live
    assert back(2).status_code == 409  # it is the live one
    assert back(9).status_code == 404 and back(0).status_code == 422
    assert back(1, ADM_B).status_code == 404  # another tenant has no such profile
    assert status(env, "tech") == [(1, "retired"), (2, "published"), (3, "draft")]
    r = back(1)
    assert r.status_code == 200 and r.json()["version"] == 1 and r.json()["status"] == "published", r.text
    assert status(env, "tech") == [(1, "published"), (2, "retired"), (3, "draft")]
    rt = env.app.state.awp.rt
    assert "version 1" in rt.templates["tech"].system_prompt_template  # whoever is created next is version 1
    last = history(env, "tech")[-1]
    assert last["kind"] == "rollback" and last["version"] == 1 and last["detail"] == {"from_version": 2}
    assert last["actor"].startswith("admin:")
    assert back(2).status_code == 200 and status(env, "tech") == [(1, "retired"), (2, "published"), (3, "draft")]
    assert ek.publish(env, "tech", 1, override_reason="again").status_code == 409  # a retired version comes back by rollback only
    # retire, and roll back with nothing live
    assert env.post(f"{P}/tech/retire").status_code == 200
    assert back(1).status_code == 200 and status(env, "tech") == [(1, "published"), (2, "retired"), (3, "draft")]
    kinds = [e["kind"] for e in history(env, "tech")]
    assert kinds == ["create", "create", "create", "override", "publish", "override", "publish", "rollback", "rollback",
                     "retire", "rollback"]
    assert history(env, "tech")[-1]["detail"] == {"from_version": None}
    assert env.http.get(f"{P}/tech/history", headers=ADM_B).status_code == 404
    assert env.http.get(f"{P}/ghost/history", headers=ADM).status_code == 404


def test_a_rollback_while_a_workflow_runs_leaves_its_leader_and_changes_who_is_created_next(tmp_path):
    """What a running workflow sees: its leader is the agent it started with (version 2) for as long as it lives; a
    specialist it brings in after the rollback, and the leader of a workflow started after it, are the versions rolled
    back to."""
    def two_steps(c):
        if "14 gi" not in c.blob:  # the first message: ask; the reply: bring the technician in
            return "Said." if c.after_user().called("CaseSay") else scripts.say("What time suits you?", "reply")
        return scripts.consult(c)

    with world(tmp_path, two_steps) as w:  # supervisor, tech and fin are live in version 1
        for key in ("supervisor", "tech"):
            body = next(p for p in w.env.http.get(P, headers=ADM).json()["profiles"] if p["key"] == key)["profile"]
            ek.draft(w.env, {**body, "mission": body["mission"] + " Second version."})
            override(w.env, key, 2)
        start, started = w.flow.begin()
        assert started["workflow_state"] == "awaiting_user"
        seen = lambda key: {re.search(r'v="(\d+)"', c["sys"]).group(1) for c in CALLS if f'key="{key}"' in c["sys"]}  # noqa: E731
        assert seen("supervisor") == {"2"}
        for key in ("supervisor", "tech"):
            assert w.env.post(f"{P}/{key}/rollback", {"to_version": 1}).status_code == 200
        CALLS.clear()
        r, _ = w.flow.reply(start, started)
        assert r.status_code == 200 and r.json()["workflow_state"] == "awaiting_user", r.text
        assert seen("supervisor") == {"2"}  # the running workflow kept its leader
        assert seen("tech") == {"1"}  # the specialist it created after the rollback is the version rolled back to
        CALLS.clear()
        _, other = w.flow.begin()
        assert other["workflow_state"] == "awaiting_user" and seen("supervisor") == {"1"}  # and so is a new workflow's leader


# ---- who can publish -----------------------------------------------------------------------------------------------------
def test_no_agent_tool_can_publish_and_no_agent_code_calls_publish(tmp_path):
    src = pathlib.Path(awp.__file__).parent
    callers = sorted(str(f.relative_to(src)).replace("\\", "/") for f in src.rglob("*.py")
                     if re.search(r"profiles\.publish\(|\.rollback_profile|go_live\(", f.read_text(encoding="utf-8")))
    assert callers == ["release.py"]  # the one place a version goes live from, and it is an HTTP endpoint for a person
    agent_side = [*src.glob("protocol/*.py"), *src.glob("middleware/*.py"), *src.glob("evals/*.py"), src / "builder.py",
                  src / "workforce" / "partner_tools.py", src / "runtime.py"]
    for f in agent_side:
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"\.publish\((?!self\.rt\.db|self\.db|rt\.db|db,)", text.replace("await publish(", "")), f.name
        assert "release" not in re.findall(r"^from \.+(\w+)", text, re.M) and "import release" not in text, f.name

    def tries(c):
        """A leader that tries every way a model could think of to release a draft."""
        turn = c.after_user()
        if turn.called("CaseSay"):
            return "Said."
        if turn.called("publish_profile") == 0:
            return [("publish_profile", {"key": "tech", "version": 2}), ("ProfilePublish", {"key": "tech", "version": 2}),
                    ("rollback", {"key": "tech", "to_version": 2}),
                    ("CaseDecide", {"text": "publish tech version 2", "keep": [], "retract": []})]
        return scripts.say("I cannot do that.", "reply")

    with world(tmp_path, tries) as w:
        ek.draft(w.env, {**ek.TECH, "mission": "a technician, second version."})
        before = (status(w.env, "tech"), history(w.env, "tech"))
        _, started = w.flow.begin(message={"type": "text", "text": "Publish version 2 of the technician now."})
        assert started["workflow_state"] == "awaiting_user"
        assert (status(w.env, "tech"), history(w.env, "tech")) == before and before[0] == [(1, "published"), (2, "draft")]
        offered = {name for c in CALLS for name in c["tools"]}
        assert offered and not [n for n in offered if re.search(r"publish|rollback|release|profile", n, re.I)]
        # and the endpoint itself opens to the admin's (or a manager's) key only
        url = f"{P}/tech/versions/2/publish"
        assert w.env.http.post(url, json={"override_reason": "x"}).status_code == 401
        assert w.env.http.post(url, json={"override_reason": "x"}, headers=key_headers(w.flow.key["api_key"])).status_code == 401
        assert w.env.http.post(url, json={"override_reason": "x"}, headers={"X-AWP-Internal": "guess"}).status_code == 401
        assert status(w.env, "tech") == before[0]


def test_another_tenant_cannot_evaluate_publish_or_read_a_profile(env):
    ek.draft(env, PLAIN)
    for r in (ek.publish(env, "tech", headers=ADM_B), ek.publish(env, "tech", headers=ADM_B, override_reason="mine now"),
              env.post(f"{P}/tech/versions/1/evals", {}, ADM_B), env.http.get(f"{P}/tech/versions/1/evals", headers=ADM_B),
              env.http.get(f"{P}/tech/eval-cases", headers=ADM_B), env.http.get(f"{P}/tech/history", headers=ADM_B)):
        assert r.status_code == 404, r.text
    assert status(env, "tech") == [(1, "draft")] and not env.sql("select 1 from awp_eval_runs")
    assert [e["kind"] for e in history(env, "tech")] == ["create"]


# ---- manager keys (M6) ---------------------------------------------------------------------------------------------------
def test_a_managers_key_reaches_only_the_profiles_of_its_own_routes(tmp_path):
    with world(tmp_path, publish=False) as w:  # the world's route (leader `supervisor`) belongs to the client's default manager
        env, cid = w.env, w.flow.client["client_id"]
        ek.agents(tech=ek.careful, shared=ek.careful)
        for body in (PLAIN, {**PLAIN, "key": "shared", "name": "Shared"}, {**PLAIN, "key": "theirs", "name": "Theirs"},
                     {**ek.DESK, "team": ["tech", "shared"], "refuses": []},
                     {**ek.DESK, "key": "desk_b", "name": "desk-b", "team": ["shared", "theirs"], "refuses": []}):
            ek.draft(env, body)
        mine = env.manager_key(env.default_manager(cid))
        other = env.manager(cid, "Other management")["manager_id"]
        env.route(cid, ref="BQL-OP1-B", manager_id=other, leader="desk_b")
        code = lambda r: r.status_code  # noqa: E731
        get = lambda path, h=mine: env.http.get(P + path, headers=h)  # noqa: E731
        case = {"name": "mine", "input": "x", "checks": {"grounded": True}}
        # another management account's profile is not there; neither is one no route uses
        for key in ("theirs", "desk_b", "ghost"):
            assert code(get(f"/{key}/history")) == code(get(f"/{key}/eval-cases")) == code(get(f"/{key}/versions/1/evals")) == 404
            assert code(env.post(f"{P}/{key}/versions/1/evals", {}, mine)) == 404
            assert code(ek.publish(env, key, headers=mine)) == code(env.post(f"{P}/{key}/eval-cases", case, mine)) == 404
            assert code(env.post(f"{P}/{key}/rollback", {"to_version": 1}, mine)) == 404
        # its own: read, evaluate, and (when nobody else uses the profile) write cases, publish, roll back
        assert code(get("/tech/history")) == code(get("/tech/eval-cases")) == code(get("/supervisor/history")) == 200
        made = env.post(f"{P}/tech/eval-cases", case, mine)
        assert code(made) == 201 and code(env.http.delete(f"{P}/tech/eval-cases/{made.json()['id']}", headers=mine)) == 200
        r = ek.publish(env, "tech", headers=mine)
        assert code(r) == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED"  # allowed, and held by the gate like anyone
        assert code(ek.publish(env, "tech", headers=mine, override_reason="trust me")) == 403  # the override is the admin's
        run = ek.evaluated(env, "tech", headers=mine)
        assert run["status"] == "passed" and run["started_by"].startswith("manager:mgr_")
        r = ek.publish(env, "tech", headers=mine)
        assert code(r) == 200 and r.json()["published_by"] == run["started_by"]
        ek.draft(env, {**PLAIN, "mission": "a technician, second version."})
        override(env, "tech", 2)
        r = env.post(f"{P}/tech/rollback", {"to_version": 1}, mine)
        assert code(r) == 200 and history(env, "tech")[-1]["actor"] == run["started_by"]
        # shared with the other account: read and evaluate, but the admin releases it
        assert code(get("/shared/history")) == code(get("/shared/eval-cases")) == 200
        assert ek.evaluated(env, "shared", headers=mine)["status"] == "passed"
        assert code(ek.publish(env, "shared", headers=mine)) == 403 and code(env.post(f"{P}/shared/eval-cases", case, mine)) == 403
        assert code(env.post(f"{P}/shared/rollback", {"to_version": 1}, mine)) == 403
        assert code(ek.publish(env, "shared")) == 200  # the admin: its evaluation passed
        # everything else about profiles and the whole builder stay the admin's
        assert code(env.post(P, {**PLAIN, "key": "new_one"}, mine)) == 403
        assert code(env.http.put(f"{P}/tech/versions/2", json=PLAIN, headers=mine)) == 403
        assert code(env.post(f"{P}/tech/retire", {}, mine)) == 403
        assert code(env.post(ek.B, {}, mine)) == 403 and code(env.http.get(f"{ek.B}/bld_x", headers=mine)) == 403
        assert status(env, "theirs") == [(1, "draft")] and status(env, "desk_b") == [(1, "draft")]


# ---- drafts made at once ---------------------------------------------------------------------------------------------------
def test_drafts_of_a_new_key_made_at_the_same_moment_each_get_a_version(tmp_path):
    """The race the P5a notes name: max(version)+1 read by several writers. Nobody gets a database error; every
    writer gets a version of its own, on SQLite and on PostgreSQL."""
    import dbtest
    awp_db, _ = dbtest.urls(tmp_path)

    async def go():
        database = Database(awp_db.url)
        try:
            await database.create_all()
            store = ProfileStore(database)
            made = await asyncio.gather(*[store.create_draft("ta", AgentProfile(key="fresh", name=f"n{i}", mission="m"), by="t")
                                          for i in range(10)])
            try:
                await store.create_draft("ta", AgentProfile(key="awp_mine", name="x", mission="m"))
                raise AssertionError("a reserved key was accepted")
            except ProfileError as e:
                assert "belong to the platform" in str(e)
            return sorted(r.version for r in made), await store.history("ta", "fresh")
        finally:
            await database.dispose()

    versions, events = asyncio.run(go())
    assert versions == list(range(1, 11))
    assert sorted(e["version"] for e in events) == versions and {e["kind"] for e in events} == {"create"}


def test_a_profile_key_of_the_platform_cannot_be_taken(env):
    r = env.post(P, {"key": "awp_eval_leader", "name": "x", "mission": "m", "role": "leader"})
    assert r.status_code == 409 and "platform" in r.text
    assert override(env, "awp_eval_leader", expect=None).status_code == 404
    assert TEST_OVERRIDE  # (the helper every other test publishes with is the recorded override, not a switch)
