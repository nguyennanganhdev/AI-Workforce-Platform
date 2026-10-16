"""What an operator configures and reads for provider events (slice T2): the integration a tool is followed by, the
schema's correction flag, and the receipts, tenant by tenant. No model."""
from __future__ import annotations

import pytest
from conftest import ADM, ADM_B
from t2kit import SCHEMA, Provider
from test_wf_t1_admin import ACTION, LOOKUP, servers, tools

W = "/platform/v1/wf"


@pytest.fixture
def world(env):
    c = env.client()
    mine = Provider(env, c["client_id"])
    other = Provider(env, env.client(domain="other")["client_id"])
    rid = env.route(c["client_id"])["route_id"]
    servers(env, rid)
    return env, c, mine, other, rid


def test_a_tool_names_the_integration_whose_events_follow_it_and_it_is_read_back(world):
    env, c, mine, other, rid = world
    r = tools(env, rid, [LOOKUP, {**ACTION, "integration_id": mine.id}])
    assert r.status_code == 200, r.text
    got = {t["name"]: t["integration_id"] for t in env.http.get(f"{W}/routes/{rid}/tools", headers=ADM).json()["tools"]}
    assert got == {"partner_lookup": None, "partner_repair": mine.id}


def test_an_integration_of_another_client_or_one_that_does_not_exist_is_refused(world):
    env, c, mine, other, rid = world
    for bad in (other.id, "intg_nothing"):
        r = tools(env, rid, [{**ACTION, "integration_id": bad}])
        assert r.status_code == 422, r.text
        assert env.sql("select count(*) from wf_tools") == [(0,)]  # nothing was stored


@pytest.mark.parametrize("tool", [
    {**LOOKUP, "integration_id": "x"},  # a look-up has no events
    {"name": "a", "server": "p", "mcp_tool": "m", "kind": "action", "tracking": "none", "integration_id": "x"},
    {"name": "a", "server": "p", "mcp_tool": "m", "kind": "action", "tracking": "status_query", "status_tool": "s",
     "client_reference_arg": "r", "integration_id": "x"}])
def test_an_integration_belongs_only_to_a_tool_that_is_followed_by_events(world, tool):
    env, c, mine, other, rid = world
    assert tools(env, rid, [{**tool, "integration_id": mine.id}]).status_code == 422


def test_the_schema_may_declare_a_correction_and_it_is_stored_with_the_rest(env):
    c = env.client()
    schema = {**SCHEMA, "events": {"x.fix": {"status": "fixed", "rank": 1, "reopen": True}, "x.a": {"status": "a", "rank": 2}}}
    r = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": schema})
    assert r.status_code == 201, r.text
    events = r.json()["event_schema"]["events"]
    assert events["x.fix"]["reopen"] is True and events["x.a"]["reopen"] is False
    bad = {**SCHEMA, "events": {"x.fix": {"status": "fixed", "rank": 1, "reopen": "yes"}}}
    assert env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": bad}).status_code == 422


def test_the_admin_reads_receipts_of_its_own_tenant_and_no_data_of_the_provider(world):
    env, c, mine, other, rid = world
    sent = mine.send("x.assigned", job="J-1", data={"worker_name": "An", "eta_minutes": 5, "phone": "0909-SECRET"})[0].json()
    one = env.http.get(f"{W}/receipts/{sent['receipt_id']}", headers=ADM)
    assert one.status_code == 200 and "0909-SECRET" not in one.text and "An" not in one.json().values()
    got = one.json()
    assert (got["event_type"], got["ingestion_status"], got["integration_id"], got["normalized_status"]) == (
        "x.assigned", "quarantined", mine.id, "assigned")
    assert got["operation_id"] is None and got["error"] is None and got["received_at"].endswith("Z")
    listed = env.http.get(f"{W}/receipts", headers=ADM).json()["receipts"]
    assert [x["receipt_id"] for x in listed] == [sent["receipt_id"]]
    assert env.http.get(f"{W}/receipts?status=applied", headers=ADM).json() == {"receipts": []}
    assert env.http.get(f"{W}/receipts?integration_id={mine.id}", headers=ADM).json()["receipts"]
    # another tenant sees nothing of it
    assert env.http.get(f"{W}/receipts/{sent['receipt_id']}", headers=ADM_B).status_code == 404
    assert env.http.get(f"{W}/receipts", headers=ADM_B).json() == {"receipts": []}
    assert env.http.get(f"{W}/receipts").status_code in (401, 403)
