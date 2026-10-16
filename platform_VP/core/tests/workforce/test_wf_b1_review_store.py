"""What the review of the tool store (B1) found, each as a test: a discovered tool is a look-up only on the server's
word or on a person's recorded reason; a schema too large for every model call is not taken; a partner tool never
replaces a platform tool of the same name; a tool typed by hand keeps its schema from the first time its server was
listed; and four rules of the store that were written down but not tested. A real FastMCP server in a thread; where an
agent is involved, the real engine on the scripted model."""
from __future__ import annotations

import json
import pathlib
import re

from conftest import ADM
from enginekit import world
from partnerkit import SECRET, Partner
from t1kit import SETTINGS, act as leader_calls, configure, lookup, ops, quiet_leader, tools_of
from test_wf_b1_store import ALL, W, Shop, act, add_server, patch, server_of, shop, store, store_of  # noqa: F401

import agentscope
from awp.workforce import tool_store
from awp.workforce.partner_mcp import ToolSpec
from awp.workforce.partner_tools import MAX_SCHEMA
from awp.workforce.tool_store import refusal, reserved

WHY = "it only reads the ticket; the partner confirmed this in writing"
AS_LOOKUP = {"kind": "lookup", "read_only": True, "requires_consent": False}


def put_tools(env, rid, *tools, headers=ADM):
    return env.http.put(f"{W}/routes/{rid}/tools", headers=headers, json={"tools": list(tools)})


# ---- a look-up is the server's word, or a person's with the reason ---------------------------------------------------------
def test_a_discovered_action_cannot_be_renamed_a_lookup_to_run_unasked_and_untraced(tmp_path, shop):  # noqa: F811
    """One PATCH (kind=lookup) would otherwise take a proposed action past consent, the waiver and the ledger."""
    script = leader_calls("book_hotel", {"hotel": "Sea View", "nights": 2}, "Noted.")
    with world(tmp_path, script, leader_tools=["book_hotel"], **SETTINGS) as w:
        env, rid = w.env, w.flow.route["route_id"]
        key = env.manager_key(w.flow.route["manager_id"])
        shop.drop("lookup_ticket")
        add_server(env, rid, shop)
        act(env, rid, "enable")
        for headers in (key, ADM):
            r = env.http.patch(f"{W}/routes/{rid}/tools/book_hotel", headers=headers, json={**AS_LOOKUP, "status": "active"})
            assert r.status_code == 422 and "read-only" in r.text and "consent_waiver" in r.text, r.text
        row = store_of(env, rid)["book_hotel"]
        assert (row["kind"], row["status"], row["requires_consent"], row["read_only"]) == ("action", "proposed", True, False)
        # the whole-set PUT is no way around it, under the tool's own name or another
        as_put = {"server": "p", "mcp_tool": "book_hotel", "kind": "lookup", "read_only": True}
        for name in ("book_hotel", "just_looking"):
            r = put_tools(env, rid, {"name": name, **as_put}, headers=key)
            assert r.status_code == 422 and "read-only" in r.text, r.text
        assert set(store_of(env, rid)) == ALL - {"lookup_ticket"}  # the refused PUT replaced nothing
        # a row that says so without the reason (written before this rule, or behind the platform's back) reaches no agent
        env.sql("update wf_tools set kind='lookup', read_only=?, requires_consent=?, status='active' where name='book_hotel'",
                (True, False))
        _, first = w.flow.begin()
        w.quiet()
        assert "book_hotel" not in tools_of(w)
        assert shop.of("book_hotel") == [] and ops(w, first["workflow_id"]) == []


def test_a_person_may_call_a_discovered_tool_a_lookup_with_a_recorded_reason(tmp_path, shop):  # noqa: F811
    with world(tmp_path, quiet_leader, leader_tools=["lookup_no_hint"], **SETTINGS) as w:
        env, rid = w.env, w.flow.route["route_id"]
        shop.drop("lookup_ticket")
        add_server(env, rid, shop)
        act(env, rid, "enable")
        assert patch(env, rid, "lookup_no_hint", **AS_LOOKUP, status="active").status_code == 422
        r = patch(env, rid, "lookup_no_hint", **AS_LOOKUP, status="active", consent_waiver=WHY)
        assert r.status_code == 200, r.text
        row = store_of(env, rid)["lookup_no_hint"]
        assert (row["kind"], row["read_only"], row["status"], row["consent_waiver"]) == ("lookup", True, "active", WHY)
        w.flow.begin()
        assert "lookup_no_hint" in tools_of(w)
        # a refresh does not take it back: it never rested on the server's hint
        assert act(env, rid, "refresh").json()["changed"] == []
        assert store_of(env, rid)["lookup_no_hint"]["status"] == "active" and "lookup_no_hint" in tools_of(w)
        # the reason is the look-up's: making it an action again starts from asking the resident
        assert patch(env, rid, "lookup_no_hint", kind="action", read_only=False).status_code == 422
        back = patch(env, rid, "lookup_no_hint", kind="action", read_only=False, requires_consent=True)
        assert back.status_code == 200 and (back.json()["requires_consent"], back.json()["consent_waiver"]) == (True, None)
        # a tool typed by hand is a person's own statement, as before the store (main spec 13.19)
        typed = {"name": "typed_lookup", "server": "p", "mcp_tool": "structured_only", "kind": "lookup", "read_only": True}
        env.sql("delete from wf_tools where name = 'structured_only'")
        assert put_tools(env, rid, typed).status_code == 200


# ---- what a server may push into every model call ---------------------------------------------------------------------------
def wide(n: int) -> dict:
    return {"type": "object", "properties": {f"p{i}": {"type": "string", "description": "x" * 20} for i in range(n)}}


def test_a_schema_too_large_to_send_with_every_model_call_is_not_taken(tmp_path, shop):  # noqa: F811
    assert "too large" in refusal(ToolSpec("wide", "d", wide(2000), read_only=True))
    assert refusal(ToolSpec("fine", "d", wide(100), read_only=True)) is None

    def probe(text: str) -> str:
        """probe"""
        return text

    with world(tmp_path, quiet_leader, leader_tools=["wide", "repair_status", "typed_wide"], **SETTINGS) as w:
        env, rid = w.env, w.flow.route["route_id"]
        shop.drop("lookup_ticket")
        shop.add(probe, "wide", read_only=True)
        add_server(env, rid, shop)
        assert act(env, rid, "enable").json()["rejected"] == []  # as the function declares it: small, taken, active
        w.flow.begin()
        assert {"wide", "repair_status"} <= set(tools_of(w))
        shop.mcp._tool_manager._tools["wide"].parameters = wide(2000)  # the partner swells it afterwards
        body = act(env, rid, "refresh").json()
        assert body["rejected"] == [{"mcp_tool": "wide", "reason": "its schema is too large"}] and body["gone"] == ["wide"]
        row = store_of(env, rid)["wide"]
        assert row["status"] == "gone" and len(json.dumps(row["schema"])) < MAX_SCHEMA  # the stored one is the small one
        assert set(tools_of(w)) == {"repair_status"}
        # and a tool typed by hand onto it gets the live list: it is left out there too
        typed = {"name": "typed_wide", "server": "p", "mcp_tool": "wide", "kind": "lookup", "read_only": True}
        assert put_tools(env, rid, typed).status_code == 200
        assert tools_of(w) == {}


def test_a_swollen_tool_is_refused_when_the_server_is_first_enabled(store):  # noqa: F811
    env, rid, shop_ = store

    def probe(text: str) -> str:
        """probe"""
        return text

    shop_.add(probe, "wide", read_only=True)
    shop_.mcp._tool_manager._tools["wide"].parameters = wide(2000)
    body = act(env, rid, "enable").json()
    assert body["rejected"] == [{"mcp_tool": "wide", "reason": "its schema is too large"}]
    assert set(store_of(env, rid)) == ALL


# ---- names ---------------------------------------------------------------------------------------------------------------
def test_every_tool_name_of_the_framework_is_refused_to_a_partner():
    """Read from the vendored package, so a tool the framework gains later is noticed here."""
    names = set()
    for path in pathlib.Path(agentscope.__file__).parent.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "ToolBase" in text:
            names |= set(re.findall(r'^\s+name(?:: str)? = "([A-Za-z_]\w*)"', text, re.M))
    assert {"search_knowledge", "add_memory", "search_memory", "memory_search", "ListUsers", "ReadWikiDocument", "Bash"} <= names
    assert sorted(n for n in names if not reserved(n)) == []
    assert not reserved("lookup_ticket") and not reserved("book_hotel")


def test_a_partner_tool_never_replaces_a_platform_tool_of_the_same_name(tmp_path, shop):  # noqa: F811
    """The engine tests give every agent an in-process `lookup_ticket`; the partner lists one too. The store cannot know
    the in-process one, so the agent's own tool list decides: the platform's stays."""
    script = leader_calls("lookup_ticket", {"ticket_id": "T-1001"}, "Noted.")
    with world(tmp_path, script, **SETTINGS) as w:
        env, rid = w.env, w.flow.route["route_id"]
        add_server(env, rid, shop)
        assert "lookup_ticket" in act(env, rid, "enable").json()["added"]
        w.flow.begin()
        w.quiet()
        assert "lookup_ticket" in tools_of(w)  # the route does offer it
        called = [c for c in w.model_calls() if any(role == "tool" and "leaking pipe" in text for role, text, _ in c.get("shape", []))]
        assert called and shop.of("lookup_ticket") == []  # the leader used the tool, and it was not the partner's


# ---- a tool typed by hand survives the partner being down ----------------------------------------------------------------
def test_a_hand_typed_tool_keeps_its_schema_from_the_first_time_its_server_was_listed(tmp_path):
    partner = Partner().start()
    try:
        with world(tmp_path, quiet_leader, leader_tools=["partner_lookup"], **SETTINGS) as w:
            rid = configure(w, partner, tools=[lookup()])
            assert store_of(w.env, rid)["partner_lookup"]["schema"] is None  # typed: nothing was asked of the server
            w.flow.begin()
            live = tools_of(w)
            assert set(live) == {"partner_lookup"}
            kept = store_of(w.env, rid)["partner_lookup"]
            assert kept["schema"]["read_only"] is True and "ticket_id" in kept["schema"]["input_schema"]["properties"]
            assert (kept["source"], kept["status"], kept["schema_changed_at"]) == ("manual", "active", None)
    finally:
        partner.stop()
    with world(tmp_path, quiet_leader, publish=False, **SETTINGS) as w2:  # a new process, the partner still down
        tools = tools_of(w2)
        assert set(tools) == {"partner_lookup"} and tools["partner_lookup"].input_schema == live["partner_lookup"].input_schema
        got = w2.run(lambda: tools["partner_lookup"].call(ticket_id="T-1"))
        assert got.state.value == "error" and got.content[0].text.startswith(("FAILED", "UNAVAILABLE"))


# ---- rules of the store that were written down and not tested -------------------------------------------------------------
def test_refresh_of_a_server_that_went_down_after_it_was_listed_says_so_and_takes_no_tool_from_the_agents(tmp_path):
    partner = Partner().start()
    stopped = False
    try:
        with world(tmp_path, quiet_leader, leader_tools=["partner_lookup"], **SETTINGS) as w:
            env, rid = w.env, configure(w, partner, tools=[lookup()])
            w.flow.begin()
            assert act(env, rid, "refresh").status_code == 200 and "partner_lookup" in tools_of(w)
            before = store_of(env, rid)
            partner.stop()
            stopped = True
            r = act(env, rid, "refresh")  # the list as it is now cannot be read: not a quiet success from the cached one
            assert r.status_code == 502 and server_of(env, rid)["last_error"]
            assert store_of(env, rid) == before
            # the client's cached list is still there for the agents: a refresh during an outage makes nothing worse
            client = w.rt.mcp.client(rid, w.run(lambda: w.rt.mcp.servers(rid))["p"])
            assert {s.name for s in w.run(client.list_tools)} >= {"lookup_ticket"}
            assert "partner_lookup" in tools_of(w)
    finally:
        if not stopped:
            partner.stop()


def test_the_whole_set_put_of_servers_leaves_a_disabled_server_disabled(store):  # noqa: F811
    env, rid, shop_ = store
    assert act(env, rid, "enable").status_code == 200 and act(env, rid, "disable").status_code == 200
    body = {"servers": [{"name": "p", "url": shop_.url, "headers": {"Authorization": f"Bearer {SECRET}"}},
                        {"name": "q", "url": shop_.url}]}
    r = env.http.put(f"{W}/routes/{rid}/mcp", headers=ADM, json=body)
    assert r.status_code == 200
    seen = {s["name"]: s for s in r.json()["servers"]}
    assert seen["p"]["enabled"] is False and seen["p"]["last_discovered_at"]  # what the store knew of it stays
    assert seen["q"]["enabled"] is True  # one declared here for the first time is on, as before the store
    assert server_of(env, rid)["enabled"] is False


def test_the_whole_set_put_of_tools_does_not_bring_back_a_tool_the_server_dropped(store):  # noqa: F811
    env, rid, shop_ = store
    act(env, rid, "enable")
    shop_.drop("repair_status")
    assert act(env, rid, "refresh").json()["gone"] == ["repair_status"]
    same = {"name": "repair_status", "server": "p", "mcp_tool": "repair_status", "kind": "lookup", "read_only": True}
    r = put_tools(env, rid, same)
    assert r.status_code == 200 and r.json()["tools"][0]["status"] == "gone"
    assert store_of(env, rid)["repair_status"]["status"] == "gone"
    other = put_tools(env, rid, {**same, "mcp_tool": "lookup_ticket"})  # another tool under the name: a new, typed row
    assert other.json()["tools"][0]["status"] == "active" and other.json()["tools"][0]["source"] == "manual"


def test_a_store_that_is_full_takes_no_more_tools(store, monkeypatch):  # noqa: F811
    env, rid, _ = store
    monkeypatch.setattr(tool_store, "MAX_TOOLS", 3)
    body = act(env, rid, "enable").json()
    assert len(body["added"]) == 3 and len(store_of(env, rid)) == 3
    assert len(body["rejected"]) == len(ALL) - 3 and {x["reason"] for x in body["rejected"]} == {"the route's tool store is full"}
    again = act(env, rid, "refresh").json()
    assert again["added"] == [] and len(again["rejected"]) == len(ALL) - 3 and len(store_of(env, rid)) == 3
