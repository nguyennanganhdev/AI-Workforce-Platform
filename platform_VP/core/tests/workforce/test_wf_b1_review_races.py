"""What the review of B1 found about things done at the same moment, each as a test: two people changing one tool, a
person and a discovery, an enable still waiting for the partner's list while the server is switched off or removed,
two routes made at once for one ref, and two drafts or two publications of one profile key. Threads against one app;
where a gap is too short to hit by chance it is widened at the exact place (a slow `tools/list`, a held read).
Run on PostgreSQL too (AWP_TEST_PG_URL): two of these races cannot show on SQLite, which has one writer."""
from __future__ import annotations

import asyncio
import threading
import time

from conftest import ADM, TEST_OVERRIDE
from test_wf_b1_store import ALL, W, act, add_server, patch, server_of, shop, store, store_of  # noqa: F401

from awp.profiles import AgentProfile
from awp.workforce import admin_tools
from awp.workforce.partner_mcp import PartnerMCP

P = "/platform/v1/profiles"
OVERRIDE = {"override_reason": TEST_OVERRIDE}


def together(*fns):
    """Run the callables at the same moment, each in its thread: their results, or the exception each raised."""
    gate, out = threading.Barrier(len(fns)), [None] * len(fns)

    def run(i, fn):
        gate.wait()
        try:
            out[i] = fn()
        except BaseException as e:  # noqa: BLE001
            out[i] = e

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(fns)]
    [x.start() for x in threads]
    [x.join(120) for x in threads]
    return out


def code(r):
    return r.status_code if hasattr(r, "status_code") else repr(r)[:200]


def later(fn) -> tuple[threading.Thread, dict]:
    got: dict = {}
    th = threading.Thread(target=lambda: got.setdefault("r", fn()))
    th.start()
    return th, got


def hold_patch(monkeypatch, seconds: float) -> None:
    """A PATCH that has read its tool row and has not written yet, for `seconds`."""
    real = admin_tools.first

    async def slow(conn, query, what):
        row = await real(conn, query, what)
        if what == "tool":
            await asyncio.sleep(seconds)
        return row

    monkeypatch.setattr(admin_tools, "first", slow)


def slow_list(monkeypatch, seconds: float) -> None:
    """A partner that takes its time to answer tools/list."""
    real = PartnerMCP.list_tools

    async def slow(self, refresh: bool = False, strict: bool = False):
        await asyncio.sleep(seconds)
        return await real(self, refresh, strict)

    monkeypatch.setattr(PartnerMCP, "list_tools", slow)


# ---- one tool, two writers ---------------------------------------------------------------------------------------------
def test_two_patches_of_different_fields_at_once_both_land(store):  # noqa: F811
    env, rid, _ = store
    act(env, rid, "enable")
    lost = []
    for i in range(15):
        assert patch(env, rid, "lookup_ticket", status="active").status_code == 200
        a, b = together(lambda: patch(env, rid, "lookup_ticket", status="proposed"),
                        lambda: patch(env, rid, "lookup_ticket", description_override=f"d{i}"))
        assert (code(a), code(b)) == (200, 200), (code(a), code(b))
        row = store_of(env, rid)["lookup_ticket"]
        if (row["status"], row["description_override"]) != ("proposed", f"d{i}"):
            lost.append((i, row["status"], row["description_override"]))
    assert not lost, f"{len(lost)} of 15 rounds lost one of the two changes: {lost[:5]}"


def test_a_patch_in_flight_does_not_undo_the_demotion_a_refresh_makes(store, monkeypatch):  # noqa: F811
    env, rid, shop_ = store
    act(env, rid, "enable")

    def lookup_ticket(ticket_id: str) -> str:
        """Now it changes things (no read-only hint any more)."""
        return ticket_id

    shop_.drop("lookup_ticket")
    shop_.add(lookup_ticket, "lookup_ticket")
    hold_patch(monkeypatch, 1.2)
    th, got = later(lambda: patch(env, rid, "lookup_ticket", description_override="Find a ticket"))
    time.sleep(0.4)  # the PATCH has read the row, an active look-up
    r = act(env, rid, "refresh")
    assert r.status_code == 200 and "lookup_ticket" in r.json()["changed"]
    th.join(30)
    assert got["r"].status_code == 200
    end = store_of(env, rid)["lookup_ticket"]
    assert (end["kind"], end["read_only"], end["requires_consent"], end["status"], end["description_override"]) == (
        "action", False, True, "proposed", "Find a ticket"), end  # both: the demotion, and the description that was asked


def test_a_patch_in_flight_does_not_hand_back_a_tool_another_patch_took_away(store, monkeypatch):  # noqa: F811
    env, rid, _ = store
    act(env, rid, "enable")
    assert patch(env, rid, "book_hotel", status="active", tracking="none").status_code == 200
    hold_patch(monkeypatch, 1.2)
    th, got = later(lambda: patch(env, rid, "book_hotel", call_timeout=5.0))
    time.sleep(0.4)
    monkeypatch.undo()  # the second PATCH is not held
    assert patch(env, rid, "book_hotel", status="proposed").status_code == 200  # an operator takes it from the agents
    th.join(30)
    assert got["r"].status_code == 200
    end = store_of(env, rid)["book_hotel"]
    assert (end["status"], end["call_timeout"]) == ("proposed", 5.0)


# ---- a discovery waiting for the partner, and a person who does not wait ------------------------------------------------
def test_a_disable_is_not_undone_by_an_enable_that_was_still_reading_the_list(store, monkeypatch):  # noqa: F811
    env, rid, _ = store
    slow_list(monkeypatch, 1.2)
    th, got = later(lambda: act(env, rid, "enable"))
    time.sleep(0.4)
    r = act(env, rid, "disable")
    assert r.status_code == 200 and r.json()["server"]["enabled"] is False
    th.join(30)
    assert got["r"].status_code == 409 and "changed meanwhile" in got["r"].text
    assert server_of(env, rid)["enabled"] is False and store_of(env, rid) == {}  # nothing of the stale discovery was written
    monkeypatch.undo()
    assert act(env, rid, "enable").status_code == 200 and server_of(env, rid)["enabled"] is True  # asked again, it works


def test_an_enable_racing_the_removal_of_its_server_leaves_no_tool_without_a_server(store, monkeypatch):  # noqa: F811
    env, rid, _ = store
    slow_list(monkeypatch, 1.2)
    th, got = later(lambda: act(env, rid, "enable"))
    time.sleep(0.4)
    assert env.http.put(f"{W}/routes/{rid}/mcp", headers=ADM, json={"servers": []}).status_code == 200  # no tool uses it yet
    th.join(30)
    assert got["r"].status_code == 409
    assert env.sql("select count(*) from wf_mcp_servers where route_id = ?", (rid,)) == [(0,)]
    assert env.sql("select count(*) from wf_tools where route_id = ?", (rid,)) == [(0,)]


def test_an_enable_of_a_server_whose_address_changed_meanwhile_writes_nothing(store, monkeypatch, shop):  # noqa: F811
    env, rid, _ = store
    slow_list(monkeypatch, 1.2)
    th, got = later(lambda: act(env, rid, "enable"))
    time.sleep(0.4)
    moved = {"servers": [{"name": "p", "url": shop.url + "?v=2"}]}  # the same name, another address and no key
    assert env.http.put(f"{W}/routes/{rid}/mcp", headers=ADM, json=moved).status_code == 200
    th.join(30)
    assert got["r"].status_code == 409 and store_of(env, rid) == {}  # the old address's tools are not the new one's
    assert server_of(env, rid)["enabled"] is False and server_of(env, rid)["last_discovered_at"] is None


def test_two_enables_at_once_end_in_one_whole_store(store):  # noqa: F811
    env, rid, _ = store
    a, b = together(lambda: act(env, rid, "enable"), lambda: act(env, rid, "enable"))
    assert {code(a), code(b)} <= {200, 409} and 200 in (code(a), code(b)), (code(a), code(b))
    assert server_of(env, rid)["enabled"] is True and set(store_of(env, rid)) == ALL


# ---- one ref, one manager ------------------------------------------------------------------------------------------------
def owners(env, ref: str) -> set:
    return {m for (m,) in env.sql("select manager_id from wf_routes where external_management_ref = ? and status != 'replaced'", (ref,))}


def test_a_replacement_cannot_take_a_ref_that_belongs_to_another_manager(env):
    c = env.client()["client_id"]
    k = env.key(c)
    a, b = env.manager(c, "North")["manager_id"], env.manager(c, "South")["manager_id"]
    mine = env.active_route(c, k["api_key"], ref="AREA-1", manager_id=a)
    theirs = env.route(c, "AREA-2", manager_id=b)  # South's area, not confirmed yet: the active-ref index does not guard it
    r = env.post(f"{W}/routes/{mine['route_id']}/replace", {"external_management_ref": "AREA-2"})
    assert r.status_code == 409 and "another manager" in r.text
    assert owners(env, "AREA-2") == {b} and owners(env, "AREA-1") == {a}
    assert env.sql("select status from wf_routes where id = ?", (mine["route_id"],)) == [("active",)]  # nothing was replaced
    assert env.confirm(k["api_key"], theirs).status_code == 200  # and South can still confirm its own
    # its own ref again, or one nobody has, is fine
    new = env.post(f"{W}/routes/{mine['route_id']}/replace", {"external_management_ref": "AREA-3"})
    assert new.status_code == 201 and new.json()["route"]["manager_id"] == a and owners(env, "AREA-3") == {a}


def test_two_managers_never_both_get_a_ref_when_their_routes_are_made_at_once(env):
    c = env.client()["client_id"]
    a, b = env.manager(c, "North")["manager_id"], env.manager(c, "South")["manager_id"]
    env.leader()
    both = []
    for i in range(12):
        ref = f"AREA-{i}"
        make = lambda m: lambda: env.post(f"{W}/clients/{c}/routes", {  # noqa: E731
            "external_management_ref": ref, "leader_profile": "supervisor", "config": {}, "manager_id": m})
        x, y = together(make(a), make(b))
        assert sorted((code(x), code(y))) == [201, 409], (code(x), code(y))
        if len(owners(env, ref)) != 1:
            both.append(ref)
    assert not both, f"{len(both)} of 12 refs ended with routes of two managers"


# ---- profiles ----------------------------------------------------------------------------------------------------------------
def helper(key="helper", n=0) -> dict:
    return {"key": key, "name": "Helper", "role": "specialist", "mission": f"helps with thing {n}."}


def test_drafts_of_one_key_made_at_once_each_get_a_version(env):
    out = together(*[(lambda i=i: env.post(P, helper(n=i))) for i in range(8)])
    assert [code(x) for x in out] == [201] * 8, [code(x) for x in out]  # never a database error for the caller
    assert sorted(v for (v,) in env.sql("select version from awp_profiles where key = ?", ("helper",))) == list(range(1, 9))
    assert sorted(x.json()["version"] for x in out) == list(range(1, 9))


def test_two_versions_published_at_once_leave_one_published(env):
    bad = []
    for i in range(12):
        key = f"helper{i}"
        for n in (1, 2):
            assert env.post(P, helper(key, n)).status_code == 201
        pub = lambda v: lambda: env.post(f"{P}/{key}/versions/{v}/publish", OVERRIDE)  # noqa: E731
        a, b = together(pub(1), pub(2))
        published = env.sql("select count(*) from awp_profiles where key = ? and status = 'published'", (key,))[0][0]
        if published != 1 or not {code(a), code(b)} <= {200, 409} or 200 not in (code(a), code(b)):
            bad.append((key, code(a), code(b), published))
    assert not bad, f"{len(bad)} of 12: {bad[:5]}"


def test_the_database_refuses_a_second_published_version_of_a_key(env):
    for n in (1, 2):
        assert env.post(P, helper(n=n)).status_code == 201
    assert env.post(f"{P}/helper/versions/1/publish", OVERRIDE).status_code == 200
    import dbtest
    import pytest
    with pytest.raises(dbtest.IntegrityError):  # behind the store's back: the index, not the code, says no
        env.sql("update awp_profiles set status = 'published' where key = 'helper' and version = 2")
    assert env.post(f"{P}/helper/versions/2/publish", OVERRIDE).status_code == 200  # the store retires the old one first
    assert env.sql("select version, status from awp_profiles where key = 'helper' order by version") == [
        (1, "retired"), (2, "published")]


def test_a_leader_draft_edited_after_its_team_was_checked_is_not_published_on_that_check(env, monkeypatch):
    for body in ({"key": "desk", "name": "Desk", "role": "leader", "mission": "leads.", "team": ["plumber"]},
                 {"key": "plumber", "name": "Plumber", "mission": "fixes pipes."}):
        assert env.post(P, body).status_code == 201
    store_ = env.app.state.awp.rt.profiles
    real = store_.team_gaps
    edited = AgentProfile(key="desk", name="Desk", role="leader", mission="leads.", team=["nobody"])

    async def edit_after_the_check(tenant, profile):
        gaps = await real(tenant, profile)
        await store_.update_draft(tenant, "desk", 1, edited)  # the PUT that lands between the check and the publish
        return gaps

    monkeypatch.setattr(store_, "team_gaps", edit_after_the_check)
    r = env.post(f"{P}/desk/versions/1/publish", OVERRIDE)
    assert r.status_code == 409 and "edited" in r.text
    assert env.sql("select status from awp_profiles where key = 'desk'") == [("draft",)]
    monkeypatch.undo()
    assert env.post(f"{P}/desk/versions/1/publish", OVERRIDE).status_code == 422  # checked again: nobody is no specialist
