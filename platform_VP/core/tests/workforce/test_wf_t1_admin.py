"""Admin: a route's MCP servers and tools (slice T1; spec 7.4, 8). Validation, the SSRF check, sealed headers that
never come back, names the platform keeps for itself, and the isolation of tenants."""
from __future__ import annotations


import pytest
from conftest import ADM, ADM_B
from t1kit import WAIVER, waived

W = "/platform/v1/wf"
PUBLIC = "http://93.184.216.34/mcp"  # a public address by number, so no test depends on a name server
KEY = "Bearer tok-ADMIN-SECRET-98765"
SERVER = {"name": "p", "url": PUBLIC, "headers": {"Authorization": KEY, "X-Tenant": "homes"}, "timeout": 5}
LOOKUP = {"name": "partner_lookup", "server": "p", "mcp_tool": "lookup_ticket", "kind": "lookup", "read_only": True}
ACTION = waived({"name": "partner_repair", "server": "p", "mcp_tool": "book_repair", "kind": "action", "tracking": "events",
                 "client_reference_arg": "client_reference", "call_timeout": 6})  # not about consent: a recorded waiver (M5)


@pytest.fixture
def route(env):
    client = env.client()
    return env, env.route(client["client_id"])["route_id"]


def put(env, rid, what, body, headers=ADM):
    return env.http.put(f"{W}/routes/{rid}/{what}", json=body, headers=headers)


def servers(env, rid, items=(SERVER,)):
    r = put(env, rid, "mcp", {"servers": list(items)})
    assert r.status_code == 200, r.text
    return r


def tools(env, rid, items):
    return put(env, rid, "tools", {"tools": list(items)})


# ---- servers -------------------------------------------------------------------------------------------------------
def test_servers_are_stored_sealed_and_never_shown(route):
    env, rid = route
    body = servers(env, rid).json()
    assert body == {"servers": [{"name": "p", "url": PUBLIC, "transport": "streamable_http", "timeout": 5.0,
                                 "header_names": ["Authorization", "X-Tenant"],
                                 "enabled": True, "last_discovered_at": None, "last_error": None}]}  # declared whole: on, as before
    got = env.http.get(f"{W}/routes/{rid}/mcp", headers=ADM)
    assert got.json() == body and "ADMIN-SECRET" not in got.text and "homes" not in got.text
    assert "ADMIN-SECRET" not in env.dump() and "Bearer" not in env.dump()  # sealed in the database
    (sealed,) = env.sql("select headers_enc from wf_mcp_servers")[0]
    assert sealed and sealed.startswith("gAAAA")  # a Fernet token


def test_put_replaces_the_whole_set_and_a_server_without_headers_stores_none(route):
    env, rid = route
    servers(env, rid, [SERVER, {"name": "q", "url": PUBLIC}])
    assert env.sql("select name, headers_enc is null from wf_mcp_servers order by name") == [("p", 0), ("q", 1)]
    servers(env, rid, [{"name": "q", "url": "https://93.184.216.34/other", "timeout": 3}])
    assert env.sql("select name, url, timeout from wf_mcp_servers") == [("q", "https://93.184.216.34/other", 3.0)]
    servers(env, rid, [])
    assert env.sql("select count(*) from wf_mcp_servers") == [(0,)]


@pytest.mark.parametrize("url", [
    "http://localhost/mcp", "http://127.0.0.1:8000/mcp", "http://10.1.2.3/mcp", "http://192.168.0.9/mcp",
    "http://169.254.169.254/latest/meta-data", "http://[::1]/mcp", "http://metadata.internal/mcp",
    "http://0.0.0.0/mcp", "http://example.com@127.0.0.1/mcp", "ftp://93.184.216.34/mcp", "file:///etc/passwd"])
def test_a_server_inside_the_platforms_network_is_refused(route, url):
    env, rid = route
    r = put(env, rid, "mcp", {"servers": [{"name": "p", "url": url}]})
    assert r.status_code == 422, r.text
    assert env.sql("select count(*) from wf_mcp_servers") == [(0,)]


def test_the_switch_for_private_addresses_lets_a_closed_network_in(make_env):
    with make_env(mcp_allow_private=True) as env:
        rid = env.route(env.client()["client_id"])["route_id"]
        assert put(env, rid, "mcp", {"servers": [{"name": "p", "url": "http://127.0.0.1:9000/mcp"}]}).status_code == 200


@pytest.mark.parametrize("bad", [
    {"name": "has space", "url": PUBLIC}, {"name": "", "url": PUBLIC}, {"name": "x" * 65, "url": PUBLIC},
    {"name": "p", "url": "x"}, {"name": "p", "url": PUBLIC, "timeout": 0.1}, {"name": "p", "url": PUBLIC, "timeout": 99},
    {"name": "p", "url": PUBLIC, "transport": "stdio"}, {"name": "p", "url": PUBLIC, "extra": 1},
    {"name": "p", "url": PUBLIC, "headers": {"Host": "evil"}}, {"name": "p", "url": PUBLIC, "headers": {"Content-Type": "x"}},
    {"name": "p", "url": PUBLIC, "headers": {"Mcp-Session-Id": "x"}},
    {"name": "p", "url": PUBLIC, "headers": {"X-A": "line\r\nInjected: 1"}},
    {"name": "p", "url": PUBLIC, "headers": {"bad name": "v"}}, {"name": "p", "url": PUBLIC, "headers": {"X": ""}},
    {"name": "p", "url": PUBLIC, "headers": {f"X-{i}": "v" for i in range(21)}},
    {"name": "p", "url": "https://user:pw@93.184.216.34/mcp"},
])
def test_server_input_is_validated(route, bad):
    env, rid = route
    assert put(env, rid, "mcp", {"servers": [bad]}).status_code == 422


def test_two_servers_with_one_name_are_refused(route):
    env, rid = route
    assert put(env, rid, "mcp", {"servers": [SERVER, SERVER]}).status_code == 422


def test_headers_need_the_secret_key_but_a_server_without_headers_does_not(make_env):
    with make_env(secret_key="") as env:
        rid = env.route(env.client()["client_id"])["route_id"]
        assert put(env, rid, "mcp", {"servers": [SERVER]}).status_code == 503
        assert put(env, rid, "mcp", {"servers": [{"name": "p", "url": PUBLIC}]}).status_code == 200


# ---- tools -----------------------------------------------------------------------------------------------------------
def test_tools_are_stored_and_read_back_as_declared(route):
    env, rid = route
    servers(env, rid)
    r = tools(env, rid, [ACTION, LOOKUP])
    assert r.status_code == 200, r.text
    got = env.http.get(f"{W}/routes/{rid}/tools", headers=ADM).json()["tools"]
    assert [t["name"] for t in got] == ["partner_lookup", "partner_repair"]
    repair = got[1]
    assert repair == {"name": "partner_repair", "server": "p", "mcp_tool": "book_repair", "kind": "action",
                      "read_only": False, "requires_consent": False, "consent_waiver": WAIVER, "tracking": "events",
                      "client_reference_arg": "client_reference", "idempotency_arg": None, "status_tool": None,
                      "integration_id": None, "consent_summary": None, "call_timeout": 6.0, "description_override": None,
                      "source": "manual", "status": "active", "discovered_at": None, "schema": None, "schema_changed_at": None}
    assert got[0]["call_timeout"] == 8.0 and got[0]["read_only"] is True  # the defaults
    assert tools(env, rid, [LOOKUP]).status_code == 200  # PUT replaces
    assert env.sql("select name from wf_tools") == [("partner_lookup",)]


def test_a_tool_needs_a_server_the_route_has_and_a_server_with_tools_cannot_be_removed(route):
    env, rid = route
    assert tools(env, rid, [LOOKUP]).status_code == 422  # no server yet
    servers(env, rid, [SERVER, {"name": "q", "url": PUBLIC}])
    assert tools(env, rid, [{**LOOKUP, "server": "nope"}]).status_code == 422
    assert tools(env, rid, [LOOKUP]).status_code == 200
    r = put(env, rid, "mcp", {"servers": [{"name": "q", "url": PUBLIC}]})
    assert r.status_code == 409 and "p" in r.text
    assert env.sql("select count(*) from wf_mcp_servers") == [(2,)]


@pytest.mark.parametrize("name", ["CaseSay", "CaseFinalize", "Case_anything", "TeamSay", "TeamCreate", "AgentCreate",
                                  "AgentInvite", "AgentWhatever", "calc_sum", "Bash", "bash", "Read", "WRITE", "ToolStop"])
def test_a_tool_cannot_take_a_name_the_platform_or_the_framework_keeps(route, name):
    env, rid = route
    servers(env, rid)
    r = tools(env, rid, [{**LOOKUP, "name": name}])
    assert r.status_code == 422 and (name in r.text or "platform" in r.text)
    assert env.sql("select count(*) from wf_tools") == [(0,)]


@pytest.mark.parametrize("change", [
    {"name": "has space"}, {"name": "dots.not.allowed"}, {"name": ""}, {"name": "x" * 65}, {"mcp_tool": "bad name"},
    {"kind": "write"}, {"tracking": "webhook"}, {"call_timeout": 9.5}, {"call_timeout": 30}, {"call_timeout": 0.1},
    {"extra": 1}, {"description_override": ""}, {"description_override": "x" * 1001},
    # a look-up changes nothing: none of the things an action has
    {"requires_consent": True}, {"tracking": "events"}, {"client_reference_arg": "client_reference"},
    {"idempotency_arg": "key"}, {"status_tool": "status"}, {"consent_summary": "Book"},
])
def test_look_up_input_is_validated(route, change):
    env, rid = route
    servers(env, rid)
    assert tools(env, rid, [{**LOOKUP, **change}]).status_code == 422


@pytest.mark.parametrize("change", [
    {"read_only": True}, {"consent_summary": "Book it"},  # a summary belongs to a tool that needs consent
    {"tracking": "status_query"},  # needs status_tool and client_reference_arg
    {"tracking": "status_query", "status_tool": "status", "client_reference_arg": None},
    {"status_tool": "status"},  # without status_query tracking
    {"client_reference_arg": "idempotency_nonce"}, {"idempotency_arg": "idempotency_nonce"},
    {"client_reference_arg": "1bad"}, {"client_reference_arg": "has-dash"}, {"call_timeout": 9.1},
])
def test_action_input_is_validated(route, change):
    env, rid = route
    servers(env, rid)
    assert tools(env, rid, [{**ACTION, **change}]).status_code == 422


def test_actions_may_need_consent_or_be_followed_by_a_status_query(route):
    env, rid = route
    servers(env, rid)
    ok = [{**ACTION, "name": "a1", "requires_consent": True, "consent_waiver": None, "consent_summary": "Book {slot}"},
          {**ACTION, "name": "a2", "tracking": "status_query", "status_tool": "repair_status"},
          {**ACTION, "name": "a3", "idempotency_arg": "request_key", "client_reference_arg": None, "tracking": "none"}]
    assert tools(env, rid, ok).status_code == 200


def test_two_tools_with_one_name_are_refused_and_so_are_too_many(route):
    env, rid = route
    servers(env, rid)
    assert tools(env, rid, [LOOKUP, LOOKUP]).status_code == 422
    many = [{**LOOKUP, "name": f"t{i}"} for i in range(101)]
    assert tools(env, rid, many).status_code == 422


# ---- who may configure what ----------------------------------------------------------------------------------------
def test_another_tenant_sees_and_changes_nothing_of_a_route(route):
    env, rid = route
    servers(env, rid)
    tools(env, rid, [LOOKUP])
    for what, body in (("mcp", {"servers": []}), ("tools", {"tools": []})):
        assert put(env, rid, what, body, ADM_B).status_code == 404
        assert env.http.get(f"{W}/routes/{rid}/{what}", headers=ADM_B).status_code == 404
    assert env.sql("select count(*) from wf_mcp_servers") == [(1,)] and env.sql("select count(*) from wf_tools") == [(1,)]
    assert put(env, "route_nope", "mcp", {"servers": []}).status_code == 404


def test_configuration_needs_the_admin_key_and_a_replaced_route_cannot_be_configured(route):
    env, rid = route
    assert env.http.put(f"{W}/routes/{rid}/mcp", json={"servers": []}).status_code == 401
    assert env.http.put(f"{W}/routes/{rid}/mcp", json={"servers": []}, headers={"Authorization": "Bearer svc-key"}).status_code == 401
    assert env.post(f"{W}/routes/{rid}/replace").status_code == 201
    assert put(env, rid, "mcp", {"servers": []}).status_code == 409
    assert tools(env, rid, []).status_code == 409


def test_a_route_that_is_not_yet_confirmed_can_be_configured_and_the_replacement_takes_its_configuration(route):
    """M1: replacing a route copies its servers and tools (it used to start empty, which threw the tool store away)."""
    env, rid = route
    servers(env, rid)
    tools(env, rid, [LOOKUP])
    new = env.post(f"{W}/routes/{rid}/replace").json()["route"]["route_id"]
    for what in ("tools", "mcp"):
        old = env.http.get(f"{W}/routes/{rid}/{what}", headers=ADM).json()
        assert env.http.get(f"{W}/routes/{new}/{what}", headers=ADM).json() == old and len(old[what if what == "tools" else "servers"]) == 1
    assert tools(env, new, []).status_code == 200  # each route has its own copy
    assert len(env.http.get(f"{W}/routes/{rid}/tools", headers=ADM).json()["tools"]) == 1
